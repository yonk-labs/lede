"""Comparison matrix for skimr v0.2 vs sumy.

Axes:
  - method  (skimr mode+attach, sumy backend, rust)
  - chars   (output length per corpus)
  - time    (p50 ms over N iterations, warm)
  - extras  (enrichment counts: stats / outline / metadata / phrases / correlated_facts)

Writes benchmarks/quality/matrix-{date}.md.

SC-B gate: every (method, corpus) cell must report p50 <= 250 ms warm.
SC-E gate: matrix doc produced with every row filled.

Run: ``python benchmarks/matrix_eval.py``. Exit 0 on SC-B pass, 1 on FAIL.
"""

from __future__ import annotations

import json
import statistics
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from skimr import SummaryResult, summarize  # noqa: E402
from sumy.nlp.tokenizers import Tokenizer  # noqa: E402
from sumy.parsers.plaintext import PlaintextParser  # noqa: E402
from sumy.summarizers.lex_rank import LexRankSummarizer  # noqa: E402
from sumy.summarizers.lsa import LsaSummarizer  # noqa: E402
from sumy.summarizers.text_rank import TextRankSummarizer  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_DIR = ROOT / "benchmarks" / "quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

ITERATIONS = 50
TARGET_CHARS = 500
TARGET_SENTENCES = 3
LATENCY_BUDGET_MS = 250.0


def _timed(fn: Callable[[str], object], text: str) -> tuple[float, object]:
    """Return (p50_ms, last_result). One unrecorded warmup call."""
    _ = fn(text)
    samples: list[float] = []
    last: object = None
    for _ in range(ITERATIONS):
        t0 = time.perf_counter_ns()
        last = fn(text)
        samples.append((time.perf_counter_ns() - t0) / 1e6)
    return statistics.median(samples), last


def _skimr_bare(mode: str) -> Callable[[str], SummaryResult]:
    def run(text: str) -> SummaryResult:
        return summarize(text, max_length=TARGET_CHARS, mode=mode)
    return run


def _skimr_rich(mode: str, attach: list[str]) -> Callable[[str], SummaryResult]:
    def run(text: str) -> SummaryResult:
        return summarize(text, max_length=TARGET_CHARS, mode=mode, attach=attach)
    return run


def _sumy(cls):
    def run(text: str) -> str:
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        return " ".join(str(s) for s in cls()(parser.document, TARGET_SENTENCES))
    return run


ALL_ENRICHMENTS = ["stats", "outline", "metadata", "phrases", "correlated_facts"]

METHODS: dict[str, Callable[[str], object]] = {
    "skimr/tfidf mode=legacy": _skimr_bare("legacy"),
    "skimr/tfidf mode=default": _skimr_bare("default"),
    "skimr/tfidf mode=default +stats": _skimr_rich("default", ["stats"]),
    "skimr/tfidf mode=default +outline": _skimr_rich("default", ["outline"]),
    "skimr/tfidf mode=default +all": _skimr_rich("default", ALL_ENRICHMENTS),
    "skimr/tfidf mode=coverage": _skimr_bare("coverage"),
    "skimr/tfidf mode=coverage +all": _skimr_rich("coverage", ALL_ENRICHMENTS),
    "sumy/LexRank": _sumy(LexRankSummarizer),
    "sumy/TextRank": _sumy(TextRankSummarizer),
    "sumy/LSA": _sumy(LsaSummarizer),
}


