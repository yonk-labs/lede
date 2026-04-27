# Maintainers

skimr is maintained by **The Yonk** (`<matt@theyonk.com>`).

This is a **single-maintainer project**. Adopters should weigh the bus-factor
risk that goes with that:

- Issues and PRs are reviewed when time allows. Best-effort, no SLA.
- Security reports go to `<matt@theyonk.com>` — please do not file public
  issues for security findings (see [`SECURITY.md`](SECURITY.md)).
- Major design decisions get written down in `docs/superpowers/specs/` and
  `docs/superpowers/plans/` as they happen, so the project's intent is
  recoverable from the repo even without me.

If you'd like to help maintain skimr or take over a piece of it long-term,
open an issue tagged `maintainers` or email me directly. The license
(Apache-2.0) explicitly allows forking; the non-trivial pieces of the
project — the byte-identical Python ↔ Rust contract, the structured-extract
primitives, the SC-D evaluation harness — are documented well enough that
a determined fork can keep going without me.

## Decision authority

- **API surface changes** (new public functions, breaking signature changes,
  default-mode changes): require a written design note in
  `docs/superpowers/specs/` before implementation.
- **Bug fixes and quality improvements**: PRs welcome; CI must stay green
  on Python + Rust + skimr-spacy + clippy + fmt.
- **Performance changes**: must include a benchmark delta from
  `benchmarks/matrix_eval.py`.
- **New scoring modes / extract primitives**: must come with byte-identical
  Python ↔ Rust parity tests and an SC-D-style evaluation against the
  existing gold corpus.

## Release cadence

skimr does not have a fixed release cadence. Versions are cut when a
coherent batch of work is ready and `docs/RESUME.md` reflects a stable
state. The git tag annotation is the canonical release notes.
