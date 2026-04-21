# Resume: skimr v0.2 SC-A gate cleared, stopped after T5

**Last session:** 2026-04-21. Stopped after T5 at commit `a9e94dd`. v0.0.1 shipped (Plan 1, 2026-04-19); Plan 2 Rust port complete but never tagged as v0.1.0-rc1 (we pivoted straight into v0.2 planning after the quality review). v0.2 plan in progress — **SC-A quality gate cleared** on first attempt: skimr/tfidf-v0.2 beats sumy/TextRank on both A2 ROUGE (0.455 vs 0.409) and A4 Qwen judge (42/60 vs 40/60).

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main`
- **Local HEAD:** `a9e94dd`
- **Unpushed:** 0 — `origin/main` is current.
- **v0.0.1 tag:** pushed; points at `4c3e7d4`.
- **No v0.1.0-rc1 tag** — pivoted into v0.2 before tagging. The Rust port from Plan 2 is still on main; v0.2 builds on it directly.
- **CI:** `tests` + `zero-deps` + `rust` workflows all green on recent pushes.

## v0.2 plan — progress so far

Plan: `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` (15 tasks).
Spec: `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md`.

**Done (5/15):**

| # | Task | SHA | Notes |
|---|---|---|---|
| T1 | C1 Python scorer + mode='legacy' | `b100280` | 4 tweaks (heading filter + cue-phrase boost + digit bonus + section-position weight); SummaryResult dataclass; 72 Python tests passing. Subagent discovered existing `split_sentences()` doesn't handle `"heading\nbody..."` so added `_separate_heading_lines()` preprocessing. |
| T2 | C1 Rust port | `b388edf` | Mirrored preprocessing; Mode enum + SummaryResult struct; **22/22 byte-identity matches** across all 10 corpora × 4 max_length values. 56 Rust tests passing; clippy clean. |
| T3 | C2 coverage mode | `e892ff9` | Paragraph-aware selector. Subagent DEVIATION: greedy-fill restricted to unrepresented paragraphs (spec said "globally" which would fail the one-per-para test; interpretation aligns with "coverage" intent). **10/10 Python↔Rust byte-identity** on coverage mode across all corpora. |
| T4 | SummaryResult + attach= plumbing | `0bf82ce` | Full attachment fields + `skimr.extract.*` namespace (stubs returning empty). Python `_split_sentences` vs `split_sentences` name-mismatch in plan — subagent corrected to actual exported name. `struct_excessive_bools` clippy allow on AttachOpts (intentional API shape). 87 Python + 61 Rust tests passing. |
| T5 | ⛔ SC-A gate re-run | `a9e94dd` | **SC-A PASS.** A2 ROUGE: skimr/tfidf-v0.2 **0.455** > sumy/TextRank 0.409. A4 Qwen: skimr/tfidf-v0.2 **42/60** > sumy/TextRank 40/60. Privacy-policy +0.107 R1-F, scientific-paper +0.164 — heading filter working as designed. Fixtures regenerated at `fixtures/tfidf-v0.2/` with `scorer_mode: "default"`; walker config schema extended backward-compatibly. |

**Pending (10/15):** T6 outline · T7 stats · T8 metadata core · T9 metadata NER (skimr[ner]) · T10 phrases · T11 correlate_facts · T12 gold fixtures · T13 extraction eval (SC-D gate) · T14 comparison matrix + latency (SC-B gate) · T15 tag v0.2.0.

**Test suite state:**
- **Python:** 87 passing (64 baseline + 8 scorer + 4 coverage + 11 summaryresult).
- **Rust:** 61 passing (existing + 5 scorer_v0_2 + 4 coverage + 5 summaryresult). Clippy `--all-targets -- -D warnings` clean.
- **Fixtures:** 10 tfidf-v0.2 (scorer_mode=default) + 1 tfidf-legacy + clean_text + keyword + strip_think. All byte-identical Python↔Rust per Rust fixture walker.

## Quality methodology — v0.2 state

Three methodologies established in the prior review (`review-2026-04-20.md`):
- **A1 (primary):** author-scored 5-dim rubric /250. Not re-run in T5 — A2+A4 agreement treated as proxy signal for SC-A.
- **A2 (supporting color):** token/bigram ROUGE vs hand-written gold references in `benchmarks/references/`. Noisy signal; lifted ~6% under v0.2 default.
- **A4 (cross-family):** Qwen3-Coder LLM judge via local vLLM at `192.168.1.193:8000/v1`. Cross-family to both Anthropic (reference writer) and OpenAI lineage. 6-summarizer ranking now (was 5 before adding legacy split).

Re-run scripts: `benchmarks/quality_eval.py` (A1+A2), `benchmarks/quality_eval_llm.py` (A4). Latest outputs under `benchmarks/quality/` dated 2026-04-21.

## Execution cadence — what worked

Same subagent-driven pattern as Plan 2, with task-specific dispatches via `superpowers:subagent-driven-development`:

- **Task prompt includes full text** (no reading plan file) + scene-setting + explicit constraints + cross-language parity requirement where relevant + self-review checklist.
- **Byte-identity critical tasks** (T2 default-mode port, T3 coverage port): demanded spot-check against Python output as part of DONE criteria. T2 spot-checked 22/22, T3 spot-checked 10/10.
- **Inline for validation** (T5): the SC-A gate eval is author-scoring + doc-writing, not mechanical implementation — done in main context.
- **Each task commits independently**; pushed at natural break points.

The implementer subagents caught several plan-level issues the plan writer missed:
1. T1: plan referenced `_split_sentences` that doesn't handle embedded headings → subagent added `_separate_heading_lines` preprocessing.
2. T2: plan needed to mirror the T1 preprocessing for parity — subagent read the Python source and ported exactly.
3. T4: plan referenced `_split_sentences` as an import from `..tfidf`, but actual export is `split_sentences` in `skimr.sentences` — subagent corrected.

Accept deviations when: (a) tests pass, (b) byte-identity holds, (c) justification matches the design intent. Reject when: byte-identity fails or scope creep.

## What's next — T6 entry point

**T6 is `extract.outline`** — the first real primitive to replace its T4 stub. Scope:
- Python: detect section headings (reuse `_headings.is_heading` + `heading_name`), pick highest-scoring non-heading sentence per section as `representative_sentence`. Depth from `^#+` count.
- Rust: port.
- Cross-language parity required on shared inputs.

