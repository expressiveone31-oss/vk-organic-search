from __future__ import annotations
import os, datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple

from bot.integrations.vk import VKClient, VKError
from bot.integrations.telemetr import TelemetrClient, TelemetrError
from bot.integrations.tgstat import TGStatClient, TGStatError
from bot.utils.similarity import contains_phrase, match_score, find_match_window

# Config
USE_TELEMETR = os.getenv("USE_TELEMETR", "1") == "1"
TELEMETR_STRICT = os.getenv("TELEMETR_STRICT", "1") == "1"
TELEMETR_PAGES = int(os.getenv("TELEMETR_PAGES", "5"))
TELEMETR_FUZZY_THRESHOLD = float(os.getenv("TELEMETR_FUZZY_THRESHOLD", "0.7"))

USE_TGSTAT = os.getenv("USE_TGSTAT", "0") == "1"

VK_MIN_VIEWS = int(os.getenv("VK_MIN_VIEWS", "500"))
VK_MAX_PAGES = int(os.getenv("VK_MAX_PAGES", "5"))
VK_FUZZY_THRESHOLD = float(os.getenv("VK_FUZZY_THRESHOLD", "0.62"))

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
    try: vk = VKClient()
    except Exception as e: return pubs, [f"VK disabled: {e}"]
    raw = await _vk_fetch_all(vk, seed, since, until)
    diags.append(f"VK raw items: {len(raw)} for '{seed}'")
    owner_ids = list({it.get('owner_id') for it in raw if isinstance(it, dict) and 'owner_id' in it})
    names = {}
    try: names = await vk.resolve_names([oid for oid in owner_ids if isinstance(oid, int)])
    except Exception as e: diags.append(f"VK resolve_names error: {e}")
    for it in raw:
        if not isinstance(it, dict): continue
        text = it.get('text') or ''
        score = match_score(seed, text)
        if score < VK_FUZZY_THRESHOLD: continue
        views = (it.get('views') or {}).get('count')
        if isinstance(views, int) and views < VK_MIN_VIEWS: continue
        date = dt.datetime.fromtimestamp(it.get('date', 0) or 0)
        owner_id, post_id = it.get('owner_id'), it.get('id')
        if owner_id is None or post_id is None: continue
        url = f"https://vk.com/wall{owner_id}_{post_id}"
        channel_name = names.get(owner_id, f"owner{owner_id}")
        snippet = find_match_window(seed, text)
        pubs.append(Publication("vk", channel_name, url, url, date, views, None, snippet, seed))
    return pubs, diags

async def _search_telemetr(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []; pubs: List[Publication] = []
    if not USE_TELEMETR: return pubs, diags
    try: tm = TelemetrClient()
    except TelemetrError as e: return pubs, [f"Telemetr disabled: {e}"]
    total = 0
    for page in range(TELEMETR_PAGES):
        offset = page * 100
        data = await tm.search_posts(seed, limit=100, offset=offset)
        if data.get("status") != "ok":
            diags.append(f"Telemetr error: {data.get('error') or data}"); break
        resp = data.get("response") or {}
        items = resp.get("items") or []
        total = max(total, int(resp.get("total_count") or 0))
        if not items: break
        for it in items:
            ch = it.get("channel") or {}
            title = it.get("title") or ""
            text = it.get("text") or ""
            body = f"{title} {text}".strip()
            if TELEMETR_STRICT:
                if not contains_phrase(seed, body): continue
            else:
                if match_score(seed, body) < TELEMETR_FUZZY_THRESHOLD: continue
            post_url = it.get("link") or it.get("url") or ""
            channel_name = ch.get("title") or ch.get("username") or "Channel"
            channel_url = ch.get("link") or (f"https://t.me/{ch.get('username','')}" if ch.get('username') else "https://t.me")
            date = TelemetrClient.parse_date(it.get("date"))
            if not (dt.datetime.combine(since, dt.time.min) <= date <= dt.datetime.combine(until, dt.time.max)): continue
            views = it.get("views") if isinstance(it.get("views"), int) else None
            snippet = (body[:300] + ("…" if len(body) > 300 else "")) or None
            pubs.append(Publication("telegram", channel_name, channel_url, post_url or channel_url, date, views, title[:120] or None, snippet, seed))
        if len(items) < 100: break
    diags.append(f"Telemetr total≈{total}")
    return pubs, diags

async def _search_tgstat(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []; pubs: List[Publication] = []
    if not USE_TGSTAT: return pubs, diags
    try: tg = TGStatClient()
    except TGStatError as e: return pubs, [f"TGStat disabled: {e}"]
    data = await tg.search(seed, limit=50)
    if data.get("status") != "ok":
        return pubs, [f"TGStat error: {data.get('error') or data}"]
    items = (data.get("response") or {}).get("items") or []
    for it in items:
        ch = it.get("channel") or {}
        title = it.get("title") or ""
        text = it.get("text") or ""
        body = f"{title} {text}".strip()
        if not contains_phrase(seed, body): continue
        post_url = it.get("link") or it.get("url") or ""
        channel_name = ch.get("title") or ch.get("username") or "Channel"
        channel_url = ch.get("link") or (f"https://t.me/{ch.get('username','')}" if ch.get('username') else "https://t.me")
        ts = it.get("date") or 0
        try: date = dt.datetime.fromtimestamp(int(ts))
        except Exception: date = dt.datetime.utcnow()
        if not (dt.datetime.combine(since, dt.time.min) <= date <= dt.datetime.combine(until, dt.time.max)): continue
        views = it.get("views") if isinstance(it.get("views"), int) else None
        snippet = (body[:300] + ("…" if len(body) > 300 else "")) or None
        pubs.append(Publication("telegram", channel_name, channel_url, post_url or channel_url, date, views, title[:120] or None, snippet, seed))
    return pubs, diags

async def search_organic(seeds: List[str], since: dt.date, until: dt.date) -> SearchResults:
    diagnostics: List[str] = []; all_items: List[Publication] = []
    for seed in seeds:
        vk_items, d = await _search_vk(seed, since, until); diagnostics += d; all_items += vk_items
        tm_items, d = await _search_telemetr(seed, since, until); diagnostics += d; all_items += tm_items
        tg_items, d = await _search_tgstat(seed, since, until); diagnostics += d; all_items += tg_items
    filtered = _filter_by_time(all_items, since, until)
    uniq = _dedup(filtered)
    uniq.sort(key=lambda p: (p.platform != "telegram", -(p.views or 0), p.post_date), reverse=False)
    return SearchResults(uniq, diagnostics)
