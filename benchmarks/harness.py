"""Benchmark harness for skimr vs Sumy. Designed to extend with Rust skimr.

Usage:
    python benchmarks/harness.py                      # run default corpus, 100 iterations
    python benchmarks/harness.py --iterations 200     # more repeats
    python benchmarks/harness.py --output path.md     # write results elsewhere

Scaffolds SC-006 infra. Rust skimr is left as explicit `—` rows in the
output table; fill in once Plan 2 lands.

DC-004 note: Sumy baselines are captured on this machine. Cross-machine
comparisons are invalid.
"""
from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

BENCH_ROOT = Path(__file__).resolve().parent
CORPUS_ROOT = BENCH_ROOT / "corpus"

TARGET_SENTENCES = 3
TARGET_CHARS = 500


# --- Summarizer adapters ---

def _skimr_tfidf(text: str) -> str:
    from skimr import summarize
    return summarize(text, max_length=TARGET_CHARS)


def _skimr_textrank(text: str) -> str:
    from skimr.textrank import summarize_textrank
    return summarize_textrank(text, num_sentences=TARGET_SENTENCES)


def _sumy_backend(cls_name: str) -> Callable[[str], str]:
    def run(text: str) -> str:
        from sumy.parsers.plaintext import PlaintextParser
        from sumy.nlp.tokenizers import Tokenizer
        from sumy.summarizers.lex_rank import LexRankSummarizer
        from sumy.summarizers.text_rank import TextRankSummarizer
        from sumy.summarizers.lsa import LsaSummarizer
        backends = {
            "LexRank": LexRankSummarizer,
            "TextRank": TextRankSummarizer,
            "LSA": LsaSummarizer,
        }
        parser = PlaintextParser.from_string(text, Tokenizer("english"))
        summarizer = backends[cls_name]()
        return " ".join(str(s) for s in summarizer(parser.document, TARGET_SENTENCES))
    return run


SUMMARIZERS: dict[str, Callable[[str], str]] = {
    "skimr/tfidf": _skimr_tfidf,
    "skimr/textrank": _skimr_textrank,
    "sumy/LexRank": _sumy_backend("LexRank"),
    "sumy/TextRank": _sumy_backend("TextRank"),
    "sumy/LSA": _sumy_backend("LSA"),
}

RUST_PLACEHOLDERS = ["rust-skimr/tfidf", "rust-skimr/textrank"]


# --- Measurement ---

@dataclass
class Measurement:
    summarizer: str
    corpus: str
    input_chars: int
    output_chars: int
    p50_ms: float
    p95_ms: float
    iterations: int


def _bench_one(fn: Callable[[str], str], text: str, iterations: int) -> tuple[float, float, int]:
    # Warmup: one unrecorded run to prime caches / lazy imports.
    out = fn(text)
    samples: list[float] = []
    for _ in range(iterations):
        t0 = time.perf_counter_ns()
        fn(text)
        samples.append((time.perf_counter_ns() - t0) / 1e6)
    samples.sort()
    p50 = statistics.median(samples)
    p95 = samples[int(0.95 * len(samples))]
    return p50, p95, len(out)


# --- Environment fingerprint ---

def _env_fingerprint() -> dict[str, str]:
    info = {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor() or "unknown",
    }
    try:
        cpu_model = subprocess.check_output(
            ["bash", "-c", "grep -m1 'model name' /proc/cpuinfo | cut -d: -f2 | xargs"],
            text=True,
        ).strip()
        if cpu_model:
            info["cpu_model"] = cpu_model
    except Exception:
        pass
    try:
        cores = subprocess.check_output(["nproc"], text=True).strip()
        info["cores"] = cores
    except Exception:
        pass
    # Versions of the compared libraries
    try:
        import skimr
        info["skimr_version"] = getattr(skimr, "__version__", "unknown")
    except Exception:
        pass
    try:
        import sumy
        info["sumy_version"] = getattr(sumy, "__version__", "unknown")
    except Exception:
        pass
    return info


# --- Report rendering ---

