"""
Запускает aiohttp-сервер рядом с ботом для приёма webhook-уведомлений ЮKassa.

Используется в production вместе с основным polling-ботом.
Рекомендуется запускать через supervisord или systemd.
"""

from aiohttp import web
from aiogram import Bot

from bot.handlers.payments import yukassa_webhook_handler
from config import settings


def create_webhook_app(bot: Bot) -> web.Application:
    app = web.Application()
    app["bot"] = bot
    app.router.add_post(settings.WEBHOOK_PATH, yukassa_webhook_handler)
    return app


async def run_webhook_server(bot: Bot):
    app = create_webhook_app(bot)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    print(f"Webhook server started on port 8080")
    print(f"ЮKassa endpoint: POST {settings.WEBHOOK_HOST}{settings.WEBHOOK_PATH}")
    return runner
