from datetime import datetime

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db.models import Booking, Class
from config import settings


def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📅 Расписание", callback_data="schedule"))
    builder.row(InlineKeyboardButton(text="✏️ Записаться на занятие", callback_data="book"))
    builder.row(InlineKeyboardButton(text="🗓 Мои записи", callback_data="my_bookings"))
    builder.row(InlineKeyboardButton(text="💳 Оплатить абонемент", callback_data="pay"))
    builder.row(InlineKeyboardButton(text="📊 Мой абонемент", callback_data="my_sub"))
    return builder.as_markup()


def classes_keyboard(classes: list[Class]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for cls in classes:
        time_str = cls.starts_at.strftime("%d.%m %H:%M")
        spots = cls.free_spots
        spots_label = f"✅ {spots} мест" if spots > 2 else (f"⚠️ {spots} место" if spots > 0 else "❌ мест нет")
        builder.row(
            InlineKeyboardButton(
                text=f"{time_str} · {cls.title} · {spots_label}",
                callback_data=f"book_{cls.id}" if spots > 0 else "full",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu"))
    return builder.as_markup()


def confirm_booking_keyboard(class_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="✅ Записаться", callback_data=f"confirm_book_{class_id}"),
        InlineKeyboardButton(text="❌ Отмена", callback_data="book"),
    )
    return builder.as_markup()


def my_bookings_keyboard(bookings: list[Booking]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for b in bookings:
        time_str = b.cls.starts_at.strftime("%d.%m %H:%M")
        builder.row(
            InlineKeyboardButton(
                text=f"❌ Отменить: {time_str} {b.cls.title}",
                callback_data=f"cancel_booking_{b.id}",
            )
        )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu"))
    return builder.as_markup()


def payment_plans_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=f"1 занятие — {settings.PRICE_SINGLE} ₽",
            callback_data="pay_single",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"4 занятия — {settings.PRICE_4_CLASSES} ₽",
            callback_data="pay_pack_4",
        )
    )
    builder.row(
        InlineKeyboardButton(
            text=f"8 занятий — {settings.PRICE_8_CLASSES} ₽ 🔥",
            callback_data="pay_pack_8",
        )
    )
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="menu"))
    return builder.as_markup()


def payment_link_keyboard(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Перейти к оплате", url=url))
    builder.row(InlineKeyboardButton(text="◀️ Назад", callback_data="pay"))
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="◀️ В меню", callback_data="menu"))
    return builder.as_markup()
