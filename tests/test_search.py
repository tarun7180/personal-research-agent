import httpx
import pytest

from pra.tools.search import SearchError, TavilySearch


def client_returning(status, payload):
    def handler(request):
        return httpx.Response(status, json=payload)

    return httpx.Client(transport=httpx.MockTransport(handler))


def test_parses_results_and_skips_entries_without_url():
    payload = {"results": [
        {"title": "RAG", "url": "https://a.com", "content": "a snippet", "score": 0.9},
        {"title": "No url", "content": "dropped"},
    ]}
    s = TavilySearch(api_key="k", client=client_returning(200, payload))
    out = s.search("rag", 5)
    assert len(out) == 1
    assert out[0].url == "https://a.com"
    assert out[0].snippet == "a snippet"


def test_http_error_raises_search_error():
    s = TavilySearch(api_key="k", client=client_returning(401, {}))
    with pytest.raises(SearchError, match="401"):
        s.search("x", 5)


def test_missing_key_raises(monkeypatch):
    monkeypatch.delenv("SEARCH_API_KEY", raising=False)
    with pytest.raises(SearchError):
        TavilySearch()