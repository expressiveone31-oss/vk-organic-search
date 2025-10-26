from __future__ import annotations
from aiogram import Router, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove

from bot.handlers.help import router as help_router
from bot.handlers.organic import router as organic_router

root = Router(name="root")

@root.message(Command("start", "help"))
async def _start(m: Message):
    # Без Markdown, чтобы не ловить экранирование
    await m.answer(
        "Привет! Я помогу найти органику в VK и TG.\nКоманда: /organic",
        reply_markup=ReplyKeyboardRemove(),
        parse_mode=None,
    )

def setup_routers(dp: Dispatcher):
    dp.include_router(root)
    dp.include_router(help_router)
    dp.include_router(organic_router)
