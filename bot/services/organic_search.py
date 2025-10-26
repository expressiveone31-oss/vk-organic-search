from __future__ import annotations
import datetime as dt
from dataclasses import dataclass
from typing import List, Optional, Iterable

@dataclass
class Publication:
    platform: str  # "telegram" | "vk"
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

async def search_organic(seeds: List[str], since: dt.date, until: dt.date) -> SearchResults:
    fetched: List[Publication] = []
    # TODO: integrate your real Telegram/VK search here
    filtered = _filter_by_time(fetched, since, until)
    uniq = _dedup(filtered)
    return SearchResults(items=sorted(uniq, key=lambda p: p.post_date, reverse=True))
