"""
Все запросы к БД в одном месте — чисто и без дублирования.
"""

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import select, update, and_, delete
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import (
    Booking, BookingStatus, Class, ClassFeedback, Payment, PaymentStatus,
    Subscription, SubscriptionType, User, Waitlist,
)


# ═══════════════════════ USERS ═══════════════════════════════════

async def get_or_create_user(session: AsyncSession, tg_user) -> User:
    result = await session.execute(select(User).where(User.id == tg_user.id))
    user = result.scalar_one_or_none()
    if not user:
        user = User(
            id=tg_user.id,
            username=tg_user.username,
            full_name=tg_user.full_name,
        )
        session.add(user)
        await session.commit()
    return user


async def get_user(session: AsyncSession, user_id: int) -> Optional[User]:
    result = await session.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def get_all_active_users(session: AsyncSession) -> list[User]:
    result = await session.execute(select(User).where(User.is_active == True))
    return result.scalars().all()


async def get_users_by_filter(
    session: AsyncSession,
    gender=None,
    fitness_level=None,
    has_sub: Optional[bool] = None,
) -> list[User]:
    q = select(User).where(User.is_active == True)
    if gender is not None:
        q = q.where(User.gender == gender)
    if fitness_level is not None:
        q = q.where(User.fitness_level == fitness_level)
    if has_sub is True:
        active_ids = select(Subscription.user_id).where(Subscription.classes_left > 0)
        q = q.where(User.id.in_(active_ids))
    elif has_sub is False:
        active_ids = select(Subscription.user_id).where(Subscription.classes_left > 0)
        q = q.where(User.id.not_in(active_ids))
    result = await session.execute(q)
    return result.scalars().all()


# ═══════════════════════ CLASSES ══════════════════════════════════

async def get_upcoming_classes(session: AsyncSession, days: int = 7) -> list[Class]:
    now = datetime.utcnow()
    until = now + timedelta(days=days)
    result = await session.execute(
        select(Class)
        .options(selectinload(Class.bookings))
        .where(
            and_(
                Class.starts_at >= now,
                Class.starts_at <= until,
                Class.is_cancelled == False,
            )
        )
        .order_by(Class.starts_at)
    )
    return result.scalars().all()


async def get_class_by_id(session: AsyncSession, class_id: int) -> Optional[Class]:
    result = await session.execute(
        select(Class)
        .options(selectinload(Class.bookings))
        .where(Class.id == class_id)
    )
    return result.scalar_one_or_none()


async def create_class(session: AsyncSession, **kwargs) -> Class:
    cls = Class(**kwargs)
    session.add(cls)
    await session.commit()
    return cls


# ═══════════════════════ BOOKINGS ════════════════════════════════

async def get_user_upcoming_bookings(session: AsyncSession, user_id: int) -> list[Booking]:
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.cls))
        .join(Class)
        .where(
            and_(
                Booking.user_id == user_id,
                Booking.status == BookingStatus.CONFIRMED,
                Class.starts_at >= datetime.utcnow(),
            )
        )
        .order_by(Class.starts_at)
    )
    return result.scalars().all()


async def get_booking(session: AsyncSession, user_id: int, class_id: int) -> Optional[Booking]:
    result = await session.execute(
        select(Booking).where(
            and_(Booking.user_id == user_id, Booking.class_id == class_id)
        )
    )
    return result.scalar_one_or_none()


async def create_booking(session: AsyncSession, user_id: int, class_id: int) -> Booking:
    booking = Booking(user_id=user_id, class_id=class_id)
    session.add(booking)
    await session.commit()
    return booking


async def cancel_booking(session: AsyncSession, booking_id: int):
    booking = await session.get(Booking, booking_id)
    if not booking or booking.status != BookingStatus.CONFIRMED:
        return
    cls = await session.get(Class, booking.class_id)
    if cls and cls.starts_at > datetime.utcnow():
        # Возвращаем занятие в любой абонемент (включая замороженный)
        now = datetime.utcnow()
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.user_id == booking.user_id,
                    Subscription.classes_left > 0,
                    (Subscription.expires_at == None) | (Subscription.expires_at > now),
                )
            )
            .order_by(Subscription.expires_at)
        )
        sub = result.scalar_one_or_none()
        if sub:
            sub.classes_left += 1
    booking.status = BookingStatus.CANCELLED
    await session.commit()


