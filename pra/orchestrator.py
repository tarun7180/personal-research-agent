from __future__ import annotations

import logging

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient
from pra.planner import plan
from pra.research import research
from pra.tools.notes import NoteBook
from pra.tools.search import SearchProvider
from pra.verify import verify_report
from pra.writer import sources_section, write_report

log = logging.getLogger("pra")

DEPTH = {
    "quick":    dict(subqs=3, max_sources=3, sub_steps=8,  steps=30, tokens=400_000,   seconds=900),
    "standard": dict(subqs=4, max_sources=5, sub_steps=10, steps=48, tokens=800_000,   seconds=1200),
    "deep":     dict(subqs=6, max_sources=6, sub_steps=12, steps=80, tokens=1_500_000, seconds=1800),
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
    statuses: list[str] = []
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
            max_steps=cfg["sub_steps"],
        )
        statuses.append(f"- {sub} ({status})")
        if status.startswith(("stopped", "ended")):
            problems.append(f"sub-question {i} {status}")

    if not notebook.notes:
        tried = "\n".join(statuses) or "- none"
        return (f"# {question}\n\n"
                "No usable evidence was found, so no report was written. "
                "The question may rely on something that does not exist or is not documented online.\n\n"
                f"## What was tried\n\n{tried}\n\n"
                f"Problems: {'; '.join(problems) or 'none recorded'}\n")

    log.info("Writing report from %d notes", len(notebook.notes))
    body = write_report(question, notebook, llm, budget)
    log.info("Verifying claims")
    body, summary = verify_report(body, notebook, llm, budget)
    report = body.strip() + "\n\n" + sources_section(notebook) + "\n\n" + summary + "\n"
    if problems:
        report = "> **Partial report:** " + "; ".join(problems) + "\n\n" + report
    return report