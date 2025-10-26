from __future__ import annotations
import asyncio
import datetime as dt
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery
from bot.keyboards.common import time_range_kb, cancel_kb
from bot.services.organic_search import search_organic
from bot.utils.formatting import parse_date, humanize_range, render_publication_card, render_summary

router = Router(name=__name__)

class OrganicStates(StatesGroup):
    waiting_for_range = State()
    waiting_for_custom_from = State()
    waiting_for_custom_to = State()
    waiting_for_seeds = State()

@router.message(Command("organic"))
async def organic_entry(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OrganicStates.waiting_for_range)
    await message.answer(
        ("🔎 Поиск органики в ТГ и ВК.\n\n"
         "Сначала выбери временные рамки публикаций, которые нужно найти.\n"
         "Можно взять пресеты ниже или указать свой диапазон дат."),
        reply_markup=time_range_kb(),
    )

@router.callback_query(OrganicStates.waiting_for_range, F.data.startswith("rng:"))
async def pick_preset_range(cb: CallbackQuery, state: FSMContext):
    await cb.answer()
    _, val = cb.data.split(":", 1)
    if val == "custom":
        await state.set_state(OrganicStates.waiting_for_custom_from)
        await cb.message.edit_text(
            "Введи дату *с* в формате YYYY-MM-DD (например, 2025-09-01).",
            reply_markup=cancel_kb(),
            parse_mode="Markdown",
        )
        return
    days = int(val)
    until = dt.date.today()
    since = until - dt.timedelta(days=days)
    await state.update_data(since=str(since), until=str(until))
    await state.set_state(OrganicStates.waiting_for_seeds)
    await cb.message.edit_text(
        (f"Диапазон: {humanize_range(since, until)}.\n\n"
         "Теперь пришли *подводки/поисковые фразы* — по одной на строку.\n"
         "Когда закончишь — просто отправь сообщение."),
        reply_markup=cancel_kb(),
        parse_mode="Markdown",
    )

@router.message(OrganicStates.waiting_for_custom_from)
async def custom_from(message: Message, state: FSMContext):
    d = parse_date(message.text)
    if not d:
        await message.reply("Не распознал дату. Формат: YYYY-MM-DD. Попробуй ещё раз.")
        return
    await state.update_data(since=str(d))
    await state.set_state(OrganicStates.waiting_for_custom_to)
    await message.answer("Отлично. Теперь введи дату *по* (включительно) в формате YYYY-MM-DD.",
                         parse_mode="Markdown", reply_markup=cancel_kb())

@router.message(OrganicStates.waiting_for_custom_to)
async def custom_to(message: Message, state: FSMContext):
    d = parse_date(message.text)
    if not d:
        await message.reply("Не распознал дату. Формат: YYYY-MM-DD. Попробуй ещё раз.")
        return
    data = await state.get_data()
    since = parse_date(data.get("since"))
    if since and d < since:
        await message.reply("Дата окончания раньше даты начала. Введи корректную дату.")
        return
    await state.update_data(until=str(d))
    await state.set_state(OrganicStates.waiting_for_seeds)
    await message.answer(
        (f"Диапазон: {humanize_range(since, d)}.\n\n"
         "Теперь пришли *подводки/поисковые фразы* — по одной на строку.\n"
         "Когда закончишь — просто отправь сообщение."),
        parse_mode="Markdown", reply_markup=cancel_kb()
    )

@router.message(OrganicStates.waiting_for_seeds)
async def receive_seeds(message: Message, state: FSMContext):
    seeds = [s.strip() for s in (message.text or "").splitlines() if s.strip()]
    if not seeds:
        await message.reply("Не увидел фраз. Пришли хотя бы одну строку.")
        return
    data = await state.get_data()
    since = parse_date(data.get("since"))
    until = parse_date(data.get("until"))
    await message.answer(
        ("Запускаю поиск… Это может занять до 1–2 минут при большом количестве источников.\n"
         f"Диапазон: {humanize_range(since, until)}\n"
         f"Фраз: {len(seeds)}")
    )
    try:
        results = await search_organic(seeds=seeds, since=since, until=until)
    except Exception as e:
        await message.answer(f"⚠️ Ошибка при поиске: {type(e).__name__}: {e}")
        await state.clear()
        return
    if not results.items:
        await message.answer("Ничего не нашёл по заданным параметрам. Попробуй расширить диапазон или перефразировать запросы.")
        await state.clear()
        return
    summary_text = render_summary(results)
    await message.answer(summary_text, disable_web_page_preview=True)
    CHUNK = 8
    for i in range(0, len(results.items), CHUNK):
        chunk = results.items[i:i+CHUNK]
        text = "\n\n".join(render_publication_card(it) for it in chunk)
        await message.answer(text, disable_web_page_preview=False)
        await asyncio.sleep(0.2)
    await state.clear()
