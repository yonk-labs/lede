## TL;DR

`extractive_summary` is a pre-implementation seed directory for a planned multi-language (Python, Rust, Go, Node) library that performs deterministic extractive summarization of text and file contents with zero required runtime dependencies. No code has been written yet — the repo currently holds algorithmic specs, a PL/pgSQL reference implementation, a standalone Python summarizer, and an architectural doc borrowed from an upstream project.

---

## Project Identity

| Field | Value |
|---|---|
| Name | `extractive_summary` (working directory name; no formal package name chosen) |
| One-line description | Multi-language library for deterministic extractive summarization of text and files |
| Problem statement | LLM-based summarization is slow, non-deterministic, and expensive; callers need a fast, reproducible, zero-dependency primitive that shrinks text before it hits an LLM, cache, or display |
| Target user | Application developers who need a preview/summary primitive they can invoke identically from Python, Rust, Go, or Node services in the same stack |
| Stage | Pre-implementation (seed material only) |
| Organization / maintainer | Yonk (`/home/yonk/yonk-tools/`) — appears to be a personal/solo tools workspace |
| License | Not yet declared |
| Deployment model | Libraries shipped via language-native registries (PyPI, crates.io, Go modules, npm) — no server, no service |

## Tech stack (stated intent)

- **Python** — stdlib-first; optional upgrade to TextRank via `nltk`/`networkx`
- **Rust** — stdlib-first; `regex` crate unavoidable for sentence splitting
- **Go** — stdlib-first
- **Node** — stdlib-first; TypeScript likely for published artifact

The SQL functions in `extractive_functions.sql` are a **reference implementation** (PL/pgSQL, Postgres 12+), not a deployment target.

## Algorithmic scope

Two distinct extractive algorithms specified:

1. **TF-IDF + position + length** (default, no query) — weighting 60/25/15. Spec in `SUMMARIZATION.md`.
2. **Keyword-scored** (query-driven) — keyword count + length/number/causal-language bonuses. Spec in `extractive_functions.sql`.

Plus two utilities: `clean_text` (markdown + filler + CRM boilerplate stripper) and `strip_think` (removes `<think>…</think>` blocks from reasoning-model output).

## Repo signals

| Signal | Value |
|---|---|
| Is a git repository | No (per environment metadata) |
| File count | 6 files (5 reference docs + 1 Python script + this skill-output tree) |
| Last modified | 2026-04-19 (all files same mtime — bulk seeded) |
| Contributors | Single user (`yonk`) |
| Tests | None |
| CI/CD | None |
| External docs / site | None |

## Current files (reference material, not implementation)

| File | Role |
|---|---|
| `SUMMARIZATION.md` | **Behavioral contract** — pipeline spec (splitter, scorer, selector, reorder) |
| `extractive_functions.sql` | **Reference impl** — pure PL/pgSQL, four functions |
| `extractive_functions.md` | Docs + examples for the SQL functions |
| `extractive-performance.md` | Benchmark results: 50% input reduction, 22% faster LLM calls on 1,828 notes |
| `summarize-output.py` | Working standalone Python extractive summarizer (keyword-freq × position × length-penalty variant) |
| `ARCHITECTURE.md` | Background from upstream `yonk-taskstash` project — *why* extractive matters for middleware/MCP previews |
| `CLAUDE.md` | Guidance for future Claude Code sessions |

**Sources:** Local filesystem; contents of repository.
