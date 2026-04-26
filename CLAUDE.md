# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Status & contracts

**Shipped:** `v0.2.0` (tag on `github.com:yonk-labs/skimr`). All three CI workflows green on the tagged commit.

**Authoritative docs in priority order:**
- `docs/RESUME.md` — current state, where to pick up next session.
- `docs/REFERENCE.md` — primitive catalog and public API contract for v0.2.
- `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md` — v0.2 design spec (SC-A through SC-F).
- `skill-output/mission-brief/Mission-Brief-skimr.md` — original v0.1.0 mission brief, retained as **historical contract**. Don't take it as the live spec; v0.2 has shipped on top of it.

When restarting, re-read `docs/RESUME.md` first, then the v0.2 spec for SC framing. Project name is `skimr`. v1 + v0.2 = Python + Rust; Node + Go defer further. Neural summarization stays out of core.

## Project intent

A multi-language library (`skimr`) for **extractive summarization** and **lightweight text summarization**, targeting byte-identical feature parity across **Python, Rust, Go, and Node**. v1 ships Python + Rust. The goal is a small, deterministic, zero-dep primitive that shrinks text before it's sent to an LLM, stored, or displayed as a preview — with the same bytes from any runtime.

Extractive is the default because it is deterministic, sub-millisecond, and dependency-free. LLM/neural summarization is out of scope for the core (may become an optional companion package, but never inside `skimr` itself).

## Current state

v0.2.0 shipped on 2026-04-26. Implementation lives at:

- `src/skimr/` — Python core. Public surface: `summarize(attach=…)`, `brief()`, `clean_text`, `strip_think`, `extract_keyword`, plus `skimr.extract.{outline,toc,stats,key_facts,metadata,phrases,correlate_facts}`. Default install is zero-dep; `[ner]`, `[wordforms]`, `[yake]`, `[textrank]` are opt-in extras.
- `rust/src/` — Rust mirror. Public surface mirrors Python's regex backend; `Mode::{Default, Legacy, Coverage}` selects the scorer. Optional `wordforms` cargo feature bridges to the same `text2num` crate as Python's `[wordforms]` extra so output stays byte-identical.
- `packages/skimr-spacy/` — companion package providing `extract_entities`, `spacy_metadata`, `spacy_phrases`, `spacy_correlate_facts` for callers who install `skimr-spacy` and `en_core_web_sm`.
- `fixtures/` — language-agnostic input/output corpus that both implementations must reproduce byte-for-byte. `rust/tests/fixtures.rs` walks every fixture on every push (SC-C / SC-002).

Reference / seed material that's still useful but **not the live spec**:
- `extractive_functions.sql` / `extractive_functions.md` — original PL/pgSQL reference for `clean_text` / `extract_relevant` / `strip_think`.
- `summarize-output.py` — original standalone Python prototype with the keyword-frequency scoring variant.
- `SUMMARIZATION.md` — original algorithmic spec for the TF-IDF + position + length pipeline. v0.2 default mode adds C1 scorer tweaks (heading filter, cue-phrase boost, digit bonus, section-position weighting) on top of this; legacy mode preserves the original 60/25/15 bytes.
- `extractive-performance.md` / `ARCHITECTURE.md` — context-only.

For the live API contract see `docs/REFERENCE.md`. For SC-level acceptance tests see `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md`.

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
