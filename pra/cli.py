from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from pathlib import Path

import anthropic
import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown

from pra.llm.anthropic_client import AnthropicClient
from pra.llm.base import LLMClient, LLMError
from pra.llm.openai_compat import OpenAICompatClient
from pra.orchestrator import DEPTH, run
from pra.tools.search import SearchError, TavilySearch

app = typer.Typer(add_completion=False)


def make_llm() -> LLMClient:
    """Anthropic if its key is set; otherwise any OpenAI-compatible API from LLM_* settings."""
    if os.getenv("LLM_PROVIDER", "").lower() == "openai" or not os.getenv("ANTHROPIC_API_KEY"):
        return OpenAICompatClient()
    return AnthropicClient()


@app.command()
def main(
    question: str,
    depth: str = typer.Option("standard", help="quick, standard or deep"),
    out_dir: Path = typer.Option(Path("reports"), help="where reports are saved"),
) -> None:
    """Research QUESTION and save a cited Markdown report."""
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="  %(message)s")
    for noisy in ("httpx", "anthropic", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    if depth not in DEPTH:
        raise typer.BadParameter(f"depth must be one of: {', '.join(DEPTH)}")

    try:
        report = run(question, make_llm(), TavilySearch(), depth)
    except (SearchError, LLMError, anthropic.APIError) as e:
        typer.echo(f"Error: {e}")
        raise typer.Exit(1)

    out_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", question.lower()).strip("-")[:40]
    path = out_dir / f"{datetime.now():%Y%m%d-%H%M%S}-{slug}.md"
    path.write_text(report, encoding="utf-8")

    Console().print(Markdown(report))
    typer.echo(f"\nSaved: {path}")


if __name__ == "__main__":
    app()