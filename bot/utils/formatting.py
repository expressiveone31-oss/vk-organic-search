from __future__ import annotations
import datetime as dt
import html
from typing import Optional
from bot.services.organic_search import Publication, SearchResults

_DATE_FMT = "%Y-%m-%d"
_DT_FMT = "%Y-%m-%d %H:%M"

def parse_date(text: Optional[str]) -> Optional[dt.date]:
    if not text:
        return None
    try:
        return dt.datetime.strptime(text.strip(), _DATE_FMT).date()
    except Exception:
        return None

def humanize_range(since: dt.date, until: dt.date) -> str:
    return f"{since.strftime(_DATE_FMT)} — {until.strftime(_DATE_FMT)}"

def _fmt_views(v: Optional[int]) -> str:
    if v is None:
        return "—"
    if v >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v/1_000:.1f}K"
    return str(v)

def _a(href: str, text: str) -> str:
    # HTML link with escaped text and href
    safe_href = html.escape(href, quote=True)
    safe_text = html.escape(text, quote=False)
    return f'<a href="{safe_href}">{safe_text}</a>'

def render_publication_card(p: Publication) -> str:
    title = p.title or "Без заголовка"
    snippet = (p.snippet or "")[:250]
    parts = [
        f"<b>{html.escape(title)}</b>",
        f"Площадка: <code>{html.escape(p.platform)}</code> · Канал: {_a(p.channel_url, p.channel_name)}",
        f"Дата: {p.post_date.strftime(_DT_FMT)} · Просмотры: {_fmt_views(p.views)}",
        f"Совпадение с фразой: <code>{html.escape(p.matched_seed)}</code>",
        f"Ссылка на пост: {_a(p.post_url, p.post_url)}",
    ]
    if snippet:
        parts.append("")
        parts.append(html.escape(snippet))
    return "\n".join(parts)

def render_summary(res: SearchResults) -> str:
    per_pl = res.per_platform
    return (
        "<b>Итоги поиска</b>\n"
        f"Публикаций: {len(res.items)}\n"
        f"TG: {per_pl.get('telegram', 0)} · VK: {per_pl.get('vk', 0)}\n"
        f"Суммарные просмотры (по найденным постам): {_fmt_views(res.total_views)}"
    )
