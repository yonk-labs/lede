# Resume: skimr Rust Plan 2 — stopped after T5

**Last session:** 2026-04-19 evening → 2026-04-20 early morning. Stopped after T5 at commit `c704a7c`. v0.0.1 already shipped (Plan 1); Plan 2 (Rust port) in progress.

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main` (all Plan 2 work continues here, matching Plan 1 pattern)
- **Latest pushed SHA:** `c704a7c`
- **v0.0.1 tag:** pushed; points at `4c3e7d4` (Plan 1 exit, Python reference complete)
- **CI:** `tests` + `zero-deps` workflows exist and pass on every push. Rust-specific `rust.yml` lands in T13.

## Plan 2 — progress so far

Plan file: `docs/superpowers/plans/2026-04-19-skimr-rust-v01.md` (16 tasks total).

**Done (5/16):**

| # | Task | SHA | Notes |
|---|---|---|---|
| T1 | Cargo skeleton | `942d018` | edition 2024, MSRV 1.85 (plan was fixed at `5098721` — orig said 1.75 which cargo rejects) |
| T2 | Sentence splitter | `786000b` | Lookbehind-free port; 9 tests; cross-language spot check identical |
| T3 | `strip_think` | `72ee24d` | Trivial 16-line port |
| T4 | `clean_text` | `2a30987` | Both `crm-boilerplate` and `markdown-basic` fixtures verified byte-identical to Python |
| T5 | TF-IDF scorer | `c704a7c` | **Flagged — see Concerns #1 below** |

**Pending (11/16):** T6 greedy selector · T7 keyword extractor · T8 public API re-exports · T9 fixture walker (⛔ DC-002 gate) · T10 CLI · T11 determinism · T12 zero-dep assertion · T13 Rust CI · T14 README · T15 benchmark row fill · T16 DC-FINAL + tag.

**Test suite state (Rust):** 22 passing (9 sentences + 6 strip_think + 7 clean_text + 5 tfidf scorer). Python side still 64 passing, untouched.

## Execution cadence

Subagent-driven, per `superpowers:subagent-driven-development`. Pattern that has worked:

- Dispatch implementer subagent with the task's full text + byte-identity constraints explicitly called out.
- For trivial (T3-style, <50 lines, verbatim port): verify inline via `git show` + `cargo test`, skip the spec + quality subagent reviewers.
- For byte-identity-critical (T2, T4, T5, T6, T7, T9): demand cross-language spot check in the implementer prompt; only dispatch spec + quality reviews if the spot check is ambiguous or concerns are raised.
- Push periodically, not after every commit — less CI noise.

User gave autonomous full-send consent mid-session ("accept all requests, headed to bed"); next session can pick that back up if desired.

## ⚠️ Critical carry-forward concerns

### 1. TF-IDF float-sum divergence (will fail T9 fixture walker as-is)

**Discovered at T5.** Rust's `Iterator::sum()` and Python 3.13's built-in `sum()` **do not produce bit-identical results** on accumulations of 6-8+ f64 values, even when every input bit and iteration order is identical. Observed gap: **1-3 ULPs** on per-sentence TF-IDF sums.

**Concrete test case the T5 subagent ran:**
- Input: `[1.916290731874155] * 8`
- Python `sum(...)` → `15.33032585499324` (bits `0x402ea9207870703c`)
- Rust `iter().sum::<f64>()` → `15.330325854993244` (bits `0x402ea9207870703e`)

(That exact case may not reproduce trivially — Python's `sum()` fast-path for lists-of-floats may be the non-obvious actor. Verify before building on it.)

**What passes today:** the plan's 5 scorer unit tests in `rust/tests/tfidf.rs`, plus a short-sentence cross-language diff (`["Revenue grew.", "Margins improved.", "Churn remained flat."]` → `[1.0, 1.0, 1.0]` identical bits).

**What will break:** T9's fixture walker on any fixture whose `tfidf_score` path involves a sentence with many terms. The `tfidf/short-passthrough` fixture is short enough to passthrough the scorer (len(text) ≤ max_length branch in `summarize` short-circuits), so it may NOT trip this. But any richer corpus will.

**Fix options (pick one at T6, before T9 gate):**

- **(A) Compensated summation on Rust side.** Add Neumaier or Kahan summation in `rust/src/tfidf.rs`'s `tfidf_score` per-sentence sum. ~10-15 lines. Preserves Python as the frozen spec. **Recommended.** Python is the spec per the mission brief; Rust adapts.
- **(B) Force Python to plain left-fold.** Replace Python's `sum(tf[term] * idf.get(...) for term in tf)` with `functools.reduce(operator.add, ..., 0.0)` which bypasses any `sum()` fast path. Fixtures would need regeneration (byte-identical regeneration is likely but must be verified). Less desirable — changes the spec implementation even if the spec itself doesn't change.
- **(C) Relax SC-002 to "within 1 ULP".** Rejected — breaks the whole "byte-identical across runtimes" thesis the mission brief is built on.

**Where to apply fix A:** `rust/src/tfidf.rs`, inside `tfidf_score`, the `.map(|tc| { ... let sum: f64 = tc.keys.iter().map(...).sum(); ... })` block. Replace `.sum()` with a Neumaier fold. Add a unit test that constructs a known-divergent input and asserts identical bits with the Python reference (run the Python diff from a test harness at `rust/tests/float_parity.rs`).

**Don't touch at T9.** The T9 walker should see green if the fix is in place by T7 at the latest. If the walker fails at T9, it's a cleanup-at-the-end-of-a-long-session signal that got ignored earlier.

### 2. Existing concerns carried from pre-Rust work

- `__init__.py` try/except shield removed in Plan 1 T7. Resolved.
- `fixtures/clean_text/crm-boilerplate/expected.txt` has SQL-faithful quirks (trailing `.`, leading `,`). Do NOT edit; Rust T4 reproduced them byte-identical.
- `fixtures/keyword/pricing-notes/expected.txt` has `..` double-periods from SQL's `\n+` → `. ` replacement colliding with line-terminal `.`. Do NOT edit; Rust T7 must reproduce.
- Python 3.13 in venv; pyproject synced to include 3.13 classifier already.
- venv uses `uv`, no `pip`. Use `.venv/bin/python -m pytest` directly; for installs use `/home/yonk/.local/bin/uv pip install ...`.

## Rust-side quick facts

- **Dir:** `rust/` (crate root with `Cargo.toml`)
- **Edition:** 2024 / MSRV 1.85 (locked by `rust-toolchain.toml` to 1.93)
- **Runtime deps:** `regex = "1"` only. `Cargo.lock` committed (idiomatic for binary-shipping crate).
- **Lints:** `unsafe_code = "forbid"` + clippy pedantic with 5 allows: `cast_precision_loss`, `cast_possible_truncation`, `missing_errors_doc`, `missing_panics_doc`, `module_name_repetitions`.
- **Module layout so far:**
  ```
  rust/src/
    lib.rs              # pub mod clean; pub mod sentences; pub mod tfidf;
    sentences.rs        # split_sentences
    clean.rs            # strip_think, clean_text
    tfidf.rs            # OrderedCounter, tfidf_score, position_score, length_score, composite_score
    bin/skimr.rs        # stub; real CLI lands in T10
  ```
- **Tests:**
  ```
  rust/tests/
    sentences.rs        # 9 tests
    strip_think.rs      # 6 tests
    clean_text.rs       # 7 tests
    tfidf.rs            # 5 tests (scorer only; summarize tests land in T6)
  ```

## What's next (T6 through T16)

Pick up with T6. Read the plan's T6 section at `docs/superpowers/plans/2026-04-19-skimr-rust-v01.md` (~lines 950–1120). **Before dispatching T6's subagent**, decide on fix A/B/C above for the float-sum issue. My strong recommendation: **fix A (Neumaier in Rust), addressed as a preamble to T6** — either a small dedicated task "T5.1: Neumaier summation" or folded into T6's implementer prompt as an additional constraint.

Then T6 (summarize pipeline) can land with a new `rust/tests/float_parity.rs` that asserts byte-identity on a known-rich case, gating future drift.

Subsequent tasks:
- T7 keyword extractor — byte-identity risk on the SQL-style splitter
- T8 re-exports (trivial)
- T9 fixture walker — **⛔ DC-002 hard gate**; this is where byte-identity is proven
- T10 CLI — hand-rolled argparse (no clap dep)
- T11 determinism (100 runs × every fixture bit-identical)
- T12 zero-dep assertion (parse Cargo.toml, assert `regex` only)
- T13 CI workflow for Rust
- T14 README Rust section
- T15 benchmark harness Rust row fill
- T16 DC-FINAL + tag — likely `v0.1.0-rc1` (not `v0.1.0`) since SC-009 integration memo isn't satisfied; flag to user before tagging

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr Plan 2 is in progress — T1-T5 complete, pushed to `yonk-labs/skimr` main. **Read `docs/RESUME.md` FIRST** — it flags a byte-identity divergence between Python and Rust `sum()` that must be resolved before T9's DC-002 gate. Plan: `docs/superpowers/plans/2026-04-19-skimr-rust-v01.md`. Mission brief: `skill-output/mission-brief/Mission-Brief-skimr.md`. Execution is subagent-driven per `superpowers:subagent-driven-development`; user has given full-send autonomous consent. Start by deciding on fix A/B/C for the float-sum issue (my recommendation: A, Neumaier in Rust, addressed as a T5.1 preamble to T6). Then resume with T6.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest -q                        # Python side — 64 tests
cd rust && cargo test && cargo clippy --all-targets -- -D warnings  # Rust side — 27 tests so far
git log --oneline                                    # commit progress
gh run list --repo yonk-labs/skimr --limit 5         # CI status
```

## Companion repo

`/home/yonk/yonk-tools/skimr-neural/` has been worked on in a parallel session — its mission brief was updated to `status: approved — design locked, ready for /writing-plans` and a design spec at `docs/superpowers/specs/2026-04-19-skimr-neural-v0-0-1-design.md` was produced. That repo is on its own track; no skimr-core work needed from that side.
