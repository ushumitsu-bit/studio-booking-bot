from datetime import datetime, timedelta
from fastapi import APIRouter, Header
from pydantic import BaseModel
from sqlalchemy import select
from db.engine import AsyncSessionFactory
from db.models import Booking, BookingStatus, Class, Subscription, User
from db.queries import (
    get_active_subscription, get_upcoming_classes,
    get_user_upcoming_bookings, create_booking,
    cancel_booking, get_booking, decrement_subscription,
    SUBSCRIPTION_CLASSES,
)
from services.attendance import verify_token

router = APIRouter(prefix="/miniapp/api")
MONTHS_SHORT = ["янв","фев","мар","апр","май","июн","июл","авг","сен","окт","ноя","дек"]
DAYS_SHORT = ["пн","вт","ср","чт","пт","сб","вс"]

@router.get("/home")
async def api_home(x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"name":"","classes_left":0,"next_class":"—","days_until":"—","upcoming":[]}
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
                "payment_enabled": getattr(cls,"payment_enabled",True),
                "location": getattr(cls,"location","Студия"),
                "is_booked": cls.id in booked_ids,
            })
        next_class, days_until = "—", "—"
        if bookings:
            dt = bookings[0].cls.starts_at
            next_class = dt.strftime("%d.%m")
            diff = (dt.date() - datetime.now().date()).days
            days_until = "сегодня" if diff == 0 else f"{diff} дн."
        return {"name": user.full_name, "classes_left": sub.classes_left if sub else 0,
                "next_class": next_class, "days_until": days_until, "upcoming": upcoming}

@router.get("/schedule")
async def api_schedule(year: int, month: int, x_user_id: str = Header("0")):
    async with AsyncSessionFactory() as session:
        start = datetime(year, month, 1)
        end = datetime(year+1,1,1) if month==12 else datetime(year,month+1,1)
        result = await session.execute(select(Class).where(
            Class.starts_at >= start, Class.starts_at < end, Class.is_cancelled == False))
        classes = result.scalars().all()
        return {"classes": [{"date": c.starts_at.strftime("%Y-%m-%d")} for c in classes]}

@router.get("/schedule/day")
async def api_schedule_day(date: str, x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    async with AsyncSessionFactory() as session:
        dt = datetime.strptime(date, "%Y-%m-%d")
        result = await session.execute(select(Class).where(
            Class.starts_at >= dt, Class.starts_at < dt + timedelta(days=1),
            Class.is_cancelled == False).order_by(Class.starts_at))
        classes = result.scalars().all()
        booked_ids = set()
        if tg_id:
            bk = await session.execute(select(Booking).where(
                Booking.user_id == tg_id, Booking.status == BookingStatus.CONFIRMED))
            booked_ids = {b.class_id for b in bk.scalars().all()}
        out = []
        for cls in classes:
            confirmed = [b for b in cls.bookings if b.status == BookingStatus.CONFIRMED]
            out.append({"id": cls.id, "title": cls.title, "trainer": cls.trainer,
                "time": cls.starts_at.strftime("%H:%M"),
                "free_spots": cls.max_spots - len(confirmed),
                "payment_enabled": getattr(cls,"payment_enabled",True),
                "location": getattr(cls,"location","Студия"),
                "is_booked": cls.id in booked_ids})
        return {"classes": out}

class BookReq(BaseModel):
    class_id: int

@router.post("/book")
async def api_book(req: BookReq, x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    if not tg_id:
        return {"ok": False, "error": "Не авторизован"}
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
        cls = await session.get(Class, req.class_id)
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
async def api_cancel(req: CancelReq, x_user_id: str = Header("0")):
    async with AsyncSessionFactory() as session:
        await cancel_booking(session, req.booking_id)
        return {"ok": True}

@router.get("/bookings")
async def api_bookings(x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"bookings": []}
        bookings = await get_user_upcoming_bookings(session, user.id)
        return {"bookings": [{"booking_id": b.id, "title": b.cls.title,
            "trainer": b.cls.trainer, "date": b.cls.starts_at.strftime("%Y-%m-%d"),
            "time": b.cls.starts_at.strftime("%H:%M")} for b in bookings]}

@router.get("/subscription")
async def api_subscription(x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    async with AsyncSessionFactory() as session:
        result = await session.execute(select(User).where(User.id == tg_id))
        user = result.scalar_one_or_none()
        if not user:
            return {"classes_left": 0, "total": 0, "used": 0}
        sub = await get_active_subscription(session, user.id)
        if not sub:
            return {"classes_left": 0, "total": 0, "used": 0}
        total = SUBSCRIPTION_CLASSES.get(sub.sub_type, sub.classes_left)
        return {"classes_left": sub.classes_left, "total": total, "used": total - sub.classes_left}

class AttendReq(BaseModel):
    token: str

@router.post("/attend")
async def api_attend(req: AttendReq, x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    if not tg_id:
        return {"ok": False, "error": "Не авторизован"}

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
async def api_pay(req: PayReq, x_user_id: str = Header("0")):
    tg_id = int(x_user_id) if x_user_id.isdigit() else 0
    from db.models import SubscriptionType
    from services.payme import make_payment_url
    from db.queries import create_payment
    from config import settings as cfg
    plan_map = {
        "four":    SubscriptionType.PACK_4,
        "eight":   SubscriptionType.PACK_8,
        "twelve":  SubscriptionType.PACK_12,
        "sixteen": SubscriptionType.PACK_16,
    }
    price_map = {
        "four":    cfg.PRICE_4_CLASSES,
        "eight":   cfg.PRICE_8_CLASSES,
        "twelve":  cfg.PRICE_12_CLASSES,
        "sixteen": cfg.PRICE_16_CLASSES,
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
        payment = await create_payment(session, tg_id, price_map[req.plan], desc_map[req.plan], sub_type)
        payment_url = make_payment_url(payment.id, price_map[req.plan])
        return {"payment_url": payment_url}
