
from __future__ import annotations
import os
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Iterable, Tuple
from bot.integrations.vk import VKClient
from bot.integrations.tgstat import TGStatClient, TGStatError
from bot.utils.similarity import seed_match_ratio, contains_phrase

STRICT = os.getenv("SEARCH_STRICT") == "1"

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
        out = {"telegram": 0, "vk": 0}
        for p in self.items:
            out[p.platform] = out.get(p.platform, 0) + 1
        return out

def _filter_by_time(posts: Iterable[Publication], since: dt.date, until: dt.date) -> List[Publication]:
    start_dt = dt.datetime.combine(since, dt.time.min)
    end_dt = dt.datetime.combine(until, dt.time.max)
    return [p for p in posts if start_dt <= p.post_date <= end_dt]

def _dedup(posts: Iterable[Publication]) -> List[Publication]:
    seen = set()
    uniq = []
    for p in posts:
        key = (p.platform, p.post_url)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(p)
    return uniq

async def _vk_search(seed: str, since: dt.date, until: dt.date) -> List[Publication]:
    vk = VKClient()
    items = await vk.search(seed, since, until, limit=200)
    owner_ids = list({it.get('owner_id') for it in items if isinstance(it, dict) and 'owner_id' in it})
    names = await vk.resolve_names([oid for oid in owner_ids if isinstance(oid, int)])
    pubs: List[Publication] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        text = it.get('text') or ''
        if STRICT and not contains_phrase(seed, text):
            continue
        date = dt.datetime.fromtimestamp(it.get('date', 0))
        views = (it.get('views') or {}).get('count')
        owner_id = it.get('owner_id')
        post_id = it.get('id')
        if owner_id is None or post_id is None:
            continue
        url = f"https://vk.com/wall{owner_id}_{post_id}"
        channel_name = names.get(owner_id, f"owner{owner_id}")
        pubs.append(Publication(
            platform="vk",
            channel_name=channel_name,
            channel_url=url,
            post_url=url,
            post_date=date,
            views=views,
            title=(text[:100] if text else None),
            snippet=(text[:400] if text else None),
            matched_seed=seed,
        ))
    return pubs

async def _tg_search(seed: str, since: dt.date, until: dt.date) -> Tuple[List[Publication], List[str]]:
    diags: List[str] = []
    try:
        tg = TGStatClient()
    except TGStatError as e:
        return [], [f"TG disabled: {e}"]
    items, meta = await tg.search(seed, since, until, limit=50, strict=STRICT)
    if meta:
        diags.append(f"TG meta: {meta}")
    pubs: List[Publication] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        ch = it.get('channel', {}) if isinstance(it, dict) else {}
        channel_name = ch.get('title') or ch.get('username') or 'Channel'
        channel_url = ch.get('link') or (f"https://t.me/{ch.get('username','')}" if ch.get('username') else 'https://t.me')
        post_url = it.get('link') or it.get('url') or channel_url
        ts = it.get('date') or it.get('views_date') or 0
        try:
            date = dt.datetime.fromtimestamp(int(ts))
        except Exception:
            date = dt.datetime.utcnow()
        views = it.get('views')
        title = it.get('title') or ''
        snippet = it.get('text') or ''
        body = f"{title} {snippet}"
        if STRICT and not contains_phrase(seed, body):
            continue
        if not STRICT:
            ratio = seed_match_ratio(seed, body)
            if ratio < 0.5:
                continue
        pubs.append(Publication(
            platform="telegram",
            channel_name=channel_name,
            channel_url=channel_url,
            post_url=post_url,
            post_date=date,
            views=views,
            title=(title or snippet[:100] if snippet else None),
            snippet=(snippet[:400] if snippet else None),
            matched_seed=seed,
        ))
    return pubs, diags

async def search_organic(seeds: List[str], since: dt.date, until: dt.date) -> SearchResults:
    fetched: List[Publication] = []
    diagnostics: List[str] = []
    for seed in seeds:
        try:
            fetched += await _vk_search(seed, since, until)
        except Exception as e:
            diagnostics.append(f"VK error: {e}")
        tg_items, diags = await _tg_search(seed, since, until)
        diagnostics.extend(diags)
        fetched += tg_items
    filtered = _filter_by_time(fetched, since, until)
    uniq = _dedup(filtered)
    return SearchResults(items=sorted(uniq, key=lambda p: p.post_date, reverse=True), diagnostics=diagnostics)
