from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from datetime import date
from bot.keyboards.common import cancel_kb
from bot.services.organic_search import search_organic
from bot.utils.formatting import format_publication  # mdv2_escape больше не нужен здесь

router = Router(name="organic")

# Simple in-chat mini workflow (/organic -> dates -> seeds)
@router.message(Command("organic"))
async def organic_start(m: Message):
    today = date.today()
    since = today.replace(day=max(1, today.day - 7))
    until = today
    # без Markdown и экранирований
    await m.answer(
        f"Диапазон: {since} — {until}.\n"
        f"Теперь пришли подводки/поисковые фразы — по одной на строку.\n"
        f"Когда закончишь — просто отправь сообщение.",
        reply_markup=cancel_kb(),
        parse_mode=None,
    )
    # хранить выбранный диапазон в контексте бота
    m.bot['organic_range'] = (since, until)

@router.message(F.text & ~F.text.in_({"Отмена"}))
async def organic_collect(m: Message):
    ctx = m.bot.get('organic_range')
    if not ctx:
        return
    since, until = ctx
    seeds = [s.strip() for s in (m.text or "").splitlines() if s.strip()]
    await m.answer(
        "Запускаю поиск... Это может занять до 1–2 минут при большом количестве источников.\n"
        f"Диапазон: {since} — {until}\n"
        f"Фраз: {len(seeds)}",
        parse_mode=None,
    )
    try:
        res = await search_organic(seeds, since, until)
    except Exception as e:
        await m.answer(f"Ошибка: {e}", parse_mode=None)
        return

    if not res.items:
        await m.answer(
            "Ничего не нашёл по заданным параметрам. Попробуй расширить диапазон или перефразировать запросы.",
            parse_mode=None,
        )
        return

    tg = res.per_platform.get("telegram", 0)
    vk = res.per_platform.get("vk", 0)
    await m.answer(
        f"Итоги поиска\nПубликаций: {len(res.items)}\nTG: {tg} · VK: {vk}\n"
        f"Суммарные просмотры: {res.total_views}",
        parse_mode=None,
    )

    for p in res.items[:10]:
        # карточки можно оставлять в MarkdownV2 — они уже экранируются в format_publication
        await m.answer(format_publication(p))

    if res.diagnostics:
        await m.answer("Диагностика: " + "; ".join(res.diagnostics), parse_mode=None)
