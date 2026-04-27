# CLAUDE.md

Guidance for AI agents (Claude Code, Cursor, etc.) working in this
repository. Human contributors: read [`README.md`](README.md) and
[`CONTRIBUTING.md`](CONTRIBUTING.md) instead — this file is tooling
config.

## Status

`v0.2.0` shipped 2026-04-26. All four CI workflows (`tests`,
`zero-deps`, `rust`, `skimr-spacy`) green on `main`.

## Authoritative docs in priority order

1. [`README.md`](README.md) — what skimr is, why, how to use it.
2. [`docs/REFERENCE.md`](docs/REFERENCE.md) — primitive catalog +
   public API contract.
3. [`docs/v0-2-design.md`](docs/v0-2-design.md) — v0.2 design spec
   with SC-A through SC-F acceptance tests.
4. [`docs/skimr-spacy-integration.md`](docs/skimr-spacy-integration.md)
   — companion-package integration policy.
5. [`docs/integration-memo.md`](docs/integration-memo.md) — chunkshop
   integration contract (first downstream consumer).
6. [`docs/comparison.md`](docs/comparison.md) — worked examples
   comparing skimr against Sumy and LLM APIs with real timings.

## Code layout

| Path | Role |
|---|---|
| `src/skimr/` | Python core. Public surface: `summarize(attach=…)`, `brief()`, `clean_text`, `strip_think`, `extract_keyword`, plus `skimr.extract.{outline, toc, stats, key_facts, metadata, phrases, correlate_facts}`. Default install is zero-dep; `[ner]`, `[wordforms]`, `[yake]`, `[textrank]` are opt-in extras. |
| `rust/src/` | Rust mirror. `Mode::{Default, Legacy, Coverage}` selects the scorer. Optional `wordforms` cargo feature binds to the same `text2num` crate as Python's `[wordforms]` extra → byte-identical parity. |
| `packages/skimr-spacy/` | Python companion package. Provides `extract_entities`, `spacy_metadata`, `spacy_phrases`, `spacy_correlate_facts`. Importing it registers backends as a side effect. |
| `fixtures/` | Language-agnostic input/output corpus. **Every change to a primitive must keep the parity walker green** (`rust/tests/fixtures.rs`). Two test gates: `every_fixture_byte_identical` (v0.1 surface) and `v0_2_extract_primitives_byte_identical` (v0.2 surface, regenerated via `python benchmarks/gen_parity_fixtures.py`). |
| `tests/` + `rust/tests/` | Python and Rust test suites. 231 + 17 + 116 + 121 tests. |
| `benchmarks/` | Quality eval (A1 rubric + A2 ROUGE + A4 LLM-judge), extraction eval (gold-vs-primitive precision/recall), latency matrix. |
| `examples/` | 7 runnable scripts smoke-tested by CI. |

## Conventions

- **No LLM calls in the core library.** Extractive only. LLM /
  abstractive summarization belongs in callers, not here. May land as
  a separate `skimr-neural` companion someday; not in `skimr`.
- **Zero required runtime dependencies** in the default install path.
  Python: stdlib only. Rust: stdlib + `regex` only. Optional extras
  are opt-in.
- **Deterministic over clever.** Same input → same bytes, every call,
  every runtime. No random tie-breaking, no hash-iteration-order
  dependence, no locale-dependent case folding.
- **Byte-identical Python ↔ Rust** on the regex backend. The fixture
  walker enforces this on every push. Optional Python-only backends
  (`spacy`, `yake`) make no parity promise.
- **The SQL is reference, not a dependency.** Don't assume Postgres
  is present.

## Commands

```bash
# Python core
.venv/bin/python -m pytest -q                                     # 231 tests
.venv/bin/python -m pytest tests/test_edge_cases.py -q            # 50 edge cases

# skimr-spacy companion
cd packages/skimr-spacy && ../../.venv/bin/python -m pytest -q    # 17 tests

# Rust core
cd rust && cargo test                                              # 116 tests, default features
cd rust && cargo test --features wordforms                         # 121 tests, with wordforms
cd rust && cargo clippy --all-targets -- -D warnings              # must be clean
cd rust && cargo fmt --check                                       # must be clean

# Cross-runtime parity (v0.2 differentiator)
.venv/bin/python benchmarks/gen_parity_fixtures.py                # regenerate fixtures
cd rust && cargo test --test fixtures                              # walker green = no drift

# Benchmarks
.venv/bin/python benchmarks/matrix_eval.py                        # SC-B latency matrix
.venv/bin/python benchmarks/extraction_eval.py                    # SC-D primitive quality
```

## Skill-output discipline

`skill-output/` is gitignored. AI agents that produce research,
audits, or session artifacts should write to that directory and not
commit the contents to the repo. Past artifacts (research-base,
mission-brief, AAT, prod-ready, secret-scan reports) lived there
historically; they were removed from tracking before the public flip.
