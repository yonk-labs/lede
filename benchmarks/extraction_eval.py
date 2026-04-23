"""Precision/recall eval for skimr.extract primitives vs hand-labeled gold.

Run:
    .venv/bin/python benchmarks/extraction_eval.py

Writes benchmarks/quality/extraction-{date}.md with per-corpus and
aggregate precision / recall / F1 for each of the 5 primitives.

Scope
-----
This harness scores the regex backend of skimr.extract against the T12
hand-labeled gold files at fixtures/extract/**. No filtering is applied —
the gold set was labeled against corpus intent (per
`docs/extraction-gold-labeling.md`, rule #1) and the harness measures the
primitive directly against that intent. Gaps therefore surface as recall
or precision misses, which is exactly what the SC-D gate is supposed to
reveal (protocol lines 123-133).

Matching rules per primitive follow the plan's verbatim spec
(`docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` lines 4083-4150).
The only matching-fairness tweak is `_norm_phrase`, applied symmetrically
to both sides of set comparisons for `phrases` and `correlate` so that
hyphen/slash token variants do not split TP counts.
"""
from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from skimr.extract import stats, outline, metadata, phrases, correlate_facts  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
GOLD_DIR = ROOT / "fixtures" / "extract"
OUT_DIR = ROOT / "benchmarks" / "quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

_HYPHEN_RE = re.compile(r"[-/]+")


