from __future__ import annotations
import os, re, html, datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple

from bot.integrations.vk import VKClient, VKError
from bot.integrations.telemetr import TelemetrClient, TelemetrError
from bot.integrations.tgstat import TGStatClient, TGStatError
from bot.utils.similarity import contains_phrase, match_score, find_match_window

# --------------------------- настройки из ENV ---------------------------

USE_TELEMETR = os.getenv("USE_TELEMETR", "1") == "1"
TELEMETR_STRICT = os.getenv("TELEMETR_STRICT", "1") == "1"
TELEMETR_PAGES = int(os.getenv("TELEMETR_PAGES", "5"))
TELEMETR_FUZZY_THRESHOLD = float(os.getenv("TELEMETR_FUZZY_THRESHOLD", "0.7"))

USE_TGSTAT = os.getenv("USE_TGSTAT", "0") == "1"

VK_MIN_VIEWS = int(os.getenv("VK_MIN_VIEWS", "500"))
VK_MAX_PAGES = int(os.getenv("VK_MAX_PAGES", "5"))
# поднял порог
VK_FUZZY_THRESHOLD = float(os.getenv("VK_FUZZY_THRESHOLD", "0.8"))
# строгий режим VK можно включить/выключить
VK_STRICT = os.getenv("VK_STRICT", "1") == "1"

# --------------------------- модели ---------------------------

@dataclass
class Publication:
    platform: str
    channel_name: str
    channel_url: str
    post_url: str
    post_date: dt.datetime
    views: Optional[int]
    title: Optional[str]
    snippet: Optional[str]
    matched_seed: str

@dataclass
class SearchResults:
    items: List[Publication]
    diagnostics: List[str]
    @property
    def total_views(self) -> int:
        return sum(p.views or 0 for p in self.items)
    @property
    def per_platform(self) -> dict:
        out = {"vk": 0, "telegram": 0}
        for p in self.items:
            out[p.platform] = out.get(p.platform, 0) + 1
        return out

# --------------------------- утилиты ---------------------------

def _filter_by_time(posts: Iterable[Publication], since: dt.date, until: dt.date) -> List[Publication]:
    start_dt = dt.datetime.combine(since, dt.time.min)
    end_dt = dt.datetime.combine(until, dt.time.max)
    return [p for p in posts if start_dt <= p.post_date <= end_dt]

def _dedup(posts: Iterable[Publication]) -> List[Publication]:
    seen = set(); out = []
    for p in posts:
        k = (p.platform, p.post_url)
        if k in seen: continue
        seen.add(k); out.append(p)
    return out

def _strip_html(s: Optional[str]) -> str:
    if not s: return ""
    s = html.unescape(s)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"\s+", " ", s, flags=re.U).strip()
    return s

def _words_count(seed: str) -> int:
    return len([w for w in re.split(r"[^\w]+", seed, flags=re.U) if w])

# --------------------------- VK ---------------------------

async def _vk_fetch_all(vk: VKClient, q: str, since: dt.date, until: dt.date) -> List[dict]:
    items: List[dict] = []
    for page in range(VK_MAX_PAGES):
        offset = page * 200
        batch = await vk.search(q, since, until, limit=200, offset=offset)
        if not batch: break
        items.extend(batch)
        if len(batch) < 200: break
    return items

