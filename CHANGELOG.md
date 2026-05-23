# Changelog

lede's release notes. Tag annotations on each `vX.Y.Z` git tag are the
canonical record; this file is a human-readable summary in one place.

Entries below `## [0.2.2]` reference the project under its previous name,
`skimr`. The v0.0.1 / v0.2.0 / v0.2.1 / v0.2.2 git tags + GitHub Releases
remain as `skimr` releases — they were real shipped artifacts under that
name. See the v0.3.0 entry for the rename rationale.

## [0.4.3] — 2026-05-23

### Added

- **`headings: Sequence[str] | None` kwarg on `summarize`.** Caller-supplied
  heading lines that replace auto heading-detection when non-empty.

  Motivation: the auto-detector recognises Markdown-style headings (`#`, `##`,
  …).  Documents such as SCOTUS opinions, regulatory filings, and transcripts
  use caption-style labels (`BACKGROUND`, `I.`, `FINDINGS`) that
  `lede.extract.toc()` returns empty for.  Callers can supply the known heading
  lines — from chunk metadata, a prior `toc()` call, or a document index — and
  get fully structured output without touching the heading-detection heuristics.

  Behaviour when `headings` is non-empty:

  - **`keep_headings=True`** — headings are matched against the sentence list
    verbatim (stripped).  The first heading in the list is always emitted at
    the top of the body as the document title.  Unmatched headings (e.g.
    `"CONCLUSION"` when the word doesn't appear in the body) survive as a
    leading block immediately after the title.  Matched headings interleave at
    their body position in document order.  `SummaryResult.pinned_headings`
    lists every heading emitted, in emission order.

  - **`include_toc=True`** — a flat TOC is rendered from the supplied list
    (deduplicated, original order) instead of running `extract.outline` on the
    text.

  - Both `keep_headings` and `include_toc` can be combined; the TOC block
    prepends the structured body in the usual order.

  - Has no effect when both `keep_headings` and `include_toc` are `False`.

  - Rejected in `mode="legacy"` with a `ValueError` (same restriction as the
    other v0.4 structural kwargs).

  - Composes with `hints`, `hint_focus`, `hint_mode`, and `pin`.

  - Default `None` — auto-detection runs as before; output is byte-identical
    to v0.4.2.

- **`fixtures/v0_4_3_headings` parity walker** — new fixture set covering
  multiple corpora × headings configurations, enforced by
  `rust/tests/fixtures.rs`.  Python↔Rust byte-identical output is a hard CI
  gate.

- **First-class Python CLI surface.** The `lede` Python command now exposes
  current library features: summary modes, `brief`, extraction primitives
  (`stats`, `key_facts`, `metadata`, `outline`, `toc`, `phrases`,
  `correlate_facts`, `top_terms`), hints, heading retention, caller-supplied
  headings, `pin`, backend selection, spaCy registration/warmup, and
  `--output text|markdown|json`.

- **API output helpers.** `SummaryResult` now has `to_dict()`, `to_json()`,
  and `to_markdown()`. Generic helpers `lede.to_data`, `lede.to_json`, and
  `lede.format_result` are exported for callers that want consistent
  JSON/Markdown rendering without going through the CLI.

- **CLI and agent docs.** Added `docs/cli.md` and
  `docs/llms-agents-reference.md`, plus refreshed active docs for current CLI,
  spaCy, output-format, and version guidance.

### Notes

- `is_structural_heading` (the auto-detection heuristic) is **not modified**
  in this release.  Broadening auto-detection to cover caption-style patterns
  is deferred — the `headings=` override is the explicit opt-in path for
  non-Markdown documents.

- `lede-spacy` 0.4.3 and the `lede` Rust crate 0.4.3 are version-lock bumps
  with no functional change.

## [0.4.2] — 2026-05-22

### Added

- **`keep_headings`, `include_toc`, `pin` kwargs on `summarize`.** Optional
  heading and line-pin retention for the extractive body.

  - `keep_headings: bool` (default `False`) — auto-detects Markdown headings
    in the input and re-inserts them at their original document positions in
    the summary.  The document title (depth-1 heading) is always pinned at
    the top; deeper headings interleave in document order.
  - `include_toc: bool` (default `False`) — prepends a full table-of-contents
    (depth ≥ 2 headings, indented) before the body.
  - `pin: Sequence[str] | None` (default `None`) — caller-supplied lines
    forced verbatim into the output.  Lines are prepended in given order
    before the TOC and body.

  Prepend order is: `pin` block → TOC block → extractive body with woven
  headings.  All pinned content is additive — it does not consume the
  `max_length` budget; `max_length` governs only the extractive body.

  These kwargs work in default and coverage modes and compose with `hints`.
  They are rejected in legacy mode with a `ValueError`.

  Default-off: callers that pass none of the three kwargs get byte-identical
  output to v0.4.1.

- **`SummaryResult.pinned_headings: tuple[str, ...]`** — new field on the
  return value of `summarize`.  Contains the auto-detected headings injected
  by `keep_headings` (empty tuple otherwise).  `pin` lines and TOC entries
  are not recorded here.

- **`fixtures/v0_4_2_pins` parity walker** — new fixture set (10 corpora ×
  multiple pin configurations) enforced by `rust/tests/fixtures.rs`.
  Python↔Rust byte-identical output is a hard CI gate.

- **`lede-spacy` 0.4.2** — fixes a crash in `expand_hints(kinds=("similar",))`
  when the spaCy model has no word vectors.

## [0.4.1] — 2026-05-22

### Added

- **`extract.top_terms(..., with_scores=True)`.** Returns
  `tuple[TermScore, ...]` instead of `tuple[str, ...]`, where `TermScore`
  is a `NamedTuple` `(term, score, kind)` in the same unified ranked order.
  `score` is the per-kind-normalized salience that drove the ranking (plus
  the `hint_bonus` in soft-hint mode); `kind` is `"word"` or `"phrase"`.
  Lets downstream consumers store real relevance scores and the word/phrase
  distinction in a single call, without per-kind calls or merge heuristics.
  Default `with_scores=False` returns the v0.4.0 `tuple[str]` byte-for-byte.
- **`lede.extract.TermScore`** — the new `NamedTuple` return record.
  Tuple-unpackable (`for term, score, kind in result`) and name-accessible
  (`ts.term` / `ts.score` / `ts.kind`).

### Notes

- Scores are normalized **within each kind independently**, so a word at
  `1.0` and a phrase at `1.0` are each top-of-their-kind, not equal on a
  shared cross-kind scale. Treat them as per-kind salience, not a global
  composite. See `lede.extract.TermScore` and `docs/REFERENCE.md`.
- `lede-spacy` 0.4.1 and the `lede` Rust crate 0.4.1 are **version-lock
  bumps with no functional change** — `top_terms` (and therefore
  `with_scores`) remains Python-only; the Rust mirror is still deferred to
  v0.5.

## [0.4.0] — 2026-05-21

### Added

- **Hint-biased extraction.** Optional `hints`, `hint_focus`, `hint_mode`
  kwargs added to `summarize`, `brief`, `extract.key_facts`,
  `extract.phrases`, `extract.correlate_facts`, and the new
  `extract.top_terms` primitive. Callers pass a list or weighted dict of
  terms; lede biases sentence/fact/phrase selection toward content
  mentioning those terms.

  - `hints: list[str] | dict[str, float]` — hint terms. List entries get
    weight 1.0; dict values are numeric weights.
  - `hint_focus: float` (default `0.7`) — fraction of the selection budget
    reserved for hint-matching candidates (chars for `summarize`; count
    for `key_facts`; validated but no-op for `phrases`, `correlate_facts`,
    `top_terms`).
  - `hint_mode: "soft" | "hard"` (default `"soft"`) — soft adds a bonus and
    reorders without filtering; hard restricts the hint pool to
    hint-matching candidates only.

  See `docs/REFERENCE.md` "Hint biasing" for the full contract.

- **`lede.extract.top_terms(text, *, n=10, kinds=("words", "phrases"))`** —
  new primitive returning the top-N salient words and/or phrases in a
  unified ranking. Composes single-word TF-IDF with multi-word phrase
  frequency. Accepts the same `hints` / `hint_focus` / `hint_mode` kwargs.
  Python-only for v0.4; Rust mirror deferred to v0.5.

- **`lede_spacy.expand_hints(hints, *, kinds=("lemma",), top_k=5, expand_weight=0.5)`** —
  companion function for expanding hint terms before passing them to any
  lede primitive. Three expansion strategies:
  - `"lemma"` — spaCy lemmatizer (any spaCy model).
  - `"synonyms"` — WordNet via nltk (requires `lede-spacy[synonyms]`).
  - `"similar"` — spaCy word-vector cosine similarity (requires
    `en_core_web_md` or `en_core_web_lg`).

- **`lede-spacy[synonyms]` extra** — new optional extra on the `lede-spacy`
  companion package. Pulls `nltk` and the `wordnet` corpus. Required for
  `expand_hints(kinds=("synonyms",))`.

- **`v0_4_hints_byte_identical` parity walker** — new fixture gate in
  `rust/tests/fixtures.rs`. Covers 140 fixtures (10 corpora × 14 hint
  configurations) verifying byte-identical Python ↔ Rust output for
  `summarize`, `brief`, and `key_facts` with hints. Runs on every push.

### Backward compatibility

Callers that do not pass `hints` see byte-identical output to v0.3.0 across
all primitives. The existing `every_fixture_byte_identical` and
`v0_2_extract_primitives_byte_identical` fixture walkers continue to pass
unchanged. No existing API surface was removed or changed.

### Changed (Rust crate — breaking for direct struct users)

- `KeyFactsOptions` and `BriefOptions` structs are no longer `Copy` — they
  now hold `Vec<HintWeight>` for the hint kwargs. Callers using `Copy`
  semantics need to clone explicitly or pass by reference.

## [0.3.0] — 2026-04-28

**Renamed: `skimr` → `lede`.** No behavior, fixture, or output changes;
this is a wholesale rename to avoid namespace conflict with the
well-known `skimr` R package. New install / import:

```bash
pip install lede
```

```python
from lede import summarize
```

Companion package: `skimr-spacy` → `lede-spacy`, module
`skimr_spacy` → `lede_spacy`. Rust crate: `skimr` → `lede`. Repo:
`yonk-labs/skimr` → `yonk-labs/lede` (GitHub auto-redirects the old
URL).

The historical `v0.2.x` `skimr` tags + GitHub Releases stay as-is for
archaeology — they were real releases, just under the old name.

### Migration

```bash
# Python
pip uninstall skimr skimr-spacy
pip install lede           # or: pip install lede[wordforms,yake,textrank]
pip install lede-spacy     # if you used the spaCy companion
```

```diff
- from skimr import summarize, brief, clean_text, strip_think, extract_keyword
+ from lede   import summarize, brief, clean_text, strip_think, extract_keyword

- from skimr.extract import stats, outline, metadata, phrases, correlate_facts
+ from lede.extract  import stats, outline, metadata, phrases, correlate_facts

- import skimr_spacy
+ import lede_spacy
```

```toml
# Rust Cargo.toml
- skimr = { version = "0.2.2" }
+ lede  = { version = "0.3.0" }
```

```rust
- use skimr::{summarize, Mode};
+ use lede::{summarize, Mode};
```

Other than the rename, identical to v0.2.2.

## [0.2.2] — 2026-04-27

**Docs-only patch.** No code changes; behavior, fixtures, and public
API unchanged from `v0.2.1`. This release rolls up the documentation
work that landed between the `v0.2.1` tag and the public-flip click,
plus the prod-ready audit's day-1 paper cuts.

### Added
- **`docs/guide.md`** — user-facing tutorial. 9 lessons walking through
  every feature with actual outputs and "change this knob, see what
  happens" prompts. Each lesson tags whether the snippet is byte-
  identical in Rust or Python-only with rationale.
- **`docs/REFERENCE.md` § Runtime parity** — explicit per-feature
  Python vs Rust availability matrix. Calls out which Python-only
  features (`textrank`, `yake`, spaCy NER) are feasible-to-port-but-
  not-yet vs which are deliberately Python-only by contract.
- **`packages/skimr-spacy/README.md` rewrite** — user-facing pitch
  with a real side-by-side example: same input through `backend="regex"`
  (returns `entities=()`) and `backend="spacy"` (returns 11 entities).
  Performance numbers measured locally. Decision criteria (when to
  use, when not to) called out explicitly.
- `SECURITY.md` § "Known transitive dependency notes" — documents the
  `rand 0.7.3` `unsound` advisory (RUSTSEC-2026-0097) that surfaces
  under `cargo audit` when the `wordforms` cargo feature is enabled.
  Practical exposure on the `wordforms` path is effectively zero
  (skimr ships no custom logger); documented per public-OSS hygiene.

### Fixed (paper cuts from the v0.2.1 prod-ready audit)
- `CONTRIBUTING.md` and `CLAUDE.md` cited stale test counts (181 / 116);
  updated to soft `~230` / `~120` so future test additions don't
  require an immediate doc edit.
- `CLAUDE.md` Status block: `v0.2.0 shipped 2026-04-26` →
  `v0.2.1 shipped 2026-04-27`.
- `README.md` Apollo-example timing claim (`Time: 0.16 ms`) was
  ambiguous about which runtime; now reads `~0.15 ms (Python, p50 of
  50 runs on this paragraph)` with the cross-corpus p50 (Python 0.42
  ms, Rust 0.13 ms) cited for context. Same treatment on the
  `attach=` timing.
- `.github/workflows/test.yml` `pip-audit --ignore-vuln GHSA-rrqc-c2jx-6jgv`
  flag dropped — the suppression had no comment and the advisory was
  no longer flagged by `pip-audit --strict` anyway. Replaced with an
  inline comment explaining the warn-only triage policy and how to
  add a properly-documented suppression in the future.

## [0.2.1] — 2026-04-27

**Patch release — public-flip readiness.** No new API surface; this is
a quality, robustness, and presentation pass on top of v0.2.0.
External callers of `summarize()` / `brief()` / `skimr.extract.*` see
the same shapes; existing fixture bytes are preserved. The v0.2 design
contract is unchanged.

### Fixed (real bugs)
- **ReDoS in `extract.stats`** — Python `re` engine took **224 s** on a
  50 K-digit input followed by a near-unit keyword. Numeric quantifiers
  bounded to `\d{1,15}` and sentences with 20+ digit unbroken runs
  skipped. Now **1.5 ms** on the same input. Mirrored in Rust for
  parity. Two new regression tests in each language.
- **Rust `extract::stats::ctx()` UTF-8 panic and Python ↔ Rust drift** —
  the ±25-char context window was 25 *bytes* in Rust vs 25 *chars* in
  Python. Em-dashes / accented Latin / emoji adjacent to a stat token
  pushed the two outputs 2+ bytes apart and could panic Rust on a
  multi-byte boundary. Now char-counted on both sides; the new
  per-fixture parity walker enforces this.
- **Python CLI mojibake on non-UTF-8 locales** — `Path.read_text()`
  picked up the OS default encoding (cp1252 on Windows). Forced
  UTF-8 for both file and stdin reads; restores parity with the
  Rust CLI.
- **Rust CLI swallowed stdout write errors** — `let _ =` ate
  `BrokenPipe` and other I/O errors. Now `BrokenPipe` (user piped
  into `head`) returns 0; other errors propagate to non-zero exit.
- **Sentence splitter NUL panic** — Rust used `assert!` on the
  internal sentinel byte; PDF-extracted text and ETL outputs can
  contain NULs. Now silently stripped in both languages.
- **Sentence splitter "no." handling** — the unconditional `"no"`
  abbreviation merged "He said no. Then he left." into one sentence.
  Now context-sensitive: `"No. 5"` is protected; bare `"no."` is not.
- **Coverage paragraph mapping** — substring-based "first containing
  paragraph wins" biased coverage on docs with template/FAQ-style
  repeated sentences. Now occurrence-counted: K-th occurrence → K-th
  matching paragraph.
- **Coverage join separator** — was `"\n"` while default and legacy
  modes used `" "`. Now `" "` in all three for byte-stability across
  modes.
- **`extract_keyword` empty-keys footgun** — silent `LEFT(text, 2000)`
  chop is gone; empty/all-filtered keywords now return `""` in both
  languages.
- **`metadata.dates` bare-years claim** — `extract.metadata` regex
  now matches `(?:19|20)\d{2}` years to match the doc and parallel
  `extract.stats._DATE_RE`.
- **Four `.expect("no NaN")` panic sites in Rust** — replaced with
  `.unwrap_or(Ordering::Equal)`. NaN in pipeline scores now degrades
  to deterministic Equal rather than panicking the worker.
- **Rust 1.93 `clippy::cast_sign_loss` regression in `brief.rs`** —
  allow-listed with a justification comment; the cast is provably
  non-negative.

### Added
- **Per-fixture v0.2 parity walker** — 70 fixtures (7 primitives × 10
  corpora) byte-identical between Python and Rust. Enforces SC-C on
  the v0.2 differentiator surface, not just the v0.1 four-function
  contract. Caught the `ctx()` char-vs-byte drift above.
- **Edge-case fixtures** (`fixtures/edge_cases/`) — multibyte UTF-8,
  CP1252 smart quotes, 50K-digit ReDoS bait, ~1 MB document. 50
  parametrized tests across 10 primitives × 5 fixtures.
- **CI matrix expansion** — `tests` workflow installs `[dev,textrank,
  wordforms,yake]` and verifies each extra path. New `skimr-spacy`
  workflow runs the 17 companion-package tests + downloads the
  `en_core_web_sm` model. Both `cargo audit` and `pip-audit` run on
  every push (warn-only on findings).
- **`brief()` explicit `convert_word_names` kwarg** — Python and Rust
  now accept an explicit override (`None` = auto-detect for
  back-compat; `True` / `False` locks parity across runtimes
  regardless of which extras are installed).
- **`docs/comparison.md`** — worked side-by-side examples of skimr
  vs Sumy LexRank/TextRank/LSA vs LLM API on real corpora, with
  measured timings from the benchmark suite.
- **`docs/v0-2-design.md` + `docs/skimr-spacy-integration.md`** —
  promoted from buried `docs/superpowers/specs/` paths. Same content,
  cleaner public-facing location.
- **Status badges in README** — 4 CI workflow badges + release +
  license + Python 3.10+ + Rust 1.85+.
- **Plain-language README opening + Apollo 11 quick example** —
  replaces the academic "deterministic, zero-dependency
  text-shrinker" framing with a concrete demonstration.
- **`MAINTAINERS.md`** — single-maintainer disclosure with bus-factor
  honesty + decision authority + release cadence.
- **`SECURITY.md`** — private report path + threat model scope.
- **`CONTRIBUTING.md`** — quick-start + parity contract + style
  notes + CI overview.
- **`examples/` directory** — 7 runnable scripts covering quickstart,
  the `attach=` RAG-prep API, `brief()`, each extract primitive
  standalone, paragraph-chunked pipeline for long docs, the
  `skimr-spacy` companion, and the `[wordforms]` extra. CI smoke-runs
  the no-extras-needed ones on every push.
- **Heading-pattern shared helper** — heading regexes live in
  `_headings.{py,rs}` only; previously-duplicated 70-line copies in
  `extract/outline.{py,rs}` deleted.
- **Scaling notes in `docs/REFERENCE.md`** — typical-document p50
  table, large-document warnings, recommended chunking pattern for
  >100 KB inputs.
- **GitHub Release object** for `v0.2.0`.

### Changed
- **`networkx` pin** — `networkx>=3.0,<3.5` because `skimr.textrank`
  uses `_pagerank_python` (private API; underscore prefix). Drop the
  upper bound when textrank is rewritten against the public API.
- **`pyproject.toml` Development Status classifier** —
  `3 - Alpha` → `4 - Beta`. 427 tests, tagged release, CI green is
  past alpha.

### Removed (transient or pre-skimr)
- `docs/RESUME.md` — agent session-state.
- `skill-output/` — research, audit, and session artifacts; now
  gitignored.
- `summarize-output.py` — original Python prototype, predates skimr.
- `extractive-performance.md` — pre-skimr benchmark notes (superseded
  by `benchmarks/quality/matrix-2026-04-26.md`).
- `SUMMARIZATION.md`, `extractive_functions.{sql,md}` — original
  algorithmic spec and PL/pgSQL reference. Provenance comments in
  source updated to describe the algorithm directly without name-
  checking the now-removed files.
- `docs/upstream-context-yonk-taskstash.md` — wrong project's context.
- `docs/superpowers/plans/` — executed implementation plans.

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
