---
spec: skimr v0.2.0 — RAG-prep primitive (summary + structured enrichments)
created: 2026-04-21
status: draft — pending user review
---

## TL;DR

Evolve skimr from a deterministic summarizer into a **RAG-prep primitive**: one call produces a summary PLUS a suite of structured enrichments (stats, outline, metadata, phrases, correlated facts) that ride along in a single pass. Optimized for pipelines where ingested text is summarized, embedded, and stored as a retrieval point — end-to-end budget under 250 ms per document. Shipped as a single big-bang v0.2.0 release with a new `skimr.extract.*` namespace and an optional `skimr[ner]` extra for named-entity recognition.

## Mission

Primary use case: **application ingests text → fast summary → summary embedded → stored as retrieval point**. The retrieval quality hinges on (1) how factually accurate the summary is, (2) how much structured enrichment rides alongside (stats, entities, outline) for hybrid filtering, and (3) how fast the whole pipeline runs so it can live on a hot path.

skimr v0.2.0 is that primitive.

**Not** competing with sumy on prose elegance. Competing on:
- **Speed** (sub-ms core, sub-250 ms full enrichment pass).
- **Factual preservation** (scorer tuned to keep "load-bearing" sentences: holdings, action items, numeric facts).
- **Structured data attached to the summary** (stats, outline, metadata — things sumy does not produce).
- **Determinism** (bit-identical across Python + Rust; cross-runtime parity via `fixtures/`).
- **Zero-dep core** (stdlib-only Python; `regex`-only Rust). NER is an optional extra, never required.

## Target pipeline

```
ingest → clean_text → summarize(attach=[...]) → embed(result.summary) → pgvector row
                              │
                              └─► result.stats, result.outline, result.metadata
                                  promoted to typed columns for hybrid search
```

Target end-to-end latency for summarize-with-all-enrichments: **< 250 ms (cold), < 10 ms (warm)** on the 10-corpus benchmark set. Ship when that budget holds for every corpus type.

## API surface — v0.2.0

```python
from skimr import summarize, clean_text, strip_think, extract_keyword
from skimr.extract import (
    stats,           # list[Stat]
    outline,         # list[Section]
    metadata,        # Metadata (dict-like)
    phrases,         # list[str]
    correlate_facts, # list[PhraseFact]
)

# --- Summary + enrichments in one call ---
result = summarize(
    text,
    max_length=500,
    mode="default",              # "default" | "coverage" | "legacy"
    attach=["stats", "outline"], # any subset of extract.* primitives
)
# result.summary: str
# result.stats:   list[Stat]   (None if not attached)
# result.outline: list[Section]
# result.metadata, result.phrases, result.correlated_facts: same pattern

# --- Each primitive is also standalone ---
s = skimr.extract.stats(text)
o = skimr.extract.outline(text)
m = skimr.extract.metadata(text)
p = skimr.extract.phrases(text)
c = skimr.extract.correlate_facts(text)
```

### Return types

**`summarize()` always returns `SummaryResult`.** This is a v0.2.0 breaking change from v0.0.1's `-> str`, and is called out in the release notes. `SummaryResult.__str__` returns `self.summary`, so `print(summarize(text))` and `f"{summarize(text)}"` continue to work. Callers that need a raw string use `summarize(text).summary` explicitly. `mode="legacy"` does not change this — the scorer is legacy, the return shape is v0.2.0. Consumers that absolutely need the old `-> str` contract pin to v0.1.x.

All dataclasses are frozen for hashability, serializable to JSON via `dataclasses.asdict`. Rust mirrors with `serde`-derivable structs (once JSON emit is needed; Plan 2 Rust adds crate-local types).

