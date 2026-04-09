"""
Обработка платежей через ЮKassa.

Флоу:
  1. Клиент нажимает «Оплатить» → выбирает тариф
  2. Бот создаёт Payment в БД + платёж в ЮKassa
  3. Отправляет клиенту кнопку с ссылкой на оплату
  4. ЮKassa вызывает webhook → activate_subscription()
  5. Бот уведомляет клиента об успешной оплате
"""

import logging

from aiohttp import web
from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards.inline import back_to_menu, payment_link_keyboard, payment_plans_keyboard
from config import settings
from db.models import SubscriptionType, User
from db.queries import confirm_payment, create_payment, set_yukassa_id
from services.yukassa import create_yukassa_payment, parse_webhook

logger = logging.getLogger(__name__)
router = Router()

PRICES = {
    SubscriptionType.SINGLE: settings.PRICE_SINGLE,
    SubscriptionType.PACK_4: settings.PRICE_4_CLASSES,
    SubscriptionType.PACK_8: settings.PRICE_8_CLASSES,
}

DESCRIPTIONS = {
    SubscriptionType.SINGLE: "1 занятие пилатес",
    SubscriptionType.PACK_4: "Абонемент 4 занятия",
    SubscriptionType.PACK_8: "Абонемент 8 занятий",
}


# ─────────────────────── Меню оплаты ─────────────────────────────

@router.message(Command("pay"))
@router.callback_query(F.data == "pay")
async def show_payment_menu(event: Message | CallbackQuery):
    text = (
        "💳 <b>Выбери тариф:</b>\n\n"
        f"🔹 1 занятие — {settings.PRICE_SINGLE} ₽\n"
        f"🔹 4 занятия — {settings.PRICE_4_CLASSES} ₽ "
        f"({settings.PRICE_4_CLASSES // 4} ₽/занятие)\n"
        f"🔹 8 занятий — {settings.PRICE_8_CLASSES} ₽ 🔥 "
        f"({settings.PRICE_8_CLASSES // 8} ₽/занятие)\n\n"
        "Оплата через <b>ЮKassa</b> — банковской картой, СБП, кошельком."
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

    # Сохраняем платёж в БД
    payment = await create_payment(session, db_user.id, amount, description, sub_type)

    try:
        # Создаём платёж в ЮKassa
        result = await create_yukassa_payment(
            amount_rub=amount,
            description=description,
            internal_payment_id=payment.id,
            user_id=db_user.id,
        )
        await set_yukassa_id(session, payment.id, result["yukassa_id"])

        await call.message.edit_text(
            f"✅ <b>Счёт создан!</b>\n\n"
            f"Тариф: <b>{description}</b>\n"
            f"Сумма: <b>{amount} ₽</b>\n\n"
            f"Нажми кнопку ниже, чтобы перейти к оплате.\n"
            f"После успешной оплаты абонемент активируется <b>автоматически</b> 🎉",
            reply_markup=payment_link_keyboard(result["payment_url"]),
        )

    except Exception as e:
        logger.error(f"ЮKassa payment creation failed for user {db_user.id}: {e}", exc_info=True)
        await call.message.edit_text(
            "❌ Ошибка при создании платежа. Попробуй позже или напиши тренеру.",
            reply_markup=back_to_menu(),
        )


# ─────────────────────── Webhook ЮKassa ──────────────────────────

async def yukassa_webhook_handler(request: web.Request) -> web.Response:
    """
    aiohttp endpoint для уведомлений ЮKassa.
    Регистрируется в app.router отдельно (см. webhook_app.py).
    """
    body = await request.read()
    signature = request.headers.get("X-Signature", "")

    data = parse_webhook(body, signature)
    if not data:
        return web.Response(status=400, text="Invalid signature")

    event_type = data.get("type")
    if event_type != "notification":
        return web.Response(status=200, text="ok")

    obj = data.get("object", {})
    if obj.get("status") != "succeeded":
        return web.Response(status=200, text="ok")

    yukassa_id = obj.get("id")

    # Получаем бота из app (передаётся при старте)
    bot: Bot = request.app["bot"]

    from db.engine import AsyncSessionFactory
    async with AsyncSessionFactory() as session:
        payment = await confirm_payment(session, yukassa_id)
        if not payment:
            logger.warning(f"Payment not found for yukassa_id={yukassa_id}")
            return web.Response(status=200, text="ok")

        try:
            sub = payment.subscription
            await bot.send_message(
                payment.user_id,
                f"🎉 <b>Оплата прошла успешно!</b>\n\n"
                f"{DESCRIPTIONS[sub.sub_type]} активирован.\n"
                f"Осталось занятий: <b>{sub.classes_left}</b>\n"
                f"Действует до: <b>{sub.expires_at.strftime('%d.%m.%Y')}</b>\n\n"
                f"Записывайся на занятие: /book",
            )
        except Exception as e:
            logger.error(f"Failed to notify user {payment.user_id}: {e}")

    return web.Response(status=200, text="ok")
