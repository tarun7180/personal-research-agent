from typing import Protocol


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[dict],
                 tools: list[dict] | None = None) -> dict: ...
