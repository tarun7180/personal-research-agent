from __future__ import annotations

import json
from pathlib import Path

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient

SYSTEM = (Path(__file__).parent / "prompts" / "planner.md").read_text(encoding="utf-8")


def _parse(text: str, question: str, n: int) -> list[str]:
    try:
        items = json.loads(text[text.index("["): text.rindex("]") + 1])
        subs = [s.strip() for s in items if isinstance(s, str) and s.strip()]
    except ValueError:
        subs = []
    return subs[:n] or [question]


def plan(question: str, llm: LLMClient, budget: Budget, n: int = 4) -> list[str]:
    user = f"Question: {question}\nNumber of sub-questions: {n}"
    resp = llm.complete(SYSTEM, [{"role": "user", "content": user}])
    try:
        budget.charge(resp.tokens)
    except BudgetExceeded:
        pass  # planning always completes
    return _parse(resp.text, question, n)