def _render_markdown(measurements: list[Measurement], env: dict[str, str], iterations: int) -> str:
    corpus_names = sorted({m.corpus for m in measurements})
    summ_names = list(SUMMARIZERS)

    lines: list[str] = []
    lines.append(f"# Benchmark Results — {time.strftime('%Y-%m-%d')}")
    lines.append("")
    lines.append(f"**Iterations per cell:** {iterations}")
    lines.append(f"**Target budget:** {TARGET_SENTENCES} sentences (Sumy / textrank) or {TARGET_CHARS} chars (skimr/tfidf)")
    lines.append("")
    lines.append("## System")
    lines.append("")
    for k, v in env.items():
        lines.append(f"- **{k}:** {v}")
    lines.append("")
    lines.append("## Corpus")
    lines.append("")
    lines.append("| Input | Chars |")
    lines.append("|---|---|")
    for corpus in corpus_names:
        chars = next(m.input_chars for m in measurements if m.corpus == corpus)
        lines.append(f"| `{corpus}` | {chars:,} |")
    lines.append("")
    lines.append("## Wall-clock latency (ms, median / P95)")
    lines.append("")

    header_cols = ["Input"] + summ_names + RUST_PLACEHOLDERS
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cols)) + "|")

    by_corpus = {m.corpus: {} for m in measurements}
    for m in measurements:
        by_corpus[m.corpus][m.summarizer] = m

    for corpus in corpus_names:
        row = [f"`{corpus}`"]
        for summ in summ_names:
            m = by_corpus[corpus].get(summ)
            if m is None:
                row.append("—")
            else:
                row.append(f"{m.p50_ms:.2f} / {m.p95_ms:.2f}")
        for _ in RUST_PLACEHOLDERS:
            row.append("—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    lines.append("## Output length (chars)")
    lines.append("")
    lines.append("Sanity-check that each summarizer produces non-trivial output for each input.")
    lines.append("")
    header_cols = ["Input"] + summ_names
    lines.append("| " + " | ".join(header_cols) + " |")
    lines.append("|" + "|".join(["---"] * len(header_cols)) + "|")
    for corpus in corpus_names:
        row = [f"`{corpus}`"]
        for summ in summ_names:
            m = by_corpus[corpus].get(summ)
            row.append(str(m.output_chars) if m else "—")
        lines.append("| " + " | ".join(row) + " |")
    lines.append("")

    # Key comparison: skimr vs fastest Sumy backend at the median
    lines.append("## Headline comparison")
    lines.append("")
    for corpus in corpus_names:
        s_tfidf = by_corpus[corpus].get("skimr/tfidf")
        sumy_fastest = min(
            (m for summ, m in by_corpus[corpus].items() if summ.startswith("sumy/")),
            key=lambda m: m.p50_ms,
            default=None,
        )
        if s_tfidf and sumy_fastest:
            ratio = sumy_fastest.p50_ms / s_tfidf.p50_ms
            lines.append(
                f"- **{corpus}:** skimr/tfidf is **{ratio:.0f}×** faster than "
                f"the fastest Sumy backend ({sumy_fastest.summarizer}) at the median."
            )
    lines.append("")

    lines.append("## Notes")
    lines.append("")
    lines.append("- Cross-machine numbers are invalid (DC-004). Re-run on the target machine.")
    lines.append("- Rust skimr columns are placeholders; fill in after Plan 2 lands.")
    lines.append("- Output length differences are expected — skimr/tfidf uses a char budget; others use a sentence count.")
    lines.append("- P95 over 100 iterations is coarse; bump `--iterations` for tighter tails.")
    return "\n".join(lines) + "\n"


# --- Main ---

def main() -> int:
    ap = argparse.ArgumentParser(description="skimr vs Sumy wall-clock benchmark")
    ap.add_argument("--iterations", type=int, default=100)
    ap.add_argument("--output", type=Path, default=None, help="Markdown output path (default: benchmarks/results/results-YYYY-MM-DD.md)")
    ap.add_argument("--json", type=Path, default=None, help="Also write raw measurements as JSON")
    args = ap.parse_args()

    inputs = sorted(CORPUS_ROOT.glob("*.txt"))
    if not inputs:
        raise SystemExit(f"no corpus files in {CORPUS_ROOT}")

    measurements: list[Measurement] = []
    print(f"Running {args.iterations} iterations × {len(inputs)} inputs × {len(SUMMARIZERS)} summarizers")
    for path in inputs:
        text = path.read_text()
        for summ, fn in SUMMARIZERS.items():
            p50, p95, out_chars = _bench_one(fn, text, args.iterations)
            measurements.append(Measurement(
                summarizer=summ,
                corpus=path.stem,
                input_chars=len(text),
                output_chars=out_chars,
                p50_ms=p50,
                p95_ms=p95,
                iterations=args.iterations,
            ))
            print(f"  {summ:22s} {path.stem:22s} p50={p50:7.2f} ms  p95={p95:7.2f} ms  out={out_chars} chars")

    env = _env_fingerprint()
    report = _render_markdown(measurements, env, args.iterations)

    out_path = args.output
    if out_path is None:
        out_path = BENCH_ROOT / "results" / f"results-{time.strftime('%Y-%m-%d')}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"\nReport written to {out_path}")

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(
            [m.__dict__ for m in measurements],
            indent=2,
        ))
        print(f"Raw measurements written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
