"""Quality evaluation harness — A1 (qualitative rubric) + A2 (ROUGE vs gold).

Loops every corpus in benchmarks/corpus/, runs each summarizer, computes
A2 token/bigram overlap against benchmarks/references/{name}.txt.

A1 scoring is done manually in the review doc after reading outputs.

Run:
    .venv/bin/python benchmarks/quality_eval.py

Writes:
    benchmarks/quality/outputs-YYYY-MM-DD.md  — all summarizer outputs, per corpus
    benchmarks/quality/rouge-YYYY-MM-DD.md    — A2 ROUGE table
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from skimr import summarize  # noqa: E402
from skimr.textrank import summarize_textrank  # noqa: E402
from sumy.parsers.plaintext import PlaintextParser  # noqa: E402
from sumy.nlp.tokenizers import Tokenizer  # noqa: E402
from sumy.summarizers.lex_rank import LexRankSummarizer  # noqa: E402
from sumy.summarizers.text_rank import TextRankSummarizer  # noqa: E402
from sumy.summarizers.lsa import LsaSummarizer  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
REF_DIR = ROOT / "benchmarks" / "references"
OUT_DIR = ROOT / "benchmarks" / "quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TARGET_SENTENCES = 3
TARGET_CHARS = 500

# Stopword list matched to the skimr tokenization intent — drop function words
# and common connective tokens so overlap measures content-level similarity.
STOP = set(
    "the a an and or but if then with by of to in on at for from as is are was "
    "were be been being has have had do does did will would could should may "
    "might can must this that these those it its they them their there here "
    "about up down into out over off just also not no our we you your he she "
    "his her him new one two three per over under less more most least".split()
)


def tokens(s: str) -> list[str]:
    return [t for t in re.findall(r"\b[a-z]{3,}\b", s.lower()) if t not in STOP]


def bigrams(toks: list[str]) -> list[tuple[str, str]]:
    return list(zip(toks, toks[1:]))


def rouge(cand: str, ref: str) -> dict:
    c_toks, r_toks = tokens(cand), tokens(ref)
    c_set, r_set = set(c_toks), set(r_toks)
    c_bi, r_bi = set(bigrams(c_toks)), set(bigrams(r_toks))
    p1 = len(c_set & r_set) / max(len(c_set), 1)
    r1 = len(c_set & r_set) / max(len(r_set), 1)
    p2 = len(c_bi & r_bi) / max(len(c_bi), 1)
    r2 = len(c_bi & r_bi) / max(len(r_bi), 1)
    f1 = 2 * p1 * r1 / (p1 + r1) if (p1 + r1) else 0.0
    f2 = 2 * p2 * r2 / (p2 + r2) if (p2 + r2) else 0.0
    return {
        "r1_p": p1, "r1_r": r1, "r1_f": f1,
        "r2_p": p2, "r2_r": r2, "r2_f": f2,
        "out_chars": len(cand),
    }


def run_sumy(cls, parser):
    return " ".join(str(s) for s in cls()(parser.document, TARGET_SENTENCES))


def main() -> int:
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    date = time.strftime("%Y-%m-%d")

    outputs_doc: list[str] = []
    outputs_doc.append(f"# Summarizer outputs — {date}\n")
    outputs_doc.append("Every corpus is run through every summarizer at shared budgets "
                       f"({TARGET_SENTENCES} sentences for Sumy/textrank, "
                       f"{TARGET_CHARS} chars for skimr/tfidf).\n\n")

    rouge_rows: list[dict] = []

    for path in corpora:
        name = path.stem
        text = path.read_text()
        ref_path = REF_DIR / f"{name}.txt"
        if not ref_path.exists():
            print(f"  MISSING reference: {name}; skip", file=sys.stderr)
            continue
        reference = ref_path.read_text().strip()
        parser = PlaintextParser.from_string(text, Tokenizer("english"))

        outs = {
            "skimr/tfidf":    summarize(text, max_length=TARGET_CHARS),
            "skimr/textrank": summarize_textrank(text, num_sentences=TARGET_SENTENCES),
            "sumy/LexRank":   run_sumy(LexRankSummarizer, parser),
            "sumy/TextRank":  run_sumy(TextRankSummarizer, parser),
            "sumy/LSA":       run_sumy(LsaSummarizer, parser),
        }

        outputs_doc.append(f"## `{name}` ({len(text)} chars)\n")
        outputs_doc.append(f"**Reference ({len(reference)} chars):**\n\n> {reference}\n\n")
        for summ, out in outs.items():
            outputs_doc.append(f"**{summ}** ({len(out)} chars):\n\n```\n{out}\n```\n\n")

        for summ, out in outs.items():
            m = rouge(out, reference)
            m.update({"corpus": name, "summarizer": summ})
            rouge_rows.append(m)

    (OUT_DIR / f"outputs-{date}.md").write_text("".join(outputs_doc))

    # ROUGE table — grouped by corpus
    rouge_doc: list[str] = [f"# A2 ROUGE-style overlap vs gold reference — {date}\n\n"]
    rouge_doc.append(
        "Unigram/bigram content-token overlap (stopwords removed, lowercased, "
        "3+ char tokens). Higher = better lexical match to the human-written "
        "reference summary. Does not capture semantic quality (see review doc).\n\n"
    )

    corpora_names = sorted({r["corpus"] for r in rouge_rows})
    summ_names = ["skimr/tfidf", "skimr/textrank", "sumy/LexRank", "sumy/TextRank", "sumy/LSA"]

    # Headline table — R1-F and R2-F side-by-side per corpus
    rouge_doc.append("## Headline: R1-F / R2-F by corpus × summarizer\n\n")
    header = ["corpus"] + summ_names
    rouge_doc.append("| " + " | ".join(header) + " |\n")
    rouge_doc.append("|" + "|".join(["---"] * len(header)) + "|\n")
    by_corpus: dict[str, dict[str, dict]] = {c: {} for c in corpora_names}
    for r in rouge_rows:
        by_corpus[r["corpus"]][r["summarizer"]] = r
    for c in corpora_names:
        row = [f"`{c}`"]
        for s in summ_names:
            m = by_corpus[c][s]
            row.append(f"{m['r1_f']:.3f} / {m['r2_f']:.3f}")
        rouge_doc.append("| " + " | ".join(row) + " |\n")
    rouge_doc.append("\n")

    # Averages per summarizer
    rouge_doc.append("## Averaged across all corpora\n\n")
    rouge_doc.append("| summarizer | avg R1-F | avg R2-F | avg out chars |\n")
    rouge_doc.append("|---|---|---|---|\n")
    for s in summ_names:
        rs = [r for r in rouge_rows if r["summarizer"] == s]
        r1 = sum(r["r1_f"] for r in rs) / len(rs)
        r2 = sum(r["r2_f"] for r in rs) / len(rs)
        oc = sum(r["out_chars"] for r in rs) / len(rs)
        rouge_doc.append(f"| `{s}` | {r1:.3f} | {r2:.3f} | {oc:.0f} |\n")

    (OUT_DIR / f"rouge-{date}.md").write_text("".join(rouge_doc))

    # JSON dump for programmatic reuse
    (OUT_DIR / f"rouge-{date}.json").write_text(json.dumps(rouge_rows, indent=2))

    print(f"Wrote {OUT_DIR}/outputs-{date}.md ({len(corpora)} corpora)")
    print(f"Wrote {OUT_DIR}/rouge-{date}.md")
    print(f"Wrote {OUT_DIR}/rouge-{date}.json ({len(rouge_rows)} rows)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