def _prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    p = tp / (tp + fp) if (tp + fp) else 0.0
    r = tp / (tp + fn) if (tp + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _norm_phrase(s: str) -> str:
    """Lowercase, normalize hyphens/slashes to spaces, collapse whitespace.

    Applied symmetrically to predicted and gold phrases so hyphenated token
    variants ("high-dimensional" vs "high dimensional") don't split TPs.
    """
    return re.sub(r"\s+", " ", _HYPHEN_RE.sub(" ", s.lower())).strip()


def eval_stats(corpus_text: str, gold: dict) -> tuple[int, int, int]:
    predicted = stats(corpus_text)
    gold_facts = gold.get("facts", [])
    matched: set[int] = set()
    tp = 0
    for g in gold_facts:
        hint = g.get("context_hint", "")
        matched_idx = None
        for i, s in enumerate(predicted):
            if i in matched:
                continue
            if (s.stat_type == g.get("stat_type") and
                    hint.lower() in s.context_sentence.lower() and
                    g["value"].lower() in s.value.lower()):
                matched_idx = i
                break
        if matched_idx is not None:
            matched.add(matched_idx)
            tp += 1
    fp = len(predicted) - len(matched)
    fn = len(gold_facts) - tp
    return tp, max(fp, 0), max(fn, 0)


def eval_outline(corpus_text: str, gold: dict) -> tuple[int, int, int]:
    predicted_names = [s.name.lower() for s in outline(corpus_text)]
    gold_names = [s["name"].lower() for s in gold.get("sections", [])]
    # Consumed-prediction set avoids double-counting duplicate gold names
    # against a single prediction. Matching itself is verbatim equality
    # (per plan line 4117).
    consumed: set[int] = set()
    tp = 0
    for n in gold_names:
        for i, pn in enumerate(predicted_names):
            if i in consumed:
                continue
            if n == pn:
                consumed.add(i)
                tp += 1
                break
    fp = len(predicted_names) - len(consumed)
    fn = len(gold_names) - tp
    return tp, max(fp, 0), max(fn, 0)


def eval_metadata(corpus_text: str, gold: dict) -> tuple[int, int, int]:
    m = metadata(corpus_text)
    tp = fp = fn = 0
    # `entities` is omitted: regex backend always returns [] by design, so
    # including it would force every corpus's entity gold into FN.
    for field in ("dates", "amounts", "urls"):
        pred = set(getattr(m, field))
        g = set(gold.get(field, []))
        tp += len(pred & g)
        fp += len(pred - g)
        fn += len(g - pred)
    return tp, fp, fn


def eval_phrases(corpus_text: str, gold: dict) -> tuple[int, int, int]:
    predicted = {_norm_phrase(p) for p in phrases(corpus_text)}
    g = {_norm_phrase(p) for p in gold.get("phrases", [])}
    tp = len(predicted & g)
    fp = len(predicted - g)
    fn = len(g - predicted)
    return tp, fp, fn


def eval_correlate(corpus_text: str, gold: dict) -> tuple[int, int, int]:
    predicted = {
        (_norm_phrase(pf.entity), pf.polarity)
        for pf in correlate_facts(corpus_text)
    }
    g = {
        (_norm_phrase(pf["entity"]), pf["polarity"])
        for pf in gold.get("pairings", [])
    }
    tp = len(predicted & g)
    fp = len(predicted - g)
    fn = len(g - predicted)
    return tp, fp, fn


EVALS = {
    "stats": eval_stats,
    "outline": eval_outline,
    "metadata": eval_metadata,
    "phrases": eval_phrases,
    "correlate": eval_correlate,
}


def main() -> int:
    date = time.strftime("%Y-%m-%d")
    corpora = sorted(CORPUS_DIR.glob("*.txt"))

    rows: list[dict] = []
    for primitive, fn in EVALS.items():
        agg_tp = agg_fp = agg_fn = 0
        per_corpus: list[tuple[str, int, int, int]] = []
        for p in corpora:
            gold_file = GOLD_DIR / primitive / f"{p.stem}.json"
            gold = json.loads(gold_file.read_text()) if gold_file.exists() else {}
            tp, fp, fn_count = fn(p.read_text(), gold)
            per_corpus.append((p.stem, tp, fp, fn_count))
            agg_tp += tp
            agg_fp += fp
            agg_fn += fn_count
        prec, rec, f1 = _prf(agg_tp, agg_fp, agg_fn)
        rows.append({
            "primitive": primitive,
            "tp": agg_tp, "fp": agg_fp, "fn": agg_fn,
            "precision": prec, "recall": rec, "f1": f1,
            "per_corpus": per_corpus,
        })

    md = [f"# extract.* eval vs gold fixtures — {date}\n\n"]
    md.append(
        "Backend under test: **regex** (default, zero-dep). Precision / "
        "recall vs. hand-labeled gold at `fixtures/extract/**`. No filtering — "
        "the gold set is the contract and the SC-D gate measures the primitive "
        "directly against corpus intent (labeling protocol rule #1). "
        "`_norm_phrase` is applied symmetrically for hyphen/slash matching "
        "fairness on `phrases` and `correlate`.\n\n"
    )
    md.append("## Aggregate (target: recall >= 0.85, precision >= 0.80)\n\n")
    md.append("| primitive | precision | recall | F1 | TP | FP | FN | status |\n")
    md.append("|---|---|---|---|---|---|---|---|\n")
    for row in rows:
        passing = "pass" if row["recall"] >= 0.85 and row["precision"] >= 0.80 else "FAIL"
        md.append(
            f"| `{row['primitive']}` | {row['precision']:.3f} | "
            f"{row['recall']:.3f} | {row['f1']:.3f} | {row['tp']} | "
            f"{row['fp']} | {row['fn']} | **{passing}** |\n"
        )
    md.append("\n## Per-corpus breakdown\n\n")
    for row in rows:
        md.append(f"### `{row['primitive']}`\n\n")
        md.append("| corpus | TP | FP | FN |\n|---|---|---|---|\n")
        for (name, tp, fp, fn_count) in row["per_corpus"]:
            md.append(f"| `{name}` | {tp} | {fp} | {fn_count} |\n")
        md.append("\n")

    out_path = OUT_DIR / f"extraction-{date}.md"
    out_path.write_text("".join(md))
    print(f"Wrote {out_path}")

    # SC-D gate
    failures = [
        r["primitive"] for r in rows
        if r["recall"] < 0.85 or r["precision"] < 0.80
    ]
    if failures:
        print(f"SC-D FAIL for: {failures}")
        return 1
    print("SC-D pass")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
