import asyncio
import logging
import os
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
from bot.entrypoints.commands import setup_routers

logging.basicConfig(level=logging.INFO)

async def main():
    # Load .env for local and Railway environments
    load_dotenv()
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is not set")
    bot = Bot(token=token)
    dp = Dispatcher()
    dp.include_router(setup_routers())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
