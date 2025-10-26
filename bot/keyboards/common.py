from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def time_range_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1 день", callback_data="rng:1"),
                InlineKeyboardButton(text="3 дня", callback_data="rng:3"),
                InlineKeyboardButton(text="7 дней", callback_data="rng:7"),
            ],
            [
                InlineKeyboardButton(text="30 дней", callback_data="rng:30"),
                InlineKeyboardButton(text="Свои даты…", callback_data="rng:custom"),
            ],
        ]
    )

def cancel_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Отмена", callback_data="cancel")]]
    )
