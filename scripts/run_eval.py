"""Run the evaluation questions through the agent and score the reports.

Examples:
  python scripts/run_eval.py --depth quick --limit 3 --pause 20
  python scripts/run_eval.py --limit 0 --sheet      (summary + manual check sheet, no runs)

Safe to stop and rerun: finished questions are skipped.
"""
import argparse
import csv
import json
import logging
import random
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from pra.cli import make_llm
from pra.orchestrator import run
from pra.tools.search import TavilySearch
from pra.verify import parse

ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = ROOT / "tests" / "eval" / "questions.json"
RESULTS = ROOT / "tests" / "eval" / "results.jsonl"
MANUAL = ROOT / "tests" / "eval" / "manual_check.csv"
REPORT_DIR = ROOT / "reports" / "eval"


def score(report: str) -> dict:
    """Read the numbers from the report's Verification section."""
    section = report.split("## Verification")[-1] if "## Verification" in report else ""

    def num(pattern: str) -> int:
        m = re.search(pattern, section)
        return int(m.group(1)) if m else 0

    return {
        "claims": num(r"Checked (\d+) cited claims"),
        "supported": num(r"(\d+) supported"),
        "partial": num(r"(\d+) partly supported"),
        "removed": num(r"(\d+) removed"),
        "unchecked": num(r"(\d+) not checked"),
        "quotes_ok": num(r"source pages: (\d+) of"),
        "quotes_total": num(r"source pages: \d+ of (\d+)"),
        "uncited": num(r"which are not checked: (\d+)"),
    }


def load_results() -> list[dict]:
    """Latest record per question id, so a rerun replaces an earlier failure."""
    if not RESULTS.exists():
        return []
    latest: dict[str, dict] = {}
    for line in RESULTS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            record = json.loads(line)
            latest[record["id"]] = record
    return list(latest.values())


def pct(a: int, b: int) -> str:
    return f"{100 * a / b:.0f}%" if b else "n/a"


def summarize() -> None:
    rows = load_results()
    if not rows:
        print("No results yet.")
        return
    ok = [r for r in rows if not r["error"]]

    def total(key: str) -> int:
        return sum(r["score"][key] for r in ok)

    claims = total("claims")
    print("\n=== Evaluation summary ===")
    print(f"Questions run: {len(rows)} ({len(rows) - len(ok)} failed with an error)")
    print(f"Partial reports (budget ran out): {sum(r['partial'] for r in ok)}")
    print(f"No usable evidence: {sum(r['no_evidence'] for r in ok)}")
    print(f"Cited claims checked: {claims}")
    print(f"  supported:        {total('supported')} ({pct(total('supported'), claims)})")
    print(f"  partly supported: {total('partial')} ({pct(total('partial'), claims)})")
    print(f"  removed:          {total('removed')} ({pct(total('removed'), claims)})")
    print(f"Quotes found word for word: {total('quotes_ok')} of {total('quotes_total')} "
          f"({pct(total('quotes_ok'), total('quotes_total'))})")
    if ok:
        print(f"Uncited sentences per report: {total('uncited') / len(ok):.1f}")
        print(f"Average time per question: {sum(r['seconds'] for r in ok) / len(ok):.0f} s")


def write_manual_sheet(per_question: int = 2, seed: int = 7) -> None:
    if MANUAL.exists():
        print(f"{MANUAL.name} already exists, so it was not overwritten. "
              "Delete it first if you want a fresh sample.")
        return
    rng = random.Random(seed)
    out = []
    for r in load_results():
        if r["error"] or not r["report_file"]:
            continue
        report = (ROOT / r["report_file"]).read_text(encoding="utf-8")
        body, _, rest = report.partition("## Sources")
        sources = dict(re.findall(r"^(\d+)\. \[.*?\]\((\S+?)\)\s*$", rest, flags=re.M))
        _, claims = parse(body)
        for c in rng.sample(claims, min(per_question, len(claims))):
            urls = " ; ".join(sources.get(str(n), "?") for n in c.cites)
            out.append([r["id"], re.sub(r"\s+", " ", c.text), urls, "", ""])
    with MANUAL.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow(["question_id", "claim", "source_urls", "supported_yes_no", "notes"])
        writer.writerows(out)
    print(f"Wrote {len(out)} claims to {MANUAL}. Open each source and fill in yes/no.")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--depth", default="quick")
    ap.add_argument("--limit", type=int, default=5, help="questions to run this time")
    ap.add_argument("--pause", type=float, default=15, help="seconds between questions")
    ap.add_argument("--sheet", action="store_true", help="create the manual check sheet")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="    %(message)s")
    for noisy in ("httpx", "anthropic", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    questions = json.loads(QUESTIONS.read_text(encoding="utf-8"))
    done = {r["id"] for r in load_results() if not r["error"]}
    todo = [q for q in questions if q["id"] not in done][: args.limit]
    print(f"{len(done)} done, {len(todo)} to run now.")

    if todo:
        llm, search = make_llm(), TavilySearch()
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        errors_in_a_row = 0
        for i, q in enumerate(todo):
            print(f"\n[{q['id']}] {q['question']}")
            start = time.time()
            report, error = "", None
            try:
                report = run(q["question"], llm, search, args.depth)
            except Exception as e:      # a batch runner should record failures, not die
                error = f"{type(e).__name__}: {e}"
                print(f"  ERROR: {error}")
            seconds = round(time.time() - start, 1)

            path = REPORT_DIR / f"{q['id']}.md"
            if report:
                path.write_text(report, encoding="utf-8")
            record = {
                "id": q["id"], "type": q["type"], "question": q["question"],
                "depth": args.depth, "seconds": seconds, "error": error,
                "partial": "**Partial report:**" in report,
                "no_evidence": "No usable evidence" in report,
                "score": score(report),
                "report_file": str(path.relative_to(ROOT)) if report else "",
            }
            with RESULTS.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            errors_in_a_row = errors_in_a_row + 1 if error else 0
            if errors_in_a_row >= 2:
                print("Two errors in a row, stopping. Check your connection or quota.")
                break
            if i < len(todo) - 1:
                time.sleep(args.pause)

    summarize()
    if args.sheet:
        write_manual_sheet()


if __name__ == "__main__":
    main()