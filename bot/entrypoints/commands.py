from __future__ import annotations
from aiogram import Router, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardRemove
from datetime import date, timedelta

from bot.handlers.help import router as help_router
from bot.handlers.organic import router as organic_router

root = Router(name="root")

@root.message(Command("start", "help"))
async def _start(m: Message):
    await m.answer("Привет\! Я помогу найти органику в VK и TG\.
Команда: `/organic`", reply_markup=ReplyKeyboardRemove())

def setup_routers(dp: Dispatcher):
    dp.include_router(root)
    dp.include_router(help_router)
    dp.include_router(organic_router)
