from __future__ import annotations
import os, datetime as dt
from typing import Dict, Any, Optional
import httpx

BASE = "https://api.tgstat.ru"

class TGStatError(RuntimeError): pass

class TGStatClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("TGSTAT_TOKEN")
        if not self.token: raise TGStatError("TGSTAT_TOKEN is not set")
    async def search(self, query: str, *, limit: int = 50) -> Dict[str, Any]:
        params = {"token": self.token, "q": query, "limit": min(limit, 50)}
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{BASE}/posts/search", params=params)
            r.raise_for_status()
            return r.json()