async def mark_missed_bookings(session: AsyncSession):
    now = datetime.utcnow()
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.cls), selectinload(Booking.user))
        .join(Class)
        .where(
            and_(
                Booking.status == BookingStatus.CONFIRMED,
                Class.starts_at < now,
            )
        )
    )
    bookings = result.scalars().all()
    for b in bookings:
        b.status = BookingStatus.MISSED
    await session.commit()
    return bookings


async def get_attended_bookings_for_feedback(session: AsyncSession) -> list[Booking]:
    """Attended-записи, по которым ещё не отправлен запрос отзыва."""
    result = await session.execute(
        select(Booking)
        .options(selectinload(Booking.cls), selectinload(Booking.user))
        .join(Class)
        .where(
            and_(
                Booking.status == BookingStatus.ATTENDED,
                Booking.feedback_sent == False,
                Class.starts_at < datetime.utcnow(),
            )
        )
    )
    return result.scalars().all()


# ═══════════════════════ SUBSCRIPTIONS ═══════════════════════════

SUBSCRIPTION_CLASSES = {
    SubscriptionType.SINGLE:  1,
    SubscriptionType.TRIAL:   1,
    SubscriptionType.PACK_4:  4,
    SubscriptionType.PACK_8:  8,
    SubscriptionType.PACK_12: 12,
    SubscriptionType.PACK_16: 16,
}


async def get_active_subscription(session: AsyncSession, user_id: int) -> Optional[Subscription]:
    now = datetime.utcnow()
    result = await session.execute(
        select(Subscription).where(
            and_(
                Subscription.user_id == user_id,
                Subscription.classes_left > 0,
                Subscription.is_frozen == False,
                (Subscription.expires_at == None) | (Subscription.expires_at > now),
            )
        )
        .order_by(Subscription.expires_at)
    )
    return result.scalar_one_or_none()


async def create_subscription(
    session: AsyncSession, user_id: int, sub_type: SubscriptionType
) -> Subscription:
    classes = SUBSCRIPTION_CLASSES[sub_type]
    sub = Subscription(
        user_id=user_id,
        sub_type=sub_type,
        classes_left=classes,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    session.add(sub)
    await session.commit()
    return sub


async def decrement_subscription(session: AsyncSession, user_id: int):
    sub = await get_active_subscription(session, user_id)
    if sub:
        sub.classes_left -= 1
        await session.commit()
    return sub


async def freeze_subscription(
    session: AsyncSession, sub_id: int, days: int
) -> Optional[Subscription]:
    sub = await session.get(Subscription, sub_id)
    if not sub or sub.classes_left <= 0:
        return None
    sub.is_frozen = True
    sub.frozen_until = datetime.utcnow() + timedelta(days=days)
    if sub.expires_at:
        sub.expires_at = sub.expires_at + timedelta(days=days)
    await session.commit()
    return sub


async def unfreeze_subscription(session: AsyncSession, sub_id: int) -> Optional[Subscription]:
    sub = await session.get(Subscription, sub_id)
    if not sub:
        return None
    sub.is_frozen = False
    sub.frozen_until = None
    await session.commit()
    return sub


async def get_expiring_subscriptions(session: AsyncSession) -> list[Subscription]:
    deadline = datetime.utcnow() + timedelta(days=3)
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            and_(
                Subscription.classes_left > 0,
                Subscription.expires_at != None,
                Subscription.expires_at <= deadline,
                Subscription.expiry_warned == False,
            )
        )
    )
    return result.scalars().all()


async def get_low_classes_subscriptions(session: AsyncSession) -> list[Subscription]:
    result = await session.execute(
        select(Subscription)
        .options(selectinload(Subscription.user))
        .where(
            and_(
                Subscription.classes_left > 0,
                Subscription.classes_left <= 2,
                Subscription.low_classes_warned == False,
            )
        )
    )
    return result.scalars().all()


# ═══════════════════════ WAITLIST ════════════════════════════════

async def get_waitlist_entry(
    session: AsyncSession, user_id: int, class_id: int
) -> Optional[Waitlist]:
    result = await session.execute(
        select(Waitlist).where(
            and_(Waitlist.user_id == user_id, Waitlist.class_id == class_id)
        )
    )
    return result.scalar_one_or_none()


async def add_to_waitlist(
    session: AsyncSession, user_id: int, class_id: int
) -> Waitlist:
    entry = Waitlist(user_id=user_id, class_id=class_id)
    session.add(entry)
    await session.commit()
    return entry


