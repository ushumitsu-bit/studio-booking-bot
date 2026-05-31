"""
Обработка платежей через Payme.

Флоу:
  1. Клиент нажимает «Оплатить» → выбирает тариф
  2. Бот создаёт Payment в БД и формирует ссылку на Payme Checkout
  3. Payme вызывает webhook (JSON-RPC) → confirm_payme_payment()
  4. Бот уведомляет клиента об успешной оплате
"""

import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_menu, payment_link_keyboard, payment_plans_keyboard
from config import settings
from db.models import SubscriptionType, User
from db.queries import create_payment, set_payme_id
from services.payme import make_payment_url

logger = logging.getLogger(__name__)
router = Router()

PRICES = {
    SubscriptionType.PACK_4:  settings.PRICE_4_CLASSES,
    SubscriptionType.PACK_8:  settings.PRICE_8_CLASSES,
    SubscriptionType.PACK_12: settings.PRICE_12_CLASSES,
    SubscriptionType.PACK_16: settings.PRICE_16_CLASSES,
}

DESCRIPTIONS = {
    SubscriptionType.PACK_4:  "Абонемент 4 занятия",
    SubscriptionType.PACK_8:  "Абонемент 8 занятий",
    SubscriptionType.PACK_12: "Абонемент 12 занятий",
    SubscriptionType.PACK_16: "Абонемент 16 занятий",
}


# ─────────────────────── Меню оплаты ─────────────────────────────

@router.message(Command("pay"))
@router.callback_query(F.data == "pay")
async def show_payment_menu(event: Message | CallbackQuery):
    text = (
        "💳 <b>Выбери тариф:</b>\n\n"
        f"🔹 4 занятия — {settings.PRICE_4_CLASSES:,} сум "
        f"({settings.PRICE_4_CLASSES // 4:,} сум/зан.)\n"
        f"🔹 8 занятий — {settings.PRICE_8_CLASSES:,} сум "
        f"({settings.PRICE_8_CLASSES // 8:,} сум/зан.)\n"
        f"🔹 12 занятий — {settings.PRICE_12_CLASSES:,} сум 🔥 "
        f"({settings.PRICE_12_CLASSES // 12:,} сум/зан.)\n"
        f"🔹 16 занятий — {settings.PRICE_16_CLASSES:,} сум 💎 "
        f"({settings.PRICE_16_CLASSES // 16:,} сум/зан.)\n\n"
        "Срок действия: <b>30 дней</b> с момента оплаты.\n"
        "Оплата через <b>Payme</b> — Uzcard, Humo, Visa/Mastercard."
    )
    kb = payment_plans_keyboard()

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=kb)
    else:
        await event.answer(text, reply_markup=kb)


# ─────────────────────── Создание платежа ────────────────────────

@router.callback_query(F.data.startswith("pay_"))
async def initiate_payment(call: CallbackQuery, session: AsyncSession, db_user: User):
    sub_type_str = call.data.split("_", 1)[1]
    try:
        sub_type = SubscriptionType(sub_type_str)
    except ValueError:
        await call.answer("Неверный тариф", show_alert=True)
        return

    amount = PRICES[sub_type]
    description = DESCRIPTIONS[sub_type]

    payment = await create_payment(session, db_user.id, amount, description, sub_type)

    try:
        payment_url = make_payment_url(payment.id, amount)

        await call.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"Тариф: <b>{description}</b>\n"
            f"Сумма: <b>{amount:,} сум</b>\n\n"
            f"1️⃣ Нажми «Оплатить» — откроется Payme\n"
            f"2️⃣ Оплати удобным способом (Uzcard, Humo, Visa/MC)\n"
            f"3️⃣ Вернись в бот — абонемент активируется и я пришлю подтверждение 🎉\n\n"
            f"<i>Оплата обрабатывается автоматически, ждать не нужно.</i>",
            reply_markup=payment_link_keyboard(payment_url),
        )

    except Exception as e:
        logger.error(f"Payme payment creation failed for user {db_user.id}: {e}", exc_info=True)
        await call.message.edit_text(
            "❌ Ошибка при создании платежа. Попробуй позже или напиши тренеру.",
            reply_markup=back_to_menu(),
        )
