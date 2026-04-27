# Integration Memo — skimr in chunkshop

**Status:** Design agreed; runtime before/after pending chunkshop Brief 4 implementation.
**Date:** 2026-04-26 (refreshed for skimr v0.2.0).
**SC-009 evidence:** Partial — design/contract complete, quantitative before/after deferred until consumer code ships.

> **v0.2 update:** the four-function contract below remains supported and byte-stable; v0.2 layered on a richer `summarize(attach=…) -> SummaryResult` shape plus the `skimr.extract.*` namespace and the `skimr.brief()` composer. chunkshop wrappers can adopt the new shape incrementally — see [Adopting the v0.2 RAG-prep API](#adopting-the-v02-rag-prep-api) below.

This memo documents how `skimr` integrates into [`chunkshop`](https://github.com/yonk-labs/chunkshop) as its first real downstream consumer. It is deliberately **API-contract-focused**: there is **zero chunkshop-specific code in skimr**, and zero skimr-specific code in chunkshop. Integration lives entirely in chunkshop's wrappers.

## Consumer project

`chunkshop` is a standalone ingestion tool — Source → Chunker → Embedder → Extractor → pgvector. One YAML config drives one end-to-end ingest; multiple YAMLs run in parallel. It ships Python v0.2.0 today with Rust and Go ports planned.

Before this design, chunkshop had exactly one extractor (`rake_keywords`) and no concept of summarization in the pipeline. Summarization wasn't "replaced" — it's a **new capability** chunkshop gains by consuming skimr. For retrieval, chunkshop previously embedded raw chunk text, which is noisier than embedding a focused summary.

## Integration architecture

skimr's job is to expose four stable library functions. chunkshop's job is to wrap them in whatever pipeline shape it needs. Neither project names the other in its source.

| skimr exposes                                 | chunkshop consumes via                                                                    | Reference brief (chunkshop-side)        |
|-----------------------------------------------|-------------------------------------------------------------------------------------------|-----------------------------------------|
| `summarize(text, max_length) -> str`          | `summary_embed` wrapper — embeds summary instead of raw chunk                             | Mission-Brief-summary-embed             |
| `summarize(text, max_length) -> str`          | `hierarchical_summary` wrapper — emits fine rows + coarse summary rows linked by group id | Mission-Brief-summary-embed             |
| `extract_keyword(text, keywords, n) -> str`   | `callable_phrases` extractor variant — emits phrases into `ExtractResult.tags`            | Mission-Brief-metadata-extractors (ext) |
| `clean_text(text) -> str`                     | Source preprocessor chain — `Source.preprocessors: list[Callable[[str], str]]`            | Future Brief 5 (not yet drafted)        |
| `strip_think(text) -> str`                    | Source preprocessor chain — same mechanism                                                | Future Brief 5                          |

The contract chunkshop extractors write to is `ExtractResult(tags: list[str], metadata: dict)`, introduced in the [schema-flexibility brief](https://github.com/yonk-labs/chunkshop/blob/main/skill-output/mission-brief/Mission-Brief-schema-flexibility.md). Future skimr additions (e.g. structured metadata extraction from Thread C) flow through the same field without touching the contract shape.

## skimr API contract

The four functions above are part of skimr's stable public surface and have not changed signatures since the v0.0.1 reference. Their output bytes are deterministic and byte-identical across Python and Rust (`fixtures/` is the source of truth; `rust/tests/fixtures.rs` asserts parity on every CI push).

```python
from skimr import summarize, extract_keyword, clean_text, strip_think

summarize(text: str, max_length: int = 500) -> SummaryResult   # str(r)/f"{r}" yields the summary
extract_keyword(text: str, keywords: str, num_sentences: int = 10) -> str
clean_text(text: str) -> str
strip_think(text: str) -> str
```

```rust
use skimr::{summarize, extract_keyword, clean_text, strip_think};

skimr::summarize(text: &str, max_length: usize, mode: skimr::Mode) -> SummaryResult
skimr::extract_keyword(text: &str, keywords: &str, num_sentences: usize) -> String
skimr::clean_text(text: &str) -> String
skimr::strip_think(text: &str) -> String
```

`SummaryResult` is a thin wrapper over a `summary: String` field plus optional structured enrichments (see v0.2 section below). For chunkshop wrappers that just want the legacy string, `str(r)` / `f"{r}"` (Python) and `r.summary` (Rust) are the no-cost paths.

chunkshop wrappers may compose these freely. skimr does not know chunkshop exists.

## Adopting the v0.2 RAG-prep API

skimr v0.2.0 added a single-call RAG-prep primitive that returns a summary plus structured enrichments. chunkshop's existing wrappers can keep calling the four-function surface unchanged; **new** chunkshop work that wants per-chunk facts/sections/entities can pull them from one call instead of running multiple extractors.

```python
from skimr import summarize, brief
from skimr.extract import stats, outline, metadata, phrases, correlate_facts, toc, key_facts

r = summarize(
    chunk_text,
    max_length=500,
    mode="default",                              # also "coverage" / "legacy"
    attach=["stats", "outline", "metadata", "phrases", "correlated_facts"],
)

r.summary            # str — what summary_embed currently consumes
r.stats              # tuple[Stat]    — numeric facts with sentence context
r.outline            # tuple[Section] — section headings + key sentence
r.metadata           # Metadata(dates, amounts, urls, entities)
r.phrases            # tuple[str]     — repeated multi-word phrases
r.correlated_facts   # tuple[PhraseFact] — entity ↔ number/polarity pairs
```

How this maps to chunkshop's contracts:

| skimr v0.2 surface | chunkshop consumption (proposed/incremental) | Notes |
|---|---|---|
| `r.summary` | drop-in replacement for current `summarize()` calls in `summary_embed` / `hierarchical_summary` wrappers | zero migration; identical bytes via `mode="legacy"` if pinning needed |
| `r.stats`, `r.metadata.dates`, `r.metadata.amounts`, `r.metadata.urls` | `metadata` field of `ExtractResult` — structured per-chunk facts without a second pass | replaces the proposed `skimr.extract_metadata` shape from Thread C; the contract was already there |
| `r.metadata.entities` (requires `skimr[ner]` extra) | `tags` field of `ExtractResult` (PERSON/ORG/GPE) | optional — Rust path leaves `entities` empty; chunkshop opts in via the extra |
| `r.phrases`, `r.correlated_facts` | additional `metadata` keys, or upgraded `tags` | known v0.3+ work — design mismatch documented in `docs/REFERENCE.md` and the v0.2.0 tag annotation |
| `skimr.brief(chunk_text, format="dict")` | preview/citation generator for each chunk's coarse row in `hierarchical_summary` | one call yields overview + key facts + section names |
| `skimr.extract.toc(chunk_text)` | section-aware chunking heuristic in semantic chunker | replaces a manual heading regex |

**Migration discipline.** None of this is forced. The four legacy functions still exist and produce stable bytes. Adopting `attach=` is opt-in per chunkshop wrapper, and chunkshop's `ExtractResult(tags, metadata)` contract absorbs every new field without re-shaping.

## What chunkshop does with each

- **`summarize`**: Brief 4 defines two wrappers. `summary_embed` replaces `embedded_content` with the summary while preserving raw text in `original_content`. `hierarchical_summary` emits both fine chunks and coarse summary rows to the same pgvector table, linked by group id for "match coarse, return fine" retrieval.
- **`extract_keyword`**: proposed extension of Brief 1 (metadata-extractors). A `callable_phrases` variant takes a user-supplied callable whose signature matches skimr's `extract_keyword`, producing tags attached to each chunk. Keeps chunkshop origin-agnostic. (v0.2 alternative: `summarize(attach=["phrases"])` returns the same kind of thing in a single call.)
- **`clean_text` / `strip_think`**: proposed Brief 5 introduces `Source.preprocessors: list[Callable[[str], str]]` — a generic preprocessing chain. Users compose skimr's functions (or their own) to scrub filler/markdown/`<think>` blocks before chunking.

None of this requires chunkshop to depend on skimr. The contracts accept any Python callable with matching signatures. skimr happens to be the deterministic zero-dep implementation that ships with chunkshop's docs.

## Measurements (pending)

Honest status: no runtime before/after numbers exist yet. The design is agreed; the consumer code is pre-implementation.

Metrics to capture once Brief 4 (`summary_embed`) implementation lands in chunkshop:

- **Retrieval recall @ k** — identical query, identical k, measured before (raw chunk embedding) vs after (summary embedding) on chunkshop's shipped sample corpus. Expected: recall up, because the embedding space is less polluted by boilerplate.
- **Chunk storage size** — `original_content` byte count stays the same; `embedded_content` shrinks to summary length. Compression ratio is just `len(summary) / len(raw)`.
- **Ingest wall-clock overhead** — per-chunk skimr time is sub-millisecond on the legacy path. With `attach=["stats","outline","metadata","phrases","correlated_facts"]` (full RAG enrichment, regex backend), p50 stays ~2-4 ms across the 10-corpus benchmark — see [`benchmarks/quality/matrix-2026-04-26.md`](../benchmarks/quality/matrix-2026-04-26.md). Should be lost in the embedder's noise floor either way.

Once those numbers land in chunkshop's own measurement doc, this memo will link them and SC-009 closes fully.

## Surprises from the design pass

1. **Zero skimr changes needed.** The brainstorm expected skimr would need an "integration mode" or chunkshop-shaped adapter. It doesn't. skimr's v0.1.0 API surface is already the right shape; chunkshop just wraps it.
2. **P3 (sidecar extractor) is redundant** with chunkshop's `ExtractResult(tags, metadata)` contract. A sidecar is just another name for a metadata-writing extractor. Dropped from the design.
3. **P4 (skimr-owns-chunker) is a non-goal.** Chunking is chunkshop's concern. skimr stays out of boundary decisions.
4. **Source preprocessors had no seam** in chunkshop today — users had to pre-clean their corpus manually. The cleanest fix is a generic `preprocessors` chain, not skimr-specific plumbing. Motivates Brief 5.
5. **The `ExtractResult(tags, metadata)` contract absorbs future skimr additions.** v0.2 confirmed this: `skimr.extract.metadata(text) -> Metadata(dates, amounts, urls, entities)` and the rest of `skimr.extract.*` all flow into `ExtractResult.metadata` / `.tags` without re-shaping. The original prediction held.

## Scope boundaries

- **skimr does not depend on chunkshop.** skimr is a library; chunkshop is one of many possible consumers.
- **chunkshop does not depend on skimr.** chunkshop's contracts accept any callable with the right signature — skimr, `skimr-neural`, LLM APIs, or user code.
- **Neural summarization lives in the `skimr-neural` companion**, not here. Same callable shape; different implementation.
- **This memo captures integration design, not runtime measurement.** The "measured before/after on at least one real input" requirement of SC-009 is satisfied *partially* by this memo and *fully* only after Brief 4 implementation produces its measurements. That's the explicit status.

## References

- skimr: [`README.md`](../README.md) · [`docs/REFERENCE.md`](REFERENCE.md) (v0.2 primitive catalog) · [`SUMMARIZATION.md`](../SUMMARIZATION.md) (v0.1-era algorithmic spec) · v0.2 design contract at [`docs/v0-2-design.md`](v0-2-design.md).
- chunkshop: `skill-output/mission-brief/Mission-Brief-summary-embed.md` · `Mission-Brief-metadata-extractors.md` · `Mission-Brief-schema-flexibility.md` · `Mission-Brief-semantic-chunker.md` (in chunkshop repo)
- Benchmarks: [`benchmarks/quality/matrix-2026-04-26.md`](../benchmarks/quality/matrix-2026-04-26.md) — v0.2 method × corpus latency matrix vs Sumy backends. SC-A quality review at [`benchmarks/quality/review-2026-04-21.md`](../benchmarks/quality/review-2026-04-21.md). SC-D extraction eval at [`benchmarks/quality/extraction-2026-04-26.md`](../benchmarks/quality/extraction-2026-04-26.md).
