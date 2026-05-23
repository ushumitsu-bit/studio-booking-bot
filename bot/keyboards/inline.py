from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings


def payment_plans_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"1 занятие — {settings.PRICE_SINGLE} ₽",       callback_data="pay_single")
    builder.button(text=f"4 занятия — {settings.PRICE_4_CLASSES} ₽",     callback_data="pay_pack_4")
    builder.button(text=f"8 занятий — {settings.PRICE_8_CLASSES} ₽ 🔥",  callback_data="pay_pack_8")
    builder.button(text="← Меню",                                          callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()


def payment_link_keyboard(url: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Перейти к оплате", url=url)
    builder.button(text="← Назад",             callback_data="pay")
    builder.adjust(1)
    return builder.as_markup()


def back_to_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="← Меню", callback_data="menu")
    builder.adjust(1)
    return builder.as_markup()
