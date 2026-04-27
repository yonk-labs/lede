# Security Policy

## Reporting a vulnerability

If you find a security issue in skimr, please report it privately by
emailing **`matt@theyonk.com`** with the subject line `skimr security`.
**Do not open a public GitHub issue** for security findings.

You can encrypt your report with the maintainer's GitHub-published GPG
key if you prefer, but plain email is fine — skimr's threat surface is
small enough that most reports can be triaged without strict
confidentiality.

I (the single maintainer) aim to acknowledge security reports within
**5 business days**. There is no formal SLA — see
[`MAINTAINERS.md`](MAINTAINERS.md) for the bus-factor disclosure.

## Scope

skimr is a deterministic text-processing library. Its threat model is
narrow:

**In scope:**
- Regex denial-of-service (catastrophic backtracking) — the most common
  failure mode for a regex-heavy primitive. v0.2.0 onward bounds all
  numeric quantifiers and skips sentences with 20+ digit unbroken runs;
  Rust uses RE2 and is structurally immune. Reports on bypasses welcome.
- Panic-on-input — any caller-supplied `str` that crashes a primitive.
  The Rust port should never panic on a valid `&str`; UTF-8 boundary
  bugs in particular are in scope.
- Determinism violations — same input producing different output across
  runs or runtimes (Python ↔ Rust core path) is treated as a security-
  adjacent bug because byte-identical parity is a contract.
- Memory blowups — any input that drives unbounded memory in any
  primitive.

**Out of scope:**
- Quality of summaries / extracted facts — that's tracked under SC-A and
  SC-D, not security.
- Inputs that exhaust normal CPU/memory budgets at expected size — open
  a perf issue, not a security report.
- The optional `[ner]`/`[wordforms]`/`[yake]`/`[textrank]` extras — each
  pulls in third-party deps with their own threat models. Report
  upstream where appropriate.
- Any caller-misuse pattern — e.g. running skimr on attacker-controlled
  input as part of a pipeline that trusts skimr's output. skimr only
  promises deterministic, bounded-time output.

## Supported versions

| Version | Supported |
|---|---|
| 0.2.x | ✅ |
| 0.1.x and earlier | ❌ — pre-public; please use 0.2.0+ |

## Disclosure

Once a fix lands, the original reporter is credited in the release notes
unless they prefer to stay anonymous.

## Known transitive dependency notes

- **`rand 0.7.3` `unsound` (RUSTSEC-2026-0097), via `text2num → phf 0.8 →
  phf_macros → phf_generator → rand`** — only present when the
  `wordforms` cargo feature is enabled (Rust) or the `[wordforms]`
  extra is installed (Python's bound `text2num` crate). The advisory's
  trigger is "custom logger using `rand::rng()`"; skimr does not call
  `rand` directly and ships no custom logger, so practical exposure on
  the `wordforms` path is effectively zero. `cargo audit` runs warn-only
  in CI and surfaces this in the build log. Will resolve when an
  upstream `text2num` version pulls a `phf 0.11+` chain.

CI runs `cargo audit` (Rust) and `pip-audit --strict` (Python) on every
push, both warn-only — they'll flag a fresh advisory in a transitive
dep without blocking the build, and triage happens in the next release.
