import hashlib
import hmac as _hmac
import json
import urllib.parse
from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import selectinload as _sl

from config import settings
from db.engine import AsyncSessionFactory
from db.models import Booking, BookingStatus, Class, Subscription, User
from db.queries import (
    SUBSCRIPTION_CLASSES,
    cancel_booking,
    create_booking,
    decrement_subscription,
    get_active_subscription,
    get_booking,
    get_upcoming_classes,
    get_user_upcoming_bookings,
)
from services.attendance import verify_token

router = APIRouter(prefix="/miniapp/api")


# ─── Telegram InitData auth ───────────────────────────────────────

def _parse_init_data(init_data: str) -> dict:
    """Validate Telegram WebApp initData HMAC and return user dict."""
    parsed = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        raise HTTPException(status_code=403, detail="Missing hash")

    check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret = _hmac.new(b"WebAppData", settings.BOT_TOKEN.encode(), hashlib.sha256).digest()
    expected = _hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()

    if not _hmac.compare_digest(received_hash, expected):
        raise HTTPException(status_code=403, detail="Invalid signature")

    return json.loads(parsed.get("user", "{}"))


async def _get_tg_user(x_telegram_init_data: str = Header(...)) -> dict:
    return _parse_init_data(x_telegram_init_data)


TgUser = Annotated[dict, Depends(_get_tg_user)]


# ─── Helpers ─────────────────────────────────────────────────────

MONTHS_SHORT = ["янв", "фев", "мар", "апр", "май", "июн",
                 "июл", "авг", "сен", "окт", "ноя", "дек"]
DAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


# ─── Endpoints ───────────────────────────────────────────────────

@router.get("/health")
async def api_health():
    try:
        async with AsyncSessionFactory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "ok", "ts": datetime.now().isoformat()}
    except Exception as e:
        return JSONResponse(status_code=503, content={"status": "error", "detail": str(e)})


@router.get("/home")
async def api_home(tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"name": "", "classes_left": 0, "next_class": "—",
                    "days_until": "—", "upcoming": []}
        sub = await get_active_subscription(session, user.id)
        classes = await get_upcoming_classes(session, days=14)
        bookings = await get_user_upcoming_bookings(session, user.id)
        booked_ids = {b.class_id for b in bookings}
        upcoming = []
        for cls in classes[:5]:
            confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
            free = cls.max_spots - len(confirmed)
            dt = cls.starts_at
            upcoming.append({
                "id": cls.id, "title": cls.title, "trainer": cls.trainer,
                "date_str": f"{dt.day} {MONTHS_SHORT[dt.month-1]} {DAYS_SHORT[dt.weekday()]}",
                "time": dt.strftime("%H:%M"), "free_spots": free,
                "payment_enabled": getattr(cls, "payment_enabled", True),
                "location": getattr(cls, "location", "Студия"),
                "is_booked": cls.id in booked_ids,
            })
        next_class, days_until = "—", "—"
        if bookings:
            dt = bookings[0].cls.starts_at
            next_class = dt.strftime("%d.%m")
            diff = (dt.date() - datetime.now().date()).days
            days_until = "сегодня" if diff == 0 else f"{diff} дн."
        return {
            "name": user.full_name,
            "classes_left": sub.classes_left if sub else 0,
            "next_class": next_class,
            "days_until": days_until,
            "upcoming": upcoming,
        }


@router.get("/schedule")
async def api_schedule(year: int, month: int):
    async with AsyncSessionFactory() as session:
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        result = await session.execute(
            select(Class).where(
                Class.starts_at >= start,
                Class.starts_at < end,
                Class.is_cancelled == False,
            )
        )
        classes = result.scalars().all()
        return {"classes": [{"date": c.starts_at.strftime("%Y-%m-%d")} for c in classes]}


