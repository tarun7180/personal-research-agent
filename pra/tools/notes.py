from __future__ import annotations

import re
from dataclasses import dataclass, field

from pra.models import Note, Page


def _norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


@dataclass
class NoteBook:
    sources: dict[str, Page] = field(default_factory=dict)
    notes: list[Note] = field(default_factory=list)

    def add_source(self, page: Page) -> None:
        self.sources[page.url] = page

    def save_note(self, url: str, facts: str, evidence: str) -> None:
        """Raises ValueError with a message the model can act on."""
        if url not in self.sources:
            raise ValueError("fetch the page before saving a note from it")
        if not facts.strip():
            raise ValueError("facts is empty")
        if len(evidence.split()) >= 25:
            raise ValueError("evidence must be a quote under 25 words")
        if not evidence.strip() or _norm(evidence) not in _norm(self.sources[url].text):
            raise ValueError("evidence must be copied word for word from the page text")
        self.notes.append(Note(source_url=url, facts=facts.strip(),
                               evidence=evidence.strip()))

    def source_urls(self) -> list[str]:
        """Source URLs in order of first note. Position + 1 is the citation number."""
        urls: list[str] = []
        for n in self.notes:
            if n.source_url not in urls:
                urls.append(n.source_url)
        return urls