async def get_next_waitlist(
    session: AsyncSession, class_id: int
) -> Optional[Waitlist]:
    result = await session.execute(
        select(Waitlist)
        .options(selectinload(Waitlist.user))
        .where(
            and_(Waitlist.class_id == class_id, Waitlist.notified == False)
        )
        .order_by(Waitlist.created_at)
        .limit(1)
    )
    return result.scalar_one_or_none()


async def mark_waitlist_notified(session: AsyncSession, entry_id: int):
    entry = await session.get(Waitlist, entry_id)
    if entry:
        entry.notified = True
        await session.commit()


async def remove_from_waitlist(session: AsyncSession, user_id: int, class_id: int):
    await session.execute(
        delete(Waitlist).where(
            and_(Waitlist.user_id == user_id, Waitlist.class_id == class_id)
        )
    )
    await session.commit()


# ═══════════════════════ FEEDBACK ════════════════════════════════

async def save_feedback(
    session: AsyncSession,
    user_id: int,
    class_id: int,
    rating: int,
    comment: str | None = None,
) -> ClassFeedback:
    fb = ClassFeedback(user_id=user_id, class_id=class_id, rating=rating, comment=comment)
    session.add(fb)
    await session.commit()
    return fb


async def has_feedback(session: AsyncSession, user_id: int, class_id: int) -> bool:
    result = await session.execute(
        select(ClassFeedback).where(
            and_(ClassFeedback.user_id == user_id, ClassFeedback.class_id == class_id)
        )
    )
    return result.scalar_one_or_none() is not None


# ═══════════════════════ PAYMENTS ════════════════════════════════

async def create_payment(
    session: AsyncSession,
    user_id: int,
    amount: int,
    description: str,
    sub_type: SubscriptionType,
) -> Payment:
    sub = Subscription(
        user_id=user_id,
        sub_type=sub_type,
        classes_left=0,
        expires_at=None,
    )
    session.add(sub)
    await session.flush()

    payment = Payment(
        user_id=user_id,
        subscription_id=sub.id,
        amount=amount,
        description=description,
    )
    session.add(payment)
    await session.commit()
    return payment


async def get_payment_by_id(session: AsyncSession, payment_id: int) -> Optional[Payment]:
    return await session.get(Payment, payment_id)


async def set_payme_id(session: AsyncSession, payment_id: int, payme_id: str):
    await session.execute(
        update(Payment).where(Payment.id == payment_id).values(payme_id=payme_id)
    )
    await session.commit()


async def confirm_payme_payment(session: AsyncSession, payme_id: str) -> Optional[Payment]:
    result = await session.execute(
        select(Payment)
        .options(selectinload(Payment.subscription), selectinload(Payment.user))
        .where(Payment.payme_id == payme_id)
    )
    payment = result.scalar_one_or_none()
    if not payment:
        return None

    payment.status = PaymentStatus.SUCCEEDED
    payment.paid_at = datetime.utcnow()

    sub = payment.subscription
    classes = SUBSCRIPTION_CLASSES[sub.sub_type]
    sub.classes_left = classes
    sub.expires_at = datetime.utcnow() + timedelta(days=30)

    await session.commit()
    return payment


async def cancel_payme_payment(session: AsyncSession, payme_id: str):
    await session.execute(
        update(Payment).where(Payment.payme_id == payme_id).values(status=PaymentStatus.CANCELLED)
    )
    await session.commit()


# ─── Настройки студии ───────────────────────────────────────
async def get_setting(session, key: str, default: str = "") -> str:
    from sqlalchemy import text
    result = await session.execute(text("SELECT value FROM settings WHERE key = :k"), {"k": key})
    row = result.fetchone()
    return row[0] if row else default

async def set_setting(session, key: str, value: str):
    from sqlalchemy import text
    await session.execute(text(
        "INSERT INTO settings (key, value, updated_at) VALUES (:k, :v, NOW()) "
        "ON CONFLICT (key) DO UPDATE SET value = :v, updated_at = NOW()"
    ), {"k": key, "v": value})
    await session.commit()

async def get_all_settings(session) -> dict:
    from sqlalchemy import text
    result = await session.execute(text("SELECT key, value FROM settings"))
    return {row[0]: row[1] for row in result.fetchall()}