```python
@dataclass(frozen=True)
class SummaryResult:
    summary: str
    stats: list[Stat] | None = None
    outline: list[Section] | None = None
    metadata: Metadata | None = None
    phrases: list[str] | None = None
    correlated_facts: list[PhraseFact] | None = None

@dataclass(frozen=True)
class Stat:
    value: str              # "23%", "$120K", "7 years"
    unit: str               # "percent", "usd", "duration"
    phrase: str             # "revenue grew 23%"
    context_sentence: str   # the full sentence containing the fact
    stat_type: str          # "money" | "percent" | "count" | "date" | "duration"

@dataclass(frozen=True)
class Section:
    depth: int              # heading level (1, 2, 3, ...)
    name: str               # "Discussion", "Goals", ...
    representative_sentence: str  # best sentence from under this heading

@dataclass(frozen=True)
class Metadata:
    dates: list[str]
    amounts: list[str]
    urls: list[str]
    entities: list[str]     # populated only when skimr[ner] is installed

@dataclass(frozen=True)
class PhraseFact:
    entity: str             # repeated term
    number: str             # correlated numeric fact
    polarity: str           # "absolute" | "growth" | "decline" | "unknown"
    sentence: str
```

### Mode selector on `summarize()`

- `"default"` — v0.2.0 scorer (C1 improvements): heading filter + cue-phrase boost + digit bonus + section-position weighting.
- `"coverage"` — C2 paragraph-aware selector. Guarantees at least one sentence per paragraph (or per `N` paragraphs via kwarg). For split-ends docs (support tickets, holdings-at-end opinions).
- `"legacy"` — byte-identical to v0.0.1 / v0.1.0-rc1 behavior. For regression-testing consumers that depend on the old output bytes.

## C1 — Scorer improvements (within `summarize`)

Four additive tweaks to the composite scorer in `tfidf.py` / `tfidf.rs`. All four default-on in `mode="default"`. All four disabled in `mode="legacy"`.

1. **Heading filter** — drop candidates matching any of:
   - `^#+\s+` (markdown headings)
   - `^\s*[A-Z][A-Z\s]{3,}:?\s*$` (ALL-CAPS titles like "HELD:", "FACTS:")
   - `^.{1,30}:\s*$` (short colon-terminated labels — "Goals:", "### Risks")
   - sentences with fewer than 4 content tokens

   Dropped candidates never enter the scoring loop. Deterministic; regex-based.

2. **Cue-phrase boost** — `+2.0` to composite score for sentences matching:
   `^(held|resolution|in summary|conclusion|action item|decision|finding|key takeaway|outcome|ruling):?\b`
   Case-insensitive. Frozen regex; documented in code.

3. **Digit bonus** — `+0.3` to composite score for sentences containing `\d+`. Ported from the keyword-scored mode's existing logic. Small bump; compounds with other signals.

4. **Section-position weighting** — multiply TF-IDF component of composite score by `1.3` for sentences that fall under a section heading matching:
   `^(discussion|conclusion|held|resolution|key findings|summary|decision)$` (case-insensitive, after stripping `#+` prefix). "Under" = between that heading and the next heading.

**Expected lift** (from A1/A4 analysis): skimr/tfidf from 186/250 → 215-225/250, passing sumy/TextRank (206/250). Per-corpus: +4 to +7 on heading-heavy docs (privacy-policy, tech-spec, sci-paper, wiki). 0 regression on front-loaded docs.

## C2 — Coverage-constrained selection

New selector (not scorer). Activated via `mode="coverage"`. Instead of pure score-descending greedy selection against a char budget, this variant:

1. Parses paragraphs. **Definition (frozen for this spec):** a paragraph is a run of non-empty lines delimited by one or more blank lines (regex: `\n\s*\n+`). Single newlines within a paragraph are preserved; paragraphs of fewer than 20 chars after trim are ignored (same threshold as the SQL-style sentence filter for consistency).
2. Scores sentences normally using the C1 scorer.
3. Selects the highest-scoring sentence per paragraph until the char budget is reached.
4. If budget remains after one pass, picks next-best ungrabbed sentence globally.

Guarantees coverage breadth on split-ends docs. Default takes every paragraph; override with `coverage_stride=N` (default `1`) to sample every Nth paragraph when the document is very long.

