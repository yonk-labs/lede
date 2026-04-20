# Resume: skimr Rust Plan 2 — DC-002 gate cleared, stopped after T9

**Last session:** 2026-04-20 afternoon. Stopped after T9 at commit `17b4f28`. v0.0.1 already shipped (Plan 1); Plan 2 (Rust port) in progress. **DC-002 hard gate passed** — all 7 fixtures byte-identical between Python and Rust on first run.

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main` (all Plan 2 work continues here, matching Plan 1 pattern)
- **Local HEAD:** `17b4f28`
- **Unpushed:** 0 — `origin/main` is at `17b4f28`. All Plan-2 work through T9 pushed this session.
- **v0.0.1 tag:** pushed; points at `4c3e7d4` (Plan 1 exit, Python reference complete)
- **CI:** `tests` + `zero-deps` workflows exist and pass on every push. Rust-specific `rust.yml` lands in T13.

## Plan 2 — progress so far

Plan file: `docs/superpowers/plans/2026-04-19-skimr-rust-v01.md` (16 tasks total).

**Done (9/16 + T5.1 preamble):**

| # | Task | SHA | Notes |
|---|---|---|---|
| T1 | Cargo skeleton | `942d018` | edition 2024, MSRV 1.85 (plan was fixed at `5098721` — orig said 1.75 which cargo rejects) |
| T2 | Sentence splitter | `786000b` | Lookbehind-free port; 9 tests; cross-language spot check identical |
| T3 | `strip_think` | `72ee24d` | Trivial 16-line port |
| T4 | `clean_text` | `2a30987` | Both `crm-boilerplate` and `markdown-basic` fixtures verified byte-identical to Python |
| T5 | TF-IDF scorer | `c704a7c` | Flagged float-sum divergence; resolved by T5.1 |
| T5.1 | Neumaier sum | `de30d95` | Compensated summation in Rust `tfidf_score` to match CPython 3.12+ built-in `sum()`. 1-3 ULP divergence on 6+ float accumulations is now eliminated. |
| T6 | Greedy selector + `summarize` | `e136257` | 7-step pipeline per SUMMARIZATION.md. Cross-language spot check matched byte-for-byte at 200- and 100-char budgets. |
| T7 | Keyword-scored extractor | `9ab4a74` | SQL-style splitter faithfully reproduces `\n+` → `". "` quirk that creates `..` double-periods in `pricing-notes` fixture. BTreeSet dedupe mirrors Python's `sorted(set(...))`. Plan's draft regex had a raw-string bug (`\<LF>` line continuation which Rust does not process); implementer used `concat!(...)` instead. |
| T8 | Public API re-exports | `224ed37` | `lib.rs` now re-exports `summarize`, `clean_text`, `strip_think`, `extract_keyword` plus `VERSION`. 6-line edit. |
| T9 | Fixture walker (⛔ DC-002) | `17b4f28` | **All 7 fixtures byte-identical first run, no reconciliation.** Dispatcher in `rust/tests/fixtures.rs` reads `config.json` per fixture and routes to the right Rust function. `textrank` mode explicitly skipped (Plan 2 is core-only). |

**Pending (7/16):** T10 CLI · T11 determinism · T12 zero-dep assertion · T13 Rust CI · T14 README Rust section · T15 benchmark row fill · T16 DC-FINAL + tag.

**Test suite state:**
- **Rust:** 40 passing (9 sentences + 6 strip_think + 7 clean_text + 10 tfidf + 1 float_parity + 6 keyword + 1 fixtures). Clippy `--all-targets -- -D warnings` clean at `17b4f28`.
- **Python:** 64 passing, untouched.

## Execution cadence

Subagent-driven, per `superpowers:subagent-driven-development`. Pattern that has worked:

- Dispatch implementer subagent with the task's full text + byte-identity constraints explicitly called out.
- For trivial (T3-style, <50 lines, verbatim port) OR surgical preamble fixes (T5.1-style): do inline via direct edits + `git show` + `cargo test`. Skip spec + quality subagent reviewers.
- For byte-identity-critical (T2, T4, T5, T6, T7, T9): demand cross-language spot check in the implementer prompt; only dispatch spec + quality reviews if the spot check is ambiguous or concerns are raised.
- Push periodically, not after every commit — less CI noise. **As of `17b4f28`, `origin/main` is current.**

User gave autonomous full-send consent mid-session; next session can pick that back up if desired.

## ⚠️ Resolved concerns

### 1. ~~TF-IDF float-sum divergence~~ — **RESOLVED at T5.1 (de30d95)**

Previous session observed Rust `Iterator::sum()` drifting 1-3 ULPs from Python's built-in `sum()` on 6+ float accumulations. Root cause: CPython 3.12 switched `sum()` to Neumaier compensated summation for float accumulators; Rust stdlib still does plain IEEE-754 left-fold.

**Fix applied:** Added `neumaier_sum` helper in `rust/src/tfidf.rs` (mirrors `CPython`'s `bltinmodule.c` fast-path) and swapped `.sum()` → `neumaier_sum(...)` in `tfidf_score`'s per-sentence loop. Regression test at `rust/tests/float_parity.rs` pins output bits on a 5-sentence, 12-13-token-per-sentence input captured from the Python oracle on 2026-04-20. If Neumaier regresses, that test trips before the T9 fixture walker.

**Do not revert** `neumaier_sum` or bypass it during future work on `tfidf.rs`.

### 2. Existing concerns carried from pre-Rust work (still active)

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
    tfidf.rs            # OrderedCounter, neumaier_sum, tfidf_score, position_score,
                        #   length_score, composite_score, truncate, summarize
    bin/skimr.rs        # stub; real CLI lands in T10
  ```
