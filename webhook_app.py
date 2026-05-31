"""
Запускает серверы рядом с ботом:
  - FastAPI (port 8080) — miniapp API
  - aiohttp (port 8081) — Payme JSON-RPC webhook
"""

import logging

from aiohttp import web
from aiogram import Bot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from config import settings

logger = logging.getLogger(__name__)


async def payme_webhook_handler(request: web.Request) -> web.Response:
    """aiohttp endpoint для JSON-RPC уведомлений Payme."""
    from services.payme import handle_rpc
    authorization = request.headers.get("Authorization", "")
    try:
        body = await request.json()
    except Exception:
        return web.Response(status=400, text="Bad JSON")

    result = await handle_rpc(body, authorization)

    # Уведомляем пользователя при успешной оплате
    if result.get("result", {}).get("state") == 2:
        bot: Bot = request.app["bot"]
        payme_tx_id = body.get("params", {}).get("id")
        if payme_tx_id:
            from db.engine import AsyncSessionFactory
            from sqlalchemy import select
            from db.models import Payment, Subscription
            from sqlalchemy.orm import selectinload
            async with AsyncSessionFactory() as session:
                res = await session.execute(
                    select(Payment)
                    .options(selectinload(Payment.subscription))
                    .where(Payment.payme_id == payme_tx_id)
                )
                payment = res.scalar_one_or_none()
                if payment and payment.subscription:
                    sub = payment.subscription
                    try:
                        await bot.send_message(
                            payment.user_id,
                            f"🎉 <b>Оплата прошла успешно!</b>\n\n"
                            f"{payment.description} активирован.\n"
                            f"Осталось занятий: <b>{sub.classes_left}</b>\n"
                            f"Действует до: <b>{sub.expires_at.strftime('%d.%m.%Y')}</b>\n\n"
                            f"Записывайся на занятие через меню 👇",
                        )
                    except Exception as e:
                        logger.error(f"Failed to notify user {payment.user_id}: {e}")

    return web.json_response(result)


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post(settings.WEBHOOK_PATH, payme_webhook_handler)
    return app


def create_fastapi_app() -> FastAPI:
    from miniapp_api import router as miniapp_router
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.WEBHOOK_HOST],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type", "X-Telegram-Init-Data"],
    )
    app.include_router(miniapp_router)
    return app


async def run_webhook_server(bot: Bot):
    import threading
    fastapi_app = create_fastapi_app()
    def run_fastapi():
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8080, log_level="warning")
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()

    app = create_webhook_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8081)
    await site.start()
    print(f"FastAPI miniapp API on port 8080")
    print(f"Payme webhook server on port 8081 at {settings.WEBHOOK_PATH}")
    return runner
