from __future__ import annotations

import io
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx
import trafilatura
from pypdf import PdfReader

from pra.models import Page

USER_AGENT = "PersonalResearchAgent/0.1"
MAX_BYTES = 5_000_000   # refuse pages bigger than this
MAX_CHARS = 20_000      # cap text sent on to the model


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _allowed_by_robots(url: str, client: httpx.Client) -> bool:
    parts = urlparse(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    try:
        resp = client.get(robots_url)
    except httpx.HTTPError:
        return True  # robots.txt unreachable: allow
    if resp.status_code != 200:
        return True
    parser = RobotFileParser()
    parser.parse(resp.text.splitlines())
    return parser.can_fetch(USER_AGENT, url)


def fetch_page(
    url: str,
    client: httpx.Client | None = None,
    timeout: float = 15.0,
    max_chars: int = MAX_CHARS,
) -> Page:
    """Fetch one URL and return readable text. Never raises: failures go in page.error."""
    page = Page(url=url, fetched_at=_now())

    parts = urlparse(url)
    if parts.scheme not in ("http", "https") or not parts.netloc:
        page.error = "unsupported or invalid URL"
        return page

    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )

    try:
        if not _allowed_by_robots(url, client):
            page.error = "blocked by robots.txt"
            return page

        resp = client.get(url)
        resp.raise_for_status()

        if len(resp.content) > MAX_BYTES:
            page.error = "page too large"
            return page

        ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
        page.content_type = ctype or "unknown"

        if "pdf" in ctype or url.lower().endswith(".pdf"):
            reader = PdfReader(io.BytesIO(resp.content))
            text = "\n".join((p.extract_text() or "") for p in reader.pages)
            page.title = (reader.metadata.title if reader.metadata else None) or ""
        elif "html" in ctype or "xml" in ctype:
            html = resp.text
            text = trafilatura.extract(html) or ""
            meta = trafilatura.extract_metadata(html)
            page.title = (meta.title if meta and meta.title else "")
        else:
            page.error = f"unsupported content type: {ctype or 'unknown'}"
            return page

        text = text.strip()
        if not text:
            page.error = "no readable text"
            return page
        page.text = text[:max_chars]

    except httpx.HTTPStatusError as e:
        page.error = f"HTTP {e.response.status_code}"
    except httpx.HTTPError as e:
        page.error = f"request failed: {type(e).__name__}"
    except Exception as e:  # bad PDF, odd encoding, etc.
        page.error = f"extract failed: {type(e).__name__}"
    finally:
        if owns_client:
            client.close()

    return page