## C3 — Extract primitives (new namespace `skimr.extract`)

All five primitives share the same input-preparation pipeline (clean text, sentence split, paragraph parse) done **once per call**. When invoked via `summarize(attach=[...])`, that preparation is shared with the summary step — no redundant re-parsing.

### C3a `extract.outline(text) -> list[Section]`

Detect sections from the same rules used by the heading filter (inverse: headings that were filtered from the summary candidate pool become outline node names). For each section, pick the top-scoring non-heading sentence as `representative_sentence`. Depth inferred from `#` count for markdown; depth 1 default for non-markdown structure.

### C3b `extract.stats(text) -> list[Stat]`

Regex passes for five numeric fact patterns:

- **Money**: `\$\d[\d,]*(?:\.\d+)?[KMB]?` and `\d[\d,]* (dollars?|USD|EUR|GBP|JPY|CHF)`
- **Percent**: `\d+(?:\.\d+)?\s*%` and `\d+(?:\.\d+)?\s*percent`
- **Count**: `\d[\d,]+\s*(?:events|users|customers|requests|per|qps|rps|chunks)` and bare numerics in clearly numeric contexts
- **Date**: `\d{4}-\d{2}-\d{2}`, `\d{1,2}/\d{1,2}/\d{2,4}`, month-name forms
- **Duration**: `\d+\s*(?:days?|weeks?|months?|years?|hours?|minutes?|seconds?)`

Each match produces a `Stat` with the surrounding phrase (±5 tokens) and full containing sentence. Deterministic, zero-dep.

### C3c `extract.metadata(text) -> Metadata`

Two layers:

**Core (stdlib)** — dates, amounts, URLs via regex. Always available. Rust port produces byte-identical output.

**Extra (`skimr[ner]`)** — named entities (persons, organizations, locations, products) via spaCy's `en_core_web_sm` model. Populates `Metadata.entities`. Python-only; Rust port leaves `entities=[]`. Clearly documented.

**Cross-language parity contract:** stdlib path is byte-identical Python ↔ Rust. NER extra is a Python-only enhancement; Rust ≡ Python-stdlib. Fixtures split into `fixtures/metadata-core/` (parity-tested) and `fixtures/metadata-ner/` (Python-only).

### C3d `extract.phrases(text, keywords=None) -> list[str]`

Heuristic noun-phrase extractor. Words-between-stopwords pattern:
- Tokenize on whitespace + punctuation
- Collect runs of non-stopword tokens (length 2-5)
- Filter runs appearing more than once in the document (phrase significance)
- Dedupe, preserve first-appearance order

If `keywords` is supplied, also pull phrases containing any keyword. Rule-based, stdlib only.

### C3e `extract.correlate_facts(text) -> list[PhraseFact]`

Composes `extract.stats(text)` + term-frequency analysis. For each numeric fact, identifies the "entity" it refers to by walking the containing sentence and picking the most-frequently-referenced noun phrase (from `extract.phrases`). Groups by entity: output is entities appearing with ≥2 numeric facts, each pairing retained as a `PhraseFact`. Polarity inferred from cue words:

- `"grew", "increased", "rose", "up"` → `polarity="growth"`
- `"fell", "declined", "decreased", "down"` → `polarity="decline"`
- Otherwise → `polarity="absolute"` (or `"unknown"` if no number context)

Aggregator, not a new extractor. Zero new dependencies.

## Comparison matrix — the primary deliverable

After implementation, produce `benchmarks/quality/matrix-{date}.md` with the following axes:

