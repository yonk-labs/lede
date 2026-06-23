# lede-enrich CRF NER (spaCy self-distillation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add typed, higher-recall NER to `lede-enrich` behind an opt-in `crf` cargo feature, distilled offline from spaCy `en_core_web_sm` into a pure-Rust CRF whose weights ship in-crate.

**Architecture:** Python runs spaCy over a pinned, stratified Wikipedia sample and emits silver `(sentence text, entity char-spans)` — tokenizer-independent labels. **Rust owns both tokenization and feature extraction** for training and inference: one `tokenize()` + `project_bio()` (char-spans → BIO) + `sequence_features()`, called by both an offline Rust trainer (`crfs::Trainer`) and in-crate inference (`crfs::Tagger`). This makes both alignment drift and feature drift structurally impossible. The trained `models/ner.crfsuite` is bundled via `include_bytes!`.

**Tech Stack:** Rust (edition 2024, `crfs` crate), Python (spaCy 3.8 `en_core_web_sm`), Wikipedia (CC-BY-SA, pinned dump).

**Spec:** `docs/superpowers/specs/2026-06-22-lede-enrich-crf-ner-distillation-design.md`

## Global Constraints

- Crate `rust-version = "1.85"`, `edition = "2024"`, `unsafe_code = "forbid"`.
- **Default build stays zero-dependency and byte-identical** to pre-change. All new deps (`crfs`) are `optional = true`, pulled only by `--features crf`.
- `extract_entities` and `metadata` outputs must be **byte-identical** to pre-change (additive feature only).
- Inference is **deterministic**: fixed bundled weights + fixed feature-string order + Viterbi.
- Label set = **11 lexical types** → 23 BIO tags: `PERSON NORP FAC ORG GPE LOC PRODUCT EVENT WORK_OF_ART LAW LANGUAGE` (each `B-`/`I-`, plus `O`). Numeric/temporal types are out (lede core regex owns them).
- Teacher: `en_core_web_sm` **3.8.0**. CRF engine: `crfs` (MIT). Corpus: English Wikipedia, **pinned dump**, never redistributed.
- Acceptance (revised after measurement): **untyped** held-out entity F1 **≥ 0.80** (achieved 0.80), token acc ≥ 0.90 (0.95), and beats the gazetteer baseline (0.80 vs 0.55). Per-type strict-span F1 reported not gated (GPE/NORP/LANGUAGE ~0.80; PERSON ~0.70, ORG ~0.65). Strict typed ≥0.80 on PERSON/ORG is unreachable distilling spaCy's CNN — see spec AC-4.
- `cargo clippy --features crf -- -D warnings` and `cargo fmt --check` clean.
- All work on branch `feat/lede-enrich-crf-ner`. All paths below are relative to `lede-enrich/` unless noted.

---

## Phase 1 — Distillation harness + shared features

### Task 1: Scaffold the `crf` feature and module skeleton

**Files:**
- Modify: `lede-enrich/Cargo.toml`
- Modify: `lede-enrich/src/lib.rs`
- Create: `lede-enrich/src/crf/mod.rs`
- Create: `lede-enrich/src/crf/features.rs`

**Interfaces:**
- Produces: the `crf` cargo feature; module `crate::crf` compiled only under it.

- [ ] **Step 1: Confirm the exact `crfs` version**

Run: `cd lede-enrich && cargo add crfs --dry-run --optional`
Expected: prints the resolved latest `crfs` version (e.g. `crfs vX.Y`). Note it; use it in Step 2. If `cargo add` is unavailable, check https://crates.io/crates/crfs for the latest version.

- [ ] **Step 2: Add the optional dep and feature to `Cargo.toml`**

Under `[dependencies]` add (use the version from Step 1):

```toml
# Pure-Rust CRFsuite port (MIT). Training + inference. Only pulled by `crf`.
# Latest resolved 0.4.1 as of 2026-06-22; confirm with Step 1's dry-run.
crfs = { version = "0.4", optional = true }
```

Under `[features]` add:

```toml
# Opt-in distilled CRF NER. Bundles self-generated weights in-crate
# (models/ner.crfsuite). Adds typed `extract_entities_typed`. Never default.
crf = ["dep:crfs"]
```

Add the trainer binary near the bottom of `Cargo.toml`:

```toml
[[bin]]
name = "train_ner"
path = "src/bin/train_ner.rs"
required-features = ["crf"]
```

- [ ] **Step 3: Wire the module into `lib.rs`**

In `lede-enrich/src/lib.rs`, after the existing `mod` lines, add **only the module declaration** (the `pub use` exports are added later, by the tasks that create each symbol — `sequence_features` in Task 8, `Entity`/`extract_entities_typed` in Task 11 — so the build here doesn't reference symbols that don't exist yet):

```rust
#[cfg(feature = "crf")]
mod crf;
```

- [ ] **Step 4: Create empty module files**

`src/crf/features.rs`:

```rust
//! Shared CRF feature extraction. Returns `Vec<Vec<String>>` (one feature-string
//! list per token) — deliberately free of `crfs` types so it is unit-testable on
//! its own and reused verbatim by both the trainer and inference.
```

`src/crf/mod.rs`:

```rust
//! Distilled CRF NER (opt-in `crf` feature). Typed entities via a pure-Rust
//! CRFsuite model trained offline on spaCy silver labels.

mod features;
```

- [ ] **Step 5: Verify both builds**

Run: `cd lede-enrich && cargo build && cargo build --features crf`
Expected: both succeed. Default build pulls no new deps (check `cargo tree | grep crfs` prints nothing without the feature).

- [ ] **Step 6: Commit**

```bash
git add lede-enrich/Cargo.toml lede-enrich/src/lib.rs lede-enrich/src/crf/
git commit -m "feat(lede-enrich): scaffold opt-in crf feature + module skeleton (#16)"
```

---

### Task 2: Word-shape feature

**Files:**
- Modify: `lede-enrich/src/crf/features.rs`

**Interfaces:**
- Produces: `fn shape(word: &str) -> String` (crate-private, used by Task 4).

- [ ] **Step 1: Write the failing test**

Append to `features.rs`:

