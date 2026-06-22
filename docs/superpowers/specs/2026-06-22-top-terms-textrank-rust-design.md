# top_terms + textrank (lede core Rust) — design spec

**Status:** draft for review
**Date:** 2026-06-22
**Tracks:** [`lede#7`](https://github.com/yonk-labs/lede/issues/7) — sibling of #5/#6
**Consumer:** chunkshop-rs `#76` (`lede_top_terms` extractor, blocked on this)

## 1. Goal

Bring two things to the lede **core** Rust crate:
1. **`top_terms`** — top-N salient words/phrases primitive, **byte-identical** to
   Python `extract/top_terms.py`. Foundational; unblocks chunkshop `lede_top_terms`.
2. **textrank backend** — term-level PageRank over a co-occurrence graph, a
   keyphrase-ranking backend, **capability-parity only** (no byte-identical
   promise, like the spaCy/yake backends).

This is **core** work (not a companion crate) → it lives in `rust/src/extract/`
and is under the **byte-identical parity contract + fixture walker** for the
default `top_terms` path.

## 2. Key finding — two different "textrank"s

`src/lede/textrank.py` already exists but is **sentence-level** TextRank
(`summarize_textrank`: cosine sentence-similarity graph → PageRank → top
*sentences*, for summarization). Issue #7's backend is **term-level** TextRank
(co-occurrence graph over tokens → ranked *keyphrases*, à la Mihalcea–Tarau).
**The term-level variant does not exist in Python.** Because the textrank backend
is capability-parity only, Rust implements it directly; a Python term-level twin
is optional (§7 decision). The existing sentence-level `summarize_textrank` is
**out of scope** here.

## 3. Scope

**In (slice 1 — `top_terms`, byte-identical):**
- Mirror `_word_scores` (per-doc TF-IDF) and `_phrase_scores` (count×token_count)
  exactly, reusing the Rust core's existing tokenizer, `_STOPWORDS`, IDF, and
  `phrases` internals.
- Merge → hints (soft/hard) → sort `(-score, term)` → top-N.
- `with_scores` → new `TermScore { term, score, kind }` (mirrors Python NamedTuple).
- Extend the parity fixtures + walker with a `top_terms` primitive.

**In (slice 2 — textrank backend, capability-parity):**
- Pure-Rust term-level PageRank over a co-occurrence window. Zero new deps.
- Exposed as a `top_terms` method/backend (`Method::TextRank`) or `textrank_terms()`.
- Deterministic, but **off the fixture walker** (no byte-identical promise).

**Deferred / out:**
- yake backend — open decision per #7; not M1.
- Python term-level textrank twin — optional (§7).
- Sentence-level `summarize_textrank` — already exists in Python, separate feature.

## 4. Slice 1 — `top_terms` (byte-identical)

Mirror `src/lede/extract/top_terms.py` precisely:

- **Word scores:** tokens via the core's `_TOKEN_RE` equivalent (3+ letters,
  lowercased), drop `_STOPWORDS`; `TF` = total occurrences, `IDF =
  log((n_sents+1)/(df+1)) + 1.0` (the same IDF `summarize` uses → already
  byte-identical in Rust), `raw = TF*IDF`, normalize by max.
- **Phrase scores:** candidates from the core's `phrases` extractor
  (`_regex_phrases`/`_runs` equivalents); `raw = count × token_count`, normalize
  by max.
- **Merge:** words then phrases. Keyspaces never collide (words have no space,
  phrases always do), so the Python "phrase shadows word" note is moot in practice.
- **Hints:** reuse `lede::hints` `preprocess_hints`/`hint_bonus`; soft = add bonus,
  hard = keep only matching. Validate `hint_focus ∈ [0,1]`, `hint_mode ∈
  {soft,hard}` (errors mirror Python).
- **Rank:** sort by `(-score, term)`; take N. `with_scores` → `Vec<TermScore>`.

**Float parity:** `f64`, same operation order as Python → IEEE-754 deterministic,
exactly as the existing `summarize` TF-IDF parity already proves.

