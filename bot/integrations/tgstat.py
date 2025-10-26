
import os
import datetime as dt
from typing import List, Dict, Any, Tuple
import httpx

API = "https://api.tgstat.ru"

class TGStatError(RuntimeError):
    pass

class TGStatClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("TGSTAT_TOKEN")
        if not self.token:
            raise TGStatError("TGSTAT_TOKEN is not set")

    async def _call(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API}{path}", params=params)
            r.raise_for_status()
            return r.json()

    async def search(self, query: str, start_date: dt.date, end_date: dt.date, limit: int = 50, strict: bool = False) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        limit = min(int(limit or 50), 50)
        base = {
            "token": self.token,
            "start_date": int(dt.datetime.combine(start_date, dt.time.min).timestamp()),
            "end_date": int(dt.datetime.combine(end_date, dt.time.max).timestamp()),
            "limit": limit,
            "extended": 1,
        }
        if strict:
            q = f'"{query}"'
            data = await self._call("/posts/search", {**base, "q": q})
            if data.get("status") != "ok":
                return [], {"error": data.get("error") or data}
            return data.get("response", {}).get("items", []), {"note": "exact_only", "limit": limit}
        data = await self._call("/posts/search", {**base, "q": query})
        if data.get("status") != "ok":
            return [], {"error": data.get("error") or data}
        items = data.get("response", {}).get("items", [])
        if items:
            return items, {"note": "direct", "limit": limit}
        data2 = await self._call("/posts/search", {**base, "q": f'"{query}"'})
        if data2.get("status") == "ok" and data2.get("response", {}).get("items"):
            return data2["response"]["items"], {"note": "exact", "limit": limit}
        import re, unicodedata
        s = unicodedata.normalize("NFKC", query).lower()
        s = s.replace("—", " ").replace("–", " ").replace("‑", " ")
        tokens = re.findall(r"[\w\-]+", s)
        short = " ".join(tokens[:6])
        if short:
            data3 = await self._call("/posts/search", {**base, "q": short})
            if data3.get("status") == "ok" and data3.get("response", {}).get("items"):
                return data3["response"]["items"], {"note": "short", "q": short, "limit": limit}
        return [], {"note": "empty", "limit": limit}
