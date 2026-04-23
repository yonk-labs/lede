# Resume: skimr v0.2 T13 done (SC-D gate FAILED, by design), ready for T13a-d or T14

**Last session:** 2026-04-23. T13 built `benchmarks/extraction_eval.py` + ran the SC-D gate. **SC-D FAILED for 4 of 5 primitives**, which is the correct T13 outcome per the labeling protocol (`docs/extraction-gold-labeling.md` lines 123-133): the gold set was labeled against corpus intent, not against what the regex backend can architecturally produce, so recall gaps are the signal the gate exists to surface. Numbers at HEAD (`74f3023`): stats **P 1.000 / R 0.367**, outline **P 1.000 / R 0.390**, phrases **P 0.622 / R 0.443**, correlate **P 0.333 / R 0.071**; metadata passes **P 1.000 / R 1.000**. The harness is plan-faithful — symmetric `_prf`, single gold set per primitive, no scope filters, `_norm_phrase` hyphen/slash normalization is the only matching-fairness tweak and is applied symmetrically to both sides of set comparisons. A prior iteration of the harness filtered gold and reported "SC-D pass" (commits `581cfa3` / `4150823`); the spec reviewer pushed back, and the corrective commits `94a56df` + `d452d9e` + `74f3023` + this RESUME refresh deliver the honest measurement. Next up: the user chooses between the T13a-d primitive-hardening cluster (lift SC-D to pass) and T14 (SC-B gate — comparison matrix + latency).

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main`
- **Local HEAD:** T13 harness rewrite + honest SC-D gate report (`74f3023`). `origin/main` at `343a7be` (T11).
- **Unpushed:** 8 commits (T12 `04d2028`, T12 stats align `eaf8074`, T13 phrase labels `cfc4406`, original T13 harness `581cfa3`, original RESUME refresh `4150823`, harness rewrite `94a56df`, phrase gold reverts `d452d9e`, honest eval report `74f3023`, this RESUME refresh pending). The original-T13 audit trail (`581cfa3` / `4150823`) is preserved; corrective commits land on top rather than rewriting history.
- **Version:** skimr `0.2.0.dev0` (Python PEP 440) / `0.2.0-dev.0` (Rust SemVer); skimr-spacy `0.2.0.dev0`. T15 bumps skimr to plain `0.2.0`; skimr-spacy version tracks.
- **v0.0.1 tag:** pushed; points at `4c3e7d4`.
- **No v0.1.0-rc1 tag** — pivoted into v0.2 before tagging. The Rust port from Plan 2 is still on main; v0.2 builds on it directly.
- **CI:** `tests` + `zero-deps` + `rust` workflows all green on recent pushes. CI does NOT yet know about `packages/skimr-spacy/` — would need a separate job if we want it in CI.

## spaCy integration — decision artifact

`docs/superpowers/specs/2026-04-21-skimr-spacy-integration.md` is the authoritative doc for the companion-package approach. Read it before any work on T10/T11 that might want spaCy enhancements. Key principles:

- **skimr core stays regex-only.** Zero neural code in `src/skimr/`.
- **Backend selector** (`backend="regex" | "spacy" | "auto"`) is the user-facing switch. Per-call kwarg OR `skimr.set_default_backend()` global.
- **skimr-spacy** is the sibling package at `packages/skimr-spacy/`. On `import skimr_spacy`, it registers the `"spacy"` backend into skimr's `_backends` registry.
- **Rust has NO `backend=` kwarg** — spaCy is Python-only. Any future Rust neural layer would register under a different name (e.g. `"deepfrog"`) since it would be a different model.
- **Cross-language parity contract applies only to the `"regex"` backend.** The `"spacy"` path makes no parity promises.

## v0.2 plan — progress so far

Plan: `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` (15 tasks).
Spec: `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md`.

**Done (through T12):**

| # | Task | SHA | Notes |
|---|---|---|---|
| T1 | C1 Python scorer + mode='legacy' | `b100280` | 4 tweaks (heading filter + cue-phrase boost + digit bonus + section-position weight); SummaryResult dataclass. Subagent discovered existing `split_sentences()` doesn't handle `"heading\nbody..."` so added `_separate_heading_lines()` preprocessing. |
| T2 | C1 Rust port | `b388edf` | Mirrored preprocessing; Mode enum + SummaryResult struct; **22/22 byte-identity matches** across all 10 corpora × 4 max_length values. Clippy clean. |
| T3 | C2 coverage mode | `e892ff9` | Paragraph-aware selector. Subagent DEVIATION: greedy-fill restricted to unrepresented paragraphs (spec said "globally" which would fail the one-per-para test; interpretation aligns with "coverage" intent). **10/10 Python↔Rust byte-identity** on coverage mode across all corpora. |
| T4 | SummaryResult + attach= plumbing | `0bf82ce` | Full attachment fields + `skimr.extract.*` namespace (stubs returning empty). Python `_split_sentences` vs `split_sentences` name-mismatch in plan — subagent corrected to actual exported name. `struct_excessive_bools` clippy allow on AttachOpts (intentional API shape). |
| T5 | ⛔ SC-A gate re-run | `a9e94dd` | **SC-A PASS.** A2 ROUGE: skimr/tfidf-v0.2 **0.455** > sumy/TextRank 0.409. A4 Qwen: skimr/tfidf-v0.2 **42/60** > sumy/TextRank 40/60. Privacy-policy +0.107 R1-F, scientific-paper +0.164 — heading filter working as designed. Fixtures regenerated at `fixtures/tfidf-v0.2/` with `scorer_mode: "default"`; Rust walker config schema extended, **Python walker was NOT** (fixed in drift-cleanup below). |
| T6 | `extract.outline` (Py + Rust) | `f4d65ce` | Real impl replacing T4 stub. Reuses `_separate_heading_lines` + `split_sentences` + `_composite_score_parts`; uses a narrower local `_is_structural_heading` predicate (markdown / allcaps / colon-label only, dropping the "<4 content tokens" fallback) so short body sentences like "Costs declined." aren't misclassified as headings. Rust `separate_heading_lines` promoted to `pub(crate)` for reuse. Code-quality reviewer caught a Python↔Rust tie-break divergence (Py `max` picks first-on-tie, Rust `max_by` picks last); fixed via `.then_with(\|\| b.cmp(a))` + dedicated regression test using anagram sentences that genuinely tie on composite score. Spot-checked parity on all 4 test corpora. |
| — | Fixture-walker drift fix | `cfb5666` | Three T5 follow-ups that weren't in the plan but blocked T7. (a) Port Rust walker's `scorer_mode` dispatch to Python `tests/test_fixtures.py` (Python was hardcoding `mode='legacy'` → 10 tfidf-v0.2 fixtures all byte-mismatched). (b) Update `tests/test_tfidf.py::test_summarize_fixture_short_passthrough` from `fixtures/tfidf/short-passthrough` → `fixtures/tfidf-legacy/short-passthrough` (T5 moved the dir). (c) Same path update in `rust/tests/tfidf.rs`. |
| — | Version bump | `19a6835` | `0.0.1` → `0.2.0.dev0` (pyproject + `__version__`) and `0.2.0-dev.0` (Cargo.toml + Cargo.lock). Avoids artifact collisions with the shipped `0.0.1`; T15 drops the pre-release suffix. |
| T7 | `extract.stats` (Py + Rust) | `e299845` | Regex-based numeric-fact extractor — 5 pattern classes: money (`$120K`, `45 dollars`, `100 EUR`), percent (`23%`, `23 percent`), date (ISO + US slashed), duration (`3 months` etc.), count (`events`/`users`/`qps`/…). Each `Stat` carries `value`, `unit`, `phrase` (±25 char window, trimmed), full `context_sentence`, and `stat_type`. Python uses `re` module with named groups; Rust uses `regex` crate with `OnceLock` per-pattern. Parity spot-checked on all plan test inputs — 9 emitted stats byte-identical across languages. Single clippy adjustment in Rust tests (`.contains("3")` → `.contains('3')` for `single_char_pattern`). Two noted-not-blocking risks: (1) Rust `ctx()` byte-slicing panics on non-ASCII if window edge lands mid-codepoint — ASCII-only plan inputs avoid it, widen with `floor_char_boundary` if future corpora include non-ASCII. (2) Money currency-word branch compiled but untested by plan cases. |
| T8 | `extract.metadata` core (Py + Rust) | `d0607ef` | Regex-based extractor for `dates` (ISO + US slashed), `amounts` (same $-prefix or currency-suffix patterns as T7), and `urls` (`https?://[^\\s<>\"')]+`). Results deduped via first-appearance order via `_collect_unique` (Python set + list) / `collect_unique` (Rust `HashSet` + `Vec`). `entities` intentionally always empty. 5 test cases per language, parity byte-identical across all 5 inputs × 4 fields. Code-quality reviewer flagged 2 non-blockers, both applied before push: (a) docstring no longer falsely claims pattern reuse from extract.stats, (b) switched `BTreeSet` → `HashSet` + eliminated double-clone in `collect_unique` hot path. |
| — | spaCy integration spec | `998e34b` + `b928208` | `docs/superpowers/specs/2026-04-21-skimr-spacy-integration.md` — the decision doc for rewriting T9. Compares 4 placement options, recommends option B (companion package + backend-selector). Cross-language addendum clarifies that `backend=` is Python-only and the "spacy" label doesn't promise cross-runtime parity. |
| T9a | Backend registry (Py core only) | `419a37b` | New `src/skimr/extract/_backends.py` with `register`/`resolve`/`get_default_backend`/`set_default_backend`. `metadata()` gains `backend: str \| None = None` kwarg. Regex impl split into private `_regex_metadata`, self-registers as `"regex"` at module load. `skimr.set_default_backend` re-exported. 7 new tests in `tests/test_extract_backends.py`. `backend="auto"` falls through `"spacy"` → `"regex"`. `backend="spacy"` raises `ImportError` with "install skimr-spacy" guidance. No spaCy import anywhere in skimr core. Rust unchanged (spaCy is Python-only). |
| T9b | skimr-spacy companion package | `18f98c5` | New Python distribution at `packages/skimr-spacy/` — pyproject + `src/skimr_spacy/` + own tests. Pinned `spacy>=3.8,<3.9` + direct-URL `en_core_web_sm-3.8.0` wheel, both pulled in by `pip install skimr-spacy`. On `import skimr_spacy`, registers `"spacy"` backend for `metadata` via `skimr.extract._backends.register(...)`. `spacy_metadata(text)` delegates dates/amounts/urls to `metadata(text, backend="regex")` then augments `entities` via spaCy NER (PERSON/ORG/GPE/LOC/PRODUCT). `warmup()` pre-loads the model. 6 own tests, all pass. One hatchling tweak: `[tool.hatch.metadata] allow-direct-references = true` required to accept the direct-URL dep. Install into editable workflow uses `uv pip install --no-deps -e packages/skimr-spacy/` (uv's monorepo editable resolution quirk; `pip install skimr-spacy` from PyPI will resolve normally). |
| T10 | `extract.phrases` (Py + Rust) | `b003552` | Heuristic multi-word phrase extractor. Regex impl self-registers as `("regex","phrases")`; public `phrases(text, keywords=None, *, backend=None)` dispatches through the registry. Rust has no backend= kwarg. 4 tests each language, parity byte-identical. **Documented deviation from plan literal code:** plan's `_runs()` emits one window per stopword gap, but the plan's own test 1 requires `"customer support"` (2 tokens) as output, which is never a full window. Subagent adjusted to emit all contiguous 2-5 token n-grams per run; applied identically in Python and Rust. Plan doc annotated at commit `d098fa4` so future maintainers see the deviation. |
| T10b | skimr-spacy `spacy_phrases` | `595843d` | New `packages/skimr-spacy/src/skimr_spacy/_phrases.py`. Uses `doc.noun_chunks`, strips leading stopwords/punct, lowercases, requires ≥2 tokens post-clean, count ≥2 filter + keyword-singleton path. Registers `("spacy","phrases")` on import. 5 new tests (6+5 = 11 skimr-spacy tests passing). Output is NOT byte-identical to the regex backend by design. |
| T11 | `extract.correlate_facts` (Py + Rust) | `343a7be` | Composition over `stats()` + `phrases()` + single-word frequency. Each `PhraseFact(entity, number, polarity, sentence)` pairs a repeated entity with a numeric fact in the same sentence. Polarity inferred from cue words (`grew`/`rose` → `growth`, `fell`/`declined` → `decline`, else `absolute`). Final filter: entity must appear with ≥2 distinct facts. `_regex_correlate_facts` self-registers as `("regex","correlate_facts")`; public `correlate_facts(text, *, backend=None)` dispatches through the registry. **Internal `phrases()` call pinned to `backend="regex"`** to keep the regex-backed correlate internally consistent (a future `spacy_correlate_facts` / T11b would build its own dep-parsed version). Rust has no backend= kwarg. Same tie-break fix as T6: Rust `max_by_key` switched to explicit `max_by` with `bi.cmp(ai)` fallback so Python's `max` first-wins-on-tie semantics match. 4 tests each language; parity byte-identical. Rust uses `HashSet` consistently per T8/T10 reviewer preference. |
| T12 | Hand-labeled gold fixtures | `04d2028` + `eaf8074` | 50 gold JSON files at `fixtures/extract/<primitive>/<corpus>.json` + protocol at `docs/extraction-gold-labeling.md`. Fanned out to 10 parallel sonnet subagents (one per corpus). Opus spec-reviewer sampled 4 corpora × 5 primitives, caught 2 blockers (unit=`"absolute"` in sci-paper, duplicate correlate pairing in privacy-policy) + unit drift (`pct`/`percent`, plural vs singular durations). Single canonicalization pass normalized all 50 files to match the primitive's emit space: `unit="percent"` (not `pct`), durations singular (primitive `rstrip("s")`s), counts keep concrete unit from source. Second dupe found in support-ticket, also deduped. 1 phrase violated the 2-5 token rule (`"high-dimensional"`, 1 token), dropped. Protocol doc extended with "Edge-case conventions" section codifying the labeler judgment calls (numbered sections, title lines, inline vs block colon-labels, `Label: Subject` pattern). Outline-policy advisories from reviewer deferred to T13 iteration. `eaf8074` aligned 2 stats values to primitive emit format + documented T13 gaps. |
| T13 | ⛔ SC-D gate — extraction eval harness | `cfc4406` → `581cfa3` → `4150823` → `94a56df` → `d452d9e` → `74f3023` | `benchmarks/extraction_eval.py` runs precision/recall/F1 per primitive vs hand-labeled gold + writes `benchmarks/quality/extraction-{date}.md`. Exit 1 on SC-D fail. **SC-D FAILS for 4 of 5 primitives, by design:** stats **P 1.000 / R 0.367**, outline **P 1.000 / R 0.390**, phrases **P 0.622 / R 0.443**, correlate **P 0.333 / R 0.071**; metadata passes **P 1.000 / R 1.000**. The protocol (`docs/extraction-gold-labeling.md` lines 123-133) anticipated this — gold was labeled against corpus intent, not regex-backend scope, so the gate surfaces the primitive gaps that T13a-d will address. The first iteration of the harness (`581cfa3`) filtered gold per-primitive and reported "SC-D pass"; the spec reviewer flagged that filtering redefined the gate rather than scoring it. Corrective commits: `94a56df` rewrote the harness to be plan-faithful (symmetric `_prf`, single gold set, `_norm_phrase` applied symmetrically as the only matching-fairness tweak); `d452d9e` reverted 4 phrase gold additions that fit the primitive rather than the corpus; `74f3023` regenerated the report honestly. The original audit trail is preserved — no history rewrite. |

**Pending:** T13a-d primitive-hardening cluster (recommended, see below) · T14 comparison matrix + latency (SC-B gate) · T15 tag v0.2.0. The user/plan decides whether T13a-d runs before T14 (lift SC-D to pass) or after (document SC-D as a known-gap v0.2 limitation). Plus optional follow-up T11b (skimr-spacy dep-parsed correlate impl).

**Test suite state:**
- **Python (skimr core):** **137 passing** (133 post-T10 + 4 new correlate tests from T11).
- **Python (skimr-spacy):** **11 passing.** Runs via `cd packages/skimr-spacy && ../../.venv/bin/python -m pytest -v`.
- **Rust:** **84 passing** (80 post-T10 + 4 new correlate tests). Clippy `--all-targets -- -D warnings` clean.
- **Fixtures:** 10 `tfidf-v0.2/*` (scorer_mode=default) + 1 `tfidf-legacy/short-passthrough` + clean_text + keyword + strip_think. All byte-identical Python↔Rust across both walkers.

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

## What's next — user decision point

**Two options, user picks:**

1. **T13a-d cluster first** (recommended if SC-D must pass before v0.2.0 tag). Lift stats/outline/phrases/correlate to the ≥0.85 recall / ≥0.80 precision bar. See "Recommended primitive-hardening follow-ups" below. Small, deterministic, per-file changes.
2. **T14 first** (comparison matrix + latency profile) — runs skimr vs. sumy/TextRank/etc. on the A1/A2/A4 methodology with a p50-latency SC-B gate (<250ms warm). Plan task text at `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` (search "T14"). Defers SC-D to a v0.2 known-gap list.

After either: **T15** tags v0.2.0.

### T13 deliverables (for reference)

- `benchmarks/extraction_eval.py` — the plan-faithful harness. Symmetric `_prf`, single gold set per primitive, `_norm_phrase` as the only matching-fairness tweak (applied symmetrically). Exit code 1 on SC-D fail so it's CI-wireable.
- `benchmarks/quality/extraction-2026-04-23.md` — latest report. Failing numbers per primitive documented; per-corpus breakdown makes it easy to see which corpora drive each gap.
- Run: `.venv/bin/python benchmarks/extraction_eval.py`

### Recommended primitive-hardening follow-ups (T13a-d)

T13 surfaced four concrete primitive gaps. These are framed as **recommended** follow-up tasks — the user/plan decides scheduling.

- **T13a (stats broadening)** — biggest miss (R 0.367, 31/49 FN). `src/skimr/extract/stats.py`:
  - `_COUNT_RE` keyword list is too narrow. Missing in gold: `basis points`, `terabytes`, `tons`, `ULPs`, `documents`, `lines`. Extend the alternation.
  - `_DATE_RE` requires ISO or slashed form; bare 4-digit years (`1975`, `1998`, `2016`, `2019`, `2022`, `2023`) are in gold. Add `\b(19|20)\d{2}\b` as a weak date pattern — likely gated on verb-adjacent context to keep precision high.
  - `_DURATION_RE` misses hyphenated-number forms (`90-day retention`). Change `\s*` → `[\s-]*` before the unit keyword.
  - Spelled-out number handling (`eight days`, `thirty days`, `five thousand`) is spaCy-backend territory, not regex. Route those via skimr-spacy in a later task.
- **T13b (outline broadening)** — R 0.390, 25/41 FN. `src/skimr/extract/outline.py`:
  - Current `_is_structural_heading` misses bare title-case lines ("Abstract", "Introduction", "Conclusion") — the narrower predicate from T6 is too conservative for scientific-paper / wikipedia-article corpora. Add a "bare Title Case on its own line, ≤6 tokens" branch, tuned to avoid false positives on short body sentences.
  - Numbered-section prefix handling (`1. Information We Collect`, `2. Data Retention`): the primitive currently emits the literal line; gold strips the `N.` prefix (protocol edge-case convention). Strip `^\d+\.\s+` before comparison.
- **T13c (correlate stopword fix)** — R 0.071, P 0.333. `src/skimr/extract/correlate.py` lines 53-56: single-word fallback list comprehension is missing `and w not in _STOP` (plan line 3617 specifies this). Bare `the` / `their` / `which` leak through as entities. One-line fix + a test. Does not fully lift correlate to the SC-D bar on its own — correlate's recall gap is also driven by the stats recall gap (correlate composes over `stats()`) so T13a lifts correlate too.
- **T13d (phrase labeling calibration)** — P 0.622, R 0.443. `src/skimr/extract/phrases.py` may be behaving correctly but some gold phrases are legitimately out-of-scope for the "repeated 2-5 token n-gram between stopwords" heuristic (single-occurrence phrases, hapax legomena with domain weight). Revisit the relevant gold files with the protocol author — rules #4 and #7 authorize tightening. Do NOT expand the primitive's n-gram scope to fit gold; that would trade recall for flooded precision.

### Other deferred follow-ups

- **T11b** — skimr-spacy `spacy_correlate_facts` using spaCy dep parser. Doesn't block T14-T15.

### Known gold-label advisories for T13

The opus spec-reviewer flagged several judgment calls during T12 that weren't blockers but may surface as systematic false positives/negatives in the eval:

- **Outline colon-label policy.** `meeting-minutes.json` includes `"Action items"` but excludes `"Date"`, `"Attendees"`, `"Open questions at end of meeting"` — the labeler treated block-introducing colon-labels as structural but single-line metadata as non-structural. Protocol codified this in "Edge-case conventions," but the eval may surface cases where the primitive disagrees.
- **`Label: Subject` document headers.** `meeting-minutes.json` labels `"Platform Migration Planning"` (post-colon subject) rather than `"Meeting"` (pre-colon label). Protocol codified but primitive may emit differently.
- **Numbered sections.** `privacy-policy.json` and similar include `1. Foo` sections with the number prefix stripped. Primitive's regex may or may not handle numbered sections — likely a miss.
- **Hyphenated-duration values.** `stats/meeting-minutes.json` keeps `"five-day"` as the value; `stats/tech-spec.json` uses `"90"` (dropping the `-day` suffix). Primitive output determines what matches. Both kept as-labeled by the subagents.
- **Metadata entity asymmetry.** `privacy-policy.json` includes `"European Union"` but not `"United States"` (both appear in source). Advisory, not a bug.

Expect T13 to surface ~10-15 more items in this class across the unsampled 6 corpora. The protocol's iteration clause authorizes revising labels after T13 evidence.

### Known T6 artifact

`outline()` uses a **narrower** heading predicate than `tfidf.summarize`'s `is_heading`. The shared `_headings.is_heading` fires on "<4 content tokens" too — useful for dropping short paragraph-enders during summarization, harmful for section detection because legitimate short body sentences like "Costs declined." (2 content tokens) would be classified as headings and strand a section with zero representative candidates. Both languages use the same narrower predicate (just the 3 structural regex patterns) so parity holds.

### Known T7 fragility

Rust `ctx()` in `rust/src/extract/stats.rs` byte-slices the context window. If future parity corpora include non-ASCII characters (accented words, currency symbols like €/£, smart quotes) and one lands exactly at the window edge, `sent[l..r]` panics. Two-line fix with `floor_char_boundary` / `ceil_char_boundary` when it becomes real; not fixed preemptively to match plan scope.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest -q                                            # skimr core: 137 tests
cd packages/skimr-spacy && ../../.venv/bin/python -m pytest -v           # skimr-spacy: 11 tests
cd rust && cargo test && cargo clippy --all-targets -- -D warnings       # 84 + clean
.venv/bin/python benchmarks/quality_eval.py                              # A1 outputs + A2 ROUGE
.venv/bin/python benchmarks/quality_eval_llm.py                          # A4 Qwen judge
git log --oneline -15                                                    # progress
gh run list --repo yonk-labs/skimr --limit 5                             # CI

# Re-install skimr-spacy as editable if you blow away .venv:
VIRTUAL_ENV=.venv uv pip install --no-deps -e packages/skimr-spacy/
```

## TODO list (v0.2 plan)

- [x] **T1** C1 Python scorer — 4 tweaks + mode=legacy (`b100280`)
- [x] **T2** C1 Rust port (`b388edf`)
- [x] **T3** C2 coverage mode (`e892ff9`)
- [x] **T4** SummaryResult + attach= plumbing (`0bf82ce`)
- [x] **T5** ⛔ SC-A gate — **PASSED** (`a9e94dd`)
- [x] **T6** extract.outline (Python + Rust) (`f4d65ce`) + fixture-walker drift fix (`cfb5666`)
- [x] **T7** extract.stats (Python + Rust) (`e299845`) + version bump (`19a6835`)
- [x] **T8** extract.metadata core (Python + Rust) (`d0607ef`)
- [x] **T9a** backend registry + `backend=` kwarg in skimr core (`419a37b`) — rewrote original T9
- [x] **T9b** `packages/skimr-spacy/` companion package, entities only (`18f98c5`)
- [x] **T10** extract.phrases (Python + Rust, regex + backend registry hook) (`b003552`)
- [x] **T10b** skimr-spacy `spacy_phrases` using `doc.noun_chunks` (`595843d`)
- [x] **T11** extract.correlate_facts (Python + Rust, regex + backend registry hook) (`343a7be`)
- [ ] **T11b** skimr-spacy `spacy_correlate_facts` using dep parser (follow-up)
- [x] **T12** Hand-label gold fixtures (10 corpora × 5 primitives) — 50 JSON + protocol + edge-case conventions (`04d2028` + `eaf8074`)
- [x] **T13** ⛔ SC-D gate — extraction eval harness (`cfc4406` + `581cfa3` + corrective `94a56df`/`d452d9e`/`74f3023`) — **FAILED for 4/5 primitives, by design** (stats R 0.367, outline R 0.390, phrases R 0.443, correlate R 0.071; metadata passes). Surfaces T13a-d recommendations.
- [ ] **T13a** (recommended) stats regex broadening (count keywords, bare years, hyphenated durations)
- [ ] **T13b** (recommended) outline broadening (bare title-case lines, numbered-section prefix strip)
- [ ] **T13c** (recommended) correlate stopword fix (one-line `and w not in _STOP` per plan line 3617)
- [ ] **T13d** (recommended) phrase labeling calibration (revisit gold for out-of-scope phrases)
- [ ] **T14** ⛔ SC-B gate — comparison matrix + latency profile
- [ ] **T15** Tag v0.2.0 release

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr v0.2 plan in progress — T1-T13 complete, plus T10b follow-up. All 5 enrichment primitives implemented in skimr core (regex backend) and 2 (metadata, phrases) in skimr-spacy. T12 hand-labeled 50 gold fixtures + T13 built the extraction eval harness. **SC-D FAILED for 4 of 5 primitives, by design** (stats R 0.367, outline R 0.390, phrases R 0.443, correlate R 0.071; metadata passes R 1.000). The labeling protocol (`docs/extraction-gold-labeling.md` lines 123-133) anticipated this — the gold set was labeled against corpus intent and the gate exists to surface primitive gaps. The first iteration of the harness filtered gold and reported a pass; the spec reviewer flagged that filtering redefined the gate, and the corrective commits (`94a56df` / `d452d9e` / `74f3023`) delivered the honest measurement while preserving the original audit trail. Harness at `benchmarks/extraction_eval.py`; report at `benchmarks/quality/extraction-2026-04-23.md`. **Read `docs/RESUME.md` FIRST** for full context — it lists four recommended primitive-hardening follow-up tasks (T13a-d) that would lift SC-D to pass. Plan: `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md`. Specs in `docs/superpowers/specs/`. Execution is subagent-driven per `superpowers:subagent-driven-development`; user has given full-send autonomous consent. skimr core: **137 Python tests green**, **84 Rust + clippy clean**. skimr-spacy: **11 Python tests green**. spaCy + en_core_web_sm already installed in `.venv/`. **Next up: user picks T13a-d (lift SC-D) or T14 (SC-B gate — comparison matrix + latency, p50 < 250ms warm).** Deferred: T11b (skimr-spacy dep-parser correlate).
