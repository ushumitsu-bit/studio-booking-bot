"""
Планировщик задач (APScheduler).

  • каждые 15 мин — напоминания за 24ч и 2ч до занятия
  • каждые 15 мин — пинки за пропуск + обновление streak
  • каждые 30 мин — запрос отзыва после attended-занятий
  • каждые 60 мин — предупреждения о заканчивающихся абонементах
  • каждые 60 мин — авторазморозка истёкших заморозок
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config import settings
from db.engine import AsyncSessionFactory
from db.models import Booking, BookingStatus, Class, Subscription
from db.queries import (
    get_expiring_subscriptions,
    get_low_classes_subscriptions,
    get_attended_bookings_for_feedback,
    mark_missed_bookings,
)
from sqlalchemy import select, and_, update

logger = logging.getLogger(__name__)


# ──────────────────────── Тексты сообщений ───────────────────────

def text_reminder_24h(class_title: str, starts_at: datetime) -> str:
    days_ru = {
        "monday": "понедельник", "tuesday": "вторник", "wednesday": "среда",
        "thursday": "четверг", "friday": "пятница", "saturday": "суббота",
        "sunday": "воскресенье",
    }
    day = days_ru.get(starts_at.strftime("%A").lower(), "")
    return (
        f"⏰ <b>Напоминаю о занятии!</b>\n\n"
        f"Завтра в <b>{starts_at.strftime('%H:%M')}</b> ({day}) у тебя:\n"
        f"🧘 <b>{class_title}</b>\n\n"
        f"Если не сможешь прийти — отмени заранее 🙏\n"
        f"/mybookings → Отменить"
    )


def text_reminder_2h(class_title: str, starts_at: datetime) -> str:
    return (
        f"🔔 <b>Через 2 часа — занятие!</b>\n\n"
        f"В <b>{starts_at.strftime('%H:%M')}</b> ждём тебя:\n"
        f"🧘 <b>{class_title}</b>\n\n"
        f"Не забудь взять воду 💧"
    )


def text_kick_missed(class_title: str, starts_at: datetime) -> str:
    return (
        f"😔 <b>Ты не пришла сегодня...</b>\n\n"
        f"Ждали тебя в <b>{starts_at.strftime('%H:%M')}</b> на <i>{class_title}</i>.\n\n"
        f"Всё в порядке? Если пропуск по уважительной причине — напиши тренеру 💛\n\n"
        f"Следующее занятие: /schedule"
    )


def text_expiring_subscription(classes_left: int, expires_at: datetime) -> str:
    days = (expires_at - datetime.utcnow()).days
    days_str = "сегодня" if days <= 0 else f"через {days} дн."
    return (
        f"⚠️ <b>Абонемент истекает {days_str}!</b>\n\n"
        f"Осталось занятий: <b>{classes_left}</b>\n"
        f"Срок: <b>{expires_at.strftime('%d.%m.%Y')}</b>\n\n"
        f"Продли сейчас, чтобы не потерять место 👇"
    )


def text_low_classes(classes_left: int) -> str:
    word = "занятие" if classes_left == 1 else "занятия"
    return (
        f"💳 <b>Занятия заканчиваются!</b>\n\n"
        f"На абонементе осталось <b>{classes_left} {word}</b>.\n\n"
        f"Купи новый заранее — так сохранишь место в расписании 👇"
    )


def text_feedback_request(class_title: str, starts_at: datetime, lang: str = "ru") -> str:
    from bot.translations import t
    return t("feedback_request", lang,
             title=class_title,
             dt=starts_at.strftime("%d.%m %H:%M"))


def text_streak(streak: int) -> str:
    if streak == 3:
        return f"🔥 <b>3 занятия подряд!</b> Отличная серия, так держать!"
    if streak == 7:
        return f"🏆 <b>7 занятий подряд!</b> Ты настоящая звезда студии! ⭐"
    if streak == 14:
        return f"💎 <b>2 недели без пропусков!</b> Невероятная дисциплина!"
    return ""


# ──────────────────────── Задачи ─────────────────────────────────

async def send_reminders(bot: Bot):
    """Напоминания за 24ч и за 2ч до занятия."""
    async with AsyncSessionFactory() as session:
        now = datetime.utcnow()

        result = await session.execute(
            select(Booking).join(Class).where(
                and_(
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.reminder_sent == False,
                    Class.starts_at >= now + timedelta(hours=23),
                    Class.starts_at <= now + timedelta(hours=25),
                )
            )
        )
        for booking in result.scalars().all():
            try:
                await bot.send_message(
                    booking.user_id,
                    text_reminder_24h(booking.cls.title, booking.cls.starts_at),
                )
                booking.reminder_sent = True
            except Exception as e:
                logger.error(f"Reminder 24h error {booking.user_id}: {e}")

        result2 = await session.execute(
            select(Booking).join(Class).where(
                and_(
                    Booking.status == BookingStatus.CONFIRMED,
                    Booking.reminder2_sent == False,
                    Class.starts_at >= now + timedelta(hours=1, minutes=45),
                    Class.starts_at <= now + timedelta(hours=2, minutes=15),
                )
            )
        )
        for booking in result2.scalars().all():
            try:
                await bot.send_message(
                    booking.user_id,
                    text_reminder_2h(booking.cls.title, booking.cls.starts_at),
                )
                booking.reminder2_sent = True
            except Exception as e:
                logger.error(f"Reminder 2h error {booking.user_id}: {e}")

        await session.commit()


async def send_kick_messages(bot: Bot):
    """Пинок за пропуск + обновление streak при посещении."""
    async with AsyncSessionFactory() as session:
        missed = await mark_missed_bookings(session)
        for booking in missed:
            try:
                await bot.send_message(
                    booking.user_id,
                    text_kick_missed(booking.cls.title, booking.cls.starts_at),
                )
            except Exception as e:
                logger.error(f"Kick error {booking.user_id}: {e}")

        # Обновляем streak для attended-записей, по которым ещё не обновляли
        from sqlalchemy.orm import selectinload as _sil
        now = datetime.utcnow()
        result2 = await session.execute(
            select(Booking)
            .options(_sil(Booking.user), _sil(Booking.cls))
            .where(
                and_(
                    Booking.status == BookingStatus.ATTENDED,
                    Booking.streak_updated == False,
                )
            )
        )
        for booking in result2.scalars().all():
            user = booking.user
            if not user:
                continue
            # Streak: сбрасываем если последнее посещение было давно
            if user.last_attended_at and (now - user.last_attended_at).days > 14:
                user.streak_count = 1
            else:
                user.streak_count = (user.streak_count or 0) + 1
            user.last_attended_at = now
            booking.streak_updated = True

            streak_text = text_streak(user.streak_count)
            if streak_text:
                try:
                    await bot.send_message(user.id, streak_text)
                except Exception:
                    pass

        await session.commit()


async def send_feedback_requests(bot: Bot):
    """Запрос отзыва после посещённого занятия."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with AsyncSessionFactory() as session:
        bookings = await get_attended_bookings_for_feedback(session)
        for booking in bookings:
            user = booking.user
            lang = user.language.value if user and user.language else "ru"
            try:
                b = InlineKeyboardBuilder()
                for star in range(1, 6):
                    emoji = "⭐" * star
                    b.button(
                        text=emoji,
                        callback_data=f"feedback_rate_{booking.class_id}_{star}",
                    )
                b.adjust(5)
                await bot.send_message(
                    booking.user_id,
                    text_feedback_request(booking.cls.title, booking.cls.starts_at, lang),
                    reply_markup=b.as_markup(),
                )
                booking.feedback_sent = True
            except Exception as e:
                logger.error(f"Feedback request error {booking.user_id}: {e}")
        await session.commit()


