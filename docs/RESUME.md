# Resume: skimr v0.2.0 tagged locally — push to origin pending

**Last session:** 2026-04-26. Closed v0.2: T14 SC-B comparison matrix landed (10 corpora × 11 methods, every cell ≤ 4 ms vs the 250 ms budget), T15 release prep done (versions bumped, README "What's new in v0.2" section added, brief.rs clippy lint allow-listed). Local tag `v0.2.0` placed; **`git push origin main && git push origin v0.2.0` is the only remaining step** and is held back per standing instruction (no push without explicit request).

SC-D ships at **3/5 pass** by design — `phrases` and `correlate` have documented gold/primitive design mismatches, flagged in `README.md` § "Known v0.2 gates", `docs/REFERENCE.md`, and the v0.2.0 tag annotation. They're tracked for v0.3+, not blockers for v0.2.

## Repo state

- **Remote:** https://github.com/yonk-labs/skimr (private, yonk-labs org)
- **Branch:** `main`
- **Local HEAD:** `5380530` (release: v0.2.0). Annotated tag `v0.2.0` points at the same commit. `origin/main` still at `e005c20` (T11).
- **Unpushed:** 27 commits — everything from T12 through `5380530` plus the `v0.2.0` tag.
- **Version:** skimr `0.2.0` / Rust `0.2.0`; skimr-spacy `0.2.0`. Cargo.lock refreshed.
- **CI:** `tests` + `zero-deps` + `rust` green on origin/main. After push, verify all three workflows go green on the tag commit (`gh run list --repo yonk-labs/skimr --limit 5`).

## Test suite state (all green)

- **Python (skimr core):** **176 passing, 2 skipped**. The 2 skips are the `pytest.raises(ImportError)` tests that skip when the optional dep *is* installed.
- **Python (skimr-spacy):** **17 passing**. Runs via `cd packages/skimr-spacy && ../../.venv/bin/python -m pytest -v`.
- **Rust default features:** **113 passing**, clippy `--all-targets -- -D warnings` clean.
- **Rust `--features wordforms`:** **121 passing**, clippy clean.

## SC-D gate status — 3/5 pass under format-tolerant match

Latest eval: `benchmarks/quality/extraction-2026-04-26.md` (re-run at T15 verification; numbers identical to the 2026-04-24 baseline). Match rule is format-tolerant: bidirectional substring on value after hyphen/underscore/whitespace normalization for stats; sub/super-ngram overlap for phrases; strict equality for metadata/outline/correlate. **Not a gate redefinition** — same full T12 gold on both sides, only the match rule tolerates format variance that doesn't change semantic correctness. User ratified this on 2026-04-24. Rationale documented in `benchmarks/extraction_eval.py` module docstring.

| primitive | P | R | F1 | status | summary |
|---|---|---|---|---|---|
| `stats` | 0.913 | 0.857 | 0.884 | **pass** | Closed via T13e (text2num wordforms) + T13a (bare years, hyphenated durations) + T13g (count nouns) + T13g2 (`tons per year/month/day`). |
| `outline` | 0.972 | 0.854 | 0.909 | **pass** | Closed via T13b (bare title-case + numbered sections + ALLCAPS 80) + T13d (em-dash title line). |
| `metadata` | 1.000 | 1.000 | 1.000 | **pass** | No work needed. |
| `phrases` | 0.809 | 0.478 | 0.601 | **FAIL (R)** | T13h subsumption lifted P above 0.80. Recall structurally capped: 60 FN are all gold phrases that appear exactly once in corpus (primitive requires count ≥ 2). Design mismatch between gold's "meaningful" criterion and primitive's "repeated n-gram" heuristic. No regex tweak closes it. YAKE (T13f) underperforms regex on this gold. spaCy noun_chunks has even lower recall. |
| `correlate` | 0.250 | 0.071 | 0.111 | **FAIL** | Gold expects polarities inferred from verbs attached to single-mention entities (e.g. `risk register` mentioned once, labeled with both `growth` and `decline` from one sentence). Neither regex nor spaCy DepMatcher (T11b) produces this without coref + salience ranking. Needs gold-protocol reconciliation. |

**3/5 clearly pass. Phrases and correlate remain v0.3+ work** — their gold fixtures are valid targets for a future coref-capable backend.

## v0.2 plan — this session's commits (on top of T11 `e005c20`)

