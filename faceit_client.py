import time
from typing import Any

import httpx
from config import FACEIT_API_KEY

BASE_URL = "https://open.faceit.com/data/v4"


class FaceitError(Exception):
    pass


class PlayerNotFoundError(FaceitError):
    pass


class _TTLCache:
    """Minimal time-based cache. Single-process, single-threaded (asyncio) friendly."""

    def __init__(self, ttl_seconds: float, max_size: int = 512):
        self._ttl = ttl_seconds
        self._max = max_size
        self._data: dict[str, tuple[float, Any]] = {}

    def get(self, key: str):
        item = self._data.get(key)
        if item is None:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            self._data.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any):
        if len(self._data) >= self._max:
            # Drop the oldest expired entry, or the first one if none expired.
            now = time.monotonic()
            for k, (exp, _) in list(self._data.items()):
                if exp < now:
                    self._data.pop(k, None)
            if len(self._data) >= self._max:
                self._data.pop(next(iter(self._data)))
        self._data[key] = (time.monotonic() + self._ttl, value)


class FaceitClient:
    """Async wrapper for Faceit Open API v4. Reuses one httpx.AsyncClient and caches hot reads."""

    def __init__(self):
        self._client: httpx.AsyncClient | None = None
        self._headers = {
            "Authorization": f"Bearer {FACEIT_API_KEY}",
            "Accept": "application/json",
        }
        self._player_cache = _TTLCache(ttl_seconds=300)        # 5 min
        self._stats_cache = _TTLCache(ttl_seconds=300)         # 5 min
        self._match_stats_cache = _TTLCache(ttl_seconds=3600)  # 1 hour — finished matches are immutable

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                headers=self._headers,
                timeout=10,
            )
        return self._client

    async def close(self):
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def get_player(self, nickname: str) -> dict:
        """Fetch player info by Faceit nickname."""
        key = nickname.lower()
        cached = self._player_cache.get(key)
        if cached is not None:
            return cached

        resp = await self.client.get(
            "/players",
            params={"nickname": nickname},
        )
        if resp.status_code == 404:
            raise PlayerNotFoundError(f"Игрок «{nickname}» не найден на Faceit")
        if resp.status_code == 429:
            raise FaceitError("Faceit API перегружен, попробуй через 30 секунд")
        resp.raise_for_status()
        data = resp.json()
        self._player_cache.set(key, data)
        return data

    async def get_stats(self, player_id: str) -> dict:
        """Fetch CS2 lifetime stats for a player."""
        cached = self._stats_cache.get(player_id)
        if cached is not None:
            return cached

        resp = await self.client.get(f"/players/{player_id}/stats/cs2")
        if resp.status_code == 404:
            raise FaceitError("У этого игрока нет статистики по CS2 на Faceit")
        if resp.status_code == 429:
            raise FaceitError("Faceit API перегружен, попробуй через 30 секунд")
        resp.raise_for_status()
        data = resp.json()
        self._stats_cache.set(player_id, data)
        return data

    async def get_history(self, player_id: str, limit: int = 10) -> dict:
        """Fetch recent match history for a player. Not cached — list changes after every game."""
        resp = await self.client.get(
            f"/players/{player_id}/history",
            params={"game": "cs2", "limit": limit},
        )
        if resp.status_code == 429:
            raise FaceitError("Faceit API перегружен, попробуй через 30 секунд")
        resp.raise_for_status()
        return resp.json()

    async def get_match_stats(self, match_id: str) -> dict:
        """Fetch detailed stats for a specific match. Cached — finished matches don't mutate."""
        cached = self._match_stats_cache.get(match_id)
        if cached is not None:
            return cached

        resp = await self.client.get(f"/matches/{match_id}/stats")
        if resp.status_code == 429:
            raise FaceitError("Faceit API перегружен, попробуй через 30 секунд")
        resp.raise_for_status()
        data = resp.json()
        self._match_stats_cache.set(match_id, data)
        return data


# Module-level singleton — one client for the whole bot.
faceit = FaceitClient()
