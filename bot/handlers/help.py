from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

router = Router(name=__name__)

HELP_TEXT = (
    "Доступные команды:\n"
    "• /organic — запустить поиск органики (сначала укажем даты, потом фразы)\n"
    "• /help — эта справка\n"
)

@router.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(HELP_TEXT)
