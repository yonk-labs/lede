# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Active mission brief

`skill-output/mission-brief/Mission-Brief-skimr.md` — v0.1.0 scope. Re-read it at any phase transition. Project name is `skimr`. v1 = Python + Rust only; Node + Go defer to v0.2+. Neural summarization is out of core forever (companion package at most). The file is the contract.

## Project intent

A multi-language library (`skimr`) for **extractive summarization** and **lightweight text summarization**, targeting byte-identical feature parity across **Python, Rust, Go, and Node**. v1 ships Python + Rust. The goal is a small, deterministic, zero-dep primitive that shrinks text before it's sent to an LLM, stored, or displayed as a preview — with the same bytes from any runtime.

Extractive is the default because it is deterministic, sub-millisecond, and dependency-free. LLM/neural summarization is out of scope for the core (may become an optional companion package, but never inside `skimr` itself).

## Current state

No implementation code exists yet. The repo is **seed material** for the design:

- `extractive_functions.sql` / `extractive_functions.md` — reference implementation as pure PL/pgSQL (`clean_text`, `extract_sentences`, `extract_relevant`, `strip_think`). The canonical spec for the keyword-scored extractor and the text-cleaner.
- `summarize-output.py` — a working standalone extractive summarizer with a different scoring model (keyword frequency × position × length penalty). Closest thing to a reference Python implementation; no external deps.
- `SUMMARIZATION.md` — the algorithmic spec for the TF-IDF + position + length pipeline (60/25/15 weighting), including sentence splitting rules, greedy selection, and reorder-by-original-position. This is the authoritative pipeline description for the library.
- `extractive-performance.md` — benchmark results from pre-filtering 1,828 notes before an LLM call (~50% size reduction, ~22% faster). Useful for validating that new implementations stay in the same ballpark.
- `ARCHITECTURE.md` — architectural doc from the upstream `yonk-taskstash` project. Background on *why* extractive matters (middleware hot path, MCP previews). Not the spec for this repo — read selectively.

When building out the implementation, treat `SUMMARIZATION.md` as the behavioral contract and the SQL functions as the reference for the cleaning/keyword-scoring variant.

## Two scoring modes to implement

There are two distinct extractive algorithms across the reference material. Both should be supported; they are not interchangeable:

1. **TF-IDF + position + length (no query)** — the default, from `SUMMARIZATION.md`. Use when the caller just wants "the most important N characters/sentences of this document."
2. **Keyword-scored (query-driven)** — from `extractive_functions.sql`. Use when the caller has a prompt/keywords and wants sentences relevant to *that*. Adds bonuses for length > 200 chars, presence of numbers, and causal/analytical vocabulary.

Also port `clean_text` (markdown/filler/CRM-boilerplate stripper) and `strip_think` (removes `<think>…</think>` blocks from reasoning-model output) — both are small, deterministic, and useful independent utilities.

## Cross-language parity requirements

The four implementations must produce **byte-identical output** for a shared test corpus. Before any implementation work:

- Agree on a shared sentence-splitter spec (regex + abbreviation/decimal handling per `SUMMARIZATION.md` step 2).
- Agree on a shared stopword list (the Python script has one; SQL doesn't — pick one and freeze it).
- Agree on a shared tokenization rule (`\b[a-z]{3,}\b` per the Python reference).
- Build a language-agnostic test fixture directory (input text + expected output) that each implementation runs against.

Deterministic output is a hard requirement — the SQL functions are marked `IMMUTABLE` and the Python reference produces stable output for the same input. Don't introduce anything that breaks that (no random tie-breaking, no hash-iteration-order dependence, no locale-dependent case folding).

## File input

"Summarize files" means extracting text content from common formats, then running extractive summarization over that text. Decide per-language which formats are in-scope (plain text and markdown are the floor; PDF/DOCX depend on available libs per runtime). File extraction should be a separate layer from the core summarizer so the summarizer stays dependency-free.

## Commands

No build/test/lint tooling exists yet. The only runnable thing today:

```bash
python3 summarize-output.py <file-or-dir> [--top N]   # default N=20
```

When adding each language implementation, pick idiomatic tooling (`pytest`/`ruff` for Python, `cargo test`/`cargo clippy` for Rust, `go test`/`golangci-lint` for Go, `vitest`+`tsc` or similar for Node) and document the actual commands here — don't leave this section aspirational.

## Conventions specific to this repo

- **No LLM calls in the core library.** Extractive only. LLM/abstractive summarization belongs in callers, not here.
- **Zero required runtime dependencies** for the core extractive path in each language. Optional deps (e.g., a TextRank upgrade via `networkx` in Python) are fine as feature flags, but the default path must work with stdlib only.
- **Deterministic over clever.** If a scoring tweak would improve quality but make output non-reproducible across runs or languages, don't add it.
- **The SQL is reference, not a dependency.** Don't assume Postgres is present; the SQL functions exist to document behavior and as a drop-in for Postgres users.
