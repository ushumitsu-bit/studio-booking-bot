"""
Запускает aiohttp-сервер рядом с ботом для приёма webhook-уведомлений ЮKassa.

Используется в production вместе с основным polling-ботом.
Рекомендуется запускать через supervisord или systemd.
"""

from aiohttp import web
from aiogram import Bot
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

from bot.handlers.payments import yukassa_webhook_handler
from config import settings


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post(settings.WEBHOOK_PATH, yukassa_webhook_handler)
    return app

def create_fastapi_app() -> FastAPI:
    from miniapp_api import router as miniapp_router
    app = FastAPI()
    app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
    app.include_router(miniapp_router)
    return app


async def run_webhook_server(bot: Bot):
    import threading
    # FastAPI для miniapp API
    fastapi_app = create_fastapi_app()
    def run_fastapi():
        uvicorn.run(fastapi_app, host="0.0.0.0", port=8080, log_level="warning")
    t = threading.Thread(target=run_fastapi, daemon=True)
    t.start()

    # aiohttp для yukassa webhook — на другом пути через nginx proxy
    app = create_webhook_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8081)
    await site.start()
    print(f"FastAPI miniapp API on port 8080")
    print(f"Webhook server on port 8081")
    return runner
