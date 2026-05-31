import hashlib
import hmac
import json
import os
import time
import urllib.parse

# Фейковые env ДО импорта проекта
os.environ.setdefault("BOT_TOKEN", "123456789:test_token_placeholder")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost/testdb")
os.environ.setdefault("PAYME_MERCHANT_ID", "test_merchant")
os.environ.setdefault("PAYME_SECRET_KEY", "test_secret_key")
os.environ.setdefault("WEBHOOK_HOST", "https://test.example.com")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("ATTENDANCE_SECRET", "test_attendance_secret")

import pytest_asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.pool import StaticPool
from httpx import AsyncClient, ASGITransport
from db.models import Base

TEST_DB = "sqlite+aiosqlite:///:memory:"
_BOT_TOKEN = os.environ["BOT_TOKEN"]


def make_init_data(user_id: int, first_name: str = "Test") -> str:
    """Generate a valid Telegram WebApp initData string for tests."""
    user = {"id": user_id, "first_name": first_name, "language_code": "ru"}
    params = {
        "user": json.dumps(user, separators=(",", ":")),
        "auth_date": str(int(time.time())),
    }
    check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items()))
    secret = hmac.new(b"WebAppData", _BOT_TOKEN.encode(), hashlib.sha256).digest()
    params["hash"] = hmac.new(secret, check_string.encode(), hashlib.sha256).hexdigest()
    return urllib.parse.urlencode(params)


@pytest_asyncio.fixture
async def engine():
    """Свежая in-memory БД для каждого теста."""
    eng = create_async_engine(
        TEST_DB,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine):
    """Сессия для прямого добавления тестовых данных."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session


@pytest_asyncio.fixture
async def api_client(engine, monkeypatch):
    """HTTP-клиент с пропатченной тестовой БД."""
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import miniapp_api
    import db.engine as db_eng
    monkeypatch.setattr(miniapp_api, "AsyncSessionFactory", factory)
    monkeypatch.setattr(db_eng,      "AsyncSessionFactory", factory)

    from webhook_app import create_fastapi_app
    app = create_fastapi_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
