# Personal Research Agent (PRA)

A command-line AI agent that takes a question, searches the web, reads the pages, saves notes with word-for-word quotes, writes a cited Markdown report, and then checks its own claims against its notes.

It runs entirely on free tiers (Google Gemini API + Tavily search). No paid key is needed.

```
pra "How does retrieval-augmented generation work?" --depth quick
```

## Why this project

Most "research agents" produce fluent text that cannot be checked. PRA is built around one rule: **every factual sentence must trace back to a quote that was actually found on a page the agent fetched.** The goal was not a clever agent, but one whose answers you can verify, and an honest measurement of how well it does that.

## How it works

```
question
   |
   v
 Plan ---> 3-6 sub-questions
   |
   v
 Research loop (per sub-question, with step cap)
   tools: web_search, fetch_page, save_note, finish_research
   save_note is rejected unless the quote (under 25 words) appears word for word in the fetched page
   |
   v
 Write ---> report with [n] citations; source list is built by code, not by the model
   |
   v
 Verify ---> each cited sentence judged against its notes:
             supported / partly (marked with a dagger) / unsupported (removed)
             plus: do the quotes exist in the source pages? how many sentences have no citation?
   |
   v
 reports/<timestamp>-<slug>.md
```

Design points:

- **Budgets:** steps, tokens and time are capped per depth level (`quick`, `standard`, `deep`). A sub-question that runs out of steps is reported, not hidden: the report gets a "Partial report" banner.
- **Swappable providers:** `LLMClient` and `SearchProvider` are small interfaces. There are two LLM clients (Anthropic, and any OpenAI-compatible endpoint such as Gemini).
- **Prompt-injection guard:** page text is passed to the model as untrusted data, never as instructions.
- **No evidence, no report:** if no note survives the quote check, the agent says so and lists what it tried, instead of writing something plausible.

## Setup (free)

Requires Python 3.10+.

```powershell
git clone <this repo>
cd personal-research-agent
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

Create a `.env` file (it is git-ignored; never commit it):

```
LLM_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai
LLM_API_KEY=<free key from Google AI Studio>
LLM_MODEL=gemini-flash-lite-latest
LLM_TIMEOUT=90
SEARCH_API_KEY=<free key from Tavily>
```

Run it:

```powershell
pra "What is the CAP theorem?" --depth quick
pytest
```

Free-tier note: Gemini's free quota is limited per day, and the service sometimes returns 503/429 errors. The client retries with back-off and stops with a clear message when the daily quota is used up.

## Sample report

reports/eval/q16.md

# How Does the Transformer Attention Mechanism Work?

The transformer attention mechanism computes interactions between tokens using scaled dot-product attention and can be scaled using multi-head processing [1, 2]. † Standard self-attention requires every token to attend to all other tokens, leading to quadratic complexity [3].

## Scaled Dot-Product Attention
The formula for scaled dot-product attention is $\text{Attention}(Q, K, V) = \text{softmax}(QK^T / \sqrt{d_k})V$ [1].

## Multi-Head Attention
In multi-head attention, the query, key, and value representations are split into multiple parts and processed in parallel across different attention heads [2].

## Complexity and Interactions
Standard transformer self-attention requires every token to attend to every other token [3]. This creates $n^2$ pairwise interactions for a sequence of $n$ tokens, resulting in quadratic complexity [3].

## Sources

1. [Why Do We Scale Attention by √dₖ? The Math Behind the Scaling Factor](https://outcomeschool.com/blog/scaling-dot-product-attention)
2. [Transformers Explained Visually (Part 3): Multi-head Attention, deep dive](https://medium.com/data-science/transformers-explained-visually-part-3-multi-head-attention-deep-dive-1c1ff1024853)
3. [Attention Complexity: Quadratic Scaling, Memory Limits](https://mbrenndoerfer.com/writing/attention-complexity-quadratic-scaling-memory-efficient-transformers)

## Verification

Checked 6 cited claims against their notes: 5 supported, 1 partly supported (†), 0 removed. Quotes found word for word in the source pages: 3 of 3. Sentences without a citation, which are not checked: 0.


## Evaluation

I wrote 20 questions (`tests/eval/questions.json`): 19 factual questions across computing, security, economics and health, and one trap question about a treaty that does not exist (plus two more traps, if you added q21 and q22). `scripts/run_eval.py` runs them and writes a sheet of randomly chosen claims. I then opened the cited source page for each claim and marked it by hand.

| Check | Result |
|---|---|
| Questions answered (quick depth) | _fill in: n of 19_ |
| Claims judged by the agent's own verifier | 96% supported (145 claims) |
| Quotes found word for word in source pages | 81 of 81 |
| Sentences without a citation (average per report) | 0.6 |
| Trap question (nonexistent treaty) | "No usable evidence", nothing invented |
| **Manual check, baseline run** | **29 of 33 supported (88%)** |
| **Manual check, after prompt changes** | **27 of 30 supported (90%)** |
| **Manual check, final run** | **31 of 38 supported (82%)** |

95% confidence ranges are wide (about 67% to 97%) because only 30 to 38 claims were checked per run. The three runs cannot be told apart statistically; the honest summary is "roughly 85% of sampled claims fully supported, none flatly wrong."

## What I learned

1. **The agent's self-check was too kind.** The built-in verifier said 96 to 98% supported. Checking by hand gave about 82 to 90%. The gap is almost entirely overstatement: "widely deployed" where the source says "most common use cases", "do not exist in monolithic architectures" where the source says "harder", "O(log N)" where the source never uses it. The verifier approved all of them.
2. **Exact quotes do not guarantee a correct claim.** A quote can be present word for word and the sentence built on it can still say more than it does. Checking quotes is a rule that catches fabrication, not a measure of accuracy.
3. **Rules beat prompts for some problems.** Tightening the writer prompt ("stay at the strength of the note") helped a little. Checking quotes, building the source list, and refusing to write without notes work because they are code, not requests.
4. **Free tiers shape the design.** Timeouts, 503s, daily quotas and Gemini's "thought signature" requirement all had to be handled. Retries, per-sub-question step caps and resumable evaluation runs came from real failures.
5. **Measure small and say so.** 30 hand-checked claims is enough to find the failure pattern, not enough to claim a precise accuracy.

## Known limits and next steps

- Overstatement is the main weakness. Planned: a rule-based check that flags intensifiers and absolutes ("widely", "always", "directly", "do not exist") that are missing from the cited note.
- The verifier uses the same model as the writer; a separate verifier model is an option.
- PDF fetching and prompt-injection resistance have light testing only.
- Quick runs take about 100 to 130 seconds when the free provider behaves, longer with retries.

## Project layout

```
pra/            cli, orchestrator, planner, research loop, writer, verify, budget, store
pra/llm/        LLM clients (Anthropic, OpenAI-compatible)
pra/tools/      fetch, search, notes
pra/prompts/    planner, researcher, writer, verifier prompts
tests/          unit tests, eval questions and results
scripts/        run_eval.py and small try-out scripts
```
