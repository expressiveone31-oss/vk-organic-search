import os
import re
from datetime import datetime
from aiogram import Router, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from bot.services.vk_search import search_vk

router = Router()

DATE_RE = re.compile(r"^\s*(\d{4}-\d{2}-\d{2})\s*[—\-]\s*(\d{4}-\d{2}-\d{2})\s*$")

class OrganicFlow(StatesGroup):
    waiting_date_range = State()
    waiting_phrases = State()

@router.message(F.text.in_({"/start", "/organic"}))
async def organic_start(m: Message, state: FSMContext):
    await state.clear()
    await state.set_state(OrganicFlow.waiting_date_range)
    await m.answer(
        "Напиши диапазон дат для поиска.\nФорматы: YYYY-MM-DD — YYYY-MM-DD\nНапример: 2025-10-19 — 2025-10-26"
    )

@router.message(OrganicFlow.waiting_date_range, F.text)
async def receive_range(m: Message, state: FSMContext):
    mt = DATE_RE.match(m.text.strip())
    if not mt:
        return await m.answer("Не понял формат. Пример: 2025-10-19 — 2025-10-26")
    since_s, until_s = mt.group(1), mt.group(2)
    since = int(datetime.fromisoformat(since_s).timestamp())
    until = int(datetime.fromisoformat(until_s).timestamp()) + 86399
    await state.update_data(since=since, until=until, human=f"{since_s} — {until_s}")
    await state.set_state(OrganicFlow.waiting_phrases)
    await m.answer(f"Диапазон принят: {since_s} — {until_s}.\nТеперь пришли <b>подводки/поисковые фразы</b> — по одной на строку.\nКогда закончишь — просто отправь сообщение.")

@router.message(OrganicFlow.waiting_phrases, F.text)
async def receive_phrases(m: Message, state: FSMContext):
    data = await state.get_data()
    since = data["since"]
    until = data["until"]
    human_range = data["human"]

    lines = [s.strip() for s in m.text.split("\n")]
    seeds = [s for s in lines if s]
    if not seeds:
        return await m.answer("Нужна хотя бы одна строка с фразой.")

    await m.answer(f"Запускаю поиск… Это может занять до 1–2 минут.\nДиапазон: {human_range}\nФраз: {len(seeds)}")

    results, diag = await search_vk(seeds=seeds, since=since, until=until)

    total = len(results)
    total_views = sum(r["views"] for r in results)
    await m.answer(f"<b>Итоги поиска</b>\nПубликаций: {total}\nTG: 0 · VK: {total}\nСуммарные просмотры: {total_views}")

    for r in results[:30]:
        await m.answer(
            f"VK · <code>owner={r['owner_id']}</code>\n"
            f"{datetime.fromtimestamp(r['date']).strftime('%Y-%m-%d %H:%M')} | 👀 {r['views']}\n"
            f"{r['excerpt']}\n{r['url']}"
        )

    if os.getenv("ORGANIC_DEBUG") == "1":
        await m.answer(f"🛠 Диагностика: {diag}")

    await state.clear()
