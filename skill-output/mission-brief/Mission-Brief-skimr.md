---
mission: skimr v0.1.0 — deterministic extractive summarization, Python + Rust first
created: 2026-04-19
status: active
---

## TL;DR

Build `skimr`, a deterministic extractive summarization library for Python and Rust (Node and Go defer to v0.2+) that produces byte-identical output across runtimes from a shared fixture corpus, supports four core modes plus optional TextRank, ships a library + CLI per language, and actually integrates into at least one existing Yonk project. v1 ships as a public GitHub repo with CI and a v0.1.0 tag — not yet published to PyPI / crates.io.

## Purpose

Every Yonk project today that does summarization rolls its own or pulls in a heavyweight library. The result: inconsistent previews, non-deterministic output, and summarization code that only runs in Python. The problem isn't that no summarizer exists (Sumy, `tldr`, `node-summarizer` do); the problem is that no summarizer offers byte-identical behavior across the runtimes a real multi-service stack uses. `skimr` collapses that variance into one primitive with one spec.

## Desired Outcome

- `skimr` Python package and `skimr` Rust crate, co-located in a single public GitHub repo
- Library API + CLI for both languages, mirroring the ergonomics of the existing `summarize-output.py` reference
- Five core capabilities: TF-IDF/position/length (default), keyword-scored (query-driven), `clean_text`, `strip_think`, and optional TextRank
- Shared language-agnostic test-fixture corpus (inputs + expected outputs) that both implementations pass byte-for-byte
- Benchmark harness timing both implementations against Sumy on equivalent algorithms
- README that gets a new user from `git clone` to a working summary in under 5 minutes
- CI running tests for both languages on every push
- Tagged `v0.1.0` release
- Integrated into at least one existing Yonk project with a one-page integration memo documenting before/after

## Success Criteria

- **SC-001:** Python `skimr` passes every fixture in the shared test-fixture corpus. Every `(input, mode, params) → output` tuple matches expected bytes.
- **SC-002:** Rust `skimr` passes every fixture in the shared corpus and produces **byte-identical output to the Python implementation** for every fixture.
- **SC-003:** Four core modes implemented and spec-compliant:
  - TF-IDF + position + length (60/25/15) per `SUMMARIZATION.md`
  - Keyword-scored with length / numeric / causal-language bonuses per `extractive_functions.sql`
  - `clean_text` (markdown + filler + CRM-boilerplate stripper) per `extractive_functions.sql`
  - `strip_think` (removes `<think>…</think>` blocks) per `extractive_functions.sql`
- **SC-004:** Optional TextRank mode available behind an optional dep — `pip install skimr[textrank]` for Python, Rust feature flag `textrank`. Default install does not pull any TextRank-related dependency.
- **SC-005:** Each language ships a CLI that reads a file or stdin and prints a summary, mirroring the `summarize-output.py` ergonomics (positional path, `--top N`, `--mode`, `--keywords`).
- **SC-006:** Fastest of {Python `skimr`, Rust `skimr`} is within **2× of Sumy's wall-clock time** on an equivalent-algorithm benchmark run on the same machine with the same input corpus and same target sentence count. (Rust is expected to beat Sumy; Python allowed to be slower but must stay within 2×.)
- **SC-007:** Zero required runtime dependencies in the default path. Python: stdlib only. Rust: stdlib plus the `regex` crate only. Optional extras (TextRank) are the only exceptions.
- **SC-008:** Determinism: 100 consecutive runs of any fixture return bit-identical bytes in both languages.
- **SC-009:** `skimr` is installed and used inside at least one existing Yonk project. A one-page integration memo lives in the repo (`docs/integration-memo.md`) documenting before/after behavior.
- **SC-010:** Public GitHub repo exists with README, tests passing in CI on every push, tagged `v0.1.0`. A fresh-clone dry run on a clean machine can summarize a document in under 5 minutes from git clone following only the README.

## Constraints

- **Zero required runtime deps in core default path** (per SC-007). Python stdlib only; Rust stdlib + `regex` only.
- **Byte-identical output across Python and Rust** is a hard gate. Node and Go, when they land in v0.2+, must match the same fixtures — so the spec and fixture corpus are built for 4-language parity even though only 2 implementations ship in v1.
- **Deterministic execution.** No random tie-breaking, no hash-iteration-order dependence, no locale-dependent case folding.
- **Core accepts strings only.** File extraction, neural summarization, DB bindings all out of the core library.
- **Apache-2.0 license.** Preserves compatibility with borrowing from Sumy (also Apache-2.0).
- **v0.1.0 does not commit to API stability.** The spec is the contract; the public API can still churn.
- **Shared fixture corpus is the source of truth.** When Python and Rust disagree, the fix is in whichever language diverges from the fixtures, never in the fixtures themselves (unless the spec itself is wrong).

