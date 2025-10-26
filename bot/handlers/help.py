from __future__ import annotations
from aiogram import Router
from aiogram.types import Message
from aiogram.filters import Command

router = Router(name="help")

@router.message(Command("help"))
async def _help(m: Message):
    await m.answer("Команда `/organic` — выбери период и отправь фразы по одной в строке\.")