| # | Task | SHA | Notes |
|---|---|---|---|
| T12 | Hand-labeled gold (50 JSON) | `04d2028` + `eaf8074` | Protocol at `docs/extraction-gold-labeling.md`. |
| T13-corrective | Harness after spec-reviewer rejection of initial filtered-gold approach | `94a56df` + `d452d9e` + `74f3023` + `da7bf2b` | Initial T13 filtered gold to regex scope; reviewer (correctly) flagged gate redefinition. Corrective pass restored symmetric match on full gold. SC-D failed 4/5 then — correctly per protocol lines 123-133. |
| T13c | correlate stopword filter | `ef61b4d` | One-line bug: missing `not in _STOP` at `src/skimr/extract/correlate.py:53-56`. |
| T13a | stats regex broadening | `cbf8e43` | Bare years 1900–2099, hyphenated duration `90-day`, +keywords `terabytes`/`basis points`. |
| T13b | outline heading broadening | `57f323c` | Bare title-case pattern, numbered prefix (`1. Foo`), ALLCAPS upper bound 28 → 80. |
| T13e | text2num wordforms (optional dep) | `544a0b6` | `convert_word_names=True` kwarg on `stats()` / `correlate_facts()`. Python `[wordforms]` extra + Rust `wordforms` cargo feature. Both bind to the same Rust crate → byte-identical parity free. |
| T13f | YAKE phrases backend | `3f5dc4b` | `backend="yake"` (Python only, `[yake]` extra). Explored but **doesn't close SC-D phrases**; kept for users who want salient-phrase semantics vs regex's repeated-n-gram semantics. |
| T11b | spacy_correlate_facts via DepMatcher | `18428c7` | skimr-spacy `("spacy", "correlate_facts")` backend. Recall 5× lift but precision tanked — gold expects coref. |
| T13g | stats +common count nouns | `3e95cee` | `items/documents/lines/entries/records/files/actions/sections`. |
| T13h | phrases sub-ngram subsumption | `bb9a89a` | Drop ngram A when a longer ngram B contains A at equal count. P 0.62 → 0.71. |
| T13d | outline em-dash title | `8e6cd0d` | `Title — metadata` pattern + `heading_name` em-dash strip. |
| T13g2 | stats +`tons per year/month/day` | `37eeacb` | **Stats crosses SC-D** (R 0.816 → 0.857). |
| Harness: format-tolerant | `c201571` | Bidirectional substring on value + sub/super overlap on phrases. Full gold preserved on both sides. |
| Docs: REFERENCE.md | `4ea62d7` | 282-line primitive catalog — locks API shapes for T16 + T17. |
| T16 | `extract.toc()` + `extract.key_facts()` | `d4b9730` | `toc(text)` → section names. `key_facts(text, max_facts=10, convert_word_names=False)` → sentences containing stats, ranked by composite-tfidf + stat-density, deduped by `(stat_type, norm value)`, document order. Py + Rust byte-identical. |
| T17 | `skimr.brief()` | `92b9820` | Composes summarize + key_facts + toc. `format="string" \| "markdown" \| "dict"`. `overview_max=0.35` clamped `[0.05, 0.50]`. `include_phrases=False` default. Agnostic of doc type. Auto-enables wordforms when text2num importable (Python) / `wordforms` feature on (Rust). 9 Python + 7 Rust tests. |

**v0.2 closeout:**
- [x] **T14** SC-B gate — comparison matrix + latency profile (`efeba34`). Worst skimr cell 3.56 ms p50; sumy 11–12 ms p50; rust 0.13 ms p50. ~70× headroom on the 250 ms budget.
- [x] **T15** Tag v0.2.0 release. Versions bumped, README v0.2 section, brief.rs clippy allow-list, RESUME refreshed, `release: v0.2.0` commit + annotated `v0.2.0` tag.
- [ ] `git push origin main && git push origin v0.2.0` — held for explicit user request.
- [ ] Post-push: `gh run list --repo yonk-labs/skimr --limit 5` to confirm CI green on tag.

## Key artifacts & where they live

| What | Path |
|---|---|
| **Primitive reference guide** | `docs/REFERENCE.md` |
| **Mission brief (active)** | `skill-output/mission-brief/Mission-Brief-skimr.md` |
| **v0.2 design spec** | `docs/superpowers/specs/2026-04-21-skimr-v0-2-design.md` |
| **v0.2 plan** | `docs/superpowers/plans/2026-04-21-skimr-v0-2-plan.md` (T14 at line 4250) |
| **spaCy integration policy** | `docs/superpowers/specs/2026-04-21-skimr-spacy-integration.md` |
| **Gold-labeling protocol** | `docs/extraction-gold-labeling.md` |
| **10 source corpora** | `benchmarks/corpus/*.txt` |
| **50 gold fixtures** | `fixtures/extract/{stats,outline,metadata,phrases,correlate}/*.json` |
| **Eval harness** | `benchmarks/extraction_eval.py` |
| **Latest SC-D report** | `benchmarks/quality/extraction-2026-04-24.md` |
| **Quality benchmark scripts (T5 / SC-A)** | `benchmarks/quality_eval.py`, `benchmarks/quality_eval_llm.py` |
| **Sample summaries/briefs (not committed)** | `/tmp/<corpus>-summary.txt`, `/tmp/<corpus>-brief.md` |
| **Python core** | `src/skimr/` — `summarize` in `tfidf.py`; `brief` in `brief.py`; extract primitives in `src/skimr/extract/` |
| **Rust mirror** | `rust/src/` — structure mirrors Python |
| **skimr-spacy companion** | `packages/skimr-spacy/src/skimr_spacy/` |

## Design decisions reconciled over the last 3 sessions

1. **SC-D match rule is format-tolerant.** Strict substring penalized correct extractions with format variance (`"five thousand"` vs gold `"five-thousand-document"`). User ratified bidirectional-substring + normalized comparison on 2026-04-24. Not a gate redefinition — full gold on both sides.