## Testing Requirements

### Functional Testing

- **SC-001, SC-002** → Golden-output tests run in both languages against the shared fixture corpus. Each fixture file contains input text, mode, parameters, and expected output bytes. Runs in CI on every push.
- **SC-003** → Unit tests per mode verifying pipeline compliance with `SUMMARIZATION.md` (sentence splitter, scorer, greedy selector, reorder-by-position) and with `extractive_functions.sql` (keyword-scored bonuses, clean_text rules, strip_think behavior).
- **SC-004** → TextRank tests run only when the extra is installed. Default-install CI job asserts the TextRank symbol is not importable / the feature flag is off, and that the default path still works.
- **SC-005** → CLI integration tests that invoke the actual binary on sample input and assert stdout contents.
- **SC-006** → Benchmark harness script using a corpus comparable to the 1,828-note set in `extractive-performance.md`. Measures Sumy, Python `skimr`, Rust `skimr` on the same machine, same algorithm, same target sentence count. Result committed to `benchmarks/results-{date}.md`.
- **SC-007** → CI dep-check job: default `pip install skimr` must not pull any non-stdlib runtime dep; `cargo build` must succeed with only `regex` in the default feature set. Any regression here fails CI.
- **SC-008** → Determinism test: same input × 100 runs, assert identical bytes. Runs in both languages.

### E2E / User Simulation Testing

- **SC-009** → Manually install `skimr` into at least one existing Yonk project (candidates: `yonk-taskstash` per `ARCHITECTURE.md` references, or whichever has live summarization code). Replace existing summarization code with `skimr` calls. Run the project's own tests and verify behavior is unchanged or improved. Write `docs/integration-memo.md` documenting: which project, what was replaced, measured before/after on at least one real input, any surprises.
- **SC-010** → Clean-machine dry run (VM or fresh user account): `git clone`, follow README, produce a summary of a sample doc. Timed. Must be under 5 minutes. This is the `/user-test`-style verification that the README works without insider knowledge.

## Drift Checkpoints

- **DC-001:** After Python reference port is complete (before starting Rust) → verify SC-001, SC-003, SC-005, SC-008. Python must be passing all its own fixtures and be deterministic before Rust gets an authoritative target to hit.
- **DC-002:** After Rust port is complete → verify SC-002 (byte-identity with Python) on every fixture. **Any mismatch = stop and reconcile the spec, not the bytes.** If Rust and Python disagree, the first question is always "which one is spec-compliant?" — not "how do I make Rust match Python's quirks."
- **DC-003:** After TextRank optional mode is added → verify SC-004 and confirm default path still works with zero deps (SC-007). TextRank adding a hidden default dep is a real regression risk.
- **DC-004:** Before capturing benchmark numbers → first capture baseline Sumy numbers on the target machine with the target corpus. Comparing to stale or different-machine baselines invalidates SC-006.
- **DC-005:** Before writing the integration memo → confirm the chosen real project's existing summarization behavior is captured (input + output) *before* replacement, so before/after is an actual comparison.
- **DC-FINAL:** Before tagging `v0.1.0` → re-read this mission brief and verify every SC-XXX has concrete evidence of satisfaction (test output, benchmark result, memo, fresh-clone timing). Missing evidence = not done, regardless of how it feels.

## Out of Scope

- Node and Go implementations (v0.2+; spec and fixture corpus designed to accept them later)
- File format extraction — PDF, DOCX, HTML, EPUB, images. Goes into a future companion package (`skimr-files` or similar).
- LLM / abstractive / neural summarization of any kind, including DistilBART, DistilBERT, T5, Pegasus, BART, or cloud API calls (OpenAI / Anthropic / Cohere). Possible future optional companion, but not v1 and not in core ever.
- Streaming or incremental summarization (input arrives in chunks)
- Non-English stopword lists, language detection, ICU dependencies, Unicode case-folding beyond ASCII
- Topic modeling, sentiment analysis, keyword extraction exposed as standalone features
- Database / SQL bindings. The existing `extractive_functions.sql` stays as a reference implementation, not a shipped artifact.
- GUI, web UI, documentation site, or launch microsite
- PyPI / crates.io publication. Scope is B: GitHub + CI + tagged release. Registry publication waits for v0.2 or a deliberate launch decision.
- API stability commitment. v0.1.0 is pre-1.0; the public API can break between minor versions.
- Marketing materials, blog posts, social posts, comparison writeups. Defer to a `/launch-pad` run if and when registry publication happens.
