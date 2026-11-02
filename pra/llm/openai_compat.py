from __future__ import annotations

import json
import os
import time

import httpx

from pra.llm.base import LLMError, LLMResponse


def _convert(system: str, messages: list[dict]) -> list[dict]:
    """Turn the agent's internal (Anthropic-style) messages into OpenAI-style ones."""
    out = [{"role": "system", "content": system}]
    for m in messages:
        content = m["content"]
        if isinstance(content, str):
            out.append({"role": m["role"], "content": content})
        elif m["role"] == "assistant":
            text = "".join(b["text"] for b in content if b["type"] == "text")
            calls = [{"id": b["id"], "type": "function",
                      "function": {"name": b["name"], "arguments": json.dumps(b["input"])}}
                     for b in content if b["type"] == "tool_use"]
            msg = {"role": "assistant", "content": text or None}
            if calls:
                msg["tool_calls"] = calls
            out.append(msg)
        else:  # a user turn carrying tool results
            for b in content:
                if b["type"] == "tool_result":
                    out.append({"role": "tool", "tool_call_id": b["tool_use_id"],
                                "content": b["content"]})
    return out


class OpenAICompatClient:
    """Works with Gemini, Groq, OpenRouter, Ollama and other OpenAI-style APIs."""

    def __init__(self, base_url: str | None = None, api_key: str | None = None,
                 model: str | None = None, max_tokens: int = 4096,
                 client: httpx.Client | None = None, timeout: float | None = None):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL")
                         or "http://localhost:11434/v1").rstrip("/")
        self.api_key = api_key or os.getenv("LLM_API_KEY") or "none"
        self.model = model or os.getenv("LLM_MODEL", "")
        if not self.model:
            raise LLMError("LLM_MODEL is not set (see .env)")
        self.max_tokens = max_tokens
        self.retry_waits = (5, 15, 30)   # seconds to wait after a 429 or 5xx
        self._client = client or httpx.Client(timeout=timeout)

    def complete(self, system, messages, tools=None) -> LLMResponse:
        body = {"model": self.model, "max_tokens": self.max_tokens,
                "messages": _convert(system, messages)}
        if tools:
            body["tools"] = [{"type": "function",
                              "function": {"name": t["name"],
                                           "description": t["description"],
                                           "parameters": t["input_schema"]}}
                             for t in tools]

        resp = None
        for attempt in range(len(self.retry_waits) + 1):
            try:
                resp = self._client.post(
                    f"{self.base_url}/chat/completions", json=body,
                    headers={"Authorization": f"Bearer {self.api_key}"})
            except httpx.HTTPError as e:
                raise LLMError(f"model request failed: {type(e).__name__}") from e
            if resp.status_code in (429, 500, 502, 503) and attempt < len(self.retry_waits):
                time.sleep(self.retry_waits[attempt])
                continue
            break
        if resp.status_code != 200:
            raise LLMError(f"model request failed: HTTP {resp.status_code}")

        try:
            data = resp.json()
            msg = data["choices"][0]["message"]
        except (ValueError, KeyError, IndexError) as e:
            raise LLMError("unexpected response from the model API") from e

        content, calls = [], []
        text = msg.get("content") or ""
        if text:
            content.append({"type": "text", "text": text})
        for tc in msg.get("tool_calls") or []:
            try:
                args = json.loads(tc["function"].get("arguments") or "{}")
            except ValueError:
                args = {}
            call = {"id": tc.get("id") or f"call_{len(calls)}",
                    "name": tc["function"]["name"], "input": args}
            calls.append(call)
            content.append({"type": "tool_use", **call})

        usage = data.get("usage") or {}
        return LLMResponse(
            content=content, text=text, tool_calls=calls,
            tokens=usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0),
            stop_reason=data["choices"][0].get("finish_reason") or "",
        )