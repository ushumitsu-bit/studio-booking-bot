from typing import Any, Callable, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from db.engine import AsyncSessionFactory
from db.queries import get_or_create_user


class AuthMiddleware(BaseMiddleware):
    """
    Автоматически регистрирует пользователя в БД при первом обращении.
    Добавляет `user` и `session` в data.
    """

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        tg_user = None
        if isinstance(event, Message):
            tg_user = event.from_user
        elif isinstance(event, CallbackQuery):
            tg_user = event.from_user

        async with AsyncSessionFactory() as session:
            if tg_user:
                user = await get_or_create_user(session, tg_user)
                data["db_user"] = user
                data["session"] = session
            return await handler(event, data)
