from __future__ import annotations

import logging
from pathlib import Path

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient
from pra.tools.fetch import fetch_page
from pra.tools.notes import NoteBook
from pra.tools.search import SearchError, SearchProvider, web_search

log = logging.getLogger("pra")

SYSTEM = (Path(__file__).parent / "prompts" / "researcher.md").read_text(encoding="utf-8")
MAX_PAGE_CHARS = 8_000   # text of one page shown to the model

TOOLS = [
    {"name": "web_search",
     "description": "Search the web. Returns titles, URLs and short snippets.",
     "input_schema": {"type": "object",
                      "properties": {"query": {"type": "string"}},
                      "required": ["query"]}},
    {"name": "fetch_page",
     "description": "Download a web page or PDF and return its readable text.",
     "input_schema": {"type": "object",
                      "properties": {"url": {"type": "string"}},
                      "required": ["url"]}},
    {"name": "save_note",
     "description": "Save one fact from a page you fetched. evidence must be a short exact quote under 25 words.",
     "input_schema": {"type": "object",
                      "properties": {"url": {"type": "string"},
                                     "facts": {"type": "string"},
                                     "evidence": {"type": "string"}},
                      "required": ["url", "facts", "evidence"]}},
    {"name": "finish_research",
     "description": "Call when you have enough evidence or cannot find more. Ends this sub-question.",
     "input_schema": {"type": "object",
                      "properties": {"status": {"type": "string"}},
                      "required": ["status"]}},
]


def _run_tool(name: str, args: dict, search: SearchProvider,
              notebook: NoteBook, max_sources: int) -> str:
    try:
        if name == "web_search":
            results = web_search(search, args["query"], 5)
            if not results:
                return "No results. Try a different query."
            return "\n".join(f"{i}. {r.title} | {r.url}\n   {r.snippet[:200]}"
                             for i, r in enumerate(results, 1))
        if name == "fetch_page":
            url = args["url"]
            page = notebook.sources.get(url)
            if page is None:
                if len(notebook.sources) >= max_sources:
                    return "ERROR: source limit reached. Save notes and call finish_research."
                page = fetch_page(url)
                if page.error:
                    return f"ERROR: could not read page ({page.error}). Try another result."
                notebook.add_source(page)
            return f'<page url="{page.url}" title="{page.title}">\n{page.text[:MAX_PAGE_CHARS]}\n</page>'
        if name == "save_note":
            notebook.save_note(args["url"], args["facts"], args["evidence"])
            return f"Saved. {len(notebook.notes)} notes so far."
        return f"ERROR: unknown tool {name}"
    except KeyError as e:
        return f"ERROR: missing argument {e}"
    except (SearchError, ValueError) as e:
        return f"ERROR: {e}"


def research(sub_question: str, llm: LLMClient, search: SearchProvider,
             notebook: NoteBook, budget: Budget, max_sources: int = 6) -> str:
    """Run the tool loop for one sub-question. Returns a one-line status."""
    messages = [{"role": "user", "content": f"Sub-question: {sub_question}"}]
    while True:
        try:
            resp = llm.complete(SYSTEM, messages, tools=TOOLS)
            budget.charge(resp.tokens)
        except BudgetExceeded as e:
            return f"stopped: {e}"

        messages.append({"role": "assistant", "content": resp.content})
        if not resp.tool_calls:
            return "ended without finish_research"

        results, status = [], None
        for call in resp.tool_calls:
            name, args = call["name"], call["input"]
            log.info("%s %s", name, args.get("query") or args.get("url") or args.get("status") or "")
            if name == "finish_research":
                status = args.get("status", "done")
                output = "ok"
            else:
                output = _run_tool(name, args, search, notebook, max_sources)
            results.append({"type": "tool_result", "tool_use_id": call["id"],
                            "content": output})
        messages.append({"role": "user", "content": results})

        if status is not None:
            return status

def text(t):
    return LLMResponse(content=[{"type": "text", "text": t}], text=t, tokens=10)


def test_full_run_produces_cited_report(monkeypatch):
    monkeypatch.setattr(research_mod, "fetch_page", fake_fetch)
    llm = FakeLLM([
        text('["What is RAG?"]'),
        call("1", "web_search", query="what is rag"),
        call("2", "fetch_page", url="https://a.com"),
        call("3", "save_note", url="https://a.com",
             facts="RAG retrieves documents first.",
             evidence="retrieves documents first"),
        call("4", "finish_research", status="enough"),
        text("# RAG\n\nRAG retrieves documents before answering [1]."),
    ])
    report = run("What is RAG?", llm, FakeSearch(), depth="quick")
    assert "[1]" in report
    assert "## Sources" in report
    assert "https://a.com" in report
    assert "Partial report" not in report


def test_no_notes_gives_no_evidence_message():
    llm = FakeLLM([text('["q1"]'), call("1", "finish_research", status="nothing found")])
    report = run("Obscure question", llm, FakeSearch(), depth="quick")
    assert "No usable evidence" in report


def test_plan_parsing():
    assert _parse("not json", "my question", 4) == ["my question"]
    assert _parse('Here: ["a", "b", "c"] done', "q", 2) == ["a", "b"]