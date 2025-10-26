from __future__ import annotations
import datetime as dt
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

def _escape_md(text: str) -> str:
    return (
        text.replace("_", "\_")
        .replace("*", "\*")
        .replace("[", "\[")
        .replace("]", "\]")
        .replace("(`", "(\`")
    )

def render_publication_card(p: Publication) -> str:
    title = p.title or "Без заголовка"
    snippet = p.snippet or ""
    lines = [
        f"*{_escape_md(title)}*",
        f"Площадка: `{p.platform}`  ·  Канал: [{_escape_md(p.channel_name)}]({_escape_md(p.channel_url)})",
        f"Дата: {p.post_date.strftime(_DT_FMT)}  ·  Просмотры: {_fmt_views(p.views)}",
        f"Совпадение с фразой: `{_escape_md(p.matched_seed)}`",
        f"Ссылка на пост: {p.post_url}",
    ]
    if snippet:
        lines.append("")
        lines.append(_escape_md(snippet[:400]))
    return "\n".join(lines)

def render_summary(res: SearchResults) -> str:
    per_pl = res.per_platform
    return (
        "*Итоги поиска*\n"
        f"Публикаций: {len(res.items)}\n"
        f"TG: {per_pl.get('telegram', 0)} · VK: {per_pl.get('vk', 0)}\n"
        f"Суммарные просмотры (по найденным постам): {_fmt_views(res.total_views)}"
    )
