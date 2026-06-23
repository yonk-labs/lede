# lede-enrich CRF NER via spaCy self-distillation — design spec

**Status:** draft for review
**Date:** 2026-06-22
**Tracks:** [`lede#16`](https://github.com/yonk-labs/lede/issues/16); unblocks the deferred CRF NER noted in the [M1 spec](2026-06-22-lede-enrich-m1-design.md) §2 and [`#5`](https://github.com/yonk-labs/lede/issues/5)
**Teacher model:** spaCy `en_core_web_sm` 3.8.0 (the model `lede-spacy` already requires)
**CRF engine:** [`crfs`](https://docs.rs/crfs) (messense/crfs-rs) — pure-Rust CRFsuite port, MIT, `Trainer::lbfgs` + `Tagger`

## 1. Goal

Add **typed, higher-recall NER** to `lede-enrich` as an **opt-in `crf` cargo
feature**, distilled offline from `en_core_web_sm`. The trained CRF model ships
**in-crate** (`include_bytes!`). The default build is untouched — still the
zero-dep gazetteer.

This is the unblock of the M1-deferred CRF: M1 assumed CRF weights would be
PTB/LDC-derived and therefore *downloaded, never bundled*. Self-distillation over
our own corpus makes the weights **self-generated → bundleable**.

What the feature buys, in order of confidence:
1. **Real labels** — PERSON/ORG/GPE/… instead of today's unlabeled surface forms.
2. **Recall on novel *capitalized* entities** — names not in the 343-word gazetteer.
3. **(weaker) lowercase / context recall** — only as far as context/suffix
   features carry; clean corpora rarely show lowercase entities to learn from.

The CRF's quality ceiling is the teacher (`sm`); we are distilling, not exceeding it.

## 2. Scope

**In (behind `crf` feature):**
- `extract_entities_typed(text) -> Vec<Entity>` — additive, typed output.
- Bundled `model.crfsuite` (self-generated; license discussion §10).
- Shared Rust feature extractor used by *both* training and inference.
- Offline Python distillation harness (spaCy → silver BIO labels).
- Offline Rust trainer binary + a held-out fidelity report.

**Out / unchanged:**
- `extract_entities(text) -> Vec<String>` — unchanged gazetteer path.
- `metadata()` — unchanged; `entities: Vec<String>` still gazetteer-derived
  (lede core's shared `Metadata` type is not extended).
- Numeric/temporal entities (DATE/TIME/MONEY/PERCENT/CARDINAL/ORDINAL/QUANTITY)
  — stay with lede core's regex; the CRF does **not** predict them.
- Distilling a POS tagger (we reuse the existing rule-based `pos` as a feature).
- Wiring into downstream consumers (lives in their repos).

## 3. Architecture — all-Rust train+infer, Python emits labels only

```
[pinned Wikipedia dump] --spaCy(sm)--> silver (sentence text, entity char-spans)   [Python]
                                              |
                       Rust tokenize() + project_bio() + features.rs   [Rust = the contract]
                          /                                  \
            src/bin/train_ner.rs                     src/crf/mod.rs
            crfs::Trainer::lbfgs                      crfs::Tagger
              -> model.crfsuite  ----include_bytes!---->  in-crate inference
```

**Load-bearing property:** Rust owns *both* tokenization and feature extraction for
training and inference. Python emits only `(sentence text, entity char-spans)` —
tokenizer-independent labels. Both alignment drift (token boundaries) and feature
drift are therefore structurally impossible: one `tokenize()`, one `project_bio()`,
one `features.rs`, called from both sides.

## 4. Components

| Path | Role |
|---|---|
| `distill/label_corpus.py` | Loads pinned Wikipedia snapshot per `corpus_manifest.json`, runs spaCy, writes `silver.jsonl` of `{"text": "<sentence>", "ents": [{"start","end","label"}]}` (sentence-relative UTF-8 byte spans; lexical types only). Deterministic. Rust does the tokenization. |
| `src/crf/tokenize.rs` | `tokenize()` (byte-offset tokens) + `project_bio()` (char-spans → BIO over those tokens). Shared by trainer and inference. |
| `distill/corpus_manifest.json` | Committed list of selected article IDs per domain bucket. The reproducibility anchor (§5). |
| `src/crf/features.rs` | The shared feature function. Unit-tested in isolation. |
| `src/crf/mod.rs` | `extract_entities_typed`, `Entity`, BIO→span merge, `OnceLock` model load. Gated `#[cfg(feature = "crf")]`. |
| `src/bin/train_ner.rs` | Offline trainer (gated, not built by default): `silver.jsonl` → featurize → `crfs::Trainer::lbfgs` → `model.crfsuite` + fidelity report. |
| `models/ner.crfsuite` | Bundled trained weights (committed; `include_bytes!`). |
| `tests/crf.rs` | Determinism + golden typed-entity cases (gated). |

## 5. Distillation harness

- **Corpus:** English Wikipedia, a **pinned dump** (e.g. `wikimedia/wikipedia`,
  config `20231101.en`). We never redistribute the text — only the trained model.
- **Composition:** **stratified, tech-weighted** (~2–5k articles, small-first).
  Deliberate slices from broad domains — Technology/Computing, Companies/Business,
  Science, plus general (people, places, history) — so ORG/PRODUCT contexts are
  well-represented, not drowned by biographies. Selection method (category API,
  portal lists, or lead-keyword heuristic) is a one-time concern; its **output is
  the committed `corpus_manifest.json`** (article IDs), which — with the pinned
  dump — makes re-training bit-reproducible regardless of selection method.
- **Labels (11 lexical types → 23 BIO tags):** PERSON, NORP, FAC, ORG, GPE, LOC,
  PRODUCT, EVENT, WORK_OF_ART, LAW, LANGUAGE. (`B-`/`I-` each + `O`.) Numeric/
  temporal types are dropped (handled by lede core).
- **Tokenization (golden-span — Rust owns it for both train and infer):** Python
  emits only **entity spans as UTF-8 byte offsets** (converted from spaCy's
  `ent.start_char`/`end_char`, relative to the sentence) — tokenizer-independent
  labels. Byte (not character) offsets because Rust string slicing and the
  `tokenize()` offsets are byte-based; converting in Python keeps non-ASCII text
  (accents, em-dashes, non-Latin scripts — pervasive in Wikipedia) aligned. **Rust
  tokenizes the raw text for both training and inference** with the same
  `tokenize()`, and projects the byte-spans onto its own tokens to derive BIO. This makes spaCy-vs-Rust
  *alignment drift* (different token boundaries desyncing labels) structurally
  impossible — the same "Rust owns the contract" principle as the shared feature
  function (§3), extended to tokenization. No spaCy-tokenizer matching or Unicode
  normalization is needed (both sides operate on identical raw bytes; we never
  compare token strings across the language boundary).

## 6. Feature set (`features.rs`)

Per token, plus a ±2 context window (and BOS/EOS markers):
- `bias`, `word.lower()`, word **shape** (`Xxxx`, `dddd`, `XXX`…).
- **Affixes:** prefixes len 1–3, suffixes len 1–4.
- **Flags:** `is_title`, `is_upper`, `is_digit`, has-hyphen, has-digit.
- **Gazetteer membership** (reuses the existing 343-word lists as binary
  features): in `ORGS` / `COUNTRIES` / `PLACES` / `FIRST_NAMES` / `TITLES` /
  `ORG_SUFFIXES` / `CALENDAR` …. The gazetteer becomes *features*, not hard rules.
- **POS** (only when the `pos` feature is also enabled): the rule-based tag.
  When `pos` is off, the feature is simply absent — no hard dependency.
- Transition features (label→label) handled by the CRF itself.

Feature *strings* are emitted in a fixed, documented order so inference is
deterministic.

## 7. Training (`train_ner.rs`, gated, offline)

1. Read `silver.jsonl`; deterministic train/held-out split (e.g. by article id).
2. Featurize every sentence with `features.rs`.
3. `crfs::Trainer::lbfgs`, fixed hyperparameters (c1/c2, max-iter) committed in code.
4. Write `models/ner.crfsuite`; print entity-level P/R/F1 vs spaCy on the held-out
   split (distillation fidelity) and a per-label breakdown.

The trained artifact is committed. Day-to-day builds do **not** retrain or fetch
the corpus; only an explicit retrain does.

## 8. Inference & API (`crf/mod.rs`, gated)

```rust
pub struct Entity { pub text: String, pub label: String, pub start: usize, pub end: usize }
pub fn extract_entities_typed(text: &str) -> Vec<Entity>;
```
- Model loaded once via `OnceLock` from `include_bytes!("../../models/ner.crfsuite")`.
- Tokenize → featurize → `Tagger` Viterbi decode → merge BIO runs into spans
  (`start`/`end` are byte offsets into `text`).
- `extract_entities` and `metadata` are **untouched**. Typed output is purely additive.

## 9. Determinism & evaluation

- **Determinism:** inference is deterministic by construction (fixed bundled
  weights + fixed feature order + Viterbi). Add a `crf.rs` case asserting
  `extract_entities_typed(t) == extract_entities_typed(t)` and a few golden spans.
- **Fidelity eval:** entity-level P/R/F1 of CRF vs spaCy on held-out (teacher =
  ceiling). Acceptance bar set per-label in §11; PERSON/ORG/GPE are the must-pass
  classes, long-tail (LAW/EVENT/WORK_OF_ART/LANGUAGE) reported but not gated.
- Existing default-build golden/determinism tests must stay green (feature is
  additive and off by default).

## 10. Licensing & provenance (treated as a real constraint, not waved away)

- **We do not redistribute Wikipedia text** — only the self-generated
  `model.crfsuite`. The harness fetches the dump at train time; the dump is not
  committed.
- **Model card** (in README / `models/MODEL_CARD.md`): teacher (`en_core_web_sm`
  3.8.0, MIT), corpus (English Wikipedia, exact dump date), CC-BY-SA attribution,
  CRF engine (`crfs`, MIT).
- **Residual risk, stated honestly:** Wikipedia is **CC-BY-SA**, not public
  domain. Whether CRF weights trained on CC-BY-SA text are a ShareAlike derivative
  (vs. the crate's Apache-2.0) is a genuine gray area. The chosen position
  (self-generated artifact, attributed, text not redistributed) is defensible but
  **a human must bless it before any publish/tag**. Flagged, not decided by this spec.

## 11. Acceptance criteria

- **AC-1** Default build (`cargo build`, `cargo test`) unchanged and green; no new
  default dependency; `crf` is opt-in.
- **AC-2** `cargo test --features crf` green, incl. determinism + golden typed spans.
- **AC-3** `extract_entities_typed` returns typed `Entity` spans with correct byte
  offsets; `extract_entities`/`metadata` byte-identical to pre-change.
- **AC-4** (revised after measurement) Fidelity report exists. The gating bar is
  what classical-CRF distillation can actually reach and what makes this a real
  upgrade: **untyped held-out entity F1 ≥ 0.80** (does it find entities — achieved
  0.80), **token-level accuracy ≥ 0.90** (achieved 0.95), and it **beats the
  current gazetteer baseline** (untyped 0.80 vs 0.55). Per-*type* strict-span F1 is
  reported, not gated: GPE/NORP/LANGUAGE land ~0.79–0.81; PERSON ~0.70, ORG ~0.65;
  long-tail (LAW/EVENT/WORK_OF_ART/PRODUCT/FAC) lower. *Rationale:* strict typed-span
  ≥ 0.80 on PERSON/ORG is unreachable distilling spaCy's CNN — a better teacher
  (sm→lg) added ~0 there; the gap is inherent type-ambiguity + CRF capacity, not a
  tunable. The model often labels *more* cleanly than the noisy teacher. Teacher is
  `en_core_web_lg`; trainer is **L2SGD** (batch L-BFGS did not converge in practical
  time, single-threaded). See the model card for the full per-label table.
- **AC-5** `corpus_manifest.json` committed; re-running the harness from it +
  pinned dump reproduces `silver.jsonl` deterministically.
- **AC-6** `clippy --features crf -D warnings` and `fmt --check` clean.
- **AC-7** Model card present with teacher/corpus/engine + CC-BY-SA attribution.

## 12. Phasing (one spec, three implementation milestones)

1. **Distill harness + shared features** — `label_corpus.py`, `corpus_manifest.json`,
   `silver.jsonl`; `features.rs` + unit tests. No training yet.
2. **Trainer + fidelity** — `train_ner.rs` → `model.crfsuite`; held-out F1 report;
   tune corpus/hyperparams until AC-4 holds.
3. **Inference + API + ship** — `extract_entities_typed`, bundled weights,
   determinism/golden tests, model card, README. Wire `crf` into CI matrix.

## 13. Risks & open questions

- **R-1 Tokenization alignment** — *mitigated by design* via golden-span
  tokenization (§5): Rust owns tokenization for both train and infer, so token
  boundaries cannot desync labels. Residual concern is only projection of a char-
  span that partially overlaps a token (rare in clean text) — projected by
  containment, partial overlaps fall to `O`.
- **R-2 `crfs` purity** — confirm `crfs` + its lbfgs backend are pure-Rust. If
  training pulls a `-sys` crate, training is still offline but not pure-Rust; the
  *inference* path (Tagger) is unaffected. Verify in Phase 2.
- **R-3 Long-tail label noise** — `sm` is weak on LAW/EVENT/WORK_OF_ART/LANGUAGE;
  the CRF inherits that. Prune the label set in a follow-up if too noisy.
- **R-4 Bundled model size** — CRFsuite NER models can be MBs. Acceptable behind an
  opt-in feature; record the size and revisit if it bloats the crate.
- **R-5 Licensing** (§10) — CC-BY-SA ShareAlike gray area; needs human sign-off
  before publish.

## 14. Out of scope

- Beating spaCy (this is distillation — the teacher is the ceiling).
- Transformer/ONNX NER (kills the sub-ms value prop; rejected in #16).
- Lowercase-entity recall as a hard guarantee (clean corpus can't teach it well).
- Python↔Rust byte-parity (never promised for lede-enrich).
- Downstream wiring (consumer repos).
