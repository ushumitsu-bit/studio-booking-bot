"""
Планировщик задач (APScheduler).

Запускается вместе с ботом и выполняет:
  • каждые 15 мин — напоминания за 24ч и 2ч до занятия
  • каждые 15 мин — «пинки» за пропуск
  • каждые 60 мин — предупреждения о заканчивающихся абонементах
"""

import logging
from datetime import datetime, timedelta

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from db.engine import AsyncSessionFactory
from db.models import BookingStatus
from db.queries import (
    get_all_active_users,
    get_expiring_subscriptions,
    get_upcoming_classes,
    mark_missed_bookings,
)
from sqlalchemy import select, and_, update
from db.models import Booking, Class

logger = logging.getLogger(__name__)


# ──────────────────────── Тексты сообщений ───────────────────────

def text_reminder_24h(class_title: str, starts_at: datetime) -> str:
    day = starts_at.strftime("%A").lower()
    time = starts_at.strftime("%H:%M")
    days_ru = {
        "monday": "понедельник", "tuesday": "вторник", "wednesday": "среда",
        "thursday": "четверг", "friday": "пятница", "saturday": "суббота",
        "sunday": "воскресенье",
    }
    return (
        f"⏰ <b>Напоминаю о занятии!</b>\n\n"
        f"Завтра в <b>{time}</b> ({days_ru.get(day, day)}) у тебя:\n"
        f"🧘 <b>{class_title}</b>\n\n"
        f"Если не сможешь прийти — отмени заранее, чтобы место досталось другому 🙏\n"
        f"Нажми /mybookings → Отменить"
    )


def text_reminder_2h(class_title: str, starts_at: datetime) -> str:
    time = starts_at.strftime("%H:%M")
    return (
        f"🔔 <b>Через 2 часа — пилатес!</b>\n\n"
        f"В <b>{time}</b> ждём тебя на:\n"
        f"🧘 <b>{class_title}</b>\n\n"
        f"Не забудь взять коврик и воду 💧"
    )


def text_kick_missed(class_title: str, starts_at: datetime) -> str:
    time = starts_at.strftime("%H:%M")
    return (
        f"😔 <b>Ты не пришла сегодня...</b>\n\n"
        f"Мы ждали тебя в <b>{time}</b> на <i>{class_title}</i>, "
        f"но ты не появилась.\n\n"
        f"Всё в порядке? Если пропуск был по уважительной причине — "
        f"напиши тренеру, разберёмся 💛\n\n"
        f"Записаться на следующее: /schedule"
    )


def text_expiring_subscription(classes_left: int, expires_at: datetime) -> str:
    days = (expires_at - datetime.utcnow()).days
    return (
        f"💳 <b>Абонемент скоро заканчивается!</b>\n\n"
        f"Осталось занятий: <b>{classes_left}</b>\n"
        f"Срок действия истекает через <b>{days} дн.</b>\n\n"
        f"Продли сейчас, чтобы не терять место в расписании 👇\n"
        f"/pay"
    )


# ──────────────────────── Задачи ─────────────────────────────────

async def send_reminders(bot: Bot):
    """Напоминания за 24ч и за 2ч до занятия."""
    async with AsyncSessionFactory() as session:
        now = datetime.utcnow()

        # Записи на занятия, которые начнутся через 23–25 часов (окно 15 мин)
        result = await session.execute(
            select(Booking)
            .join(Class)
            .where(
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
                logger.error(f"Reminder 24h error for {booking.user_id}: {e}")

        # Напоминание за 2ч (окно 15 мин)
        result2 = await session.execute(
            select(Booking)
            .join(Class)
            .where(
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
                logger.error(f"Reminder 2h error for {booking.user_id}: {e}")

        await session.commit()


async def send_kick_messages(bot: Bot):
    """Пинок — занятие прошло, клиент не отметился."""
    async with AsyncSessionFactory() as session:
        missed = await mark_missed_bookings(session)
        for booking in missed:
            try:
                await bot.send_message(
                    booking.user_id,
                    text_kick_missed(booking.cls.title, booking.cls.starts_at),
                )
                logger.info(f"Kick sent to user {booking.user_id}")
            except Exception as e:
                logger.error(f"Kick error for {booking.user_id}: {e}")


async def warn_expiring_subscriptions(bot: Bot):
    """Предупреждение об истекающем абонементе."""
    async with AsyncSessionFactory() as session:
        subs = await get_expiring_subscriptions(session)
        for sub in subs:
            try:
                await bot.send_message(
                    sub.user_id,
                    text_expiring_subscription(sub.classes_left, sub.expires_at),
                )
                sub.expiry_warned = True
            except Exception as e:
                logger.error(f"Expiry warning error for {sub.user_id}: {e}")
        await session.commit()


# ──────────────────────── Инициализация ──────────────────────────

async def setup_scheduler(bot: Bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone="Europe/Moscow")

    scheduler.add_job(
        send_reminders, "interval", minutes=15,
        kwargs={"bot": bot}, id="reminders",
    )
    scheduler.add_job(
        send_kick_messages, "interval", minutes=15,
        kwargs={"bot": bot}, id="kicks",
    )
    scheduler.add_job(
        warn_expiring_subscriptions, "interval", minutes=60,
        kwargs={"bot": bot}, id="expiry_warnings",
    )

    return scheduler
