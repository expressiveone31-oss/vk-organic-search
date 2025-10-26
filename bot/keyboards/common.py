from __future__ import annotations
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def cancel_kb():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True, one_time_keyboard=True)