**Public API (mirrors Python kwargs via an options struct):**
```rust
// rust/src/extract/top_terms.rs
pub struct TermScore { pub term: String, pub score: f64, pub kind: String }
pub struct TopTermsOptions {       // n, kinds, with_scores, hints, hint_focus, hint_mode
    pub n: usize, pub kinds: Vec<String>, pub hints: Vec<HintWeight>,
    pub hint_focus: f64, pub hint_mode: HintMode,
}
pub fn top_terms(text: &str, n: usize) -> Vec<String>;
pub fn top_terms_with_options(text: &str, opts: &TopTermsOptions) -> Vec<String>;
pub fn top_terms_scored(text: &str, opts: &TopTermsOptions) -> Vec<TermScore>;
```
Re-export from `extract/mod.rs`. Add a `top_terms` parity format fn in `parity.rs`.

**Fixtures:** extend `benchmarks/gen_parity_fixtures.py` to emit `top_terms`
fixtures across the corpus; add `top_terms` to `rust/tests/fixtures.rs` dispatch.
This is the v0.2-extract-surface parity gate (`v0_2_extract_primitives_byte_identical`).

## 5. Slice 2 — textrank backend (capability-parity)

- **Graph:** nodes = candidate terms (non-stopword 3+ letter tokens; phrases
  optional later). Edges = co-occurrence within a sliding window (default W=4),
  weight = co-occurrence count. Undirected.
- **PageRank:** power iteration, damping `d=0.85`, fixed `max_iter` (e.g. 50) +
  `tol` (e.g. 1e-6), uniform init. **Deterministic:** iterate nodes in **sorted**
  order, accumulate in a fixed order (no `HashMap` iteration in the update loop —
  use a sorted `Vec` index), per lede's no-hash-order rule.
- **Output:** terms by PageRank score desc, tie-break on term; top-N.
- **Parity:** Rust-internal reproducibility only. **No fixture-walker entry**
  (consistent with the spaCy/yake backend policy). Zero new deps.

## 6. Determinism

- `top_terms` default: byte-identical, fixture-gated.
- textrank: same input → same bytes across runs/platforms; sorted node order +
  fixed iteration count/tol + `f64` fixed-order summation. No hash-iteration-order
  dependence.

## 7. Open decision (for review)

**Python term-level textrank twin — build it or Rust-only?**
The term-level textrank backend has no Python equivalent. Options:
- **(A) Rust-only (recommended for M1):** Rust delivers the capability (unblocks
  chunkshop); since it's capability-parity, no Python twin is required. Add the
  Python twin later for API symmetry if a Python caller wants it.
- **(B) Build both now:** symmetric API, more work, still no byte-parity.

Recommend **(A)** — ship the Rust capability that chunkshop needs; defer the
Python twin until asked.

## 8. Test plan

- Slice 1: parity fixtures (byte-identical) + Rust unit tests (word/phrase
  scoring, hints soft/hard, `with_scores`, empty input, `kinds` validation).
- Slice 2: determinism test + a sanity golden (a doc with a clearly dominant
  co-occurring term ranks it top). Rust-only; not on the walker.

## 9. Build order (tree green between)

**Slice 1 — `top_terms`:** `extract/top_terms.rs` + `TermScore` → reuse
tfidf/phrases/hints internals → re-export → parity format fn → extend
`gen_parity_fixtures.py` + `fixtures.rs` → `cargo test` (incl. fixture walker) +
Python parity green.

**Slice 2 — textrank backend:** pure-Rust PageRank → wire as a `top_terms`
method/`textrank_terms()` → determinism + sanity tests → green.

## 10. Risks

| Risk | Mitigation |
|---|---|
| Phrase-scoring parity (must match `_regex_phrases`/`_runs` exactly) | Reuse the core's existing phrases internals; verify via fixtures |
| Float byte-parity | Match Python operation order; the existing summarize TF-IDF parity proves it's achievable |
| textrank nondeterminism | Sorted node order, fixed iterations/tol, no HashMap iteration in the update |
| Touching the parity-locked core | Slice 1 gated by the fixture walker before merge; CI runs all four workflows |
