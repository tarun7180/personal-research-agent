from pydantic import BaseModel


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str = ""


class Page(BaseModel):
    url: str
    title: str = ""
    text: str = ""
    content_type: str = "text/html"
    fetched_at: str = ""
    error: str | None = None


class Note(BaseModel):
    source_url: str
    facts: str
    evidence: str  # keep under 25 words
