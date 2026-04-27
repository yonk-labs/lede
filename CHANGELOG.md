# Changelog

skimr's release notes. Tag annotations on each `vX.Y.Z` git tag are the
canonical record; this file is a human-readable summary in one place.

## [0.2.0] — 2026-04-26

**v0.2 is the RAG-prep primitive.** A single `summarize(attach=…)` call
now returns a summary plus structured stats / outline / metadata /
phrases / correlated-facts in sub-5 ms. New top-level `brief()` composes
a paste-ready overview. The `skimr.extract.*` namespace exposes every
primitive standalone.

### Added
- `summarize(text, max_length, *, mode="default", attach=…)` — returns
  `SummaryResult` with `.summary` plus optional structured enrichments.
  `str(r)` and `f"{r}"` still evaluate to the summary string for
  legacy callers.
- `Mode::Default` (Rust) / `mode="default"` (Python) — TF-IDF + position
  + length composite plus C1 scorer tweaks (heading filter, cue-phrase
  boost, digit bonus, section-position weight).
- `Mode::Coverage` / `mode="coverage"` — paragraph-aware coverage
  selection that tries to land at least one sentence per paragraph
  before greedy-filling.
- `Mode::Legacy` / `mode="legacy"` — preserves v0.0.1 60/25/15 bytes.
- `skimr.brief(text, *, format="string"|"markdown"|"dict")` — composes
  summarize + key_facts + toc.
- `skimr.extract.outline(text)` — section headings + key sentence.
- `skimr.extract.toc(text)` — section names only.
- `skimr.extract.stats(text, *, convert_word_names=False)` — numeric
  facts (money, percent, date, duration, count) with sentence context.
- `skimr.extract.key_facts(text, *, max_facts=10)` — sentences ranked
  by stat density.
- `skimr.extract.metadata(text, *, backend=None)` — dates, amounts,
  URLs, entities (entities require the spaCy backend).
- `skimr.extract.phrases(text, keywords=None)` — repeated multi-word
  n-grams (with `backend="yake"` available behind the `[yake]` extra).
- `skimr.extract.correlate_facts(text, *, backend=None)` — entity ↔
  number/polarity pairings.
- Optional `[wordforms]` extra (Python) and `wordforms` cargo feature
  (Rust) — both bind to the `text2num` crate so spelled-out numbers
  ("five thousand documents") surface as Stats with byte-identical
  output across runtimes.
- Optional `[yake]` extra — registers a YAKE backend for `phrases()`
  (Python only).
- Companion package `skimr-spacy` — provides spaCy-backed `entities`,
  `metadata`, `phrases`, and `correlate_facts` backends. Imports
  register themselves via `skimr.extract._backends`. Rust does not
  ship NER by design.

### Performance
- `summarize` core path: 0.42 ms p50 (Python) / 0.13 ms p50 (Rust),
  measured on the 10-corpus benchmark. Sumy LexRank/TextRank/LSA
  backends sit at 11–12 ms p50.
- `summarize(attach=[…all 5…])`: 2.40 ms p50 worst case 3.80 ms across
  10 corpora — still ~5× faster than any sumy backend while producing
  structured output sumy doesn't.
- See `benchmarks/quality/matrix-2026-04-26.md` for the method × corpus
  × time × enrichments grid.

### Quality
- SC-A (rubric) — `skimr/tfidf-v0.2` ranks #1 on the A1 5-dimension
  rubric and on the A4 cross-family Qwen judge across 10 corpora.
  Beats `sumy/TextRank` on both signals. See
  `benchmarks/quality/review-2026-04-21.md`.
- SC-D (extraction quality) — 3 of 5 primitives pass the gate
  (`stats`, `outline`, `metadata`) at recall ≥ 0.85, precision ≥ 0.80
  under the format-tolerant match rule. `phrases` (R 0.478) and
  `correlate_facts` (P 0.25) ship below the gate by design — the gold
  fixtures expect coreference + salience semantics that the regex
  primitive doesn't model. Tracked for v0.3+; documented in README's
  "Known v0.2 gates" section, `docs/REFERENCE.md`, and the v0.2.0 tag
  annotation.

### Hardening (this release also includes the public-flip cleanup)
- ReDoS guard in `extract.stats()`: numeric quantifiers bounded to
  `\d{1,15}` and sentences containing a 20+ digit unbroken run are
  skipped. Mirror in Rust for byte-identical parity even though Rust's
  regex engine is RE2 and structurally immune. A 50 K-digit input that
  previously hung Python for 224 s now completes in 1.5 ms.
- UTF-8 char-boundary snap in Rust `extract::stats::ctx()` — accented
  Latin / emoji adjacent to a stat token previously panicked on the
  byte-window slice.
- Python CLI forces UTF-8 file + stdin reads — fixes mojibake on
  Windows / non-UTF-8 locales and restores parity against the Rust
  CLI.

### Documentation
- `README.md` — new "What's new in v0.2" section, updated install path
  (skimr is not yet on PyPI), "Known v0.2 gates" disclosure.
- `docs/REFERENCE.md` — full primitive catalog (all 7 extract
  primitives + `summarize(attach=…)` + `brief()` 3 formats).
- `docs/integration-memo.md` — refreshed to reflect the v0.2 RAG-prep
  API for chunkshop's `summary_embed` / `metadata-extractors` consumers.
- `MAINTAINERS.md` + `SECURITY.md` + this `CHANGELOG.md` — added for
  public-flip hygiene.

## [0.0.1] — early reference tag

Original tagged commit, predates the v0.2 differentiation. Not
recommended for new use; included in the tag list only as historical
record.
