# Integration Memo — skimr in chunkshop

**Status:** Design agreed; runtime before/after pending chunkshop Brief 4 implementation.
**Date:** 2026-04-20.
**SC-009 evidence:** Partial — design/contract complete, quantitative before/after deferred until consumer code ships.

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

The four functions above are part of skimr's **frozen public surface** as of v0.1.0-rc1. Their signatures won't change across v0.1.x. Their output bytes are deterministic and byte-identical across Python and Rust (`fixtures/` is the source of truth; `rust/tests/fixtures.rs` asserts parity on every CI push).

```python
from skimr import summarize, extract_keyword, clean_text, strip_think

summarize(text: str, max_length: int = 500) -> str
extract_keyword(text: str, keywords: str, num_sentences: int = 10) -> str
clean_text(text: str) -> str
strip_think(text: str) -> str
```

```rust
use skimr::{summarize, extract_keyword, clean_text, strip_think};

skimr::summarize(text: &str, max_length: usize) -> String
skimr::extract_keyword(text: &str, keywords: &str, num_sentences: usize) -> String
skimr::clean_text(text: &str) -> String
skimr::strip_think(text: &str) -> String
```

chunkshop wrappers may compose these freely. skimr does not know chunkshop exists.

## What chunkshop does with each

- **`summarize`**: Brief 4 defines two wrappers. `summary_embed` replaces `embedded_content` with the summary while preserving raw text in `original_content`. `hierarchical_summary` emits both fine chunks and coarse summary rows to the same pgvector table, linked by group id for "match coarse, return fine" retrieval.
- **`extract_keyword`**: proposed extension of Brief 1 (metadata-extractors). A `callable_phrases` variant takes a user-supplied callable whose signature matches skimr's `extract_keyword`, producing tags attached to each chunk. Keeps chunkshop origin-agnostic.
- **`clean_text` / `strip_think`**: proposed Brief 5 introduces `Source.preprocessors: list[Callable[[str], str]]` — a generic preprocessing chain. Users compose skimr's functions (or their own) to scrub filler/markdown/`<think>` blocks before chunking.

None of this requires chunkshop to depend on skimr. The contracts accept any Python callable with matching signatures. skimr happens to be the deterministic zero-dep implementation that ships with chunkshop's docs.

## Measurements (pending)

Honest status: no runtime before/after numbers exist yet. The design is agreed; the consumer code is pre-implementation.

Metrics to capture once Brief 4 (`summary_embed`) implementation lands in chunkshop:

- **Retrieval recall @ k** — identical query, identical k, measured before (raw chunk embedding) vs after (summary embedding) on chunkshop's shipped sample corpus. Expected: recall up, because the embedding space is less polluted by boilerplate.
- **Chunk storage size** — `original_content` byte count stays the same; `embedded_content` shrinks to summary length. Compression ratio is just `len(summary) / len(raw)`.
- **Ingest wall-clock overhead** — per-chunk skimr time is sub-millisecond in Python and ~2× faster in Rust (see `benchmarks/results/results-2026-04-20.md`). Should be lost in the embedder's noise floor.

Once those numbers land in chunkshop's own measurement doc, this memo will link them and SC-009 closes fully.

## Surprises from the design pass

1. **Zero skimr changes needed.** The brainstorm expected skimr would need an "integration mode" or chunkshop-shaped adapter. It doesn't. skimr's v0.1.0 API surface is already the right shape; chunkshop just wraps it.
2. **P3 (sidecar extractor) is redundant** with chunkshop's `ExtractResult(tags, metadata)` contract. A sidecar is just another name for a metadata-writing extractor. Dropped from the design.
3. **P4 (skimr-owns-chunker) is a non-goal.** Chunking is chunkshop's concern. skimr stays out of boundary decisions.
4. **Source preprocessors had no seam** in chunkshop today — users had to pre-clean their corpus manually. The cleanest fix is a generic `preprocessors` chain, not skimr-specific plumbing. Motivates Brief 5.
5. **The `ExtractResult(tags, metadata)` contract absorbs future skimr additions.** When Thread C lands `skimr.extract_metadata(text) -> dict[str, list[str]]` (dates, amounts, named entities), the path into chunkshop is already open — the new function writes into `metadata` via a new extractor variant. No recontracting required.

## Scope boundaries

- **skimr does not depend on chunkshop.** skimr is a library; chunkshop is one of many possible consumers.
- **chunkshop does not depend on skimr.** chunkshop's contracts accept any callable with the right signature — skimr, `skimr-neural`, LLM APIs, or user code.
- **Neural summarization lives in the `skimr-neural` companion**, not here. Same callable shape; different implementation.
- **This memo captures integration design, not runtime measurement.** The "measured before/after on at least one real input" requirement of SC-009 is satisfied *partially* by this memo and *fully* only after Brief 4 implementation produces its measurements. That's the explicit status.

## References

- skimr: [`README.md`](../README.md) · [`SUMMARIZATION.md`](../SUMMARIZATION.md) · [`Mission-Brief-skimr.md`](../skill-output/mission-brief/Mission-Brief-skimr.md)
- chunkshop: `skill-output/mission-brief/Mission-Brief-summary-embed.md` · `Mission-Brief-metadata-extractors.md` · `Mission-Brief-schema-flexibility.md` · `Mission-Brief-semantic-chunker.md` (in chunkshop repo)
- Benchmarks: [`benchmarks/results/results-2026-04-20.md`](../benchmarks/results/results-2026-04-20.md) — skimr vs Sumy speed comparison; quality review in progress (Thread A).
