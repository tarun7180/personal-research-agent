import pytest

import pra.research as research_mod
from pra.budget import Budget
from pra.llm.base import LLMResponse
from pra.models import Page, SearchResult
from pra.orchestrator import run
from pra.planner import _parse
from pra.research import research
from pra.tools.notes import NoteBook
from pra.verify import verify_report


def call(id, name, **inp):
    return LLMResponse(
        content=[{"type": "tool_use", "id": id, "name": name, "input": inp}],
        tool_calls=[{"id": id, "name": name, "input": inp}],
        tokens=100,
    )


def text(t):
    return LLMResponse(content=[{"type": "text", "text": t}], text=t, tokens=10)


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


# ---- research loop ----

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


def test_sub_question_step_cap():
    llm = FakeLLM([call("1", "web_search", query="a"),
                   call("2", "web_search", query="b"),
                   call("3", "web_search", query="c")])
    status = research("q", llm, FakeSearch(), NoteBook(), Budget(), max_steps=2)
    assert status == "reached its step cap"
    assert len(llm.script) == 1      # the third call was never made


# ---- full pipeline ----

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
        text('[{"id": 1, "verdict": "supported", "reason": "matches the note"}]'),
    ])
    report = run("What is RAG?", llm, FakeSearch(), depth="quick")
    assert "[1]" in report
    assert "## Sources" in report
    assert "https://a.com" in report
    assert "## Verification" in report
    assert "Partial report" not in report


def test_no_notes_gives_no_evidence_message():
    llm = FakeLLM([text('["q1"]'), call("1", "finish_research", status="nothing found")])
    report = run("Obscure question", llm, FakeSearch(), depth="quick")
    assert "No usable evidence" in report


def test_plan_parsing():
    assert _parse("not json", "my question", 4) == ["my question"]
    assert _parse('Here: ["a", "b", "c"] done', "q", 2) == ["a", "b"]


# ---- verifier ----

def test_verifier_removes_unsupported_and_marks_partial():
    nb = NoteBook()
    nb.add_source(Page(url="https://a.com", title="A", text="alpha beta"))
    nb.save_note("https://a.com", "alpha is first", "alpha beta")
    body = ("# T\n\nAlpha is first [1]. Beta cost 5 dollars [1]. Gamma is blue [1].\n\n"
            "- Delta is next [2].")
    llm = FakeLLM([text(
        '[{"id":1,"verdict":"supported","reason":"ok"},'
        '{"id":2,"verdict":"partial","reason":"number not in notes"},'
        '{"id":3,"verdict":"unsupported","reason":"not in notes"}]')])
    out, summary = verify_report(body, nb, llm, Budget())
    assert "Alpha is first [1]." in out
    assert "Beta cost 5 dollars [1]. †" in out
    assert "Gamma" not in out
    assert "Delta" not in out        # cites source 2, which does not exist
    assert "2 removed" in summary


def test_verifier_keeps_claims_when_judge_output_is_garbage():
    nb = NoteBook()
    nb.add_source(Page(url="https://a.com", title="A", text="alpha beta"))
    nb.save_note("https://a.com", "alpha is first", "alpha beta")
    out, summary = verify_report("Alpha is first [1].", nb, FakeLLM([text("sorry")]), Budget())
    assert "Alpha is first [1]." in out
    assert "1 not checked" in summary


def test_verifier_counts_uncited_sentences():
    nb = NoteBook()
    nb.add_source(Page(url="https://a.com", title="A", text="alpha beta"))
    nb.save_note("https://a.com", "alpha is first", "alpha beta")
    body = "RAG and fine tuning differ in several important ways today. Alpha is first [1]."
    llm = FakeLLM([text('[{"id":1,"verdict":"supported","reason":"ok"}]')])
    out, summary = verify_report(body, nb, llm, Budget())
    assert "without a citation, which are not checked: 1" in summary