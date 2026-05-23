"""
Payme Subscribe API integration.

Checkout URL:
  https://checkout.paycom.uz/{base64(m=MERCHANT_ID;ac.order_id=PAYMENT_ID;a=AMOUNT_TIYIN;l=ru)}

Webhook (JSON-RPC, Basic Auth: Paycom / PAYME_SECRET_KEY):
  CheckPerformTransaction — проверить, можно ли создать транзакцию
  CreateTransaction       — создать транзакцию (state=1)
  PerformTransaction      — подтвердить транзакцию (state=2) → активируем абонемент
  CancelTransaction       — отменить транзакцию
  CheckTransaction        — статус транзакции

Amount: тийин = сумы × 100
"""

import base64
import logging
import time
from typing import Any

from config import settings

logger = logging.getLogger(__name__)

# Payme error codes
ERR_AUTH          = -32504
ERR_ORDER_NOT_FOUND = -31050
ERR_AMOUNT_MISMATCH = -31001
ERR_TX_NOT_FOUND  = -31003
ERR_CANT_CANCEL   = -31007
ERR_ALREADY_DONE  = -31060

PRICE_MAP = {
    "single": settings.PRICE_SINGLE,
    "pack_4": settings.PRICE_4_CLASSES,
    "pack_8": settings.PRICE_8_CLASSES,
}


def make_payment_url(payment_id: int, amount_uzs: int) -> str:
    amount_tiyin = amount_uzs * 100
    params = f"m={settings.PAYME_MERCHANT_ID};ac.order_id={payment_id};a={amount_tiyin};l=ru"
    encoded = base64.b64encode(params.encode()).decode()
    return f"https://checkout.paycom.uz/{encoded}"


def check_auth(authorization: str) -> bool:
    """Проверяет Basic Auth заголовок от Payme."""
    try:
        scheme, token = authorization.split(" ", 1)
        if scheme.lower() != "basic":
            return False
        decoded = base64.b64decode(token).decode()
        login, password = decoded.split(":", 1)
        return login == "Paycom" and password == settings.PAYME_SECRET_KEY
    except Exception:
        return False


def _ok(request_id: Any, result: dict) -> dict:
    return {"id": request_id, "result": result}


def _err(request_id: Any, code: int, message: str) -> dict:
    return {"id": request_id, "error": {"code": code, "message": {"ru": message, "uz": message, "en": message}}}


async def handle_rpc(body: dict, authorization: str) -> dict:
    """Диспетчер JSON-RPC методов Payme."""
    from db.engine import AsyncSessionFactory
    from db.queries import (
        get_payment_by_id, set_payme_id, confirm_payme_payment,
        cancel_payme_payment,
    )
    from db.models import Payment, PaymentStatus

    if not check_auth(authorization):
        return _err(body.get("id"), ERR_AUTH, "Ошибка авторизации")

    method = body.get("method", "")
    params = body.get("params", {})
    req_id = body.get("id")

    async with AsyncSessionFactory() as session:

        if method == "CheckPerformTransaction":
            order_id = params.get("account", {}).get("order_id")
            amount = params.get("amount")
            if not order_id:
                return _err(req_id, ERR_ORDER_NOT_FOUND, "Заказ не найден")
            payment = await get_payment_by_id(session, int(order_id))
            if not payment:
                return _err(req_id, ERR_ORDER_NOT_FOUND, "Заказ не найден")
            expected = payment.amount * 100  # UZS → tiyin
            if amount != expected:
                return _err(req_id, ERR_AMOUNT_MISMATCH, "Неверная сумма")
            return _ok(req_id, {"allow": True})

        elif method == "CreateTransaction":
            order_id = params.get("account", {}).get("order_id")
            payme_tx_id = params.get("id")
            amount = params.get("amount")
            if not order_id:
                return _err(req_id, ERR_ORDER_NOT_FOUND, "Заказ не найден")
            payment = await get_payment_by_id(session, int(order_id))
            if not payment:
                return _err(req_id, ERR_ORDER_NOT_FOUND, "Заказ не найден")
            expected = payment.amount * 100
            if amount != expected:
                return _err(req_id, ERR_AMOUNT_MISMATCH, "Неверная сумма")
            if payment.status == PaymentStatus.SUCCEEDED:
                return _err(req_id, ERR_ALREADY_DONE, "Уже оплачено")
            if payment.status == PaymentStatus.CANCELLED:
                return _err(req_id, ERR_CANT_CANCEL, "Заказ отменён")
            # Сохраняем payme transaction id
            await set_payme_id(session, payment.id, payme_tx_id)
            create_time = int(time.time() * 1000)
            return _ok(req_id, {"create_time": create_time, "transaction": str(payment.id), "state": 1})

        elif method == "PerformTransaction":
            payme_tx_id = params.get("id")
            from sqlalchemy import select
            from db.models import Payment as PaymentModel
            result = await session.execute(
                select(PaymentModel).where(PaymentModel.payme_id == payme_tx_id)
            )
            payment = result.scalar_one_or_none()
            if not payment:
                return _err(req_id, ERR_TX_NOT_FOUND, "Транзакция не найдена")
            if payment.status == PaymentStatus.SUCCEEDED:
                perform_time = int(payment.paid_at.timestamp() * 1000) if payment.paid_at else int(time.time() * 1000)
                return _ok(req_id, {"perform_time": perform_time, "transaction": str(payment.id), "state": 2})
            payment = await confirm_payme_payment(session, payme_tx_id)
            if not payment:
                return _err(req_id, ERR_TX_NOT_FOUND, "Транзакция не найдена")
            perform_time = int(payment.paid_at.timestamp() * 1000)
            return _ok(req_id, {"perform_time": perform_time, "transaction": str(payment.id), "state": 2})

        elif method == "CancelTransaction":
            payme_tx_id = params.get("id")
            reason = params.get("reason", 0)
            from sqlalchemy import select
            from db.models import Payment as PaymentModel
            result = await session.execute(
                select(PaymentModel).where(PaymentModel.payme_id == payme_tx_id)
            )
            payment = result.scalar_one_or_none()
            if not payment:
                return _err(req_id, ERR_TX_NOT_FOUND, "Транзакция не найдена")
            if payment.status == PaymentStatus.SUCCEEDED:
                return _err(req_id, ERR_CANT_CANCEL, "Нельзя отменить выполненный платёж")
            await cancel_payme_payment(session, payme_tx_id)
            cancel_time = int(time.time() * 1000)
            return _ok(req_id, {"cancel_time": cancel_time, "transaction": str(payment.id), "state": -1})

        elif method == "CheckTransaction":
            payme_tx_id = params.get("id")
            from sqlalchemy import select
            from db.models import Payment as PaymentModel
            result = await session.execute(
                select(PaymentModel).where(PaymentModel.payme_id == payme_tx_id)
            )
            payment = result.scalar_one_or_none()
            if not payment:
                return _err(req_id, ERR_TX_NOT_FOUND, "Транзакция не найдена")
            state_map = {
                PaymentStatus.PENDING: 1,
                PaymentStatus.SUCCEEDED: 2,
                PaymentStatus.CANCELLED: -1,
            }
            state = state_map.get(payment.status, 1)
            create_time = int(payment.created_at.timestamp() * 1000)
            perform_time = int(payment.paid_at.timestamp() * 1000) if payment.paid_at else 0
            return _ok(req_id, {
                "create_time": create_time,
                "perform_time": perform_time,
                "cancel_time": 0,
                "transaction": str(payment.id),
                "state": state,
                "reason": None,
            })

        else:
            return _err(req_id, -32601, f"Метод не найден: {method}")
