from __future__ import annotations

from dataclasses import dataclass, field

from pra.models import Note, Page


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
        self.notes.append(Note(source_url=url, facts=facts.strip(),
                               evidence=evidence.strip()))