- **Tests:**
  ```
  rust/tests/
    sentences.rs        # 9 tests
    strip_think.rs      # 6 tests
    clean_text.rs       # 7 tests
    tfidf.rs            # 10 tests (5 scorer + 5 summarize)
    float_parity.rs     # 1 test — T5.1 byte-identity tripwire
    keyword.rs          # 6 tests (incl. fixture_pricing_notes_byte_identical SC-002 pre-check)
    fixtures.rs         # 1 test — SC-002 / DC-002 walker over every fixtures/*/*/
  ```
- **Module layout now:**
  ```
  rust/src/
    lib.rs              # pub mod {clean,keyword,sentences,tfidf};
                        # pub use {clean::{clean_text, strip_think}, keyword::extract_keyword, tfidf::summarize};
                        # pub const VERSION
    keyword.rs          # split_sql_style, extract_keyword (T7)
  ```

## What's next (T10 through T16)

**Pick up with T10.** T9 was the DC-002 load-bearing gate; it passed on first run with zero reconciliations. The remaining tasks are well-specified:

- T10 CLI — hand-rolled argparse (no clap dep); mirrors `src/skimr/cli.py`. Replace `rust/src/bin/skimr.rs` stub + write `rust/tests/cli.rs`. ~150-200 lines + ~80 test lines. Plan starts at line ~1732.
- T11 determinism (100 runs × every fixture bit-identical)
- T12 zero-dep assertion (parse Cargo.toml, assert `regex` only)
- T13 CI workflow for Rust (`cargo test`, `cargo clippy`, `cargo fmt`)
- T14 README Rust section (install + usage + link to Rust docs; Python section already exists)
- T15 benchmark harness Rust row fill
- T16 DC-FINAL + tag — likely `v0.1.0-rc1` (not `v0.1.0`) since SC-009 integration memo isn't satisfied; flag to user before tagging

**Doc deep-dive is deferred until after the Rust port is done** (user's call at end of 2026-04-20 session). T14 will write the Rust README section; anything richer (architecture diagrams, user guide, reference docs) happens post-T16.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest -q                        # Python side — 64 tests
cd rust && cargo test && cargo clippy --all-targets -- -D warnings  # Rust side — 40 tests
git log --oneline                                    # commit progress
git push                                             # clean as of 17b4f28
gh run list --repo yonk-labs/skimr --limit 5         # CI status
```

## TODO list

- [x] **T1** Cargo crate skeleton + toolchain pin
- [x] **T2** Sentence splitter port
- [x] **T3** `strip_think` port
- [x] **T4** `clean_text` port
- [x] **T5** TF-IDF scorer port
- [x] **T5.1** Neumaier compensated summation (float-parity preamble to T6)
- [x] **T6** Greedy selector + `summarize()`
- [x] **T7** Keyword-scored extractor (SQL-style splitter reproduces `..` quirk byte-identical)
- [x] **T8** Public API re-exports in `lib.rs`
- [x] **T9** ⛔ Fixture walker — **DC-002 cleared** (7/7 fixtures byte-identical first run)
- [ ] **T10** CLI binary (hand-rolled arg parser, no clap)
- [ ] **T11** Determinism test (100 runs × every fixture)
- [ ] **T12** Zero-dep assertion (parse Cargo.toml, assert `regex` only)
- [ ] **T13** GitHub Actions CI for Rust (`rust.yml`)
- [ ] **T14** Update README with Rust install/usage
- [ ] **T15** Fill Rust rows in benchmark results
- [ ] **T16** ⛔ Plan 2 exit — DC-FINAL + tag (probably `v0.1.0-rc1`, not `v0.1.0`)

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr Plan 2 is in progress — T1-T9 complete, **DC-002 hard gate cleared** (all 7 fixtures byte-identical Python↔Rust on first run). Local and remote `main` are at `17b4f28`; nothing unpushed. **Read `docs/RESUME.md` FIRST** for full context. Plan: `docs/superpowers/plans/2026-04-19-skimr-rust-v01.md`. Mission brief: `skill-output/mission-brief/Mission-Brief-skimr.md`. Execution is subagent-driven per `superpowers:subagent-driven-development`; user has given full-send autonomous consent. Rust side is green (40 tests + clippy clean). Python side untouched (64 tests). **Next up: T10 CLI binary** — hand-rolled arg parser (no clap), mirrors `src/skimr/cli.py`, replaces the stub at `rust/src/bin/skimr.rs` and adds `rust/tests/cli.rs`. Plan section begins ~line 1732. After T10: T11 determinism, T12 zero-dep assertion, T13 Rust CI, T14 README, T15 benchmarks, T16 DC-FINAL + tag (likely `v0.1.0-rc1` since SC-009 integration memo isn't done). Doc deep-dive deferred until after Plan 2 ships.

## Companion repo

`/home/yonk/yonk-tools/skimr-neural/` has been worked on in a parallel session — its mission brief was updated to `status: approved — design locked, ready for /writing-plans` and a design spec at `docs/superpowers/specs/2026-04-19-skimr-neural-v0-0-1-design.md` was produced. That repo is on its own track; no skimr-core work needed from that side.
