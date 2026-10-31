from __future__ import annotations

from pathlib import Path

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient
from pra.tools.notes import NoteBook

SYSTEM = (Path(__file__).parent / "prompts" / "writer.md").read_text(encoding="utf-8")


def write_report(question: str, notebook: NoteBook, llm: LLMClient, budget: Budget) -> str:
    urls: list[str] = []
    for n in notebook.notes:
        if n.source_url not in urls:
            urls.append(n.source_url)
    index = {u: i for i, u in enumerate(urls, 1)}

    lines = [f'[{index[n.source_url]}] fact: {n.facts}\n    quote: "{n.evidence}"'
             for n in notebook.notes]
    user = f"Question: {question}\n\nNotes:\n" + "\n".join(lines)

    resp = llm.complete(SYSTEM, [{"role": "user", "content": user}])
    try:
        budget.charge(resp.tokens)
    except BudgetExceeded:
        pass  # the final write is always allowed, so a partial run still gets a report

    sources = []
    for u in urls:
        title = (notebook.sources[u].title or u).replace("[", "(").replace("]", ")")
        sources.append(f"{index[u]}. [{title}]({u})")
    return resp.text.strip() + "\n\n## Sources\n\n" + "\n".join(sources) + "\n"