@router.get("/schedule/day")
async def api_schedule_day(date: str, tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        dt = datetime.strptime(date, "%Y-%m-%d")
        result = await session.execute(
            select(Class).options(_sl(Class.bookings)).where(
                Class.starts_at >= dt,
                Class.starts_at < dt + timedelta(days=1),
                Class.is_cancelled == False,
            ).order_by(Class.starts_at)
        )
        classes = result.scalars().all()
        booked_ids = set()
        if tg_id:
            bk = await session.execute(
                select(Booking).where(
                    Booking.user_id == tg_id,
                    Booking.status == BookingStatus.CONFIRMED,
                )
            )
            booked_ids = {b.class_id for b in bk.scalars().all()}
        out = []
        for cls in classes:
            confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
            out.append({
                "id": cls.id, "title": cls.title, "trainer": cls.trainer,
                "time": cls.starts_at.strftime("%H:%M"),
                "free_spots": cls.max_spots - len(confirmed),
                "payment_enabled": getattr(cls, "payment_enabled", True),
                "location": getattr(cls, "location", "Студия"),
                "is_booked": cls.id in booked_ids,
            })
        return {"classes": out}


class BookReq(BaseModel):
    class_id: int


@router.post("/book")
async def api_book(req: BookReq, tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"ok": False, "error": "Пользователь не найден"}
        sub = await get_active_subscription(session, user.id)
        if not sub:
            return {"ok": False, "error": "Нет абонемента. Купи абонемент!"}
        existing = await get_booking(session, user.id, req.class_id)
        if existing and existing.status == BookingStatus.CONFIRMED:
            return {"ok": False, "error": "Ты уже записана"}
        cls_result = await session.execute(
            select(Class).options(_sl(Class.bookings)).where(Class.id == req.class_id)
        )
        cls = cls_result.scalar_one_or_none()
        if not cls:
            return {"ok": False, "error": "Занятие не найдено"}
        confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
        if len(confirmed) >= cls.max_spots:
            return {"ok": False, "error": "Мест нет"}
        await create_booking(session, user.id, req.class_id)
        await decrement_subscription(session, user.id)
        return {"ok": True}


class CancelReq(BaseModel):
    booking_id: int


@router.post("/cancel")
async def api_cancel(req: CancelReq, tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        booking = await session.get(Booking, req.booking_id)
        if not booking or booking.user_id != tg_id:
            return {"ok": False, "error": "Запись не найдена"}
        await cancel_booking(session, req.booking_id)
        return {"ok": True}


@router.get("/bookings")
async def api_bookings(tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"bookings": []}
        bookings = await get_user_upcoming_bookings(session, user.id)
        return {
            "bookings": [
                {
                    "booking_id": b.id, "title": b.cls.title,
                    "trainer": b.cls.trainer,
                    "date": b.cls.starts_at.strftime("%Y-%m-%d"),
                    "time": b.cls.starts_at.strftime("%H:%M"),
                }
                for b in bookings
            ]
        }


@router.get("/subscription")
async def api_subscription(tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"classes_left": 0, "total": 0, "used": 0}
        sub = await get_active_subscription(session, user.id)
        if not sub:
            return {"classes_left": 0, "total": 0, "used": 0}
        total = SUBSCRIPTION_CLASSES.get(sub.sub_type, sub.classes_left)
        return {"classes_left": sub.classes_left, "total": total,
                "used": total - sub.classes_left}


class AttendReq(BaseModel):
    token: str


@router.post("/attend")
async def api_attend(req: AttendReq, tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    class_id = verify_token(req.token)
    if not class_id:
        return {"ok": False, "error": "QR-код недействителен или устарел"}

    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"ok": False, "error": "Пользователь не найден"}

        bk_result = await session.execute(
            select(Booking).where(
                Booking.user_id == tg_id,
                Booking.class_id == class_id,
            )
        )
        booking = bk_result.scalar_one_or_none()
        if not booking:
            return {"ok": False, "error": "У тебя нет записи на это занятие"}
        if booking.status == BookingStatus.ATTENDED:
            return {"ok": True, "already": True, "message": "Ты уже отмечена"}
        if booking.status == BookingStatus.CANCELLED:
            return {"ok": False, "error": "Запись отменена"}

        booking.status = BookingStatus.ATTENDED
        await session.commit()
        return {"ok": True, "already": False, "message": "Явка отмечена!"}


class PayReq(BaseModel):
    plan: str


@router.post("/pay")
async def api_pay(req: PayReq, tg_user: TgUser):
    tg_id = tg_user.get("id", 0)
    from db.models import SubscriptionType
    from db.queries import create_payment
    from services.payme import make_payment_url

    plan_map = {
        "four":    SubscriptionType.PACK_4,
        "eight":   SubscriptionType.PACK_8,
        "twelve":  SubscriptionType.PACK_12,
        "sixteen": SubscriptionType.PACK_16,
    }
    price_map = {
        "four":    settings.PRICE_4_CLASSES,
        "eight":   settings.PRICE_8_CLASSES,
        "twelve":  settings.PRICE_12_CLASSES,
        "sixteen": settings.PRICE_16_CLASSES,
    }
    desc_map = {
        "four":    "Абонемент 4 занятия",
        "eight":   "Абонемент 8 занятий",
        "twelve":  "Абонемент 12 занятий",
        "sixteen": "Абонемент 16 занятий",
    }
    sub_type = plan_map.get(req.plan)
    if not sub_type:
        return {"error": "Неверный тариф"}
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"error": "Пользователь не найден"}
        payment = await create_payment(
            session, tg_id, price_map[req.plan], desc_map[req.plan], sub_type
        )
        payment_url = make_payment_url(payment.id, price_map[req.plan])
        return {"payment_url": payment_url}
