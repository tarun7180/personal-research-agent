from __future__ import annotations

import os
from typing import Protocol

import httpx

from pra.models import SearchResult

TAVILY_URL = "https://api.tavily.com/search"


class SearchError(Exception):
    pass


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[SearchResult]: ...


class TavilySearch:
    def __init__(self, api_key: str | None = None,
                 client: httpx.Client | None = None, timeout: float = 20.0):
        self.api_key = api_key or os.getenv("SEARCH_API_KEY", "")
        if not self.api_key:
            raise SearchError("SEARCH_API_KEY is not set")
        self._client = client or httpx.Client(timeout=timeout)

    def search(self, query: str, max_results: int = 5) -> list[SearchResult]:
        try:
            resp = self._client.post(
                TAVILY_URL,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "api_key": self.api_key,  # older API style; harmless with the header
                    "query": query,
                    "max_results": max_results,
                    "search_depth": "basic",
                },
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as e:
            raise SearchError(f"search failed: HTTP {e.response.status_code}") from e
        except (httpx.HTTPError, ValueError) as e:
            raise SearchError(f"search failed: {type(e).__name__}") from e

        results = []
        for r in data.get("results", []):
            if r.get("url"):
                results.append(SearchResult(
                    title=r.get("title") or r["url"],
                    url=r["url"],
                    snippet=r.get("content") or "",
                ))
        return results[:max_results]


def web_search(provider: SearchProvider, query: str, max_results: int = 5) -> list[SearchResult]:
    return provider.search(query, max_results)