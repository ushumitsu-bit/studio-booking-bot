import asyncio
import logging

import uvicorn
from aiohttp import web
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from config import settings
from webhook_app import create_fastapi_app, create_webhook_app

logging.basicConfig(level=logging.INFO)


async def main():
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # aiohttp — Payme webhook on port 8081
    aio_app = create_webhook_app(bot)
    runner = web.AppRunner(aio_app)
    await runner.setup()
    await web.TCPSite(runner, host="0.0.0.0", port=8081).start()

    # uvicorn — FastAPI miniapp API on port 8080, same event loop
    fastapi_app = create_fastapi_app()
    config = uvicorn.Config(fastapi_app, host="0.0.0.0", port=8080,
                            log_level="warning", loop="none")
    server = uvicorn.Server(config)

    print("Payme webhook on port 8081")
    print("FastAPI miniapp API on port 8080")

    try:
        await server.serve()
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
