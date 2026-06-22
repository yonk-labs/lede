# lede-spacy-rs — Milestone 1 design spec

**Status:** draft for review
**Date:** 2026-06-22
**Tracks:** [`lede#5`](https://github.com/yonk-labs/lede/issues/5) (locked M1 scope), sibling `#6` (hi-fi SVO, deferred)
**Consumer:** chunkshop-rs `#76` Phase 2 (`spacy_entities` + `lede_spacy_facts` stubs)

## 1. Goal

A deterministic, fast, classical Rust companion crate that gives the Rust ingest
path spaCy-`sm`-*class* enrichment — **no transformer in the default path**. M1
ships exactly the two capabilities chunkshop-rs has stubbed: entity surface forms
and numeric facts. Everything is integer-exact deterministic and bundles its data
in-crate (no model download, no ONNX, no network).

## 2. Scope (locked per issue #5)

**In M1 — default path (license-clean, ZERO bundled trained weights):**
- NER entities — gazetteer + capitalization/shape rules (no trained model).
- `metadata` — reuse lede core's regex dates/amounts/urls, add `entities`.
- SVO facts — existing regex `correlate_facts` re-attributed with gazetteer
  entities. Shipped as structured `PhraseFact` records for **metadata filtering**,
  NOT packed into embedded chunk text (§6 G3). Behind an opt-in feature flag.
- Lemma — rule-based + small irregulars table (no encumbered lookup table).

This default un-stubs both chunkshop stubs (`spacy_entities` + `lede_spacy_facts`)
with no PTB/LDC-derived artifact in the crate.

**Opt-in / deferred (feature-flagged, NEVER the default):**
- POS tagging + anchor-based POS-SVO (`postagger`) and higher-recall CRF NER
  (`crfs-rs`) — better recall, but weights are PTB/LDC-derived, so they are
  **downloaded on build/first-run, never bundled** (§6). Owner decides whether
  this lands in M1 or a follow-up.
- `finalfusion` "similar" expansion — low value (stele#74 / pg-raggraph#89).
- Noun-phrase chunker — nice-to-have.
- High-fidelity SVO via dependency parser — sibling issue #6.
- `gline-rs` — opt-in GPU-only feature flag, never the default.

**Explicitly out of scope (this repo):**
- Wiring lede-spacy-rs into chunkshop-rs — that lives in the chunkshop repo
  (`/home/yonk/yonk-tools/chunkshop/`), a separate PR. This spec delivers the
  crate + its API; the consumer un-stubs against it downstream.
- Python ↔ Rust **byte parity**. Like the Python spaCy backend, lede-spacy-rs
  makes **no cross-language parity promise** — it is spaCy-`sm`-*class*, not
  byte-identical to Python lede-spacy. It stays **off the fixture walker.**

## 3. Crate layout (as built)

`rust/` is a single crate (`lede`), not a workspace, and CI runs `cd rust &&
cargo test/clippy/fmt`. Making `rust/` a workspace would pull this brand-new
crate into the core's four green CI workflows. So the companion is a **standalone
sibling crate at the repo root**, depending on `lede` by path — **zero changes to
any core file**, zero CI coupling.

```
lede-spacy-rs/
  Cargo.toml        # name = "lede-spacy-rs"; deps: lede = { path = "../rust" }
  src/
    lib.rs          # public API: extract_entities, metadata, correlate_facts, lemma
    ner.rs          # gazetteer + capitalization/shape-rule entity recognition
    gazetteer.rs    # static public-domain lists + helpers
    facts.rs        # regex correlate_facts + NER entity re-attribution
    lemma.rs        # rule-based lemmatizer + irregulars
    pos.rs          # (opt-in `pos` feature — NOT built in M1 default)
  tests/
    golden.rs       # entity snapshots
    facts.rs        # fact re-attribution
    determinism.rs  # same input twice -> identical bytes
```

If a Cargo workspace is wanted later it can be added without moving files; M1
keeps the crate isolated on purpose.

## 4. Public API

Reuse core types — do **not** invent parallel `Entity`/`Fact` structs where the
core already has them. Mirror the Python surface (bare strings, no labels in
output, to match `extract_entities`/`spacy_correlate_facts`/`spacy_metadata`).

```rust
// rust/lede-spacy/src/lib.rs
use lede::extract::correlate::PhraseFact;   // { entity, number, polarity, sentence }
use lede::extract::metadata::Metadata;      // { dates, amounts, urls, entities }

/// Unique PERSON/ORG/GPE/LOC/PRODUCT surface forms, first-appearance order.
/// Mirrors Python lede_spacy.extract_entities() -> tuple[str, ...].
pub fn extract_entities(text: &str) -> Vec<String>;

/// lede core regex metadata (dates/amounts/urls) + entities filled in.
/// Mirrors Python lede_spacy.spacy_metadata() -> Metadata.
pub fn metadata(text: &str) -> Metadata;

/// Entity-aware numeric facts. Mirrors Python lede_spacy.spacy_correlate_facts().
pub fn correlate_facts(text: &str) -> Vec<PhraseFact>;
```

**Secondary (building blocks, exposed because cheap; not chunkshop-facing):**

```rust
pub fn pos_tag(text: &str) -> Vec<(String, String)>;  // (token, tag)
pub fn lemma(word: &str) -> String;
```

`polarity` values reuse the core's vocabulary: `"absolute" | "growth" | "decline"`
(Python also has `"unknown"`; M1 will not emit it).

## 5. Component design

### 5.1 NER (gazetteer + shape rules)

Pure rules + static data → integer-exact deterministic. Algorithm:

1. Tokenize on the core's sentence/word boundaries (reuse `lede::sentences`).
2. Detect **capitalized token runs** (contiguous Title-Case tokens), with a
   sentence-initial guard: a lone capitalized first word is demoted unless it
   hits the gazetteer or carries a title (Mr/Ms/Dr/President/Sen./Gov.).
3. **Gazetteer labeling** for precision:
   - GPE/LOC: bundled country + major-city list (public-domain source).
   - ORG: suffix rules (`Inc`, `Corp`, `LLC`, `Ltd`, `Co.`, `Group`, `& Co`).
   - PERSON: title prefixes + first-name list (US Census names — **public domain**).
   - PRODUCT: left to shape rules (low recall, acceptable for M1).
4. Dedup by surface form, preserve first-appearance order, return `Vec<String>`.

Output is **labelless** to mirror Python. Labels are computed internally and may
be exposed later if a consumer needs them — not in M1.

**Gazetteer sourcing (license-clean only):** US Census first/surname lists (public
domain), ISO country list (public domain). Org suffixes / titles are hand-coded
constants. Ship lists as `include_str!`-embedded data; keep them small (M1 targets
the mechanism + reasonable recall, not exhaustive coverage).

### 5.2 metadata

Thin wrapper: call `lede::extract::metadata::metadata(text)` for `dates`,
`amounts`, `urls` (byte-identical to core), then set `.entities =
extract_entities(text)`. Exactly mirrors what Python `spacy_metadata` does.

### 5.3 POS tagging — opt-in `pos` feature (built: rule-based)

POS is **not in the default path.** The built `pos` feature is a **rule-based**
tagger (closed-class word lists + suffix heuristics): no model, no weights, no
network — license-clean and deterministic. It exposes `pos_tag` and powers the
higher-recall `correlate_facts_pos` (§5.4), scoping polarity to verbs.

The averaged-perceptron path (NLTK/PTB weights) is **deferred** to a future
`pos-perceptron` feature loading **user-supplied** weights — never bundled, and
not via the `postagger` crate (which bundles the weights = transitive
redistribution, §6).

### 5.4 SVO facts

Return type is always the core `PhraseFact` (`{entity, number, polarity,
sentence}`) — no new type, no schema drift for chunkshop. Facts are **structured
records for metadata filtering, not text to embed** (§6 G3), behind an opt-in
feature flag.

- **Default path (no `pos` feature):** reuse lede core's existing regex
  `correlate_facts`, re-attributing the `entity` field with §5.1 gazetteer
  entities. Already exists, deterministic, license-clean — un-stubs
  `lede_spacy_facts` with "good enough" facts.
- **Opt-in path (`pos` feature, built):** `correlate_facts_pos` emits a fact for
  every numeric stat co-occurring with an NER entity (higher recall than core's
  repeated-word pairings), with polarity scoped to the nearest verb via the
  rule-based tagger ("rose/grew" → growth, "fell/dropped" → decline, else
  absolute).

### 5.5 lemma

Rule-based: lowercase, strip regular inflections (`-s`/`-es`/`-ies`→`-y`/`-ed`/
`-ing`) with a guard against over-stripping, plus a small hand-coded irregulars
table (`was`→`be`, `children`→`child`, `better`→`good`, …). No external lookup
table (avoids murky-license data dumps). Good enough for "sm is also lookup-based."

## 6. The crux — licensing posture (resolved via abe review)

**Verified facts (2026-06-22):**
- `postagger` is on crates.io; **code is Apache-2.0**, but its bundled model is
  **NLTK's `averaged_perceptron_tagger`, trained on the Penn Treebank (WSJ / LDC)**.
  ([repo](https://github.com/shubham0204/postagger.rs))
- A higher-recall CRF NER would similarly need CoNLL-2003 (Reuters) or OntoNotes
  (LDC) data.

**abe review correction (gemma + qwen agreed):**
- The barrier is **contract law (the LDC/Reuters EULA), not copyright.** Whether
  trained weights are a copyrightable derivative is unsettled — but the LDC user
  agreement is a binding contract forbidding redistribution of derived
  corpora/models. **Bundling weights in the published crate *is* the
  redistribution = the violation;** you cannot pass the liability to the user by
  shipping the file.
- The "spaCy-sm is MIT despite OntoNotes" precedent is **weaker than first
  framed**: spaCy/CoNLL-style training used the *permissive* subset, and NLTK
  avoids liability precisely by making the **user** run `nltk.download()` (user
  accepts the EULA; NLTK never redistributes). The "community norm" is
  *liability-avoidance* (user-downloads / permissive data), not "weights are free."

**Resolution — three tiers (DEFAULT / OPT-IN / NEVER):**
- **DEFAULT (M1, license-clean, zero bundled weights):** gazetteer NER + regex
  facts + rule lemma. No PTB/LDC-derived artifact in the crate. This is issue #5's
  gazetteer-first lock — **abe validated it.**
- **OPT-IN (feature-flagged):** `postagger` perceptron and/or CRF NER, where the
  build/first-run step **downloads a pinned, SHA-checksummed weights artifact**
  from a host — mirroring NLTK, so the **user** accepts upstream terms. Determinism
  holds because the artifact is checksum-pinned (and lede-spacy-rs makes no
  Python↔Rust parity promise; the bar is Rust-internal reproducibility).
- **NEVER:** ship PTB/CoNLL/OntoNotes-derived weights inside the repo or crate.

**Consequence for the issue #5 lock.** Issue #5 lists "POS (`postagger`) —
prerequisite for triples" as IN M1. Per this finding, **bundled `postagger` cannot
be the license-clean default.** Two ways forward:
- **(i) Recommended** — drop POS from default M1; facts = existing regex
  `correlate_facts` + gazetteer entities. License-clean, less code, and justified
  anyway by the marginal-fact benchmark (G3). POS ships later as the opt-in
  download feature.
- **(ii)** keep POS in M1 via the opt-in downloader (more work now).

**Owner decision — see handoff.**

**G3 — Triple value / framing (abe).** Facts tested marginal-to-negative *as
embedded chunk text* (dilutes the embedding). They are valuable as **structured
filter metadata** ("entity X associated with value > $N"). M1 ships facts as
structured `PhraseFact` records for metadata filtering — **not** packed into
embedded text — behind an opt-in feature flag, keeping the core lean.

## 7. Determinism & parity

- All M1 components are pure rules + static data → identical bytes every run, every
  platform. POS (if postagger) is deterministic for fixed weights with a stable
  argmax tie-break (assert in tests).
- **No float reductions anywhere** in the default path (the property that killed
  gline). The deferred `finalfusion` path is the only place floats would enter —
  another reason it stays out of M1.
- **No fixture-walker entry.** lede-spacy-rs is off the Python↔Rust byte-parity
  gate by policy, matching the Python spaCy backend. The bar is **Rust-internal
  reproducibility** (same input → same bytes across runs/platforms), not
  cross-language byte-parity.
- The opt-in POS/CRF path must use **consistent `f32` precision and avoid
  platform-specific SIMD intrinsics** (abe), and pin weights by checksum — so its
  greedy argmax is bit-stable across x86/ARM.

## 8. Test plan

Crate-local only (no cross-language fixtures):
- `tests/golden.rs` — curated `(text → expected entities)` and `(text → expected
  PhraseFacts)` snapshots covering: capitalized runs, sentence-initial guard,
  gazetteer hits (country/org-suffix/title), growth/decline/absolute polarity.
- `tests/determinism.rs` — run each public fn twice on the same input; assert
  byte-identical output.
- Unit tests in each module for the tricky bits (shape rules, lemma irregulars,
  polarity inference).

## 9. Build order (two vertical slices, tree green between)

**Slice 1 — entities (un-stubs `spacy_entities`):**
crate scaffold + workspace wiring → `gazetteer.rs` + `ner.rs` →
`extract_entities` + `metadata` → golden + determinism tests → `cargo test` /
`clippy` / `fmt` green.

**Slice 2 — facts + lemma (un-stubs `lede_spacy_facts`):**
`facts.rs` (default: regex `correlate_facts` re-attributed with gazetteer
entities) → `lemma.rs` → `correlate_facts` + `lemma` public fns → tests → green.
**No POS, no bundled weights** in the default — license-clean.

**Slice 3 (built) — opt-in `pos` feature, rule-based, license-clean:**
`pos.rs` rule-based tagger (closed-class lists + suffix heuristics; no weights,
no deps, no network) → `pos_tag` public fn → `correlate_facts_pos` (fact per
stat∩NER-entity, verb-scoped polarity) → tests behind `--features pos`. The
averaged-perceptron path (NLTK/PTB weights) is **deferred** to a future
`pos-perceptron` feature loading user-supplied weights (§5.3/§6). Default build
is unchanged (no `pos`).

Each slice is an independently reviewable, compilable increment.

## 10. Risks

| Risk | Mitigation |
|---|---|
| **postagger weights LDC-encumbered** (confirmed) | Default ships no weights; POS is opt-in via checksum-pinned downloader (§6). |
| Gazetteer recall too low for chunkshop | M1 targets mechanism; expand lists or enable opt-in CRF/POS download later. |
| Scope creep into labels/noun-phrases | Locked out per §2; resist until a consumer asks. |
| chunkshop schema drift | Reuse core `PhraseFact`/`Metadata` types — no new schema. |
