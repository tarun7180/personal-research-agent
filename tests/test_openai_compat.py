import json

import httpx
import pytest

from pra.llm.base import LLMError
from pra.llm.openai_compat import OpenAICompatClient


def test_converts_messages_and_parses_tool_calls():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={
            "choices": [{"message": {"content": None, "tool_calls": [
                {"id": "c1", "type": "function",
                 "function": {"name": "web_search", "arguments": "{\"query\": \"rag\"}"}}]}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5}})

    client = OpenAICompatClient(
        base_url="http://x/v1", api_key="k", model="m",
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    messages = [
        {"role": "user", "content": "Sub-question: rag"},
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "a1", "name": "web_search", "input": {"query": "x"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "a1", "content": "results"}]},
    ]
    tools = [{"name": "web_search", "description": "d", "input_schema": {"type": "object"}}]
    resp = client.complete("sys", messages, tools=tools)

    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user", "assistant", "tool"]
    assert seen["body"]["tools"][0]["function"]["name"] == "web_search"
    assert resp.tool_calls == [{"id": "c1", "name": "web_search", "input": {"query": "rag"}}]
    assert resp.tokens == 15


def test_retries_after_429():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(429)
        return httpx.Response(200, json={"choices": [{"message": {"content": "hi"}}]})

    client = OpenAICompatClient(
        base_url="http://x/v1", model="m",
        client=httpx.Client(transport=httpx.MockTransport(handler)))
    client.retry_waits = (0, 0, 0)
    assert client.complete("s", [{"role": "user", "content": "q"}]).text == "hi"
    assert calls["n"] == 2


def test_missing_model_raises(monkeypatch):
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(LLMError):
        OpenAICompatClient()