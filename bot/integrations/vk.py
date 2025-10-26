import os
import datetime as dt
from typing import List, Dict, Any, Iterable
import httpx

VK_API = "https://api.vk.com/method"
API_VERSION = "5.199"

class VKClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.getenv("VK_TOKEN")
        if not self.token:
            raise RuntimeError("VK_TOKEN is not set")

    async def search(self, query: str, start_date: dt.date, end_date: dt.date, limit: int = 200) -> List[Dict[str, Any]]:
        params = {
            "q": query,
            "count": min(limit, 200),
            "start_time": int(dt.datetime.combine(start_date, dt.time.min).timestamp()),
            "end_time": int(dt.datetime.combine(end_date, dt.time.max).timestamp()),
            "access_token": self.token,
            "v": API_VERSION,
        }
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{VK_API}/newsfeed.search", params=params)
            r.raise_for_status()
            data = r.json()
        if "error" in data:
            raise RuntimeError(f"VK API error: {data['error']}")
        return data.get("response", {}).get("items", [])

    async def resolve_names(self, owner_ids: List[int]) -> Dict[int, str]:
        if not owner_ids:
            return {}
        groups = [-oid for oid in owner_ids if oid < 0]
        users = [oid for oid in owner_ids if oid > 0]
        names: Dict[int, str] = {}
        async with httpx.AsyncClient(timeout=30) as client:
            if groups:
                params = {
                    "group_ids": ",".join(str(g) for g in groups),
                    "access_token": self.token,
                    "v": API_VERSION,
                }
                rg = await client.get(f"{VK_API}/groups.getById", params=params)
                rg.raise_for_status()
                gdata = rg.json()
                gres = gdata.get("response", [])
                # Normalize to iterable of dicts
                if isinstance(gres, dict):
                    gres = [gres]
                for item in gres:
                    if not isinstance(item, dict):
                        # Unexpected shape; skip defensively
                        continue
                    gid = int(item.get("id", 0))
                    if gid:
                        names[-gid] = item.get("name") or f"group{-gid}"
            if users:
                params = {
                    "user_ids": ",".join(str(u) for u in users),
                    "access_token": self.token,
                    "v": API_VERSION,
                }
                ru = await client.get(f"{VK_API}/users.get", params=params)
                ru.raise_for_status()
                udata = ru.json()
                ures = udata.get("response", [])
                if isinstance(ures, dict):
                    ures = [ures]
                for item in ures:
                    if not isinstance(item, dict):
                        continue
                    uid = int(item.get("id", 0))
                    if uid:
                        names[uid] = f"{item.get('first_name','').strip()} {item.get('last_name','').strip()}".strip() or f"id{uid}"
        return names
