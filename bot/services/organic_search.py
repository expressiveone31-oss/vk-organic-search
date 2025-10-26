
from __future__ import annotations
import os
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Iterable
from bot.integrations.vk import VKClient, VKError
from bot.utils.similarity import match_score, find_match_window, normalize_text

# --- Tunables via env ---
VK_MIN_VIEWS = int(os.getenv("VK_MIN_VIEWS", "500"))
VK_MAX_PAGES = int(os.getenv("VK_MAX_PAGES", "5"))            # 5 * 200 = 1000 max items
VK_FUZZY_THRESHOLD = float(os.getenv("VK_FUZZY_THRESHOLD", "0.62"))
VK_REQUIRE_TOKEN = os.getenv("VK_REQUIRE_TOKEN", "1") == "1"

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
        out = {"vk": 0}
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

async def _vk_fetch_all(vk: VKClient, seed: str, since: dt.date, until: dt.date) -> List[dict]:
    all_items: List[dict] = []
    for page in range(VK_MAX_PAGES):
        offset = page * 200
        batch = await vk.search(seed, since, until, limit=200, offset=offset)
        if not batch:
            break
        all_items.extend(batch)
        if len(batch) < 200:
            break
    return all_items

async def search_organic(seeds: List[str], since: dt.date, until: dt.date) -> SearchResults:
    diagnostics: List[str] = []
    fetched: List[Publication] = []
    try:
        vk = VKClient()
    except Exception as e:
        if VK_REQUIRE_TOKEN:
            return SearchResults([], [f"VK disabled: {e}"])
        vk = None

    for seed in seeds:
        if not vk:
            continue
        try:
            items = await _vk_fetch_all(vk, seed, since, until)
            diagnostics.append(f"VK fetch: {len(items)} raw items for '{seed}'")
        except VKError as e:
            diagnostics.append(f"VK error: {e}")
            continue

        # Resolve channel names
        owner_ids = list({it.get('owner_id') for it in items if isinstance(it, dict) and 'owner_id' in it})
        names = {}
        try:
            names = await vk.resolve_names([oid for oid in owner_ids if isinstance(oid, int)])
        except Exception as e:
            diagnostics.append(f"VK resolve_names error: {e}")

        for it in items:
            if not isinstance(it, dict):
                continue
            text = it.get('text') or ''
            # fuzzy score
            score = match_score(seed, text)
            if score < VK_FUZZY_THRESHOLD:
                continue
            views = None
            if isinstance(it.get('views'), dict):
                views = it['views'].get('count')
            if views is not None and views < VK_MIN_VIEWS:
                continue
            date = dt.datetime.fromtimestamp(it.get('date', 0) or 0)
            owner_id = it.get('owner_id')
            post_id = it.get('id')
            if owner_id is None or post_id is None:
                continue
            url = f"https://vk.com/wall{owner_id}_{post_id}"
            channel_name = names.get(owner_id, f"owner{owner_id}")
            snippet = find_match_window(seed, text)
            fetched.append(Publication(
                platform="vk",
                channel_name=channel_name,
                channel_url=url,
                post_url=url,
                post_date=date,
                views=views,
                title=None,
                snippet=snippet,
                matched_seed=seed,
            ))

    filtered = _filter_by_time(fetched, since, until)
    uniq = _dedup(filtered)
    uniq.sort(key=lambda p: (-(p.views or 0), p.post_date), reverse=False)
    return SearchResults(items=uniq, diagnostics=diagnostics)
