from __future__ import annotations

import logging

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient
from pra.planner import plan
from pra.research import research
from pra.tools.notes import NoteBook
from pra.tools.search import SearchProvider
from pra.writer import write_report

log = logging.getLogger("pra")

DEPTH = {
    "quick":    dict(subqs=3, max_sources=3, steps=20, tokens=200_000, seconds=300),
    "standard": dict(subqs=4, max_sources=5, steps=40, tokens=400_000, seconds=600),
    "deep":     dict(subqs=6, max_sources=6, steps=70, tokens=800_000, seconds=900),
}


def run(question: str, llm: LLMClient, search: SearchProvider,
        depth: str = "standard") -> str:
    cfg = DEPTH[depth]
    budget = Budget(max_steps=cfg["steps"], max_tokens=cfg["tokens"],
                    max_seconds=cfg["seconds"])
    notebook = NoteBook()

    subs = plan(question, llm, budget, cfg["subqs"])
    log.info("Plan: %s", subs)

    problems: list[str] = []
    for i, sub in enumerate(subs, 1):
        try:
            budget.check()
        except BudgetExceeded as e:
            problems.append(f"budget ran out before sub-question {i} ({e})")
            break
        log.info("Researching %d/%d: %s", i, len(subs), sub)
        status = research(
            f"{sub}\n(Overall question: {question})",
            llm, search, notebook, budget,
            max_sources=len(notebook.sources) + cfg["max_sources"],
        )
        if status.startswith(("stopped", "ended")):
            problems.append(f"sub-question {i} {status}")

    if not notebook.notes:
        return (f"# {question}\n\nNo usable evidence was found, so no report was "
                f"written.\n\nProblems: {'; '.join(problems) or 'none recorded'}\n")

    log.info("Writing report from %d notes", len(notebook.notes))
    report = write_report(question, notebook, llm, budget)
    if problems:
        report = "> **Partial report:** " + "; ".join(problems) + "\n\n" + report
    return report