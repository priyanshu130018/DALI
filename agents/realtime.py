"""Realtime information agent.

Provides asynchronous fetching of weather and news with caching and retries.
"""

import asyncio
import time
from typing import Optional, Dict, Any

import requests

from online.network_utils import has_internet


class TTLCache:
    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self.store: Dict[str, Any] = {}
        self.timestamps: Dict[str, float] = {}

    def get(self, key: str) -> Optional[Any]:
        ts = self.timestamps.get(key)
        if ts and (time.time() - ts) < self.ttl:
            return self.store.get(key)
        return None

    def set(self, key: str, value: Any) -> None:
        self.store[key] = value
        self.timestamps[key] = time.time()


class RealtimeAgent:
    def __init__(self):
        self.cache = TTLCache(ttl_seconds=120)

    async def get_weather(self, location: Optional[str] = None) -> str:
        if not has_internet():
            return "Internet connection is required for weather information."
        key = f"weather:{location or 'default'}"
        cached = self.cache.get(key)
        if cached:
            return cached
        async def _fetch() -> str:
            url = "https://wttr.in/"
            if location:
                url += location
            url += "?format=%t+%C"
            tries = 0
            while tries < 2:
                try:
                    r = await asyncio.to_thread(requests.get, url, timeout=5)
                    if r.status_code == 200:
                        return f"Current weather: {r.text.strip()}"
                except Exception:
                    await asyncio.sleep(0.5)
                tries += 1
            return "Unable to fetch weather right now."
        result = await _fetch()
        self.cache.set(key, result)
        return result

    async def get_news(self, country: str = "in", api_key: Optional[str] = None) -> str:
        if not has_internet():
            return "Internet connection is required for news updates."
        key = f"news:{country}"
        cached = self.cache.get(key)
        if cached:
            return cached
        async def _fetch() -> str:
            if not api_key:
                return "News API key not configured. Set NEWSAPI_KEY to enable headlines."
            url = "https://newsapi.org/v2/top-headlines"
            params = {"country": country, "pageSize": 3, "apiKey": api_key}
            tries = 0
            while tries < 2:
                try:
                    r = await asyncio.to_thread(requests.get, url, params=params, timeout=5)
                    if r.status_code == 200:
                        arts = (r.json().get("articles") or [])[:3]
                        if not arts:
                            return "No headlines available."
                        titles = ". ".join(a.get("title") for a in arts if a.get("title"))
                        return f"Top headlines: {titles}."
                except Exception:
                    await asyncio.sleep(0.5)
                tries += 1
            return "News service unavailable."
        result = await _fetch()
        self.cache.set(key, result)
        return result

    def get_weather_sync(self, location: Optional[str] = None) -> str:
        return asyncio.run(self.get_weather(location))

    def get_news_sync(self, country: str = "in", api_key: Optional[str] = None) -> str:
        return asyncio.run(self.get_news(country, api_key))