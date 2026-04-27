# Contributing to skimr

Thanks for considering a contribution. skimr is a single-maintainer
Apache-2.0 project — see [`MAINTAINERS.md`](MAINTAINERS.md) for the
bus-factor disclosure and review pace.

## Quick start

```bash
git clone git@github.com:yonk-labs/skimr.git
cd skimr
pip install -e ".[dev]"
.venv/bin/python -m pytest -q                                # 181 tests
cd packages/skimr-spacy && ../../.venv/bin/python -m pytest  # 17 spaCy tests
cd rust && cargo test                                        # 116 tests
cd rust && cargo clippy --all-targets -- -D warnings         # must be clean
cd rust && cargo fmt --check                                 # must be clean
```

## What kind of contributions land easily

| Kind | Bar |
|---|---|
| Bug fix with regression test | Easy — just open the PR. |
| Doc fix / typo / link rot | Easy — even easier. |
| Quality improvement to an existing primitive | Comes with a measured delta against `benchmarks/quality/extraction-*.md` and a parity check for the Python ↔ Rust core path. |
| New extract primitive | Needs a design note in `docs/` first. Must come with byte-identical Python ↔ Rust output and a gold-labeled fixture set. |
| New scoring mode | Same as above — design note + parity tests + benchmark vs current default. |
| Performance change | Must include a `benchmarks/matrix_eval.py` delta. |
| Adding Node / Go ports | The v0.1 brief explicitly listed these as v0.2+ deferral. Open an issue first so we can scope the parity-fixture work. |
| Neural / LLM / abstractive summarization | Out of scope forever for the core. May land as a separate `skimr-neural` companion. See [`docs/v0-2-design.md`](docs/v0-2-design.md) for the rationale. |

## The Python ↔ Rust parity contract

This is the most important rule and the most common cause of PR rework.

**Every change to a primitive's logic must produce byte-identical output
in both runtimes** for the regex backend. The contract is enforced by:

- `fixtures/` — language-agnostic input/expected pairs.
- `rust/tests/fixtures.rs::every_fixture_byte_identical` — walks every
  fixture on every push.
- `tests/test_fixtures.py` — Python equivalent.

If your change touches `src/skimr/extract/*.py` or `rust/src/extract/*.rs`,
expect to update both languages together and add a fixture proving they
match.

Optional Python-only paths (`backend="spacy"`, `backend="yake"`) are
exempt — Rust does not ship NER or YAKE.

## Style

- **Python**: stdlib only on the default path. Type hints required on
  new public APIs. Run `pytest -q` before submitting.
- **Rust**: `cargo fmt` + `cargo clippy --all-targets -- -D warnings`
  must both be clean (default features and `--features wordforms`).
- **Comments**: prefer "why" over "what". The code shows what.
- **Commits**: subject line ≤ 72 chars, body wraps at 72. Use
  conventional-ish prefixes (`fix:`, `feat:`, `docs:`, `chore:`, `bench:`)
  but it's not strict. The body should explain the *why*.

## CI

Every push to `main` runs three workflows:

- `tests` — Python core + skimr-spacy tests.
- `zero-deps` — verifies `pip install skimr` brings in zero non-stdlib
  runtime deps (the SC-007 contract).
- `rust` — `cargo fmt --check`, `cargo clippy`, `cargo test`,
  `cargo test --release`.

All three must be green before merge. If a workflow needs to skip a
file, do not add a `paths:` filter — they cause drift accumulation
(see commit `a10064a`).

## Reporting issues

- **Bugs**: GitHub issues, with a minimal reproducer (input text + the
  primitive call + the observed vs expected output).
- **Security**: see [`SECURITY.md`](SECURITY.md). Email, do not open a
  public issue.
- **Quality complaints** ("the summary should have included sentence X"):
  fine to file as issues, but understand that extractive summarization
  has fundamental limits relative to abstractive — the trade is
  determinism, sub-millisecond latency, and zero deps.

## Code of conduct

Be kind. Don't make this complicated. The maintainer reserves the right
to close interactions that aren't kind.