def _rust_tfidf_bench(text: str, mode: str) -> tuple[float, int]:
    """Call rust/target/release/bench_tfidf for a single corpus.

    Returns (p50_ms, out_chars). Returns (-1.0, 0) if the binary is missing.
    """
    bin_path = ROOT / "rust" / "target" / "release" / "bench_tfidf"
    if not bin_path.exists():
        return (-1.0, 0)
    proc = subprocess.run(
        [str(bin_path), str(ITERATIONS), mode],
        input=text,
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(proc.stdout.strip())
    return data["p50_ms"], data["out_chars"]


def _count_extras(result: object) -> dict[str, int]:
    if not isinstance(result, SummaryResult):
        return {k: 0 for k in ALL_ENRICHMENTS}
    md = result.metadata
    md_count = 0
    if md is not None:
        md_count = (
            len(md.dates or ())
            + len(md.amounts or ())
            + len(md.urls or ())
            + len(md.entities or ())
        )
    return {
        "stats": len(result.stats or ()),
        "outline": len(result.outline or ()),
        "metadata": md_count,
        "phrases": len(result.phrases or ()),
        "correlated_facts": len(result.correlated_facts or ()),
    }


def _summary_text(result: object) -> str:
    return result.summary if isinstance(result, SummaryResult) else str(result)


def _try_warmup_spacy() -> str:
    """Optional: pre-load spaCy NER so it doesn't pollute the first timed call.

    Returns a status string for the report header.
    """
    try:
        from skimr_spacy import warmup
    except ImportError:
        return "skimr-spacy not installed (regex-only metadata)"
    try:
        warmup()
    except Exception as exc:  # noqa: BLE001 — best-effort
        return f"skimr-spacy import OK but warmup failed: {exc!r}"
    return "skimr-spacy warmed (still regex-default unless caller opts in)"


def main() -> int:
    spacy_status = _try_warmup_spacy()
    date = time.strftime("%Y-%m-%d")
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    if not corpora:
        print(f"no corpora in {CORPUS_DIR}", file=sys.stderr)
        return 1

    rows: list[dict] = []
    for method, fn in METHODS.items():
        method_rows: list[dict] = []
        for p in corpora:
            text = p.read_text()
            p50, last = _timed(fn, text)
            extras = _count_extras(last)
            chars = len(_summary_text(last))
            method_rows.append({
                "corpus": p.stem, "p50_ms": p50, "chars": chars, "extras": extras,
            })
        rows.append({"method": method, "corpus_rows": method_rows})

    # Rust bench via release helper
    rust_rows: list[dict] = []
    for p in corpora:
        text = p.read_text()
        p50, chars = _rust_tfidf_bench(text, "default")
        rust_rows.append({
            "corpus": p.stem, "p50_ms": p50, "chars": chars,
            "extras": {k: 0 for k in ALL_ENRICHMENTS},
        })
    rows.append({"method": "rust-skimr/tfidf mode=default", "corpus_rows": rust_rows})

    # ---- Markdown report ----
    md: list[str] = []
    md.append(f"# Comparison matrix — skimr v0.2 vs sumy ({date})\n\n")
    md.append(
        f"**Iterations per cell:** {ITERATIONS} (one unrecorded warmup). "
        f"**Target chars:** {TARGET_CHARS}. **Sumy target sentences:** "
        f"{TARGET_SENTENCES}. **Budget gate:** p50 ≤ {LATENCY_BUDGET_MS:.0f} ms "
        f"on every (method, corpus) cell.\n\n"
    )
    md.append(f"_spaCy status: {spacy_status}._\n\n")

    md.append("## Aggregate by method (averaged across corpora)\n\n")
    md.append(
        "| method | avg chars | avg p50 ms | max p50 ms | avg stats | avg outline | "
        "avg metadata | avg phrases | avg correlated | budget? |\n"
    )
    md.append(
        "|---|---|---|---|---|---|---|---|---|---|\n"
    )
    for r in rows:
        cr = [x for x in r["corpus_rows"] if x["p50_ms"] >= 0]
        if not cr:
            md.append(f"| `{r['method']}` | — | — | — | — | — | — | — | — | n/a |\n")
            continue
        avg_chars = statistics.mean(x["chars"] for x in cr)
        avg_p50 = statistics.mean(x["p50_ms"] for x in cr)
        max_p50 = max(x["p50_ms"] for x in cr)
        avg_ex = {k: statistics.mean(x["extras"][k] for x in cr) for k in ALL_ENRICHMENTS}
        budget_ok = "pass" if max_p50 <= LATENCY_BUDGET_MS else "**FAIL**"
        md.append(
            f"| `{r['method']}` | {avg_chars:.0f} | {avg_p50:.2f} | {max_p50:.2f} | "
            f"{avg_ex['stats']:.1f} | {avg_ex['outline']:.1f} | "
            f"{avg_ex['metadata']:.1f} | {avg_ex['phrases']:.1f} | "
            f"{avg_ex['correlated_facts']:.1f} | {budget_ok} |\n"
        )

    md.append("\n## Per-corpus latency (ms p50)\n\n")
    methods_hdr = [r["method"] for r in rows]
    md.append("| corpus | " + " | ".join(f"`{m}`" for m in methods_hdr) + " |\n")
    md.append("|" + "|".join(["---"] * (1 + len(methods_hdr))) + "|\n")
    corpus_names = [p.stem for p in corpora]
    for cname in corpus_names:
        cells = [f"`{cname}`"]
        for r in rows:
            cell = next((x for x in r["corpus_rows"] if x["corpus"] == cname), None)
            if cell is None or cell["p50_ms"] < 0:
                cells.append("—")
            else:
                cells.append(f"{cell['p50_ms']:.2f}")
        md.append("| " + " | ".join(cells) + " |\n")

    md.append("\n## Per-corpus output length (chars)\n\n")
    md.append("| corpus | " + " | ".join(f"`{m}`" for m in methods_hdr) + " |\n")
    md.append("|" + "|".join(["---"] * (1 + len(methods_hdr))) + "|\n")
    for cname in corpus_names:
        cells = [f"`{cname}`"]
        for r in rows:
            cell = next((x for x in r["corpus_rows"] if x["corpus"] == cname), None)
            cells.append("—" if cell is None else f"{cell['chars']}")
        md.append("| " + " | ".join(cells) + " |\n")

    out_path = OUT_DIR / f"matrix-{date}.md"
    out_path.write_text("".join(md))
    print(f"Wrote {out_path}")

    # ---- SC-B gate ----
    over_budget = [
        (r["method"], c["corpus"], c["p50_ms"])
        for r in rows
        for c in r["corpus_rows"]
        if c["p50_ms"] >= 0 and c["p50_ms"] > LATENCY_BUDGET_MS
    ]
    if over_budget:
        print("SC-B FAIL on:")
        for m, cor, ms in over_budget:
            print(f"  {m} on {cor}: {ms:.2f} ms")
        return 1
    print("SC-B pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
