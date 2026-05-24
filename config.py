from pydantic_settings import BaseSettings
from pydantic import PostgresDsn


class Settings(BaseSettings):
    # Telegram
    BOT_TOKEN: str
    ADMIN_IDS: list[int] = []          # Telegram ID администраторов

    # PostgreSQL
    DATABASE_URL: PostgresDsn

    # Redis (FSM storage)
    REDIS_URL: str = "redis://localhost:6379"

    # Payme Business
    PAYME_MERCHANT_ID: str             # Merchant ID из личного кабинета Payme
    PAYME_SECRET_KEY: str              # Секретный ключ (TEST или PROD)
    PAYME_RETURN_URL: str = ""         # URL после оплаты (можно t.me/your_bot)

    # Webhook для Payme (куда Payme шлёт JSON-RPC уведомления)
    WEBHOOK_HOST: str                  # https://yourdomain.com
    WEBHOOK_PATH: str = "/payme/webhook"

    # Цены (в сумах)
    PRICE_4_CLASSES: int = 500000
    PRICE_8_CLASSES: int = 800000
    PRICE_12_CLASSES: int = 1100000
    PRICE_16_CLASSES: int = 1400000

    # Посещаемость — секрет для подписи QR-токенов
    ATTENDANCE_SECRET: str = "change-me-attendance-secret"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