| Method | Summary chars | Time p50 (ms) | Extra data attached | A1 rubric | A4 Qwen |
|---|---|---|---|---|---|
| `skimr/tfidf mode=legacy` | … | … | — | … | … |
| `skimr/tfidf mode=default` | … | … | — | … | … |
| `skimr/tfidf mode=default +stats` | … | … | N stats | … | … |
| `skimr/tfidf mode=default +outline` | … | … | N sections | … | … |
| `skimr/tfidf mode=default +all` | … | … | stats+outline+meta+phrases | … | … |
| `skimr/tfidf mode=coverage` | … | … | — | … | … |
| `skimr/tfidf mode=coverage +all` | … | … | stats+outline+meta+phrases | … | … |
| `rust-skimr/tfidf mode=default` | … | … | — | (same as Python) | (same) |
| `rust-skimr/tfidf mode=default +stats +outline` | … | … | (N stats, N sections) | (same) | (same) |
| `sumy/LexRank` | … | … | — | … | … |
| `sumy/TextRank` | … | … | — | … | … |
| `sumy/LSA` | … | … | — | … | … |

Averaged across all 10 corpora. Each row's timing is p50 of 100 iterations. Enrichment counts are averaged across corpora.

**Quality axis:** A1 rubric score (manual, 250 max) and A4 Qwen judge score (cross-family, 50 max). Drop A2 ROUGE from the matrix — the previous review established it as an unreliable signal. Keep it in a footnote as a cautionary data point.

**Pass criteria for v0.2.0 release:**

1. `skimr/tfidf mode=default` rubric > sumy/TextRank rubric on 10-corpus aggregate.
2. End-to-end `mode=default +all` under 250 ms p50 on every corpus (warm spaCy). Under 10 ms p50 on core path with no NER.
3. Byte-identity maintained Python ↔ Rust across core (non-NER) fixtures.
4. All 10 corpora pass the new fixture walker.

## Gold-label extraction fixtures

Per-primitive gold data lives in:

```
fixtures/extract/stats/{corpus}.json         # list[Stat]
fixtures/extract/outline/{corpus}.json       # list[Section]
fixtures/extract/metadata/{corpus}.json      # Metadata (core fields only)
fixtures/extract/phrases/{corpus}.json       # list[str]
fixtures/extract/correlate/{corpus}.json     # list[PhraseFact]
```

Hand-labeled per corpus (~30 min/file × 10 corpora × 5 primitives ≈ 25 hours; parallelizable). Precision/recall measured against these; target ≥ 0.85 recall / ≥ 0.80 precision per primitive.

Eval harness: `benchmarks/extraction_eval.py`.

## Cross-language parity plan

Python ships first; Rust follows per-feature (subagent-driven per the existing Plan 2 pattern). Fixtures land with Python; Rust passes them after port. Target: Rust parity within same v0.2.0 release — **byte-identity maintained for core path; NER extra is Python-only by design**.

Feature-by-feature:

| Feature | Python | Rust | Byte-identity? |
|---|---|---|---|
| C1 scorer tweaks | ✓ | ✓ (port composite_score) | Yes |
| C2 coverage mode | ✓ | ✓ (port selector) | Yes |
| summarize(attach=...) | ✓ | ✓ (return struct) | Yes |
| extract.stats | ✓ | ✓ (regex port) | Yes |
| extract.outline | ✓ | ✓ (port heading detect) | Yes |
| extract.metadata core | ✓ | ✓ (regex port) | Yes |
| extract.metadata NER | ✓ (skimr[ner]) | — | Python-only by design |
| extract.phrases | ✓ | ✓ (port heuristic) | Yes |
| extract.correlate_facts | ✓ | ✓ (compose ported primitives) | Yes |

## Non-goals

- **No neural summarization in core.** `skimr-neural` is a separate companion.
- **No document format extraction** (PDF, DOCX, HTML). `skimr-files` companion.
- **No language other than English.** Stopwords and regex patterns are English-specific.
- **No streaming summarization.** Input arrives as a single string.
- **NER in Rust.** Deferred to `skimr-neural` (ONNX-based); Python-only in skimr core.
- **ROUGE as a quality metric.** Demoted to a footnote; A1 + A4 are the signals.
- **PyPI / crates.io publication.** v0.2.0 ships to the GitHub repo only; registry publication is a separate decision.

## Risks and mitigations

