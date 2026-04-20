# Resume: skimr Python v0.0.1 → next up

**Current state:** Plan 1 complete. `v0.0.1` tagged locally and pushed to `yonk-labs/skimr` (private). Both CI workflows green on first push. 64 tests passing.

## Repo

- **Remote:** https://github.com/yonk-labs/skimr (private)
- **Tag:** https://github.com/yonk-labs/skimr/releases/tag/v0.0.1
- **Branch:** `main`
- **Local dir:** `/home/yonk/yonk-tools/extractive_summary` (rename to `skimr/` deferred per plan's out-of-scope list)
- **CI:** `.github/workflows/{test.yml,zero-deps.yml}` — tests run on Python 3.10-3.13 matrix; zero-deps job asserts default install has no runtime deps.

## Plan 1 — all 15 tasks complete

| # | Task | SHA |
|---|---|---|
| T1 | Package skeleton | `8ad835e` |
| T2 | Sentence splitter | `5d7ef1f` + `0c734bc` |
| T3 | `strip_think` | `f319f33` |
| T4 | `clean_text` port + crm-boilerplate fixture | `643bfbe` |
| T5 | TF-IDF scorer | `975e7f4` |
| T6 | Greedy selector + reorder | `8e523a5` |
| T7 | Keyword extractor + `__init__.py` shield removed | `0f46a65` |
| T8 | Fixture walker test | `733ae16` |
| T9 | CLI | `a238d02` |
| T10 | Determinism test | `b507ea4` |
| T11 | Zero-dep check | `b08943c` |
| T12 | Optional TextRank (DC-003 cleared) | `2d28bf7` |
| T13 | CI workflows + 3.13 classifier | `3114071` |
| T14 | README | `4c3e7d4` |
| T15 | DC-001 gate + tag `v0.0.1` | tag → `4c3e7d4` |
| post-tag | defensive `.gitignore` + archived secret-scan | `7a0a082`, `2a56674` |

## What's left for `v0.1.0`

From the mission brief (`skill-output/mission-brief/Mission-Brief-skimr.md`), v0.1.0 ships when these four SCs have concrete evidence. Plan 1 cleared the other six.

| SC | Gap | Work needed | Rough size |
|---|---|---|---|
| **SC-002** | Rust port passing every fixture **byte-identical to Python** | Plan 2 — new Rust crate, `regex`-only dep, same fixture corpus | Big |
| **SC-006** | Fastest of {Python skimr, Rust skimr} within **2× Sumy** wall-clock on same corpus / machine | Benchmark harness + Sumy baseline + results in `benchmarks/results-{date}.md`. DC-004: capture Sumy baseline first. | Small (without Rust), Medium (with) |
| **SC-009** | Integrated into ≥1 real Yonk project with `docs/integration-memo.md` | Pick host (candidates: `yonk-taskstash`), capture before/after on real input. DC-005: capture *before* behavior before replacing. | 1 evening |
| **SC-010** | Public GitHub repo, fresh-clone to summary under 5 min | Currently private. Flip visibility + timed fresh-clone run. | Small |

**DC-FINAL before tagging v0.1.0:** re-read the brief and confirm every SC has concrete evidence.

## Carry-forward concerns

1. **T12 plan deviation (documented):** `summarize_textrank` uses networkx's private `_pagerank_python` entry point instead of public `nx.pagerank` to keep `[textrank]` free of scipy/numpy. Stable across networkx 3.x; pin the version in CI if you want extra safety. Rationale in the T12 commit body (`2d28bf7`).

2. **T12 also rewrote** `test_zero_deps.py::test_textrank_not_importable_without_extra` → `test_skimr_default_import_does_not_pull_networkx` as a subprocess check, since the in-process `sys.modules` assertion is invalid once `[textrank]` is installed.

3. **`fixtures/clean_text/crm-boilerplate/expected.txt`** preserves two SQL quirks (trailing `.`, leading `,` in stripped sentences) — faithful to `extractive_functions.sql`. Do not "fix" in the port without simultaneously fixing the SQL.

4. **`fixtures/keyword/pricing-notes/expected.txt`** contains double-periods (`budget..`, `functionality..`) — the SQL splitter does `regexp_replace(E'\n+', '. ')` and the replacement collides with line-terminal periods. Faithful to SQL. Do not "fix" without updating the SQL reference.

5. **Deferred from T2 code review** (not blockers; pin when fixtures demand):
   - `Acme Co. Shares soared.` under-splits (Co. treated as abbrev)
   - Digit-after-period doesn't split (`It was 2023. 2024 was better.`) — spec-strict per SUMMARIZATION.md
   - Dotted-abbreviation regex has overreach complexity; decouple eventually

6. **venv uses `uv`, no `pip`** in it. Use `.venv/bin/python -m pytest ...` directly. For installs use `/home/yonk/.local/bin/uv pip install ...`.

## Companion project

Out-of-core neural summarization (ONNX small int8 LLM + BERT) is seeded at `/home/yonk/yonk-tools/skimr-neural/` — see that directory's README and mission brief. Explicitly out of scope for skimr core forever (per this brief's Out of Scope section).

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest                    # run all tests (64 green)
.venv/bin/skimr --help                        # CLI
git log --oneline                             # see commit progress
gh run list --repo yonk-labs/skimr --limit 5  # CI status
```

## Resume prompts for future sessions

**Plan 2 (Rust port):**
> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr Plan 1 is complete; `v0.0.1` tagged and pushed to `yonk-labs/skimr`. Read `docs/RESUME.md` for state. Next: write and execute Plan 2 — Rust port satisfying SC-002 (byte-identical output to Python across the `fixtures/` corpus). Mission brief: `skill-output/mission-brief/Mission-Brief-skimr.md`. DC-002 is the hard gate: any Rust/Python mismatch means the spec wins, not whichever language's output is convenient.

**Benchmark spike (SC-006):**
> Working directory: `/home/yonk/yonk-tools/extractive_summary`. Build a benchmark harness in `benchmarks/` that times {Python skimr, Sumy} (add Rust skimr when Plan 2 lands) on a corpus comparable to the 1,828-note set in `extractive-performance.md`. DC-004: capture Sumy baseline first. Output goes to `benchmarks/results-{date}.md` per mission brief SC-006.

**Integration memo (SC-009):**
> Working directory: `/home/yonk/yonk-tools/extractive_summary`. Integrate skimr into `yonk-taskstash` (or another existing Yonk project with live summarization). DC-005: capture *before* behavior first (input + existing output). Replace with skimr calls, measure the delta, write `docs/integration-memo.md`. Mission brief SC-009.
