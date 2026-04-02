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

    # ЮKassa
    YUKASSA_SHOP_ID: str
    YUKASSA_SECRET_KEY: str
    YUKASSA_RETURN_URL: str            # URL после оплаты (можно t.me/your_bot)

    # Webhook для ЮKassa (куда Kassa шлёт уведомления об оплате)
    WEBHOOK_HOST: str                  # https://yourdomain.com
    WEBHOOK_PATH: str = "/yukassa/webhook"

    # Цены (в рублях)
    PRICE_SINGLE: int = 1200
    PRICE_4_CLASSES: int = 4200
    PRICE_8_CLASSES: int = 6400

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
