from __future__ import annotations
import os, datetime as dt
from typing import Dict, Any, Optional
import httpx

DEFAULT_BASE = os.getenv("TELEMETR_BASE", "https://api.telemetr.me")

class TelemetrError(RuntimeError): pass

class TelemetrClient:
    def __init__(self, token: Optional[str] = None, base_url: Optional[str] = None):
        self.token = token or os.getenv("TELEMETR_TOKEN")
        if not self.token: raise TelemetrError("TELEMETR_TOKEN is not set")
        self.base = (base_url or DEFAULT_BASE).rstrip("/")
    def _headers(self) -> Dict[str, str]:
        return {"Authorization": f"Bearer {self.token}"}
    async def search_posts(self, query: str, *, limit: int = 100, offset: int = 0) -> Dict[str, Any]:
        params = {"query": query, "limit": max(1, min(int(limit or 100), 100))}
        if offset: params["offset"] = offset
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{self.base}/channels/posts/search", params=params, headers=self._headers())
            r.raise_for_status()
            return r.json()
    @staticmethod
    def parse_date(value: Any) -> dt.datetime:
        if value is None: return dt.datetime.utcnow()
        try: return dt.datetime.utcfromtimestamp(int(value))
        except Exception: pass
        if isinstance(value, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S%z","%Y-%m-%dT%H:%M:%S.%f%z","%Y-%m-%d %H:%M:%S","%Y-%m-%d"):
                try: return dt.datetime.strptime(value, fmt)
                except Exception: continue
        return dt.datetime.utcnow()
