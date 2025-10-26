
from __future__ import annotations
import os
import datetime as dt
from typing import Dict, Any, List, Optional
import httpx

VK_API = "https://api.vk.com/method"
VK_VERSION = os.getenv("VK_API_VERSION", "5.199")

class VKError(RuntimeError):
    pass

class VKClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.getenv("VK_TOKEN") or os.getenv("VK_ACCESS_TOKEN")
        if not self.token:
            raise VKError("VK token is not set (VK_TOKEN or VK_ACCESS_TOKEN)")

    async def _get(self, method: str, params: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{VK_API}/{method}", params={
                "access_token": self.token,
                "v": VK_VERSION,
                **params,
            })
            r.raise_for_status()
            data = r.json()
            if "error" in data:
                raise VKError(str(data["error"]))
            return data["response"]

    async def search(self, query: str, since: dt.date, until: dt.date, *, limit: int = 200, offset: int = 0) -> List[Dict[str, Any]]:
        # Use newsfeed.search for better coverage; extended=1 returns profiles/groups; count<=200
        start_time = int(dt.datetime.combine(since, dt.time.min).timestamp())
        end_time = int(dt.datetime.combine(until, dt.time.max).timestamp())
        resp = await self._get("newsfeed.search", {
            "q": query,
            "count": min(limit, 200),
            "offset": offset,
            "extended": 1,
            "start_time": start_time,
            "end_time": end_time,
            "fields": "screen_name,name",  # for resolve
        })
        # items is a mixed list of posts
        return resp.get("items", [])

    async def resolve_names(self, owner_ids: List[int]) -> Dict[int, str]:
        # Best-effort mapping via groups.getById and users.get if needed
        out: Dict[int, str] = {}
        group_ids = [-oid for oid in owner_ids if oid < 0]
        user_ids = [oid for oid in owner_ids if oid > 0]
        if group_ids:
            resp = await self._get("groups.getById", {"group_ids": ",".join(str(g) for g in group_ids)})
            for g in resp:
                try:
                    out[-int(g["id"])] = g.get("name") or g.get("screen_name") or f"group{-int(g['id'])}"
                except Exception:
                    pass
        if user_ids:
            resp2 = await self._get("users.get", {"user_ids": ",".join(str(u) for u in user_ids)})
            for u in resp2:
                try:
                    out[int(u["id"])] = f"{u.get('first_name','')} {u.get('last_name','')}".strip() or f"id{int(u['id'])}"
                except Exception:
                    pass
        return out
