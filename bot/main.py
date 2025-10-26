from aiogram import Bot, Dispatcher
import asyncio
from bot.entrypoints.commands import setup_routers
import os

async def main():
    bot = Bot(token=os.getenv('BOT_TOKEN'))
    dp = Dispatcher()
    dp.include_router(setup_routers())
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
