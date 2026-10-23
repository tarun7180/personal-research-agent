# Personal Research Agent (PRA)

A command-line AI agent that takes a research question, searches the web, reads sources,
and writes a Markdown report where every claim is cited.

> Status: early development (MVP in progress)

## How it works

Plan -> Research (search, read, note) -> Write -> Verify. See `docs/` for the full
requirements and architecture.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env    # add your API keys
pra "What is retrieval-augmented generation?"
```

## Project layout

```
pra/            application code
  cli.py        command-line entry point
  orchestrator.py  plan -> research -> write -> verify pipeline
  budget.py     step, token, and time limits
  llm/          LLMClient interface and implementations
  tools/        web_search, fetch_page, notes
  prompts/      planner, researcher, writer, verifier prompts
tests/          unit tests, fakes, fixtures, eval set
docs/           requirements and architecture
reports/        generated reports (git-ignored)
```

## Build order

1. Skeleton, config, logging, LLMClient wrapper
2. fetch_page (HTML + PDF)
3. web_search behind SearchProvider
4. Research loop + save_note + budget
5. Planner and writer prompts -> first cited report (MVP)
6. Verifier, source ranking, saved sessions
7. Evaluation set, follow-ups, simple web UI

## License

MIT
