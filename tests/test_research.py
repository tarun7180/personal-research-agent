import pytest

import pra.research as research_mod
from pra.budget import Budget
from pra.llm.base import LLMResponse
from pra.models import Page, SearchResult
from pra.research import research
from pra.tools.notes import NoteBook


def call(id, name, **inp):
    return LLMResponse(
        content=[{"type": "tool_use", "id": id, "name": name, "input": inp}],
        tool_calls=[{"id": id, "name": name, "input": inp}],
        tokens=100,
    )


class FakeLLM:
    def __init__(self, script):
        self.script = list(script)

    def complete(self, system, messages, tools=None):
        return self.script.pop(0)


class FakeSearch:
    def search(self, query, max_results):
        return [SearchResult(title="RAG", url="https://a.com", snippet="s")]


def fake_fetch(url, **kwargs):
    return Page(url=url, title="RAG",
                text="Retrieval-augmented generation retrieves documents first.",
                content_type="text/html")


def test_research_saves_note_and_finishes(monkeypatch):
    monkeypatch.setattr(research_mod, "fetch_page", fake_fetch)
    llm = FakeLLM([
        call("1", "web_search", query="what is rag"),
        call("2", "fetch_page", url="https://a.com"),
        call("3", "save_note", url="https://a.com",
             facts="RAG retrieves documents before answering.",
             evidence="retrieves documents first"),
        call("4", "finish_research", status="enough evidence"),
    ])
    nb = NoteBook()
    status = research("What is RAG?", llm, FakeSearch(), nb, Budget())
    assert status == "enough evidence"
    assert len(nb.notes) == 1
    assert nb.notes[0].source_url == "https://a.com"


def test_note_rejected_if_page_not_fetched():
    llm = FakeLLM([
        call("1", "save_note", url="https://x.com", facts="f", evidence="e"),
        call("2", "finish_research", status="done"),
    ])
    nb = NoteBook()
    research("q", llm, FakeSearch(), nb, Budget())
    assert nb.notes == []


def test_stops_when_budget_exceeded():
    llm = FakeLLM([call("1", "web_search", query="a"),
                   call("2", "web_search", query="b")])
    status = research("q", llm, FakeSearch(), NoteBook(), Budget(max_steps=1))
    assert status.startswith("stopped")


def test_long_evidence_rejected():
    nb = NoteBook()
    nb.add_source(Page(url="https://a.com", text="x"))
    with pytest.raises(ValueError):
        nb.save_note("https://a.com", "fact", " ".join(["w"] * 26))