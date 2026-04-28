# Gold-label protocol for lede.extract.* fixtures

## Why

SC-D (lede v0.2 plan) requires each `extract.*` primitive to hit ≥0.85 recall / ≥0.80 precision against a hand-labeled gold set. This doc captures the labeling rules so anyone can re-label or extend the corpus without drift.

## Scope

10 corpora under `benchmarks/corpus/*.txt`. Per corpus, 5 gold files under `fixtures/extract/<primitive>/<corpus>.json`:

- `fixtures/extract/stats/<corpus>.json`
- `fixtures/extract/outline/<corpus>.json`
- `fixtures/extract/metadata/<corpus>.json`
- `fixtures/extract/phrases/<corpus>.json`
- `fixtures/extract/correlate/<corpus>.json`

Total: 10 × 5 = 50 files.

## Format

Each gold file is a JSON object. Missing fields default to empty.

### stats

```
{
  "facts": [
    {
      "value": "$120K",
      "unit": "usd",
      "stat_type": "money",
      "context_hint": "original quote was $120K"
    }
  ]
}
```

- `value` — the string the primitive's regex will produce as `Stat.value` for this fact. For digit-form matches the primitive emits just the number (e.g. source `40%` → primitive `value="40"`; source `0.4 percent` → primitive `value="0.4"`). For duration matches the primitive emits just the number without the unit word (source `3 months` → primitive `value="3 months"` per pattern composition — see `src/lede/extract/stats.py`). When in doubt, run the primitive on the source and use what it emits. Word-form numeric facts (`"eight days"`, `"thirty days"`) are labeled per the human-extraction standard even though the current regex primitive cannot match them — these become known recall gaps T13 uses to decide whether the primitive needs a word-form extension.
- `unit` — the unit label the primitive emits. Canonical set: `"usd"` (money), `"percent"` (NOT `"pct"`), `"date"`, `"day"` / `"minute"` / `"month"` / `"week"` / `"year"` (singular — the primitive `rstrip("s")`s), and for `stat_type="count"` the concrete keyword from the source (`"events"`, `"users"`, `"documents"`, etc.).
- `stat_type` — one of `money`, `percent`, `date`, `duration`, `count`.
- `context_hint` — a substring that MUST appear somewhere inside the matched `Stat.context_sentence`. Short, unambiguous anchor phrase from the sentence (not the whole sentence).

### outline

```
{
  "sections": [
    {"name": "Facts", "depth": 1},
    {"name": "Discussion", "depth": 2}
  ]
}
```

- Order matters; sections should appear in the order they appear in the source.
- `representative_sentence` is NOT labeled (too noisy to hand-grade). Precision/recall is over `name`.
- Use section names as they appear in the source, with trailing colons stripped, and markdown heading markers (`#`, `##`) stripped. Preserve case.
- `depth` uses the same convention as the `extract.outline` primitive: 1 for top-level headings, 2 for sub-headings, etc.

### metadata

```
{
  "dates": ["2025-06-14"],
  "amounts": ["$120K"],
  "urls": [],
  "entities": ["Sarah Jones", "Johnson Education Co"]
}
```

- `dates` — exact strings in the source that are dates the primitive is expected to extract (ISO `YYYY-MM-DD` or US `MM/DD/YYYY`).
- `amounts` — exact strings for money amounts (e.g. `$120K`, `45 dollars`, `100 EUR`).
- `urls` — full URL strings starting with `http://` or `https://`.
- `entities` — named people, organizations, and places a human would reasonably extract. Labeled only where a human would confidently extract them.

**Eval backend routing:** the T13 harness MUST call `metadata(text, backend="regex")` to score `dates`, `amounts`, and `urls`, and call `metadata(text, backend="spacy")` (from lede-spacy) to score `entities`. The regex backend always returns an empty `entities` list by design. A single-backend eval would either score entities against an empty set (false miss on every entity) or score dates/amounts/urls against spaCy's output (false precision drop, since spaCy may emit entity-adjacent strings the regex primitive wouldn't).

### phrases

```
{"phrases": ["deployment pipeline", "customer support", "action items"]}
```

- Multi-word phrases (2-5 tokens) that feel load-bearing to the corpus. Lowercase.
- Follow the "appears ≥2 times OR contains a clearly load-bearing term" rule from Labeling rule #4 below.

### correlate

```
{
  "pairings": [
    {"entity": "revenue", "polarity": "growth"},
    {"entity": "revenue", "polarity": "absolute"}
  ]
}
```

- Only `entity` + `polarity` graded; the number value is covered by `stats`.
- `polarity` is one of `growth`, `decline`, `absolute`.
- Only include entities that appear in at least **two distinct** numeric facts in the source.

## Labeling rules

