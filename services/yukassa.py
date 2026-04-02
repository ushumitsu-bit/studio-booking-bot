import uuid
import logging
import httpx
from config import settings

logger = logging.getLogger(__name__)

# Прокси на хосте — обходит блокировку TLS в контейнере
PROXY_URL = "http://172.18.0.1:9999"
YUKASSA_API = f"{PROXY_URL}/v3"

PRICES = {
    "single": settings.PRICE_SINGLE,
    "pack_4": settings.PRICE_4_CLASSES,
    "pack_8": settings.PRICE_8_CLASSES,
}

LABELS = {
    "single": "Разовое занятие пилатес",
    "pack_4": "Абонемент на 4 занятия",
    "pack_8": "Абонемент на 8 занятий",
}


async def create_yukassa_payment(amount_rub: int, description: str, internal_payment_id: int, user_id: int) -> dict:
    idempotence_key = str(uuid.uuid4())
    payload = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "confirmation": {"type": "redirect", "return_url": settings.YUKASSA_RETURN_URL},
        "capture": True,
        "description": description,
        "metadata": {"internal_payment_id": internal_payment_id, "telegram_user_id": user_id},
    }
    async with httpx.AsyncClient(timeout=15.0) as client:
        response = await client.post(
            f"{YUKASSA_API}/payments",
            json=payload,
            auth=(settings.YUKASSA_SHOP_ID, settings.YUKASSA_SECRET_KEY),
            headers={"Idempotence-Key": idempotence_key},
        )
        response.raise_for_status()
        data = response.json()

    logger.info(f"ЮKassa payment created: {data['id']} for user {user_id}")
    return {
        "yukassa_id": data["id"],
        "payment_url": data["confirmation"]["confirmation_url"],
    }


def parse_webhook(body: bytes, signature: str) -> dict | None:
    import hashlib, hmac, json
    expected = hmac.new(
        settings.YUKASSA_SECRET_KEY.encode(),
        body,
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, signature):
        logger.warning("Invalid ЮKassa webhook signature")
        return None
    return json.loads(body)