async def _search_vk(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []; pubs: List[Publication] = []
    try:
        vk = VKClient()
    except Exception as e:
        return pubs, [f"VK disabled: {e}"]

    raw = await _vk_fetch_all(vk, seed, since, until)
    diags.append(f"VK fetch: {len(raw)} raw items for '{seed}'")

    owner_ids = list({it.get('owner_id') for it in raw if isinstance(it, dict) and 'owner_id' in it})
    names = {}
    try:
        names = await vk.resolve_names([oid for oid in owner_ids if isinstance(oid, int)])
    except Exception as e:
        diags.append(f"VK resolve_names error: {e}")

    seed_words = _words_count(seed)
    use_strict = VK_STRICT or seed_words >= 3

    for it in raw:
        if not isinstance(it, dict): continue
        text = (it.get('text') or '')[:10000]
        ok = False
        if use_strict:
            ok = contains_phrase(seed, text)
        else:
            ok = match_score(seed, text) >= VK_FUZZY_THRESHOLD
        if not ok:
            continue

        views = (it.get('views') or {}).get('count')
        if isinstance(views, int) and views < VK_MIN_VIEWS: 
            continue

        date = dt.datetime.fromtimestamp(it.get('date', 0) or 0)
        owner_id, post_id = it.get('owner_id'), it.get('id')
        if owner_id is None or post_id is None: 
            continue

        url = f"https://vk.com/wall{owner_id}_{post_id}"
        channel_name = names.get(owner_id, f"owner{owner_id}")
        snippet = find_match_window(seed, text)
        pubs.append(Publication("vk", channel_name, url, url, date, views, None, snippet, seed))

    diags.append(f"VK matched: {len(pubs)} (strict={use_strict}, thr={VK_FUZZY_THRESHOLD})")
    return pubs, diags

# --------------------------- Telemetr ---------------------------

def _telemetr_body(it: dict) -> str:
    parts = []
    for key in ("title", "text", "caption", "message", "description", "html_text", "text_html", "body"):
        v = it.get(key)
        if v:
            parts.append(_strip_html(str(v)))
    return " ".join(p for p in parts if p).strip()

async def _search_telemetr(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []; pubs: List[Publication] = []
    if not USE_TELEMETR:
        return pubs, ["Telemetr disabled by USE_TELEMETR=0"]
    try:
        tm = TelemetrClient()
    except TelemetrError as e:
        return pubs, [f"Telemetr disabled: {e}"]

    total = 0; matched = 0
    for page in range(TELEMETR_PAGES):
        offset = page * 100
        data = await tm.search_posts(seed, limit=100, offset=offset)
        status = data.get("status")
        if status != "ok":
            diags.append(f"Telemetr error: {data.get('error') or data}")
            break

        resp = data.get("response") or {}
        items = resp.get("items") or []
        total = max(total, int(resp.get("total_count") or 0))
        diags.append(f"Telemetr page {page+1}: got {len(items)}")
        if not items: break

        for it in items:
            ch = it.get("channel") or {}
            body = _telemetr_body(it)
            if not body:
                continue

            # строгий (гибкий) vs fuzzy
            if TELEMETR_STRICT:
                if not contains_phrase(seed, body):
                    continue
            else:
                if match_score(seed, body) < TELEMETR_FUZZY_THRESHOLD:
                    continue

            post_url = it.get("link") or it.get("url") or ""
            channel_name = ch.get("title") or ch.get("username") or "Channel"
            channel_url = ch.get("link") or (f"https://t.me/{ch.get('username','')}" if ch.get('username') else "https://t.me")
            date = TelemetrClient.parse_date(it.get("date"))
            if not (dt.datetime.combine(since, dt.time.min) <= date <= dt.datetime.combine(until, dt.time.max)):
                continue

            views = it.get("views") if isinstance(it.get("views"), int) else None
            snippet = find_match_window(seed, body) or (body[:300] + ("…" if len(body) > 300 else ""))
            title = (_strip_html(it.get("title")) or None)
            pubs.append(Publication("telegram", channel_name, channel_url, post_url or channel_url, date, views, title, snippet, seed))
            matched += 1

        if len(items) < 100:
            break

    diags.append(f"Telemetr total≈{total}, matched={matched}, strict={TELEMETR_STRICT}, thr={TELEMETR_FUZZY_THRESHOLD}")
    return pubs, diags

# --------------------------- TGStat (опция/запас) ---------------------------

async def _search_tgstat(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []; pubs: List[Publication] = []
    if not USE_TGSTAT:
        return pubs, []
    try:
        tg = TGStatClient()
    except TGStatError as e:
        return pubs, [f"TGStat disabled: {e}"]

    data = await tg.search(seed, limit=50)
    if data.get("status") != "ok":
        return pubs, [f"TGStat error: {data.get('error') or data}"]
    items = (data.get("response") or {}).get("items") or []
    diags.append(f"TGStat items: {len(items)}")

    for it in items:
        ch = it.get("channel") or {}
        body = _strip_html((it.get("title") or "") + " " + (it.get("text") or ""))
        if not contains_phrase(seed, body):
            continue

        post_url = it.get("link") or it.get("url") or ""
        channel_name = ch.get("title") or ch.get("username") or "Channel"
        channel_url = ch.get("link") or (f"https://t.me/{ch.get('username','')}" if ch.get('username') else "https://t.me")
        ts = it.get("date") or 0
        try: date = dt.datetime.fromtimestamp(int(ts))
        except Exception: date = dt.datetime.utcnow()
        if not (dt.datetime.combine(since, dt.time.min) <= date <= dt.datetime.combine(until, dt.time.max)):
            continue
        views = it.get("views") if isinstance(it.get("views"), int) else None
        snippet = find_match_window(seed, body) or (body[:300] + ("…" if len(body) > 300 else ""))
        title = (_strip_html(it.get("title")) or None)
        pubs.append(Publication("telegram", channel_name, channel_url, post_url or channel_url, date, views, title, snippet, seed))

    diags.append(f"TGStat matched: {len(pubs)}")
    return pubs, diags

# --------------------------- входная точка ---------------------------

async def search_organic(seeds: List[str], since: dt.date, until: dt.date) -> SearchResults:
    diagnostics: List[str] = []; all_items: List[Publication] = []
    for seed in seeds:
        vk_items, d = await _search_vk(seed, since, until); diagnostics += d; all_items += vk_items
        tm_items, d = await _search_telemetr(seed, since, until); diagnostics += d; all_items += tm_items
        tg_items, d = await _search_tgstat(seed, since, until); diagnostics += d; all_items += tg_items

    filtered = _filter_by_time(all_items, since, until)
    uniq = _dedup(filtered)
    # сначала TG, потом VK; внутри — по просмотрам убыв.
    uniq.sort(key=lambda p: (p.platform != "telegram", -(p.views or 0), p.post_date))
    return SearchResults(uniq, diagnostics)