1. **Read the source corpus slowly.** Mark what a careful human would extract. The goal is "what would a competent human annotator label" — not "what does the current regex emit."
2. **Stats and metadata — exact string matches preferred.** If the source says `$120K` use `$120K`, not `120000` or `$120k`. The `context_hint` substring match is the fallback when a value could appear in multiple sentences.
3. **Outline — use the section names as they appear in the source**, with colons and markdown markers stripped. Preserve case. Do not invent sections that are not marked by a structural heading (allcaps line, markdown heading, or colon-label).
4. **Phrases — only include phrases that appear at least twice in the source OR contain a clearly load-bearing term** (proper noun, domain jargon, multi-word technical term that drives the document's meaning). Avoid generic multiword filler like "the team" or "this week."
5. **Correlate — only entities that appear in at least two distinct numeric facts.** One-shot numeric mentions do not count. Polarity reflects the verb or cue phrase near the number: growth cue ("grew", "rose", "increased") → `growth`, decline cue ("fell", "declined", "dropped") → `decline`, otherwise → `absolute`.
6. **Use the current primitive output as a starting point, not a target.** Remove items the primitive hallucinated; add items the primitive missed. The eval grades the primitive against the gold set, so over-labeling a primitive's current output is cheating; under-labeling suppresses recall.
7. **When in doubt, exclude.** A gold set calibrated to "aggressive labeling" produces noisy precision/recall signals. Favor precision — include items that a second annotator would also pick.

## Edge-case conventions (codified from the initial labeling pass)

These are judgment calls the first labelers made. They are not hard rules — T13's eval will tell us which conventions are useful to keep and which to revise.

- **Unit labels** follow what the current regex primitive emits (so eval matching works cleanly): percent uses `"percent"` (not `"pct"`); durations are singular (`"day"`, `"minute"`, `"month"`, `"week"`, `"year"` — the primitive `rstrip("s")`s); money is always `"usd"`; dates are always `"date"`; counts reuse the keyword from the source (e.g. `"events"`, `"users"`, `"documents"`, `"terabytes"`) rather than a generic label.
- **Outline — numbered sections.** `1. Information We Collect`, `2. Data Retention`, … are treated as structural headings. Strip the `N.` prefix; keep the rest as the section name at depth 1.
- **Outline — title lines.** The first line of a document (e.g. `Privacy Policy — Effective Date: 2026-01-01`) may be treated as a depth-1 section if it functions as the document title. Strip em-dash metadata.
- **Outline — inline colon-labels.** Metadata colon-labels like `Date:`, `Attendees:` that appear as single-line leading-matter (not introducing a multi-sentence block) are NOT treated as structural sections. `Action items:` that introduces a list IS treated as a structural section.
- **Outline — `Label: Subject` document headers** (e.g. `Meeting: Platform Migration Planning`): the section name is the subject (post-colon), not the label (pre-colon). Depth 1.
- **Phrase tokens.** "2-5 tokens" is evaluated with whitespace split. `high-dimensional` = 1 token (do not include); `high-dimensional space` = 2 tokens (include if ≥2 appearances or load-bearing).
- **Duplicate correlate pairings.** The `(entity, polarity)` tuples are evaluated as a set — no duplicates. If one entity appears with two distinct polarities (e.g. growth and decline), that's two pairings; repeating the same polarity is not.

## Known primitive gaps (T13 work items)

A preview run of `extract.stats` over the 10 gold corpora shows current recall at ~37%, well below the SC-D 0.85 gate. The misses are NOT labeler errors — they are specific capability gaps in the current regex primitive, listed here so T13 can decide whether to extend the primitive, restrict the gold, or accept the recall shortfall per-corpus:

1. **Word-form numbers** (~20 misses). The primitive's patterns require `\d+`, so `"eight days"`, `"thirty days"`, `"seven years"`, `"thirteen months"`, `"two weeks"`, `"five thousand"`, `"eighteen tons per year"`, `"five-day"`, etc. all fail. Fix: extend regex to recognize spelled-out numbers, or use a `num2words`-style reverse map.
2. **Bare years as dates** (6 misses: `"1975"`, `"1998"`, `"2016"`, `"2019"`, `"2022"`, `"2023"`). Current date pattern requires ISO or US slash form. Fix: add `\b(19|20)\d{2}\b` as a weak date pattern or require a verb-adjacent year in context.
3. **Hyphen-separated durations** (`"90-day retention"` → primitive sees `\d+` but `\s*` before unit doesn't match `-`). Fix: change `\s*` to `[\s-]*` in the duration regex.
4. **Count-without-unit-keyword** (`"800,000"`, `"25,000"` as bare populations). The count pattern requires a following keyword (`events`, `users`, `customers`…). Fix: weaken to match bare large numbers, or expand keyword list.
5. **Missing count keywords**: `"basis points"`, `"terabytes"`, `"tons"`, `"ULPs"`, `"documents"`, `"lines"`. Fix: expand the count pattern's keyword alternation.

The gold was labeled against the protocol's "what a careful human would extract" rule (Labeling rule #1), not against what the current primitive can match. This means T13's recall number reveals the primitive gap, which is exactly what a good gold set should do.

## Iteration

Labels may be revised if the eval (Task 13) surfaces patterns the labeler missed — revise the JSON, re-run the eval, commit both. Treat the gold set as revisable but not casually. Every revision should have a one-line commit rationale.

## Per-corpus process (what each labeler does)

For one corpus:

1. Open the source file at `benchmarks/corpus/<corpus>.txt`.
2. Run the current Python primitives to get a starting-point dump:
   ```bash
   .venv/bin/python - <<'PY'
   from pathlib import Path
   from dataclasses import asdict
   from lede.extract import stats, outline, metadata, phrases, correlate_facts

   corpus = Path("benchmarks/corpus/<corpus>.txt").read_text()
   print("--- stats ---")
   for s in stats(corpus): print(asdict(s))
   print("--- outline ---")
   for o in outline(corpus): print(asdict(o))
   print("--- metadata ---")
   print(asdict(metadata(corpus)))
   print("--- phrases ---")
   for p in phrases(corpus): print(p)
   print("--- correlate ---")
   for pf in correlate_facts(corpus): print(asdict(pf))
   PY
   ```
3. Apply the labeling rules. Write 5 JSON files under `fixtures/extract/<primitive>/<corpus>.json`.
4. Verify each file parses as JSON.

Expected time: ~20 minutes per corpus × 10 corpora = ~3.5 hours. Parallelizable per corpus.
