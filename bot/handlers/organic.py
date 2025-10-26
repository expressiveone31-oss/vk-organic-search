from __future__ import annotations
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from datetime import date, datetime
import re
from typing import Optional, Tuple, Dict, Literal

from bot.keyboards.common import cancel_kb
from bot.services.organic_search import search_organic
from bot.utils.formatting import format_publication

router = Router(name="organic")

State = Literal["await_range", "await_seeds"]
CTX: Dict[int, Dict[str, object]] = {}

DATE_RE = re.compile(r"(\d{4}[-./]\d{2}[-./]\d{2})|(\d{2}[-./]\d{2}[-./]\d{4})")

def _parse_date(s: str) -> Optional[date]:
    s = s.strip().replace("/", "-").replace(".", "-")
    try:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", s):
            return datetime.strptime(s, "%Y-%m-%d").date()
    except Exception:
        pass
    try:
        if re.match(r"^\d{2}-\d{2}-\d{4}$", s):
            return datetime.strptime(s, "%d-%m-%Y").date()
    except Exception:
        pass
    return None

def _parse_range(text: str) -> Optional[Tuple[date, date]]:
    found = [m.group(0) for m in DATE_RE.finditer(text or "")]
    if len(found) < 2:
        parts = re.split(r"[—\-to]+", text or "")
        if len(parts) >= 2:
            d1 = _parse_date(parts[0]); d2 = _parse_date(parts[1])
            if d1 and d2:
                return (d1, d2)
        return None
    d1 = _parse_date(found[0]); d2 = _parse_date(found[1])
    if not d1 or not d2:
        return None
    if d1 > d2:
        d1, d2 = d2, d1
    return (d1, d2)

def _set_state(chat_id: int, state: State, *, rng: Optional[Tuple[date, date]] = None):
    CTX[chat_id] = {"state": state}
    if rng:
        CTX[chat_id]["range"] = rng

def _get_state(chat_id: int) -> Optional[State]:
    st = CTX.get(chat_id, {}).get("state")
    return st if isinstance(st, str) else None

def _get_range(chat_id: int) -> Optional[Tuple[date, date]]:
    rng = CTX.get(chat_id, {}).get("range")
    if isinstance(rng, tuple) and len(rng) == 2:
        return rng  # type: ignore
    return None

@router.message(Command("organic"))
async def organic_start(m: Message):
    today = date.today()
    default_since = today.replace(day=max(1, today.day - 7))
    _set_state(m.chat.id, "await_range")
    await m.answer(
        f"""Напиши диапазон дат для поиска.
Форматы: YYYY-MM-DD — YYYY-MM-DD или DD.MM.YYYY - DD.MM.YYYY
Например: {default_since} — {today}""",
        reply_markup=cancel_kb(),
        parse_mode=None,
    )

@router.message(F.text == "Отмена")
async def organic_cancel(m: Message):
    CTX.pop(m.chat.id, None)
    await m.answer("Окей, отменил.", parse_mode=None)

@router.message(F.text)
async def organic_flow(m: Message):
    text = (m.text or "").strip()
    st = _get_state(m.chat.id)

    if st == "await_range":
        rng = _parse_range(text)
        if not rng:
            await m.answer(
                "Не понял диапазон. Пришли две даты, например: 2025-10-19 — 2025-10-26",
                parse_mode=None,
            )
            return
        since, until = rng
        _set_state(m.chat.id, "await_seeds", rng=rng)
        await m.answer(
            f"""Диапазон принят: {since} — {until}.
Теперь пришли подводки/поисковые фразы — по одной на строку.
Когда закончишь — просто отправь сообщение.""",
            parse_mode=None,
        )
        return

    if st == "await_seeds":
        rng = _get_range(m.chat.id)
        if not rng:
            _set_state(m.chat.id, "await_range")
            await m.answer("Сначала пришли диапазон дат.", parse_mode=None)
            return

        seeds = [s.strip() for s in text.splitlines() if s.strip()]
        since, until = rng
        await m.answer(
            f"""Запускаю поиск... Это может занять до 1–2 минут при большом количестве источников.
Диапазон: {since} — {until}
Фраз: {len(seeds)}""",
            parse_mode=None,
        )
        try:
            res = await search_organic(seeds, since, until)
        except Exception as e:
            await m.answer(f"Ошибка: {e}", parse_mode=None)
            return
        finally:
            CTX.pop(m.chat.id, None)

        if not res.items:
            await m.answer(
                "Ничего не нашёл по заданным параметрам. Попробуй расширить диапазон или перефразировать запросы.",
                parse_mode=None,
            )
            if res.diagnostics:
                await m.answer("Диагностика: " + "; ".join(res.diagnostics), parse_mode=None)
            return

        tg = res.per_platform.get("telegram", 0)
        vk = res.per_platform.get("vk", 0)
        await m.answer(
            f"""Итоги поиска
Публикаций: {len(res.items)}
TG: {tg} · VK: {vk}
Суммарные просмотры: {res.total_views}""",
            parse_mode=None,
        )

        # Надёжная отправка карточек: пробуем MarkdownV2, при ошибке — plain text с URL
        for p in res.items[:10]:
            txt = format_publication(p)
            try:
                await m.answer(txt)  # глобальный parse_mode = MarkdownV2 из main.py
            except Exception:
                safe = f"{p.platform.upper()} · {p.channel_name}\n{p.post_date.strftime('%Y-%m-%d %H:%M')} | 👀 {p.views or '—'}\n{(p.snippet or '')[:400]}\n{p.post_url}"
                await m.answer(safe, parse_mode=None)

        if res.diagnostics:
            await m.answer("Диагностика: " + "; ".join(res.diagnostics), parse_mode=None)
        return

    await m.answer("Набери /organic, чтобы начать поиск.", parse_mode=None)
