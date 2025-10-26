from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from datetime import date, datetime
from bot.keyboards.common import cancel_kb
from bot.services.organic_search import search_organic
from bot.utils.formatting import format_publication, mdv2_escape

router = Router(name="organic")

# Simple in-chat mini workflow (/organic -> dates -> seeds)
@router.message(Command("organic"))
async def organic_start(m: Message):
    today = date.today()
    since = today.replace(day=max(1, today.day-7))
    until = today
    await m.answer(
        f"Диапазон: *{since}* — *{until}*\.
"
        f"Теперь пришли *подводки/поисковые фразы* — по одной на строку\.\n"
        f"Когда закончишь — просто отправь сообщение\.",
        reply_markup=cancel_kb()
    )
    # Set state-less: next user message = seeds
    m.bot['organic_range'] = (since, until)

@router.message(F.text & ~F.text.in_({"Отмена"}))
async def organic_collect(m: Message):
    ctx = m.bot.get('organic_range')
    if not ctx:
        return
    since, until = ctx
    seeds = [s.strip() for s in (m.text or "").splitlines() if s.strip()]
    await m.answer("Запускаю поиск… Это может занять до 1–2 минут при большом количестве источников.\n"
                   f"Диапазон: *{since}* — *{until}*\nФраз: *{len(seeds)}*")
    try:
        res = await search_organic(seeds, since, until)
    except Exception as e:
        await m.answer(f"⚠️ Ошибка: {mdv2_escape(str(e))}")
        return
    if not res.items:
        await m.answer("Ничего не нашёл по заданным параметрам\. Попробуй расширить диапазон или перефразировать запросы\.")
        return
    # brief summary
    tg = res.per_platform.get("telegram", 0); vk = res.per_platform.get("vk", 0)
    await m.answer(f"*Итоги поиска*
Публикаций: *{len(res.items)}*
TG: *{tg}* · VK: *{vk}*
Суммарные просмотры: *{res.total_views:,}*".replace(",", " "))
    # top 10
    for p in res.items[:10]:
        await m.answer(format_publication(p))
    # diagnostics
    if res.diagnostics:
        await m.answer("🛠 Диагностика:
" + mdv2_escape("; ".join(res.diagnostics)))
