from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from pra.budget import Budget, BudgetExceeded
from pra.llm.base import LLMClient
from pra.tools.notes import NoteBook

SYSTEM = (Path(__file__).parent / "prompts" / "verifier.md").read_text(encoding="utf-8")

CITE = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")
ONLY_CITES = re.compile(r"^(?:\s*\[\d+(?:\s*,\s*\d+)*\])+\s*[.!?]?$")
PREFIX = re.compile(r"^\s*(?:[-*+]|\d+\.)\s+")
VERDICTS = {"supported", "partial", "unsupported"}


@dataclass
class Claim:
    id: int
    text: str
    cites: list[int]
    verdict: str = "unchecked"
    reason: str = ""


def _cites(text: str) -> list[int]:
    return sorted({int(n) for m in CITE.findall(text) for n in re.findall(r"\d+", m)})


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text.strip()):
        if out and ONLY_CITES.match(part):
            out[-1] += " " + part      # a stray "[1]." belongs to the sentence before it
        else:
            out.append(part)
    return out


def parse(body: str):
    """Split the report into lines and sentences; cited sentences become Claims."""
    layout, claims = [], []
    for line in body.split("\n"):
        s = line.strip()
        if not s or s.startswith(("#", "|", ">", "```")):
            layout.append(("raw", line))          # headings, tables, quotes: left alone
            continue
        m = PREFIX.match(line)
        prefix = m.group(0) if m else ""
        parts = []
        for sent in _sentences(line[len(prefix):]):
            cites = _cites(sent)
            if cites:
                claim = Claim(len(claims) + 1, sent, cites)
                claims.append(claim)
                parts.append(claim)
            else:
                parts.append(sent)
        layout.append(("sents", prefix, parts))
    return layout, claims


def render(layout) -> str:
    out = []
    for item in layout:
        if item[0] == "raw":
            out.append(item[1])
            continue
        _, prefix, parts = item
        kept = []
        for p in parts:
            if isinstance(p, str):
                kept.append(p)
            elif p.verdict == "unsupported":
                continue
            elif p.verdict == "partial":
                kept.append(p.text + " †")
            else:
                kept.append(p.text)
        if kept:
            out.append(prefix + " ".join(kept))
    return "\n".join(out)


def count_uncited(layout) -> int:
    """Prose sentences (8+ words) with no citation: these are never checked."""
    total = 0
    for item in layout:
        if item[0] != "sents":
            continue
        for p in item[2]:
            if isinstance(p, str) and len(p.split()) >= 8:
                total += 1
    return total


def _judge(batch, notes_by_source, llm, budget) -> None:
    payload = [{
        "id": c.id,
        "claim": c.text,
        "notes": [{"source": n, "fact": note.facts, "quote": note.evidence}
                  for n in c.cites for note in notes_by_source.get(n, [])],
    } for c in batch]
    resp = llm.complete(SYSTEM, [{"role": "user",
                                  "content": json.dumps(payload, ensure_ascii=False)}])
    try:
        budget.charge(resp.tokens)
    except BudgetExceeded:
        pass
    try:
        items = json.loads(resp.text[resp.text.index("["): resp.text.rindex("]") + 1])
    except ValueError:
        return                                     # unreadable answer: claims stay unchecked
    verdicts = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        v = it.get("verdict")
        try:
            cid = int(it.get("id"))
        except (TypeError, ValueError):
            continue
        if isinstance(v, str) and v in VERDICTS:
            verdicts[cid] = (v, str(it.get("reason", "")))
    for c in batch:
        if c.id in verdicts:
            c.verdict, c.reason = verdicts[c.id]


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def quotes_found(notebook: NoteBook) -> tuple[int, int]:
    """How many saved quotes appear word for word in their source page."""
    ok = 0
    for n in notebook.notes:
        q = _norm(n.evidence)
        if q and q in _norm(notebook.sources[n.source_url].text):
            ok += 1
    return ok, len(notebook.notes)


def _summary(claims: list[Claim], quotes: tuple[int, int], uncited: int) -> str:
    def count(v: str) -> int:
        return sum(1 for c in claims if c.verdict == v)

    text = (f"Checked {len(claims)} cited claims against their notes: "
            f"{count('supported')} supported, {count('partial')} partly supported (†), "
            f"{count('unsupported')} removed")
    if count("unchecked"):
        text += f", {count('unchecked')} not checked"
    text += f". Quotes found word for word in the source pages: {quotes[0]} of {quotes[1]}."
    text += f" Sentences without a citation, which are not checked: {uncited}."
    lines = ["## Verification", "", text]
    removed = [c for c in claims if c.verdict == "unsupported"]
    if removed:
        lines += ["", "Removed as unsupported:"]
        lines += [f"- {CITE.sub('', c.text).strip()} ({c.reason})" for c in removed]
    return "\n".join(lines)


def verify_report(body: str, notebook: NoteBook, llm: LLMClient, budget: Budget,
                  chunk: int = 15) -> tuple[str, str]:
    """Return (checked report body, Verification section)."""
    layout, claims = parse(body)
    urls = notebook.source_urls()
    notes_by_source = {i: [n for n in notebook.notes if n.source_url == u]
                       for i, u in enumerate(urls, 1)}

    pending = []
    for c in claims:
        bad = [n for n in c.cites if n not in notes_by_source]
        if bad:
            c.verdict = "unsupported"
            c.reason = f"cites source {bad[0]}, which does not exist"
        else:
            pending.append(c)

    for i in range(0, len(pending), chunk):
        try:
            budget.check()
        except BudgetExceeded:
            break                                  # the rest stay "unchecked"
        _judge(pending[i:i + chunk], notes_by_source, llm, budget)

    return render(layout), _summary(claims, quotes_found(notebook), count_uncited(layout))