**Risk: spaCy first-call latency blows the 250 ms budget.**
Mitigation: warm-load at process start (`skimr.extract.metadata.warmup()`), document the pattern in README, benchmark cold vs warm separately.

**Risk: C1 scorer changes break downstream consumers on byte-identity assumptions.**
Mitigation: `mode="legacy"` preserves v0.0.1 behavior byte-identical. Fixtures for legacy mode remain in `fixtures/tfidf/`; new fixtures for default mode in `fixtures/tfidf-v0.2/`.

**Risk: big-bang release means long iteration time before any user feedback.**
Mitigation: internal release milestones (C1 working → C3a-c working → full matrix ready) with commits pushed to main; "big-bang" means a single tag, not a single branch.

**Risk: hand-labeled gold files are subjective.**
Mitigation: gold files are public and reviewable. Alternative labels accepted via PR. A1 rubric already has this caveat; extending it.

## Sequencing within v0.2.0

Big-bang release, single tag. Internal milestones in priority order (each commits incrementally to main):

1. **M1 — C1 scorer in Python** (~3 days). Heading filter + cue-phrase boost + digit bonus + section-position weight. Fixtures regenerated for new behavior. Re-run A1+A2+A4 on the 10-corpus set. Ship when skimr/tfidf beats sumy/TextRank rubric.
2. **M2 — C1 Rust port** (~2 days). Byte-identity maintained.
3. **M3 — `summarize(mode="coverage")` Python + Rust** (~2 days). C2 coverage mode.
4. **M4 — `SummaryResult` + `attach=` plumbing** (~1 day). Shared pipeline state; pre-parse once.
5. **M5 — `extract.outline` Python + Rust** (~2 days). Gold fixtures + eval.
6. **M6 — `extract.stats` Python + Rust** (~3 days). Gold fixtures + eval.
7. **M7 — `extract.metadata` core (stdlib) Python + Rust** (~2 days). Regex patterns for dates/amounts/URLs.
8. **M8 — `extract.metadata` NER extra** (~2 days). spaCy integration. Python-only. Warmup helper.
9. **M9 — `extract.phrases` Python + Rust** (~2 days).
10. **M10 — `extract.correlate_facts` Python + Rust** (~2 days). Composition only.
11. **M11 — Comparison matrix generator** (~2 days). `benchmarks/matrix_eval.py` + the deliverable matrix doc.
12. **M12 — Benchmark pass under 250 ms** (~1 day). Profile, fix any hot spot. Ship.

Total: ~24 days of focused work. Parallelizable across Python/Rust via subagents; realistic calendar ~3 weeks with sustained focus.

## Open questions

None at this point — all design details fixed above. If any ambiguity surfaces during implementation, escalate before guessing.

## Success criteria

1. **SC-A**: `skimr/tfidf mode=default` rubric (A1) aggregate > sumy/TextRank rubric on 10-corpus set.
2. **SC-B**: `summarize(attach=["stats","outline","metadata","phrases","correlated_facts"])` end-to-end p50 < 250 ms (warm spaCy) on every corpus.
3. **SC-C**: Core (non-NER) path byte-identical Python ↔ Rust on every fixture.
4. **SC-D**: Every extract.* primitive scores ≥ 0.85 recall / ≥ 0.80 precision against gold fixtures.
5. **SC-E**: Comparison matrix doc at `benchmarks/quality/matrix-{date}.md` shows concrete numbers for every row.
6. **SC-F**: chunkshop's `summary_embed` and metadata-extractors briefs can consume these primitives as documented in `docs/integration-memo.md` without skimr needing chunkshop-specific code.

## References

- Prior quality review: [`benchmarks/quality/review-2026-04-21.md`](../benchmarks/quality/review-2026-04-21.md)
- Integration memo: [`docs/integration-memo.md`](integration-memo.md)
- Comparison with Sumy + LLM: [`docs/comparison.md`](comparison.md)
- chunkshop briefs referenced: Mission-Brief-summary-embed, Mission-Brief-metadata-extractors, Mission-Brief-schema-flexibility (in chunkshop repo)
