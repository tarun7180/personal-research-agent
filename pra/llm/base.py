from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class LLMResponse:
    content: list[dict]                     # blocks to send back as the assistant turn
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)   # {"id", "name", "input"}
    tokens: int = 0
    stop_reason: str = ""


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[dict],
                 tools: list[dict] | None = None) -> LLMResponse: ...