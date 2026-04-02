"""
Сервис интеграции с ЮKassa.

Документация: https://yookassa.ru/developers/api
Используем официальный SDK: yookassa

Принцип работы:
  1. Бот создаёт платёж через API → получает payment_url
  2. Отправляет клиенту ссылку на оплату
  3. ЮKassa присылает webhook на WEBHOOK_HOST/yukassa/webhook
  4. Мы подтверждаем оплату и активируем абонемент
"""

import uuid
import logging

from yookassa import Configuration, Payment
from yookassa.domain.models import Currency

from config import settings

logger = logging.getLogger(__name__)

# Инициализация SDK (один раз при импорте)
Configuration.account_id = settings.YUKASSA_SHOP_ID
Configuration.secret_key = settings.YUKASSA_SECRET_KEY


async def create_yukassa_payment(
    amount_rub: int,
    description: str,
    internal_payment_id: int,
    user_id: int,
) -> dict:
    """
    Создаёт платёж в ЮKassa.

    Возвращает:
        {
            "yukassa_id": "...",
            "payment_url": "https://yookassa.ru/checkout/...",
        }
    """
    idempotence_key = str(uuid.uuid4())

    payment = Payment.create(
        {
            "amount": {
                "value": str(amount_rub) + ".00",
                "currency": Currency.RUB,
            },
            "confirmation": {
                "type": "redirect",
                "return_url": settings.YUKASSA_RETURN_URL,
            },
            "capture": True,                   # автоматическое списание
            "description": description,
            "metadata": {
                "internal_payment_id": internal_payment_id,
                "telegram_user_id": user_id,
            },
        },
        idempotence_key,
    )

    logger.info(f"ЮKassa payment created: {payment.id} for user {user_id}")

    return {
        "yukassa_id": payment.id,
        "payment_url": payment.confirmation.confirmation_url,
    }


def parse_webhook(body: bytes, signature: str) -> dict | None:
    """
    Валидирует и разбирает webhook от ЮKassa.

    ЮKassa подписывает запрос через HMAC-SHA256.
    Возвращает None если подпись невалидна.
    """
    import hashlib, hmac

    expected = hmac.new(
        settings.YUKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        logger.warning("Invalid ЮKassa webhook signature")
        return None

    import json
    return json.loads(body)
