"""
QR-токены для системы посещаемости.

Токен: "{class_id}:{window}:{hmac12}"
- window = unix_time // 3600  (окно 1 час, действует ±1 окно → до 2 часов)
- hmac12  = первые 12 символов HMAC-SHA256(secret, "{class_id}:{window}")

Токен stateless — не хранится в БД, проверяется по HMAC.
"""

import hmac
import hashlib
import time
from typing import Optional

from config import settings


def _sign(class_id: int, window: int) -> str:
    msg = f"{class_id}:{window}".encode()
    return hmac.new(settings.ATTENDANCE_SECRET.encode(), msg, hashlib.sha256).hexdigest()[:12]


def make_token(class_id: int) -> str:
    window = int(time.time()) // 3600
    return f"{class_id}:{window}:{_sign(class_id, window)}"


def verify_token(token: str) -> Optional[int]:
    """Возвращает class_id если токен валиден, иначе None."""
    parts = token.split(":")
    if len(parts) != 3:
        return None
    try:
        class_id, window, sig = int(parts[0]), int(parts[1]), parts[2]
    except ValueError:
        return None

    now_window = int(time.time()) // 3600
    # разрешаем текущее окно и предыдущее (до 2 часов назад)
    if now_window - window not in (0, 1):
        return None

    if not hmac.compare_digest(sig, _sign(class_id, window)):
        return None
    return class_id


def qr_url(class_id: int) -> str:
    """URL, который вшивается в QR-код и открывается в miniapp."""
    token = make_token(class_id)
    return f"https://pilates.fapass.xyz/miniapp/?attend={token}"
