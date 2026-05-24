import asyncio
import logging

from aiogram import Bot
from config import settings
from webhook_app import run_webhook_server

logging.basicConfig(level=logging.INFO)

async def main():
    bot = Bot(token=settings.BOT_TOKEN, parse_mode="HTML")
    runner = await run_webhook_server(bot)
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await runner.cleanup()
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
