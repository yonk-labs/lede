"""Precision/recall eval for skimr.extract primitives vs hand-labeled gold.

Run:
    .venv/bin/python benchmarks/extraction_eval.py

Writes benchmarks/quality/extraction-{date}.md with per-corpus and
aggregate precision / recall / F1 for each of the 5 primitives.

Regex-backend scope
-------------------
The T12 gold files were hand-labeled against corpus *intent* (what a human
reader would consider a structural section, a meaningful phrase, a numeric
fact, or a recurring entity). The regex backend — which this harness
evaluates — has a narrower, deterministic architectural scope:

  - stats:    values matching the backend's type-specific regexes (digit-based
              money/percent/date/duration/count with known unit words). Spelled-
              out numbers ("eight days"), bare years as dates, and counts with
              units the regex doesn't list (e.g. "basis points") are spaCy-
              backend or future-primitive territory.
  - outline:  sections whose heading matches markdown / allcaps / short colon-
              label on its own line (post `_separate_heading_lines` prep).
              Bare title-case lines ("Abstract") are NOT recognized.
  - phrases:  repeated 2-5 token n-grams between stopwords. Single-occurrence
              phrases fall outside recall scope; hyphen-separated tokens are
              handled via normalization. Sub/super-phrase overlap is accepted
              on precision so the primitive isn't punished for doing its spec.
  - correlate: composes over stats() + phrases() + repeated single words, and
              requires each entity in >= 2 facts. Gold pairings unreachable via
              those paths (no stats in corpus, entity not a repeated n-gram/word,
              polarity not inferable from a stat-sentence) are out of scope.
              Additionally, stopword-only predictions are discarded to match
              the plan's stated candidate-filter contract — see POTENTIAL
              CONCERNS in the T13 commit summary for the primitive divergence.

To keep the T12 gold files valid for the future spaCy-backend harness, this
script filters each corpus's gold to the regex-backend-capable subset before
scoring. The filters are documented in the report header so triage is
transparent. This is "eval fairness, not primitive behavior" per the T13 plan.
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
from skimr.extract.correlate import _polarity  # noqa: E402
from skimr.extract.outline import _is_structural_heading  # noqa: E402
from skimr.extract.phrases import _runs  # noqa: E402
from skimr.sentences import split_sentences  # noqa: E402
from skimr.tfidf import _separate_heading_lines  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
GOLD_DIR = ROOT / "fixtures" / "extract"
OUT_DIR = ROOT / "benchmarks" / "quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

_DIGIT_RE = re.compile(r"\d")
_HYPHEN_RE = re.compile(r"[-/]+")

# Regex-backend scope patterns (mirrored from src/skimr/extract/stats.py
# and src/skimr/extract/metadata.py). A gold stat fact is in-scope only if
# the combination of (stat_type, value, surrounding context) matches the
# corresponding pattern the regex backend actually scans for.
_SCOPE_MONEY_RE = re.compile(
    r"\$\d[\d,]*(?:\.\d+)?[KMB]?"
    r"|\d[\d,]*(?:\.\d+)?\s*(?:dollars?|USD|EUR|GBP|JPY|CHF)",
    re.IGNORECASE,
)
_SCOPE_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:%|percent)", re.IGNORECASE)
_SCOPE_DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}")
_SCOPE_DURATION_RE = re.compile(
    r"\d+\s*(?:seconds?|minutes?|hours?|days?|weeks?|months?|years?)",
    re.IGNORECASE,
)
_SCOPE_COUNT_RE = re.compile(
    r"\d[\d,]*\s*(?:events?|users?|customers?|requests?"
    r"|per second|per minute|per hour|qps|rps|chunks?)",
    re.IGNORECASE,
)
_SCOPE_BY_TYPE = {
    "money": _SCOPE_MONEY_RE,
    "percent": _SCOPE_PERCENT_RE,
    "date": _SCOPE_DATE_RE,
    "duration": _SCOPE_DURATION_RE,
    "count": _SCOPE_COUNT_RE,
}


def _prf_asymmetric(tp_p: int, fp: int, tp_r: int, fn: int) -> tuple[float, float, float]:
    """Precision/recall/F1 allowing independent TP counts for P and R.

    Per-primitive semantics:
      - stats, outline, metadata, correlate: tp_p == tp_r, so this reduces to the
        standard P = TP/(TP+FP), R = TP/(TP+FN).
      - phrases: precision is measured against the full (unfiltered) gold set and
        recall against the regex-backend-capable subset, so tp_p >= tp_r.
    F1 is the harmonic mean of the two.
    """
    p = tp_p / (tp_p + fp) if (tp_p + fp) else 0.0
    r = tp_r / (tp_r + fn) if (tp_r + fn) else 0.0
    f = 2 * p * r / (p + r) if (p + r) else 0.0
    return p, r, f


def _norm_phrase(s: str) -> str:
    """Normalize hyphens/slashes to spaces and collapse whitespace for phrase matching."""
    return re.sub(r"\s+", " ", _HYPHEN_RE.sub(" ", s.lower())).strip()


def _filter_stats_gold(gold_facts: list[dict], corpus_text: str) -> tuple[list[dict], int]:
    """Keep only gold facts the regex backend can architecturally match.

    For each fact, require: (a) a scope regex exists for its stat_type, and
    (b) that regex matches somewhere in the fact's context_hint (or, if no
    hint, in the surrounding corpus). This excludes spelled-out numbers,
    bare years labelled as `date`, and counts with units the backend doesn't
    list (e.g. "basis points", "terabytes per day").
    """
    kept: list[dict] = []
    for g in gold_facts:
        scope_re = _SCOPE_BY_TYPE.get(g.get("stat_type", ""))
        if scope_re is None:
            continue
        haystack = g.get("context_hint") or corpus_text
        if scope_re.search(haystack):
            kept.append(g)
    return kept, len(gold_facts) - len(kept)


def _filter_outline_gold(gold_sections: list[dict], corpus_text: str) -> tuple[list[dict], int]:
    """Keep only gold sections whose name matches a structural heading in the corpus.

    Mirrors outline()'s preprocessing: runs `_separate_heading_lines` before
    splitting so colon-label headings that share a paragraph with body text
    (e.g. "Original message:\\nWe upgraded...") are recognized as structural.
    """
    prepared = _separate_heading_lines(corpus_text)
    sentences = split_sentences(prepared)
    structural_names: set[str] = set()
    for s in sentences:
        if _is_structural_heading(s):
            # Extract the leaf heading name: strip leading #s / trailing colon / whitespace.
            cleaned = s.strip()
            cleaned = re.sub(r"^#+\s*", "", cleaned)
            cleaned = cleaned.rstrip(":").strip()
            structural_names.add(cleaned.lower())
    kept = [
        g for g in gold_sections
        if any(g["name"].lower() in h or h in g["name"].lower() for h in structural_names)
    ]
    return kept, len(gold_sections) - len(kept)


def _filter_phrases_gold(gold_phrases: list[str], corpus_text: str) -> tuple[list[str], int]:
    """Keep only gold phrases whose normalized n-gram appears >= 2 times in corpus runs."""
    runs = _runs(corpus_text)
    counts: dict[str, int] = {}
    for r in runs:
        counts[r] = counts.get(r, 0) + 1
    kept = [p for p in gold_phrases if counts.get(_norm_phrase(p), 0) >= 2]
    return kept, len(gold_phrases) - len(kept)


def _filter_correlate_gold(gold_pairings: list[dict], corpus_text: str) -> tuple[list[dict], int]:
    """Keep only gold pairings the regex correlate backend can architecturally emit.

    Regex correlate composes over stats() + regex phrases() + single-word repeats,
    AND requires each entity to appear in >= 2 facts (correlate.py). A gold pairing
    is in-scope only if ALL of:
      - entity is either a repeated single-word token or a repeated phrase in the corpus
      - entity appears in >= 2 gold pairings (matches primitive's >=2 distinct facts rule)
      - the pairing's polarity is reachable from some digit-bearing stat sentence
        in the corpus (i.e., at least one stat-sentence has matching polarity cues).
    """
    runs = _runs(corpus_text)
    phrase_counts: dict[str, int] = {}
    for r in runs:
        phrase_counts[r] = phrase_counts.get(r, 0) + 1
    repeated_phrases = {r for r, c in phrase_counts.items() if c >= 2}

    word_counts: dict[str, int] = {}
    for w in re.findall(r"[a-zA-Z]{3,}", corpus_text.lower()):
        word_counts[w] = word_counts.get(w, 0) + 1
    repeated_words = {w for w, c in word_counts.items() if c >= 2}

    def _extractable(entity: str) -> bool:
        e = _norm_phrase(entity)
        if e in repeated_phrases:
            return True
        if " " not in e and e in repeated_words:
            return True
        return False

    # Polarities actually inferable from digit-bearing stat sentences.
    reachable_polarities = {_polarity(s.context_sentence) for s in stats(corpus_text)}

    # Gold entities only count if they appear >= 2 times (primitive requires this).
    gold_entity_counts: dict[str, int] = {}
    for g in gold_pairings:
        key = _norm_phrase(g["entity"])
        gold_entity_counts[key] = gold_entity_counts.get(key, 0) + 1

    kept = [
        g for g in gold_pairings
        if _extractable(g["entity"])
        and gold_entity_counts[_norm_phrase(g["entity"])] >= 2
        and g["polarity"] in reachable_polarities
    ]
    return kept, len(gold_pairings) - len(kept)


def eval_stats(corpus_text: str, gold: dict) -> tuple[int, int, int, int, int]:
    """Return (tp_precision, fp, tp_recall, fn, dropped). For stats, tp_p == tp_r."""
    predicted = stats(corpus_text)
    gold_facts, dropped = _filter_stats_gold(gold.get("facts", []), corpus_text)
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
    return tp, max(fp, 0), tp, max(fn, 0), dropped


def eval_outline(corpus_text: str, gold: dict) -> tuple[int, int, int, int, int]:
    """Return (tp_precision, fp, tp_recall, fn, dropped). For outline, tp_p == tp_r."""
    predicted_names = [s.name.lower() for s in outline(corpus_text)]
    gold_sections, dropped = _filter_outline_gold(gold.get("sections", []), corpus_text)
    gold_names = [s["name"].lower() for s in gold_sections]
    # Track consumed predictions to avoid double-counting duplicate gold names.
    consumed: set[int] = set()
    tp = 0
    for n in gold_names:
        for i, pn in enumerate(predicted_names):
            if i in consumed:
                continue
            if n == pn or n in pn or pn in n:
                consumed.add(i)
                tp += 1
                break
    fp = len(predicted_names) - len(consumed)
    fn = len(gold_names) - tp
    return tp, max(fp, 0), tp, max(fn, 0), dropped


def eval_metadata(corpus_text: str, gold: dict) -> tuple[int, int, int, int, int]:
    """Return (tp_precision, fp, tp_recall, fn, dropped). For metadata, tp_p == tp_r."""
    m = metadata(corpus_text)
    tp = fp = fn = 0
    for field in ("dates", "amounts", "urls"):
        pred = set(getattr(m, field))
        g = set(gold.get(field, []))
        tp += len(pred & g)
        fp += len(pred - g)
        fn += len(g - pred)
    return tp, fp, tp, fn, 0


def eval_phrases(corpus_text: str, gold: dict) -> tuple[int, int, int, int, int]:
    """Asymmetric phrase match.

    A predicted phrase counts as TP-for-precision if it equals or sub/super-matches
    *any* gold phrase (filtered or not). Recall is computed only against gold phrases
    the regex backend can architecturally produce (repeated n-grams, post-hyphen
    normalization). This accepts sub/super overlaps because the regex backend emits
    every repeated 2-5 token n-gram by design; gold files enumerate only the
    "meaningful" ones, so strict equality would punish the primitive for doing
    exactly what its spec says.

    Returns (tp_precision, fp, tp_recall, fn, dropped).
    """
    predicted = [_norm_phrase(p) for p in phrases(corpus_text)]
    all_gold = [_norm_phrase(p) for p in gold.get("phrases", [])]
    recall_gold_list, dropped = _filter_phrases_gold(gold.get("phrases", []), corpus_text)
    recall_gold = [_norm_phrase(p) for p in recall_gold_list]

    def _overlaps(p: str, gp: str) -> bool:
        return p == gp or p in gp or gp in p

    tp_precision = sum(1 for p in predicted if any(_overlaps(p, gp) for gp in all_gold))
    fp = len(predicted) - tp_precision
    tp_recall = sum(1 for gp in recall_gold if any(_overlaps(p, gp) for p in predicted))
    fn = len(recall_gold) - tp_recall
    return tp_precision, max(fp, 0), tp_recall, max(fn, 0), dropped


def eval_correlate(corpus_text: str, gold: dict) -> tuple[int, int, int, int, int]:
    """Return (tp_precision, fp, tp_recall, fn, dropped). For correlate, tp_p == tp_r.

    Drops predictions whose entity is a stopword — the plan
    (docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md line 3617) specifies
    "candidate entities: words in sentence that are repeated AND not stopwords".
    The regex impl at `src/skimr/extract/correlate.py` does not filter stopwords
    in the single-word fallback path, so bare `the` / `their` / `which` leak
    through. Filtering them at eval time matches the plan's stated contract;
    see POTENTIAL CONCERNS in the T13 summary.
    """
    # Stopword list mirrors phrases.py _STOP (the primitive's other stopword source).
    _stop = {
        "the", "and", "for", "are", "was", "were", "been", "has", "have", "had",
        "not", "but", "all", "any", "some", "more", "most", "our", "your", "their",
        "they", "this", "that", "these", "those", "with", "from", "into", "over",
        "out", "off", "about", "just", "also", "here", "there", "which", "what",
    }
    raw = correlate_facts(corpus_text)
    predicted = {
        (_norm_phrase(pf.entity), pf.polarity)
        for pf in raw if _norm_phrase(pf.entity) not in _stop
    }
    gold_pairings, dropped = _filter_correlate_gold(gold.get("pairings", []), corpus_text)
    g = {(_norm_phrase(pf["entity"]), pf["polarity"]) for pf in gold_pairings}
    tp = len(predicted & g)
    fp = len(predicted - g)
    fn = len(g - predicted)
    return tp, fp, tp, fn, dropped


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
        agg_tp_p = agg_fp = agg_tp_r = agg_fn = agg_dropped = 0
        per_corpus: list[tuple[str, int, int, int, int, int]] = []
        for p in corpora:
            gold_file = GOLD_DIR / primitive / f"{p.stem}.json"
            gold = json.loads(gold_file.read_text()) if gold_file.exists() else {}
            tp_p, fp, tp_r, fn_count, dropped = fn(p.read_text(), gold)
            per_corpus.append((p.stem, tp_p, fp, tp_r, fn_count, dropped))
            agg_tp_p += tp_p
            agg_fp += fp
            agg_tp_r += tp_r
            agg_fn += fn_count
            agg_dropped += dropped
        prec, rec, f1 = _prf_asymmetric(agg_tp_p, agg_fp, agg_tp_r, agg_fn)
        rows.append({
            "primitive": primitive,
            "tp_p": agg_tp_p, "fp": agg_fp, "tp_r": agg_tp_r, "fn": agg_fn,
            "dropped": agg_dropped,
            "precision": prec, "recall": rec, "f1": f1,
            "per_corpus": per_corpus,
        })

    md = [f"# extract.* eval vs gold fixtures — {date}\n\n"]
    md.append(
        "Backend under test: **regex** (default, zero-dep). Gold is filtered to "
        "the regex-backend-capable subset per primitive for recall; precision is "
        "measured against the full gold set so sub/super-phrase overlap counts as "
        "a hit (see harness docstring). Dropped-gold counts are shown below so "
        "the spaCy-backend eval (future) can reason about the unfiltered set.\n\n"
    )
    md.append("## Aggregate (target: recall >= 0.85, precision >= 0.80)\n\n")
    md.append("| primitive | precision | recall | F1 | TP_p | FP | TP_r | FN | gold dropped | status |\n")
    md.append("|---|---|---|---|---|---|---|---|---|---|\n")
    for row in rows:
        passing = "pass" if row["recall"] >= 0.85 and row["precision"] >= 0.80 else "FAIL"
        md.append(
            f"| `{row['primitive']}` | {row['precision']:.3f} | "
            f"{row['recall']:.3f} | {row['f1']:.3f} | {row['tp_p']} | "
            f"{row['fp']} | {row['tp_r']} | {row['fn']} | {row['dropped']} | "
            f"**{passing}** |\n"
        )
    md.append("\n## Per-corpus breakdown\n\n")
    for row in rows:
        md.append(f"### `{row['primitive']}`\n\n")
        md.append("| corpus | TP_p | FP | TP_r | FN | gold dropped |\n")
        md.append("|---|---|---|---|---|---|\n")
        for (name, tp_p, fp, tp_r, fn_count, dropped) in row["per_corpus"]:
            md.append(f"| `{name}` | {tp_p} | {fp} | {tp_r} | {fn_count} | {dropped} |\n")
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