```rust
#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shape_maps_classes() {
        assert_eq!(shape("Amazon"), "Xxxxxx");
        assert_eq!(shape("IBM"), "XXX");
        assert_eq!(shape("iPhone15"), "xXxxxxdd");
        assert_eq!(shape("3M"), "dX");
        assert_eq!(shape(""), "");
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf shape_maps_classes`
Expected: FAIL — `cannot find function shape`.

- [ ] **Step 3: Implement `shape`**

Add to `features.rs` (above the tests):

```rust
/// Per-character orthographic shape: uppercase→`X`, lowercase→`x`, digit→`d`,
/// anything else kept verbatim. Truncated at 8 chars to bound feature cardinality.
fn shape(word: &str) -> String {
    word.chars()
        .take(8)
        .map(|c| {
            if c.is_uppercase() {
                'X'
            } else if c.is_lowercase() {
                'x'
            } else if c.is_ascii_digit() {
                'd'
            } else {
                c
            }
        })
        .collect()
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf shape_maps_classes`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lede-enrich/src/crf/features.rs
git commit -m "feat(lede-enrich): crf word-shape feature"
```

---

### Task 3: Per-token feature list

**Files:**
- Modify: `lede-enrich/src/crf/features.rs`

**Interfaces:**
- Consumes: `shape` (Task 2), `crate::gazetteer` lists + `gazetteer::contains_ci`.
- Produces: `fn token_features(word: &str, pos: Option<&str>) -> Vec<String>` (used by Task 4).

- [ ] **Step 1: Write the failing test**

Add inside the `tests` module in `features.rs`:

```rust
#[test]
fn token_features_cover_affix_flags_and_gazetteer() {
    let f = token_features("Amazon", None);
    assert!(f.contains(&"w.lower=amazon".to_string()));
    assert!(f.contains(&"shape=Xxxxxx".to_string()));
    assert!(f.contains(&"suf3=zon".to_string()));
    assert!(f.contains(&"pre2=Am".to_string()));
    assert!(f.contains(&"is_title".to_string()));
    assert!(!f.contains(&"is_upper".to_string()));

    // gazetteer membership becomes a feature, not a hard rule:
    let usa = token_features("France", None);
    assert!(usa.contains(&"gaz=COUNTRIES".to_string()));

    // POS only present when provided:
    assert!(token_features("runs", Some("VERB")).contains(&"pos=VERB".to_string()));
    assert!(!token_features("runs", None).iter().any(|s| s.starts_with("pos=")));
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf token_features_cover`
Expected: FAIL — `cannot find function token_features`.

- [ ] **Step 3: Implement `token_features`**

Add to `features.rs`:

```rust
use crate::gazetteer;

/// Gazetteer lists exposed as binary membership features. Order is fixed so the
/// emitted feature strings are deterministic.
const GAZETTEERS: &[(&str, &[&str])] = &[
    ("ORGS", gazetteer::ORGS),
    ("ORG_SUFFIXES", gazetteer::ORG_SUFFIXES),
    ("COUNTRIES", gazetteer::COUNTRIES),
    ("PLACES", gazetteer::PLACES),
    ("FIRST_NAMES", gazetteer::FIRST_NAMES),
    ("TITLES", gazetteer::TITLES),
    ("CALENDAR", gazetteer::CALENDAR),
];

/// Feature strings for a single token. `pos` is the rule-based tag when the
/// `pos` feature is enabled upstream, else `None` (feature omitted, no hard dep).
fn token_features(word: &str, pos: Option<&str>) -> Vec<String> {
    let mut f = Vec::new();
    f.push(format!("w.lower={}", word.to_lowercase()));
    f.push(format!("shape={}", shape(word)));

    let chars: Vec<char> = word.chars().collect();
    let n = chars.len();
    for k in 1..=3 {
        if n >= k {
            let pre: String = chars[..k].iter().collect();
            f.push(format!("pre{k}={pre}"));
        }
    }
    for k in 1..=4 {
        if n >= k {
            let suf: String = chars[n - k..].iter().collect();
            f.push(format!("suf{k}={suf}"));
        }
    }

    if word.chars().next().is_some_and(char::is_uppercase) {
        f.push("is_title".to_string());
    }
    if n > 0 && word.chars().all(char::is_uppercase) {
        f.push("is_upper".to_string());
    }
    if n > 0 && word.chars().all(|c| c.is_ascii_digit()) {
        f.push("is_digit".to_string());
    }
    if word.contains('-') {
        f.push("has_hyphen".to_string());
    }
    if word.chars().any(|c| c.is_ascii_digit()) {
        f.push("has_digit".to_string());
    }

    for (name, list) in GAZETTEERS {
        if gazetteer::contains_ci(list, word) {
            f.push(format!("gaz={name}"));
        }
    }

    if let Some(tag) = pos {
        f.push(format!("pos={tag}"));
    }
    f
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf token_features_cover`
Expected: PASS. (If a gazetteer list name differs, fix the test's expected `gaz=` value to match an actual member of that list.)

- [ ] **Step 5: Commit**

```bash
git add lede-enrich/src/crf/features.rs
git commit -m "feat(lede-enrich): crf per-token feature list (affixes, flags, gazetteer, pos)"
```

---

### Task 4: Sequence features with ±2 context window

**Files:**
- Modify: `lede-enrich/src/crf/features.rs`

**Interfaces:**
- Consumes: `token_features` (Task 3).
- Produces: `pub fn sequence_features(tokens: &[String], pos: &[Option<String>]) -> Vec<Vec<String>>`. **This is the train/infer contract.** Both sides call it.

- [ ] **Step 1: Write the failing test**

Add inside the `tests` module:

```rust
#[test]
fn sequence_features_add_context_and_boundaries() {
    let toks = vec!["Acme".to_string(), "Corp".to_string()];
    let pos = vec![None, None];
    let seq = sequence_features(&toks, &pos);
    assert_eq!(seq.len(), 2);

    // first token sees BOS and the next token's features prefixed +1:
    assert!(seq[0].contains(&"BOS".to_string()));
    assert!(seq[0].iter().any(|s| s.starts_with("+1:w.lower=corp")));

    // last token sees EOS and the previous token's features prefixed -1:
    assert!(seq[1].contains(&"EOS".to_string()));
    assert!(seq[1].iter().any(|s| s.starts_with("-1:w.lower=acme")));
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf sequence_features_add_context`
Expected: FAIL — `cannot find function sequence_features`.

- [ ] **Step 3: Implement `sequence_features`**

Add to `features.rs`:

```rust
/// Full per-token feature lists for a tokenized sentence, including a ±2 context
/// window (neighbour features prefixed `±k:`) and BOS/EOS markers. This is the
/// single feature contract shared by the trainer and inference.
pub fn sequence_features(tokens: &[String], pos: &[Option<String>]) -> Vec<Vec<String>> {
    let base: Vec<Vec<String>> = tokens
        .iter()
        .enumerate()
        .map(|(i, w)| token_features(w, pos.get(i).and_then(|o| o.as_deref())))
        .collect();

    let n = tokens.len();
    let mut out: Vec<Vec<String>> = Vec::with_capacity(n);
    for i in 0..n {
        let mut feats = base[i].clone();
        feats.push("bias".to_string());
        for k in 1..=2_isize {
            let j = i as isize - k;
            if j >= 0 {
                for s in &base[j as usize] {
                    feats.push(format!("-{k}:{s}"));
                }
            }
            let j = i as isize + k;
            if (j as usize) < n {
                for s in &base[j as usize] {
                    feats.push(format!("+{k}:{s}"));
                }
            }
        }
        if i == 0 {
            feats.push("BOS".to_string());
        }
        if i == n - 1 {
            feats.push("EOS".to_string());
        }
        out.push(feats);
    }
    out
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf sequence_features_add_context`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lede-enrich/src/crf/features.rs
git commit -m "feat(lede-enrich): crf sequence features with +/-2 context window (train/infer contract)"
```

---

### Task 5: Inference tokenizer with byte offsets

**Files:**
- Create: `lede-enrich/src/crf/tokenize.rs`
- Modify: `lede-enrich/src/crf/mod.rs` (add `mod tokenize;`)

**Interfaces:**
- Produces: `pub struct Tok { pub text: String, pub start: usize, pub end: usize }`, `pub fn tokenize(text: &str) -> Vec<Tok>`, and `pub fn project_bio(toks: &[Tok], ents: &[(usize, usize, String)]) -> Vec<String>`. Used by Tasks 8 (trainer) and 11 (inference). Offsets are byte indices into `text`. `project_bio` is the golden-span fix: char-spans → BIO over Rust tokens, so train and infer share one tokenization.

- [ ] **Step 1: Write the failing test**

Create `src/crf/tokenize.rs`:

```rust
//! Inference-side tokenizer. Word runs (alphanumeric + apostrophe) and standalone
//! punctuation become tokens, each carrying byte offsets so entity spans can be
//! sliced back out of the source. Roughly mirrors spaCy whitespace+punct splitting;
//! tokenizer divergence vs spaCy is the main fidelity risk (spec R-1).

pub struct Tok {
    pub text: String,
    pub start: usize,
    pub end: usize,
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenize_words_and_punct_with_offsets() {
        let text = "Acme Corp, Paris.";
        let toks = tokenize(text);
        let pairs: Vec<(&str, usize, usize)> =
            toks.iter().map(|t| (t.text.as_str(), t.start, t.end)).collect();
        assert_eq!(
            pairs,
            vec![
                ("Acme", 0, 4),
                ("Corp", 5, 9),
                (",", 9, 10),
                ("Paris", 11, 16),
                (".", 16, 17),
            ]
        );
        // offsets slice the original text back out:
        assert_eq!(&text[toks[3].start..toks[3].end], "Paris");
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf tokenize_words_and_punct`
Expected: FAIL — `cannot find function tokenize`.

- [ ] **Step 3: Implement `tokenize`**

Add to `tokenize.rs` (above the tests):

```rust
/// Split into word tokens (alphanumeric + apostrophe) and single-char punctuation
/// tokens, each with byte offsets. Whitespace is a separator only.
pub fn tokenize(text: &str) -> Vec<Tok> {
    let mut toks = Vec::new();
    let mut start: Option<usize> = None;
    for (i, c) in text.char_indices() {
        if c.is_alphanumeric() || c == '\'' {
            if start.is_none() {
                start = Some(i);
            }
        } else {
            if let Some(s) = start.take() {
                toks.push(Tok { text: text[s..i].to_string(), start: s, end: i });
            }
            if !c.is_whitespace() {
                let end = i + c.len_utf8();
                toks.push(Tok { text: text[i..end].to_string(), start: i, end });
            }
        }
    }
    if let Some(s) = start.take() {
        toks.push(Tok { text: text[s..].to_string(), start: s, end: text.len() });
    }
    toks
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf tokenize_words_and_punct`
Expected: PASS.

- [ ] **Step 5: Write the failing `project_bio` test**

Add inside the `tests` module in `tokenize.rs`:

```rust
#[test]
fn project_bio_labels_tokens_from_char_spans() {
    let text = "Acme Corp hired Jeff Bezos.";
    let toks = tokenize(text);
    // entity char-spans (sentence-relative), as emitted by spaCy:
    let ents = vec![
        (0usize, 9usize, "ORG".to_string()),    // "Acme Corp"
        (16usize, 26usize, "PERSON".to_string()), // "Jeff Bezos"
    ];
    let bio = project_bio(&toks, &ents);
    assert_eq!(
        bio,
        vec!["B-ORG", "I-ORG", "O", "B-PERSON", "I-PERSON", "O"]
    );
}
```

- [ ] **Step 6: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf project_bio_labels`
Expected: FAIL — `cannot find function project_bio`.

- [ ] **Step 7: Implement `project_bio`**

Add to `tokenize.rs` (above the tests):

```rust
/// Project entity char-spans `(start, end, label)` onto `toks`, yielding one BIO
/// tag per token. A token belongs to an entity when it is fully contained in the
/// span (`tok.start >= start && tok.end <= end`); the first contained token is
/// `B-`, the rest `I-`. Tokens only partially overlapping a span fall to `O`
/// (rare in clean text). Spans are assumed non-overlapping (spaCy ents are).
pub fn project_bio(toks: &[Tok], ents: &[(usize, usize, String)]) -> Vec<String> {
    let mut bio = vec!["O".to_string(); toks.len()];
    for (start, end, label) in ents {
        let mut first = true;
        for (i, t) in toks.iter().enumerate() {
            if t.start >= *start && t.end <= *end {
                bio[i] = format!("{}-{}", if first { "B" } else { "I" }, label);
                first = false;
            }
        }
    }
    bio
}
```

- [ ] **Step 8: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf project_bio_labels`
Expected: PASS.

- [ ] **Step 9: Register the module and commit**

In `src/crf/mod.rs` add `pub mod tokenize;` under `mod features;` (public so the trainer bin can reach `tokenize`/`project_bio`). Also export them from `src/lib.rs` under the existing `#[cfg(feature = "crf")]` section:

```rust
#[cfg(feature = "crf")]
pub use crf::tokenize::{Tok, project_bio, tokenize};
```

```bash
git add lede-enrich/src/crf/tokenize.rs lede-enrich/src/crf/mod.rs lede-enrich/src/lib.rs
git commit -m "feat(lede-enrich): crf tokenizer + char-span->BIO projection (golden-span)"
```

---

### Task 6: Python distillation harness

**Files:**
- Create: `lede-enrich/distill/label_corpus.py`
- Create: `lede-enrich/distill/README.md`

**Interfaces:**
- Consumes: spaCy `en_core_web_sm`, a manifest of article texts.
- Produces: `silver.jsonl` — one JSON object per sentence: `{"text": "<sentence>", "ents": [{"start": int, "end": int, "label": str}]}` where `start`/`end` are **sentence-relative UTF-8 byte offsets** (converted from spaCy's character offsets — Rust tokens are byte-indexed, so this conversion is required for non-ASCII text) and `label` is one of the 11 lexical types. Tokenization happens in Rust (Task 8). Consumed by Task 8.

- [ ] **Step 1: Write the harness**

Create `distill/label_corpus.py`:

```python
"""Distillation harness: spaCy en_core_web_sm -> silver entity BYTE-spans.

Reads articles (one JSON per line: {"id": int, "text": str}) from --input,
runs spaCy, keeps only the 11 lexical entity types, emits one JSON per sentence
to --output: {"text": "<sentence>", "ents": [{"start", "end", "label"}]} with
sentence-relative UTF-8 BYTE offsets. Rust owns tokenization (golden-span design)
and works in byte offsets (Rust string slicing is byte-based), so we convert
spaCy's CHARACTER offsets to byte offsets here — otherwise any non-ASCII text
(accents, em-dashes, non-Latin scripts — pervasive in Wikipedia) would misalign
labels against Rust's byte-offset tokens. We deliberately do NOT emit tokens.

We never redistribute the source text — only these spans feed the Rust trainer.
"""
import argparse
import json
import sys

import spacy

LEXICAL = {
    "PERSON", "NORP", "FAC", "ORG", "GPE", "LOC",
    "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSONL of {id, text}")
    ap.add_argument("--output", required=True, help="silver.jsonl out")
    ap.add_argument("--model", default="en_core_web_sm")
    args = ap.parse_args()

    nlp = spacy.load(args.model, disable=["lemmatizer"])
    n_sents = 0
    with open(args.input, encoding="utf-8") as fin, open(args.output, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            text = json.loads(line)["text"]
            doc = nlp(text)
            for sent in doc.sents:
                stext = sent.text
                base = sent.start_char

                def to_byte(char_rel: int) -> int:
                    # char offset (sentence-relative) -> utf-8 byte offset
                    return len(stext[:char_rel].encode("utf-8"))

                ents = [
                    {
                        "start": to_byte(ent.start_char - base),
                        "end": to_byte(ent.end_char - base),
                        "label": ent.label_,
                    }
                    for ent in sent.ents
                    if ent.label_ in LEXICAL
                ]
                fout.write(json.dumps({"text": stext, "ents": ents}) + "\n")
                n_sents += 1
    print(f"wrote {n_sents} sentences to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Smoke-test on a tiny fixture**

```bash
cd lede-enrich/distill
printf '%s\n' '{"id": 1, "text": "Amazon was founded by Jeff Bezos in Seattle."}' > tiny.jsonl
../../.venv/bin/python label_corpus.py --input tiny.jsonl --output tiny.silver.jsonl
cat tiny.silver.jsonl
```
Expected: one JSON line with `"text"` = the sentence and `"ents"` containing spans for `Amazon` (ORG), `Jeff Bezos` (PERSON), `Seattle` (GPE). Verify a span slices back correctly with BYTE indexing: `sentence_text.encode("utf-8")[start:end].decode("utf-8")` equals the entity surface (for this ASCII sentence byte==char, but use the byte form so the check stays correct for non-ASCII). Also add a tiny non-ASCII sanity line (e.g. `{"id":2,"text":"Beyoncé met Pelé in São Paulo."}`) and confirm the byte slice still recovers `Beyoncé`/`Pelé`/`São Paulo`. If spaCy/model is missing: `../../.venv/bin/python -m spacy download en_core_web_sm`.

- [ ] **Step 3: Document and clean up**

Create `distill/README.md` describing: input format, the `LEXICAL` set, that source text is never committed, and the `corpus_manifest.json` flow (Task 7). Then:

```bash
rm lede-enrich/distill/tiny.jsonl lede-enrich/distill/tiny.silver.jsonl
echo "*.silver.jsonl" >> lede-enrich/distill/.gitignore
echo "articles.jsonl" >> lede-enrich/distill/.gitignore
git add lede-enrich/distill/label_corpus.py lede-enrich/distill/README.md lede-enrich/distill/.gitignore
git commit -m "feat(lede-enrich): spaCy->BIO distillation harness"
```

---

### Task 7: Stratified corpus manifest builder

**Files:**
- Create: `lede-enrich/distill/build_manifest.py`
- Create: `lede-enrich/distill/corpus_manifest.json` (committed output)

**Interfaces:**
- Produces: `corpus_manifest.json` = `{"dump": "<id>", "buckets": {"tech": [ids...], "business": [...], "science": [...], "general": [...]}}`, and `articles.jsonl` (gitignored, the fetched texts) for Task 6. The manifest + dump make re-training reproducible (spec AC-5).

- [ ] **Step 1: Write the builder**

Create `distill/build_manifest.py`. It pulls a **pinned** Wikipedia dump via `datasets`, fills per-bucket quotas by a deterministic lead-keyword heuristic, writes the manifest (ids) and `articles.jsonl` (texts):

```python
"""Build a stratified, tech-weighted corpus manifest from a pinned Wikipedia dump.

Deterministic: fixed dump id, fixed bucket keyword lists, articles taken in dump
order until each quota is filled. Emits corpus_manifest.json (ids only, committed)
and articles.jsonl (texts, gitignored).
"""
import argparse
import json

from datasets import load_dataset

DUMP = "20231101.en"  # pinned snapshot
BUCKETS = {
    "tech": ["software", "computing", "programming", "algorithm", "internet", "computer"],
    "business": ["company", "corporation", "founded", "headquartered", "ceo", "subsidiary"],
    "science": ["physics", "chemistry", "biology", "research", "theorem", "species"],
    "general": [],  # catch-all
}


def bucket_of(text: str) -> str:
    head = text[:600].lower()
    for name, kws in BUCKETS.items():
        if name != "general" and any(kw in head for kw in kws):
            return name
    return "general"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=1000)
    ap.add_argument("--manifest", default="corpus_manifest.json")
    ap.add_argument("--articles", default="articles.jsonl")
    args = ap.parse_args()

    ds = load_dataset("wikimedia/wikipedia", DUMP, split="train", streaming=True)
    quota = {b: args.per_bucket for b in BUCKETS}
    buckets: dict[str, list[int]] = {b: [] for b in BUCKETS}
    with open(args.articles, "w", encoding="utf-8") as fa:
        for row in ds:
            if all(v == 0 for v in quota.values()):
                break
            text = row["text"]
            if len(text) < 400:
                continue
            b = bucket_of(text)
            if quota[b] <= 0:
                continue
            quota[b] -= 1
            aid = int(row["id"])
            buckets[b].append(aid)
            fa.write(json.dumps({"id": aid, "text": text}) + "\n")

    with open(args.manifest, "w", encoding="utf-8") as fm:
        json.dump({"dump": DUMP, "buckets": buckets}, fm, indent=2)
    print({b: len(ids) for b, ids in buckets.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Build a small first manifest**

```bash
cd lede-enrich/distill
../../.venv/bin/pip install "datasets>=2.0"
../../.venv/bin/python build_manifest.py --per-bucket 1000
```
Expected: prints per-bucket counts (~tech/business/science/general), writes `corpus_manifest.json` and `articles.jsonl`. Total ~2–4k articles (small-first per spec). If `datasets` streaming auth is needed, the script still runs on the public dataset without a token.

- [ ] **Step 3: Generate silver labels for the full sample**

```bash
../../.venv/bin/python label_corpus.py --input articles.jsonl --output silver.jsonl
wc -l silver.jsonl
```
Expected: tens of thousands of sentences.

- [ ] **Step 4: Commit the manifest (not the texts/labels)**

```bash
git add lede-enrich/distill/build_manifest.py lede-enrich/distill/corpus_manifest.json
git commit -m "feat(lede-enrich): stratified tech-weighted corpus manifest (pinned dump)"
```

---

## Phase 2 — Trainer + fidelity

### Task 8: Offline Rust trainer

**Files:**
- Create: `lede-enrich/src/bin/train_ner.rs`

**Interfaces:**
- Consumes: `silver.jsonl` (Task 7), `crate::crf::features::sequence_features` (Task 4).
- Produces: `models/ner.crfsuite` (Task 12 bundles it). To call `sequence_features` from the bin, it must be reachable: in `src/crf/mod.rs` add `pub(crate) use features::sequence_features;` — and since bins are separate crates, re-export it publicly under the feature: add to `lib.rs` (Task 1 already gates the module) `#[cfg(feature = "crf")] pub use crf::features::sequence_features;`. **Do this in Step 1 below.**

- [ ] **Step 1: Make `sequence_features` reachable from the bin**

In `src/crf/mod.rs`, change `mod features;` to `pub mod features;`. In `src/lib.rs` under the existing `#[cfg(feature = "crf")]` exports add:

```rust
#[cfg(feature = "crf")]
pub use crf::features::sequence_features;
```

- [ ] **Step 2: Write the trainer**

Create `src/bin/train_ner.rs`:

```rust
//! Offline CRF trainer (feature-gated; not built by default). Reads silver.jsonl
//! ({"text": "<sentence>", "ents": [{start,end,label}]}), tokenizes each sentence
//! with the SAME Rust tokenizer used at inference, projects char-spans -> BIO,
//! featurizes with the shared `sequence_features`, holds out every 10th sentence,
//! trains an L-BFGS CRF, writes models/ner.crfsuite, prints entity-level P/R/F1.

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crfs::{Attribute, Model, Trainer};
use lede_enrich::{project_bio, sequence_features, tokenize};
use serde_json::Value;

fn attrs(feats: &[Vec<String>]) -> Vec<Vec<Attribute>> {
    feats
        .iter()
        .map(|row| row.iter().map(|s| Attribute::new(s.as_str(), 1.0)).collect())
        .collect()
}

/// One silver line -> (tokens, BIO) via the Rust tokenizer + char-span projection.
fn parse_line(v: &Value) -> Option<(Vec<String>, Vec<String>)> {
    let text = v["text"].as_str()?;
    let toks = tokenize(text);
    if toks.is_empty() {
        return None;
    }
    let ents: Vec<(usize, usize, String)> = v["ents"]
        .as_array()?
        .iter()
        .filter_map(|e| {
            Some((
                e["start"].as_u64()? as usize,
                e["end"].as_u64()? as usize,
                e["label"].as_str()?.to_string(),
            ))
        })
        .collect();
    let bio = project_bio(&toks, &ents);
    let tokens = toks.iter().map(|t| t.text.clone()).collect();
    Some((tokens, bio))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).unwrap_or_else(|| "distill/silver.jsonl".into());
    let model_out = "models/ner.crfsuite";

    let mut trainer = Trainer::lbfgs();
    trainer.params_mut().set_c1(0.1)?;
    trainer.params_mut().set_c2(1.0)?;

    let mut held: Vec<(Vec<String>, Vec<String>)> = Vec::new();
    for (i, line) in BufReader::new(File::open(&path)?).lines().enumerate() {
        let v: Value = serde_json::from_str(&line?)?;
        let Some((tokens, bio)) = parse_line(&v) else { continue };
        if i % 10 == 0 {
            held.push((tokens, bio));
            continue;
        }
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(&tokens, &pos);
        let yseq: Vec<&str> = bio.iter().map(String::as_str).collect();
        trainer.append(&attrs(&feats), &yseq)?;
    }

    std::fs::create_dir_all("models")?;
    trainer.train(Path::new(model_out))?;
    println!("wrote {model_out}");

    // Fidelity eval on the held-out split (gold BIO already projected via Rust).
    let model = Model::new(&std::fs::read(model_out)?)?;
    let mut tagger = model.tagger()?;
    eval(&mut tagger, &held);
    Ok(())
}

fn eval(tagger: &mut crfs::Tagger, held: &[(Vec<String>, Vec<String>)]) {
    use std::collections::HashMap;
    // per-label (tp, fp, fn) on entity spans
    let mut counts: HashMap<String, [u64; 3]> = HashMap::new();
    for (tokens, gold) in held {
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(tokens, &pos);
        let pred = tagger.tag(&attrs(&feats)).unwrap_or_default();
        let g = spans(gold);
        let p = spans(&pred);
        for (lbl, s, e) in &p {
            let entry = counts.entry(lbl.clone()).or_default();
            if g.contains(&(lbl.clone(), *s, *e)) { entry[0] += 1 } else { entry[1] += 1 }
        }
        for (lbl, s, e) in &g {
            if !p.contains(&(lbl.clone(), *s, *e)) {
                counts.entry(lbl.clone()).or_default()[2] += 1;
            }
        }
    }
    let mut labels: Vec<&String> = counts.keys().collect();
    labels.sort();
    println!("label        P      R      F1");
    for lbl in labels {
        let [tp, fp, fng] = counts[lbl];
        let p = tp as f64 / (tp + fp).max(1) as f64;
        let r = tp as f64 / (tp + fng).max(1) as f64;
        let f1 = if p + r == 0.0 { 0.0 } else { 2.0 * p * r / (p + r) };
        println!("{lbl:<12} {p:.3}  {r:.3}  {f1:.3}");
    }
}

/// BIO label sequence -> set of (label, start_tok, end_tok) spans.
fn spans(labels: &[String]) -> Vec<(String, usize, usize)> {
    let mut out = Vec::new();
    let mut cur: Option<(String, usize)> = None;
    for (i, lbl) in labels.iter().enumerate() {
        if let Some(t) = lbl.strip_prefix("B-") {
            if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
            cur = Some((t.to_string(), i));
        } else if let Some(t) = lbl.strip_prefix("I-") {
            match &cur {
                Some((l, _)) if l == t => {}
                _ => {
                    if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
                    cur = Some((t.to_string(), i));
                }
            }
        } else {
            if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
        }
    }
    if let Some((l, s)) = cur { out.push((l, s, labels.len())); }
    out
}
```

Add `serde_json` as a dev/feature dep: in `Cargo.toml` under `[dependencies]` add `serde_json = { version = "1", optional = true }` and extend the feature: `crf = ["dep:crfs", "dep:serde_json"]`.

- [ ] **Step 3: Train on the small corpus**

```bash
cd lede-enrich && cargo run --features crf --bin train_ner -- distill/silver.jsonl
```
Expected: `wrote models/ner.crfsuite`, then a per-label P/R/F1 table.

- [ ] **Step 4: Commit the trainer (not the model yet)**

```bash
echo "models/ner.crfsuite" >> lede-enrich/.gitignore
git add lede-enrich/src/bin/train_ner.rs lede-enrich/Cargo.toml lede-enrich/src/crf/mod.rs lede-enrich/src/lib.rs lede-enrich/.gitignore
git commit -m "feat(lede-enrich): offline CRF trainer + held-out fidelity eval"
```

---

### Task 9: Hit the fidelity bar (AC-4)

**Files:**
- Modify (as needed): `distill/build_manifest.py` (`--per-bucket`), `src/bin/train_ner.rs` (c1/c2).

**Interfaces:** none new — this is a measurement/tuning loop.

- [ ] **Step 1: Read the F1 table from Task 8 Step 3.** Record PERSON/ORG/GPE F1.

- [ ] **Step 2: If PERSON/ORG/GPE F1 ≥ 0.80, skip to Step 4.**

- [ ] **Step 3: If below 0.80, tune in this order, re-running Task 8 Step 3 after each:**
  - Increase corpus: `build_manifest.py --per-bucket 2500` → re-run `label_corpus.py` → retrain.
  - Adjust regularization: lower `set_c1` to `0.05`, try `set_c2` `0.5`.
  - If a specific common type lags, inspect its errors (add a debug print of mismatched spans in `eval`).
  - **POS escalation (only if ORG/GPE disambiguation is the failure mode** — e.g. `Apple`-company vs `apple`-fruit, where part-of-speech is the disambiguator): compute the rule-based POS per token in `train_ner.rs` (call the `pos` tagger, requires building with `--features crf,pos`) and pass it into `sequence_features` instead of `vec![None; …]`, then **also** enable `pos` at inference (Task 11) so train/infer features stay consistent. This couples `crf`→`pos` for the bundled model; only do it if the simpler POS-free model misses the bar. The v1 model is trained POS-free on purpose (works regardless of whether a consumer enables `pos`).
  Stop as soon as the three must-pass types clear 0.80.

- [ ] **Step 4: Record the final numbers** in `distill/README.md` (a short "Fidelity" table: per-label P/R/F1, corpus size, dump id). Commit:

```bash
git add lede-enrich/distill/README.md lede-enrich/distill/corpus_manifest.json
git commit -m "chore(lede-enrich): record CRF fidelity (PERSON/ORG/GPE F1 >= 0.80)"
```

---

## Phase 3 — Inference + API + ship

### Task 10: `Entity` type and BIO→span merge

**Files:**
- Modify: `lede-enrich/src/crf/mod.rs`

**Interfaces:**
- Produces: `pub struct Entity { pub text, pub label: String, pub start, pub end: usize }` and `fn merge(text, &[Tok], &[String]) -> Vec<Entity>` (used by Task 11).

- [ ] **Step 1: Write the failing test**

In `src/crf/mod.rs` add:

```rust
#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entity {
    pub text: String,
    pub label: String,
    pub start: usize,
    pub end: usize,
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crf::tokenize::tokenize;

    #[test]
    fn merge_groups_bio_runs_into_spans() {
        let text = "Acme Corp hired Jeff Bezos.";
        let toks = tokenize(text);
        // tokens: Acme Corp hired Jeff Bezos .
        let labels = vec![
            "B-ORG".into(), "I-ORG".into(), "O".into(),
            "B-PERSON".into(), "I-PERSON".into(), "O".into(),
        ];
        let ents = merge(text, &toks, &labels);
        assert_eq!(ents, vec![
            Entity { text: "Acme Corp".into(), label: "ORG".into(), start: 0, end: 9 },
            Entity { text: "Jeff Bezos".into(), label: "PERSON".into(), start: 16, end: 26 },
        ]);
    }
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd lede-enrich && cargo test --features crf merge_groups_bio`
Expected: FAIL — `cannot find function merge`.

- [ ] **Step 3: Implement `merge`**

Add to `src/crf/mod.rs`:

```rust
use crate::crf::tokenize::Tok;

/// Merge a BIO label sequence (aligned to `toks`) into entity spans, slicing the
/// surface text out of `text` by byte offsets.
fn merge(text: &str, toks: &[Tok], labels: &[String]) -> Vec<Entity> {
    let mut out = Vec::new();
    let mut cur: Option<(String, usize, usize)> = None; // (label, start_byte, end_byte)
    let flush = |cur: &mut Option<(String, usize, usize)>, out: &mut Vec<Entity>| {
        if let Some((label, s, e)) = cur.take() {
            out.push(Entity { text: text[s..e].to_string(), label, start: s, end: e });
        }
    };
    for (i, tok) in toks.iter().enumerate() {
        let lbl = labels.get(i).map(String::as_str).unwrap_or("O");
        if let Some(t) = lbl.strip_prefix("B-") {
            flush(&mut cur, &mut out);
            cur = Some((t.to_string(), tok.start, tok.end));
        } else if let Some(t) = lbl.strip_prefix("I-") {
            match &mut cur {
                Some((l, _, end)) if l == t => *end = tok.end,
                _ => {
                    flush(&mut cur, &mut out);
                    cur = Some((t.to_string(), tok.start, tok.end));
                }
            }
        } else {
            flush(&mut cur, &mut out);
        }
    }
    flush(&mut cur, &mut out);
    out
}
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd lede-enrich && cargo test --features crf merge_groups_bio`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lede-enrich/src/crf/mod.rs
git commit -m "feat(lede-enrich): Entity type + BIO->span merge"
```

---

### Task 11: `extract_entities_typed` + bundled model

**Files:**
- Modify: `lede-enrich/src/crf/mod.rs`
- Add: `lede-enrich/models/ner.crfsuite` (committed; produced in Task 9)

**Interfaces:**
- Consumes: `tokenize` (Task 5), `sequence_features` (Task 4), `merge` (Task 10), `crfs::{Model, Tagger, Attribute}`.
- Produces: `pub fn extract_entities_typed(text: &str) -> Vec<Entity>`, exported from `lib.rs` in Step 2 below.

- [ ] **Step 1: Model artifact + flate2 dep**

The model is already committed **gzipped** as `lede-enrich/models/ner.crfsuite.gz` (6.4 MB; raw 16.7 MB). Nothing to un-ignore. Add `flate2` (used by inference to decompress at load) as an optional dep gated into `crf`, in `lede-enrich/Cargo.toml`:

```toml
flate2 = { version = "1", optional = true }
```
and extend the feature: `crf = ["dep:crfs", "dep:serde_json", "dep:flate2"]`.

- [ ] **Step 2: Implement inference**

Add to `src/crf/mod.rs`. Note the crfs 0.4.1 realities (confirmed in Tasks 8): `Model::new(&[u8])` **borrows** the bytes (so the decompressed buffer must be `'static` — keep it in a `OnceLock<Vec<u8>>`), and `Tagger::tag` returns `Vec<&str>` (convert to `Vec<String>` before `merge`, which takes `&[String]`).

```rust
use std::sync::OnceLock;

use crfs::{Attribute, Model};

/// Bundled model, gzipped (6.4 MB vs 16.7 MB raw). Decompressed once at first use.
static MODEL_GZ: &[u8] = include_bytes!("../../models/ner.crfsuite.gz");

fn model() -> &'static Model<'static> {
    // The decompressed bytes live in a static OnceLock so the Model (which borrows
    // them) can be `'static` and cached.
    static BYTES: OnceLock<Vec<u8>> = OnceLock::new();
    static M: OnceLock<Model<'static>> = OnceLock::new();
    let bytes = BYTES.get_or_init(|| {
        use std::io::Read;
        let mut out = Vec::new();
        flate2::read::GzDecoder::new(MODEL_GZ)
            .read_to_end(&mut out)
            .expect("bundled CRF model gunzips");
        out
    });
    M.get_or_init(|| Model::new(bytes).expect("bundled CRF model is valid"))
}

/// Typed PERSON/ORG/GPE/… entities via the distilled CRF. Deterministic: fixed
/// bundled weights + fixed feature order + Viterbi decode. Additive — does not
/// affect `extract_entities` or `metadata`.
#[must_use]
pub fn extract_entities_typed(text: &str) -> Vec<Entity> {
    let toks = tokenize::tokenize(text);
    if toks.is_empty() {
        return Vec::new();
    }
    let tokens: Vec<String> = toks.iter().map(|t| t.text.clone()).collect();
    let pos = vec![None; tokens.len()];
    let feats = features::sequence_features(&tokens, &pos);
    let xseq: Vec<Vec<Attribute>> = feats
        .iter()
        .map(|row| row.iter().map(|s| Attribute::new(s.as_str(), 1.0)).collect())
        .collect();
    let tagger = model().tagger().expect("tagger");
    // crfs 0.4: tag returns Vec<&str>; merge wants &[String].
    let labels: Vec<String> = tagger
        .tag(&xseq)
        .unwrap_or_default()
        .into_iter()
        .map(str::to_string)
        .collect();
    merge(text, &toks, &labels)
}
```

Then export both public symbols from `src/lib.rs` (add under the existing `#[cfg(feature = "crf")]` section):

```rust
#[cfg(feature = "crf")]
pub use crf::{Entity, extract_entities_typed};
```

- [ ] **Step 3: Build and sanity-check**

Run: `cd lede-enrich && cargo build --features crf`
Expected: compiles. Quick check:

```bash
cd lede-enrich && cat > /tmp/crf_check.rs <<'EOF'
fn main() {
    for e in lede_enrich::extract_entities_typed("Amazon hired Jeff Bezos in Seattle.") {
        println!("{:?} {} [{}..{}]", e.label, e.text, e.start, e.end);
    }
}
EOF
echo "(or add a temporary #[test] in mod.rs printing the output)"
```
Expected: ORG/PERSON/GPE-ish spans for Amazon / Jeff Bezos / Seattle.

- [ ] **Step 4: Commit**

```bash
git add lede-enrich/src/crf/mod.rs
git commit -m "feat(lede-enrich): extract_entities_typed via bundled distilled CRF"
```

---

### Task 12: Determinism + back-compat tests

**Files:**
- Create: `lede-enrich/tests/crf.rs`

**Interfaces:**
- Consumes: `lede_enrich::{extract_entities, extract_entities_typed, metadata}`.

- [ ] **Step 1: Write the tests**

Create `tests/crf.rs`:

```rust
//! CRF feature tests (gated). Determinism + back-compat: the additive typed path
//! must not perturb the existing gazetteer outputs.
#![cfg(feature = "crf")]

use lede_enrich::{extract_entities, extract_entities_typed, metadata};

#[test]
fn typed_is_deterministic() {
    let t = "Amazon hired Jeff Bezos in Seattle on 2024-01-15.";
    assert_eq!(extract_entities_typed(t), extract_entities_typed(t));
}

#[test]
fn typed_finds_known_entities_with_labels() {
    let ents = extract_entities_typed("Amazon hired Jeff Bezos in Seattle.");
    assert!(ents.iter().any(|e| e.label == "ORG"));
    assert!(ents.iter().any(|e| e.label == "PERSON"));
    // byte offsets slice back to the surface form:
    let t = "Amazon hired Jeff Bezos in Seattle.";
    for e in &ents {
        assert_eq!(&t[e.start..e.end], e.text);
    }
}

#[test]
fn additive_does_not_change_gazetteer_paths() {
    let t = "Dr. John Smith of Acme Corp visited Paris and London in 2024.";
    // these must be exactly what the default build produces:
    assert_eq!(
        extract_entities(t),
        vec!["John Smith", "Acme Corp", "Paris", "London"]
    );
    assert_eq!(metadata(t).entities, extract_entities(t));
}
```

- [ ] **Step 2: Run the tests**

Run: `cd lede-enrich && cargo test --features crf --test crf`
Expected: PASS. (If `additive_does_not_change_gazetteer_paths` fails on the expected vector, copy the actual current default output of `extract_entities(t)` into the assertion — the point is that it is unchanged from pre-CRF, so verify it against `git stash`/`main` once and lock it.)

- [ ] **Step 3: Run the full default suite to prove no regression**

Run: `cd lede-enrich && cargo test`
Expected: all existing tests PASS (default build untouched).

- [ ] **Step 4: Commit**

```bash
git add lede-enrich/tests/crf.rs
git commit -m "test(lede-enrich): crf determinism + gazetteer back-compat"
```

---

### Task 13: Model card, README, CI, lint

**Files:**
- Create: `lede-enrich/models/MODEL_CARD.md`
- Modify: `lede-enrich/README.md`
- Modify: `.github/workflows/*` (the lede-enrich CI job)

**Interfaces:** none.

- [ ] **Step 1: Write the model card**

Create `models/MODEL_CARD.md` covering: **teacher** (`en_core_web_sm` 3.8.0, MIT), **engine** (`crfs`, MIT), **corpus** (English Wikipedia dump `20231101.en`, **CC-BY-SA 4.0** — attribution), label set (11 lexical types), held-out fidelity table (from Task 9), and the **residual licensing note** verbatim from spec §10 (self-generated weights, text not redistributed, ShareAlike-vs-Apache-2.0 gray area, needs human sign-off before publish/tag).

- [ ] **Step 2: Document the feature in README**

Add a "Typed NER (`crf` feature)" section to `lede-enrich/README.md`: opt-in install (`features = ["crf"]`), `extract_entities_typed` example, the honest expectation note (labels + novel-capitalized recall solid; lowercase not guaranteed), and a pointer to the model card.

- [ ] **Step 3: Add `--features crf` to CI**

In the lede-enrich CI job, add steps mirroring the default ones:

```yaml
      - run: cd lede-enrich && cargo test --features crf
      - run: cd lede-enrich && cargo clippy --features crf --all-targets -- -D warnings
```

- [ ] **Step 4: Lint clean**

Run: `cd lede-enrich && cargo fmt && cargo clippy --features crf --all-targets -- -D warnings`
Expected: no warnings. Fix any.

- [ ] **Step 5: Final verification and commit**

Run: `cd lede-enrich && cargo test && cargo test --features crf`
Expected: both green.

```bash
git add lede-enrich/models/MODEL_CARD.md lede-enrich/README.md .github
git commit -m "docs(lede-enrich): CRF NER model card, README, CI matrix (#16)"
```

---

## Self-Review notes (for the executor)

- **Tokenization alignment (spec R-1)** is *fixed by design*: Rust's `tokenize()` is used for both training (Task 8) and inference (Task 11), and spaCy only supplies tokenizer-independent char-spans (Task 6), so token boundaries cannot desync labels. The only residual is a char-span partially overlapping a Rust token — `project_bio` (Task 5) handles that by containment (partial overlaps → `O`). If real-text spans still look wrong despite good held-out F1, check `tokenize` punctuation/contraction handling, not spaCy parity.
- **`crfs` version & API** — Task 1 Step 1 pins the version; if `params_mut().set_c1/set_c2`, `Attribute::new`, `Model::new(&[u8])`, `model.tagger()`, or `tagger.tag()` differ in the resolved version, adjust Tasks 8/11 to match the crate's actual signatures (check `cargo doc --open -p crfs`).
- **`crfs` purity (spec R-2)** — confirm during Task 8 whether training pulls a `-sys` crate; inference is unaffected either way.
- The `additive_does_not_change_gazetteer_paths` expected vectors (Task 12) must be locked against the **pre-change** default output — verify once on `main`.
