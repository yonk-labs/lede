---
project: extractive_summary
project_path: /home/yonk/yonk-tools/extractive_summary
last_full_update: 2026-04-19T00:00:00Z
staleness_threshold_days: 7
git_head_at_update: null  # not a git repository per environment metadata
sections:
  identity:
    file: RB-Identity.md
    last_updated: 2026-04-19T00:00:00Z
    status: current
  external_docs:
    file: RB-ExternalDocs.md
    last_updated: 2026-04-19T00:00:00Z
    status: partial  # pre-implementation; no external presence yet
  competitors:
    file: RB-Competitors.md
    last_updated: 2026-04-19T00:00:00Z
    status: current
  community:
    file: RB-Community.md
    last_updated: 2026-04-19T00:00:00Z
    status: partial  # project-level signals empty; topic-level documented
  market:
    file: RB-Market.md
    last_updated: 2026-04-19T00:00:00Z
    status: current
---

## TL;DR

Research base for a planned multi-language (Python, Rust, Go, Node) extractive summarization library. Sumy (Python) is the incumbent to beat at 3.7k stars and actively maintained into 2026; Rust and especially Node are thin; Go has one active option (`tldr`, v0.7.0 in Oct 2025) and one stale one (DavidBelicza/TextRank). The macro driver is 2026 LLM cost pressure — preprocessing/summarization before the LLM call is widely cited as an 80–90% token reduction lever, which positions deterministic, sub-millisecond extractive summarization squarely on the critical path.

---

## Section Summary

| Section | File | Status |
|---|---|---|
| Identity | [RB-Identity.md](RB-Identity.md) | current |
| External Docs | [RB-ExternalDocs.md](RB-ExternalDocs.md) | partial (pre-implementation) |
| Competitors | [RB-Competitors.md](RB-Competitors.md) | current |
| Community | [RB-Community.md](RB-Community.md) | partial (project-level empty) |
| Market | [RB-Market.md](RB-Market.md) | current |

## Key Findings

1. **Sumy owns Python extractive.** 3.7k stars, Apache-2.0, 8+ algorithms, v0.12.0 in Feb 2026 adding Thai/Polish/Swedish. A new Python-only library has a high bar to justify itself.
2. **Node is the widest OSS gap.** No package approaches Sumy-level maturity. `node-summarizer` bundles unrelated concerns (sentiment); `fast-ai-text-summary` is frequency-only and newer. Shipping a competent Node implementation alone is a viable wedge.
3. **Go has an active incumbent and a stale one.** `JesusIslam/tldr` (137★, LexRank, Oct 2025 release, ~900ns/op) is the moving target. `DavidBelicza/TextRank` (223★) has not released since 2021.
4. **Rust is thin.** `tfidf-text-summarizer` handles the default path but not the keyword-scored variant, and no graph-based (TextRank/LexRank) crate of note. Abstractive is served by `rust-bert` with a heavy footprint.
5. **Cross-language parity is unclaimed.** No surveyed library targets byte-identical output across Python+Rust+Go+Node. Real production stacks commonly run 2+ of these runtimes.
6. **Market timing is favorable.** 2026 enterprise content is dominated by "reduce LLM token cost" narratives citing preprocessing/summarization as a 40–94% cost lever. Deterministic, sub-millisecond extractive primitives fit this narrative precisely.

## Notes for consuming skills

- `gen-sales-doc`, `launch-pad`, `market-intel`: all five sections are safe to consume, with the caveat that `external_docs` and `community` are `partial` by design (pre-implementation). These will fill in post-launch.
- `aat external`: competitors and market context are strong; external docs / community are not yet a fair target for critique.
- `prod-ready`, `ux-audit`, `user-test`: identity + external_docs is enough; no product exists to audit yet.

## Refresh cadence

Competitor repos move quickly (Sumy v0.12.0 in Feb 2026, tldr v0.7.0 in Oct 2025). Refresh `competitors` every 7 days or before any launch-pad run. `market` is slower-moving, refresh monthly. `identity` refreshes on any repo structural change.
