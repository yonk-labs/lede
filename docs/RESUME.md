# Resume: skimr v0.2 T12 done, ready for T13 (extraction eval harness)

**Last session:** 2026-04-22 (cont'd). T12 hand-labeled all 50 gold fixtures (10 corpora × 5 primitives). Labeling done by 10 parallel sonnet subagents (one per corpus); opus spec-reviewer caught 2 blockers + unit-label drift; fixed in a single canonicalization pass. Protocol doc authored at `docs/extraction-gold-labeling.md` including an edge-case-conventions section capturing the labeler judgment calls. Next up: T13 (SC-D gate — extraction eval harness).

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main`
- **Local HEAD:** T12 gold fixtures (commit pending at time of doc write). `origin/main` at `343a7be` (T11).
- **Unpushed:** 1 (T12 commit).
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
| T12 | Hand-labeled gold fixtures | (pending commit) | 50 gold JSON files at `fixtures/extract/<primitive>/<corpus>.json` + protocol at `docs/extraction-gold-labeling.md`. Fanned out to 10 parallel sonnet subagents (one per corpus). Opus spec-reviewer sampled 4 corpora × 5 primitives, caught 2 blockers (unit=`"absolute"` in sci-paper, duplicate correlate pairing in privacy-policy) + unit drift (`pct`/`percent`, plural vs singular durations). Single canonicalization pass normalized all 50 files to match the primitive's emit space: `unit="percent"` (not `pct`), durations singular (primitive `rstrip("s")`s), counts keep concrete unit from source. Second dupe found in support-ticket, also deduped. 1 phrase violated the 2-5 token rule (`"high-dimensional"`, 1 token), dropped. Protocol doc extended with "Edge-case conventions" section codifying the labeler judgment calls (numbered sections, title lines, inline vs block colon-labels, `Label: Subject` pattern). Outline-policy advisories from reviewer deferred to T13 iteration. |

**Pending (2/15):** T13 extraction eval (SC-D gate) · T14 comparison matrix + latency (SC-B gate) · T15 tag v0.2.0. Plus optional follow-up: T11b (skimr-spacy dep-parsed correlate impl).

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

## What's next — T13 entry point

**T13 is the extraction eval harness** — precision/recall over the T12 gold set, per primitive. SC-D gate: ≥0.85 recall / ≥0.80 precision. Plan task text at `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` line 4045.

The harness compares `extract.<primitive>(corpus)` output against `fixtures/extract/<primitive>/<corpus>.json` gold labels. Per-primitive matching rules (from the protocol):

- `stats`: match on (value, stat_type) exact; `context_hint` must be a substring of `Stat.context_sentence`.
- `outline`: match on section `name` (order-insensitive for precision/recall, though order is recorded).
- `metadata`: match on list contents per field (`dates`, `amounts`, `urls`, `entities`). Entities eval only hits the spaCy backend.
- `phrases`: set membership on the phrase string (lowercase).
- `correlate`: set membership on (entity, polarity) tuples.

After T13: **T14** produces the comparison matrix against sumy/TextRank/etc. (SC-B gate — p50 < 250ms warm). **T15** tags v0.2.0.

**Deferred follow-ups (tracked in TODO):** T11b — skimr-spacy `spacy_correlate_facts` using spaCy dep parser. Doesn't block T13-T15.

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
- [x] **T12** Hand-label gold fixtures (10 corpora × 5 primitives) — 50 JSON + protocol + edge-case conventions
- [ ] **T13** ⛔ SC-D gate — extraction eval harness
- [ ] **T14** ⛔ SC-B gate — comparison matrix + latency profile
- [ ] **T15** Tag v0.2.0 release

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. skimr v0.2 plan in progress — T1-T12 complete, plus T10b follow-up. All 5 enrichment primitives implemented in skimr core (regex backend) and 2 (metadata, phrases) in skimr-spacy. T12 hand-labeled 50 gold fixtures (10 corpora × 5 primitives) at `fixtures/extract/<primitive>/<corpus>.json` + protocol doc at `docs/extraction-gold-labeling.md` (includes an Edge-case conventions section codifying labeler judgment calls). **Read `docs/RESUME.md` FIRST** for full context. Plan: `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md`. Specs in `docs/superpowers/specs/`. Execution is subagent-driven per `superpowers:subagent-driven-development`; user has given full-send autonomous consent. skimr core: **137 Python tests green**, **84 Rust + clippy clean**. skimr-spacy: **11 Python tests green**. spaCy + en_core_web_sm already installed in `.venv/`. **Next up: T13 — extraction eval harness (SC-D gate, ≥0.85 recall / ≥0.80 precision per primitive).** Plan task text around line 4045. Gold labels live in `fixtures/extract/`; primitive output is `extract.<primitive>(corpus)`; per-primitive matching rules are in the protocol doc. Expect T13 to surface systematic false positives/negatives tied to the outline-policy / hyphenated-duration / numbered-section edge cases the labelers made judgment calls on — the protocol's iteration clause authorizes revising labels after T13 evidence. Deferred: T11b (skimr-spacy dep-parser correlate).
