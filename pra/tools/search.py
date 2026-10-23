from typing import Protocol

from pra.models import SearchResult


class SearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[SearchResult]: ...


def web_search(provider: SearchProvider, query: str, max_results: int = 5) -> list[SearchResult]:
    # TODO: choose a provider and implement
    return provider.search(query, max_results)
