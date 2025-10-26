import re

def mdv2_escape(text: str) -> str:
    if text is None:
        return ""
    # minimal safe escaping for MarkdownV2
    return re.sub(r'([_*\[\]()~`>#+\-=|{}.!\\])', r'\\\1', str(text))

def format_publication(p) -> str:
    head = f"*{mdv2_escape(p.channel_name)}* · {mdv2_escape(p.platform)}"
    views = f"{p.views:,}".replace(",", " ") if isinstance(p.views, int) else "—"
    snippet = mdv2_escape((p.snippet or "")[:400])
    url = mdv2_escape(p.post_url)
    dt = mdv2_escape(p.post_date.strftime("%Y-%m-%d %H:%M"))
    return f"{head}\n_{dt}_ | 👀 {views}\n{snippet}\n[Ссылка]({url})"
