import os
import datetime as dt
from typing import List, Dict, Any
import httpx

API = "https://api.tgstat.ru"

class TGStatClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TGSTAT_TOKEN")
        if not self.token:
            raise RuntimeError("TGSTAT_TOKEN is not set")

    async def search(self, query: str, start_date: dt.date, end_date: dt.date, limit: int = 100) -> List[Dict[str, Any]]:
        params = {
            "token": self.token,
            "q": query,
            "start_date": int(dt.datetime.combine(start_date, dt.time.min).timestamp()),
            "end_date": int(dt.datetime.combine(end_date, dt.time.max).timestamp()),
            "limit": min(limit, 100),
            "extended": 1,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}/posts/search", params=params)
            r.raise_for_status()
            data = r.json()
        if data.get("status") != "ok":
            raise RuntimeError(f"TGStat API error: {data}")
        return data.get("response", {}).get("items", [])