async def warn_expiring_subscriptions(bot: Bot):
    """Предупреждение об истечении срока абонемента (≤3 дня)."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with AsyncSessionFactory() as session:
        subs = await get_expiring_subscriptions(session)
        for sub in subs:
            try:
                b = InlineKeyboardBuilder()
                b.button(text="💳 Продлить абонемент", callback_data="pay")
                b.adjust(1)
                await bot.send_message(
                    sub.user_id,
                    text_expiring_subscription(sub.classes_left, sub.expires_at),
                    reply_markup=b.as_markup(),
                )
                sub.expiry_warned = True
            except Exception as e:
                logger.error(f"Expiry warning error {sub.user_id}: {e}")
        await session.commit()


async def warn_low_classes(bot: Bot):
    """Предупреждение когда осталось ≤2 занятий."""
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    async with AsyncSessionFactory() as session:
        subs = await get_low_classes_subscriptions(session)
        for sub in subs:
            try:
                b = InlineKeyboardBuilder()
                b.button(text="💳 Купить абонемент", callback_data="pay")
                b.adjust(1)
                await bot.send_message(
                    sub.user_id,
                    text_low_classes(sub.classes_left),
                    reply_markup=b.as_markup(),
                )
                sub.low_classes_warned = True
            except Exception as e:
                logger.error(f"Low classes warning error {sub.user_id}: {e}")
        await session.commit()


async def auto_unfreeze_subscriptions(bot: Bot):
    """Авторазморозка абонементов у которых frozen_until прошёл."""
    async with AsyncSessionFactory() as session:
        now = datetime.utcnow()
        result = await session.execute(
            select(Subscription).where(
                and_(
                    Subscription.is_frozen == True,
                    Subscription.frozen_until != None,
                    Subscription.frozen_until <= now,
                )
            )
        )
        for sub in result.scalars().all():
            sub.is_frozen = False
            sub.frozen_until = None
            try:
                await bot.send_message(
                    sub.user_id,
                    f"🔥 <b>Абонемент разморожен!</b>\n\n"
                    f"Срок заморозки истёк — записывайся на занятия 🧘\n/schedule",
                )
            except Exception:
                pass
        await session.commit()


# ──────────────────────── Инициализация ──────────────────────────

async def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")

    scheduler.add_job(
        send_reminders, "interval", minutes=15,
        kwargs={"bot": bot}, id="reminders",
    )
    scheduler.add_job(
        send_kick_messages, "interval", minutes=15,
        kwargs={"bot": bot}, id="kicks",
    )
    scheduler.add_job(
        send_feedback_requests, "interval", minutes=30,
        kwargs={"bot": bot}, id="feedback_requests",
    )
    scheduler.add_job(
        warn_expiring_subscriptions, "interval", minutes=60,
        kwargs={"bot": bot}, id="expiry_warnings",
    )
    scheduler.add_job(
        warn_low_classes, "interval", minutes=60,
        kwargs={"bot": bot}, id="low_classes_warnings",
    )
    scheduler.add_job(
        auto_unfreeze_subscriptions, "interval", minutes=60,
        kwargs={"bot": bot}, id="auto_unfreeze",
    )

    return scheduler