2. **Phrases and correlate gold/primitive mismatches are real and design-level.** Explored every combination: regex, YAKE, spaCy noun_chunks, spaCy DepMatcher, text2num, subsumption, count thresholds, union/intersection combos. None close the gate under current gold without fundamental algorithm changes (coref for correlate; "meaningful phrase" classifier for phrases). Ship 3/5 pass and document. Don't pretend by further gold massage.

3. **text2num optional dep is the right shape.** Python 3.x binds to the Rust 2.6 crate → byte-identical parity for free. Gated behind `[wordforms]` extra (Python) / `wordforms` cargo feature (Rust). Default path stays zero-dep. `brief()` auto-enables when available.

4. **YAKE stays registered even though it doesn't close SC-D.** Users who want salient/ranked key phrases use `backend="yake"`. Callers who want repeated multi-word surfaces use regex. spaCy for named noun phrases. All three valid, just different.

5. **`summarize()` = minify, `brief()` = at-a-glance.** Different products. Both stay.

6. **`brief()` is agnostic of document type.** No heuristics detecting "this is a scientific paper, use the Abstract." Callers who want custom behavior compose their own.

7. **Rust has no `backend=` kwarg.** Cross-language parity applies only to regex backend. Python-only backends: spaCy, YAKE. The `wordforms` feature is different — same Rust crate bound from Python.

8. **Two new primitives, one new top-level API.** `toc()`, `key_facts()`, `brief()` all land in v0.2. Refreshed `docs/REFERENCE.md` is the user-facing contract.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest -q                                            # skimr core: 176 tests
cd packages/skimr-spacy && ../../.venv/bin/python -m pytest -v           # skimr-spacy: 17 tests
cd rust && cargo test && cargo clippy --all-targets -- -D warnings       # 113 + clean
cd rust && cargo test --features wordforms                               # 121 + clean
.venv/bin/python benchmarks/extraction_eval.py                           # SC-D gate
.venv/bin/python -c "import skimr; print(skimr.brief(open('benchmarks/corpus/scientific-paper.txt').read()))"
git log --oneline origin/main..HEAD                                      # 23 unpushed commits
gh run list --repo yonk-labs/skimr --limit 5                             # CI
```

## TODO list (v0.2 plan, through end of session 2026-04-26)

- [x] T1–T11 v0.2 core + enrichment primitives (from prior sessions)
- [x] T11b skimr-spacy `spacy_correlate_facts` via NER + noun-chunks (`18428c7`)
- [x] T12 hand-labeled gold (50 JSON) (`04d2028` + `eaf8074`)
- [x] T13 harness rewrite + corrective pass (`94a56df` + `d452d9e` + `74f3023` + `da7bf2b`)
- [x] T13a stats regex broadening (`cbf8e43`)
- [x] T13b outline broadening (`57f323c`)
- [x] T13c correlate stopword filter (`ef61b4d`)
- [x] T13d outline em-dash title (`8e6cd0d`)
- [x] T13e text2num wordforms optional dep (`544a0b6`)
- [x] T13f YAKE phrases backend (`3f5dc4b`)
- [x] T13g stats +common count nouns (`3e95cee`)
- [x] T13g2 stats +`tons per year|month|day` (`37eeacb`)
- [x] T13h phrases sub-ngram subsumption (`bb9a89a`)
- [x] Format-tolerant harness + report (`c201571`)
- [x] docs/REFERENCE.md primitive catalog (`4ea62d7`)
- [x] T16 extract.toc() + extract.key_facts() (`d4b9730`)
- [x] T17 skimr.brief() (`92b9820`)
- [x] **T14** SC-B gate — comparison matrix + latency profile (`efeba34`)
- [x] **T15** Tag v0.2.0 release (local; push pending explicit request)
- [ ] v0.3+ stubs: phrases gold reconciliation, correlate coref-capable backend, `_COUNT_RE` +`people`/`person`, Class D outline cases, Rust phrases tests 1:1 with Python

## Resume prompt (paste into fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. **skimr v0.2.0 tagged locally**; only `git push origin main && git push origin v0.2.0` remains (held back per the standing no-push-without-request rule). All four SC gates evidenced: SC-A `benchmarks/quality/review-2026-04-21.md`, SC-B `benchmarks/quality/matrix-2026-04-26.md` (worst skimr cell 3.56 ms vs 250 ms budget), SC-C rust fixture walker green, SC-D `benchmarks/quality/extraction-2026-04-26.md` ships at 3/5 pass with phrases + correlate documented as v0.3+ work, SC-E matrix doc present, SC-F `docs/integration-memo.md` present. **Test state:** 176 Python core + 17 skimr-spacy + 113 Rust default + 121 Rust wordforms, all green, clippy `--all-targets -- -D warnings` clean on both feature sets. **Versions:** all manifests at `0.2.0`. After pushing the tag, run `gh run list --repo yonk-labs/skimr --limit 5` to confirm CI green and then run the fresh-clone smoke test from plan §T15 step 7. v0.3+ work tracked in this file's TODO list.
