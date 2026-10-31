from __future__ import annotations

import os

import anthropic

from pra.llm.base import LLMResponse


class AnthropicClient:
    def __init__(self, model: str | None = None, max_tokens: int = 4096,
                 client: anthropic.Anthropic | None = None):
        self.model = model or os.getenv("PRA_MODEL", "claude-sonnet-5-5")
        self.max_tokens = max_tokens
        self._client = client or anthropic.Anthropic()   # reads ANTHROPIC_API_KEY

    def complete(self, system, messages, tools=None) -> LLMResponse:
        kwargs = dict(model=self.model, max_tokens=self.max_tokens,
                      system=system, messages=messages)
        if tools:
            kwargs["tools"] = tools
        resp = self._client.messages.create(**kwargs)

        content, calls, texts = [], [], []
        for b in resp.content:
            if b.type == "text":
                content.append({"type": "text", "text": b.text})
                texts.append(b.text)
            elif b.type == "tool_use":
                content.append({"type": "tool_use", "id": b.id,
                                "name": b.name, "input": b.input})
                calls.append({"id": b.id, "name": b.name, "input": b.input})
        return LLMResponse(
            content=content,
            text="\n".join(texts),
            tool_calls=calls,
            tokens=resp.usage.input_tokens + resp.usage.output_tokens,
            stop_reason=resp.stop_reason or "",
        )