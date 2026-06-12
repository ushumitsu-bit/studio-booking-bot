from typing import Any, Callable, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from db.engine import AsyncSessionFactory
from db.queries import get_or_create_user
import logging

logger = logging.getLogger(__name__)

class AuthMiddleware(BaseMiddleware):
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

        try:
            async with AsyncSessionFactory() as session:
                if tg_user:
                    user = await get_or_create_user(session, tg_user)
                    data["db_user"] = user
                    data["session"] = session
                    # Язык пользователя доступен хэндлерам через db_user.language
                return await handler(event, data)
        except Exception as e:
            logger.error(
                f"Middleware error for user {tg_user.id if tg_user else '?'}: {e}",
                exc_info=True,
            )
            if isinstance(event, Message):
                await event.answer(
                    "⚠️ Что-то пошло не так. Попробуй ещё раз или напиши /start"
                )
            elif isinstance(event, CallbackQuery):
                await event.answer(
                    "⚠️ Ошибка. Нажми /start чтобы перезапустить бота",
                    show_alert=True,
                )