After T6-T11 (each adds one primitive), T12 hand-labels gold fixtures (~25 hours of labeling work; parallelizable via subagents given the protocol at `docs/extraction-gold-labeling.md`, which is created IN T12 per the plan). T13 runs the eval harness to verify SC-D (≥0.85 recall / ≥0.80 precision per primitive). T14 produces the comparison matrix (SC-B gate — p50 < 250ms warm). T15 tags v0.2.0.

**No blockers for continuing.** User gave full-send autonomous consent; the subagent cadence is working.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest -q                                            # 87 tests
cd rust && cargo test && cargo clippy --all-targets -- -D warnings       # 61 + clean
.venv/bin/python benchmarks/quality_eval.py                              # A1 outputs + A2 ROUGE
.venv/bin/python benchmarks/quality_eval_llm.py                          # A4 Qwen judge
git log --oneline -15                                                    # progress
gh run list --repo yonk-labs/skimr --limit 5                             # CI
```

## TODO list (v0.2 plan)

- [x] **T1** C1 Python scorer — 4 tweaks + mode=legacy (`b100280`)
- [x] **T2** C1 Rust port (`b388edf`)
- [x] **T3** C2 coverage mode (`e892ff9`)
- [x] **T4** SummaryResult + attach= plumbing (`0bf82ce`)
- [x] **T5** ⛔ SC-A gate — **PASSED** (`a9e94dd`)
- [ ] **T6** extract.outline (Python + Rust)
- [ ] **T7** extract.stats (Python + Rust)
- [ ] **T8** extract.metadata core (Python + Rust)
- [ ] **T9** extract.metadata NER (skimr[ner] extra, Python-only)
- [ ] **T10** extract.phrases (Python + Rust)
- [ ] **T11** extract.correlate_facts (Python + Rust)
- [ ] **T12** Hand-label gold fixtures (10 corpora × 5 primitives)
- [ ] **T13** ⛔ SC-D gate — extraction eval harness
- [ ] **T14** ⛔ SC-B gate — comparison matrix + latency profile
- [ ] **T15** Tag v0.2.0 release

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr v0.2 plan is in progress — T1-T5 complete, **SC-A quality gate cleared** (skimr/tfidf-v0.2 beats sumy/TextRank on both A2 ROUGE and A4 Qwen judge). Local and remote `main` are at `a9e94dd`; nothing unpushed. **Read `docs/RESUME.md` FIRST** for full context. Plan: `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md`. Spec: `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md`. Execution is subagent-driven per `superpowers:subagent-driven-development`; user has given full-send autonomous consent. Python: 87 tests green. Rust: 61 tests green + clippy clean. **Next up: T6 extract.outline** — real implementation replacing the T4 stub at `src/skimr/extract/outline.py` and `rust/src/extract/outline.rs`. Uses `_headings.is_heading` + `heading_name` to detect sections; picks highest-scoring non-heading sentence per section. Python-first, Rust port after, cross-language parity required.
