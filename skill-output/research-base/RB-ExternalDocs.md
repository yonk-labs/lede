## TL;DR

The project has no external presence — no published docs, website, package listing, repo visibility, or tutorials. All documentation lives as markdown files inside the working directory. This is expected for a pre-implementation project; this section will become populated once packages ship to PyPI / crates.io / Go modules / npm.

---

## Status

`status: partial` — the project is pre-implementation with no external-facing material. No external URLs to inventory.

## Internal reference material (in-repo)

Since there is nothing external, here is the in-repo docs inventory that external docs will eventually have to cover. Keeping this table so downstream skills (`gen-blog`, `gen-architecture`, `launch-pad`) can see what source material is available.

| Path | Type | Quality | Covers |
|---|---|---|---|
| `SUMMARIZATION.md` | Algorithmic spec | Good | TF-IDF+position+length pipeline, decision tree, performance table |
| `extractive_functions.md` | API reference (SQL) | Good | `clean_text`, `extract_sentences`, `extract_relevant`, examples |
| `extractive_functions.sql` | Reference implementation | Good | Pure PL/pgSQL, four functions, `IMMUTABLE STRICT` guarantees |
| `extractive-performance.md` | Benchmark results | Good | Real numbers: 50% size reduction, 22% speedup on 1,828 notes |
| `ARCHITECTURE.md` | Upstream architecture | Adequate | Context from `yonk-taskstash` about *why* extractive matters; not spec for this project |
| `CLAUDE.md` | Agent guidance | Good | Project intent, current state, two scoring modes, parity requirements |

## Key URLs

None. There are no external URLs to cite for this project as it exists today.

## Gap analysis — what's missing externally (to fix at launch)

- No README targeted at end users of each language package
- No getting-started doc per language
- No API reference per language (Python, Rust, Go, Node)
- No changelog / release notes (no releases)
- No benchmark page hosted anywhere
- No comparison-with-alternatives page (Sumy, tldr, node-summarizer)
- No issue tracker visible (not yet a git repo per environment metadata)

When the project publishes, each language target needs at minimum: README, API reference, one "getting started" example, one "why this exists" doc. A single cross-language comparison doc proving byte-identical output across runtimes would be a strong differentiator per RB-Competitors.

**Sources:** Local filesystem inventory.
