# lede-enrich

Deterministic, license-clean **classical NLP enrichment** for the
[`lede`](https://crates.io/crates/lede) Rust path — entities and numeric facts
for an ingest pipeline, with **no spaCy and no transformers**. Reaches
spaCy-`sm`-*class* quality from gazetteer + rule-based techniques, so it stays
fast, integer-exact deterministic, and free of model downloads on the default
path.

It is the Rust sibling of the Python `lede-spacy` companion. (The Python one
*is* spaCy-backed; this one deliberately is not — hence the different name.)

## What it provides

```rust
use lede_enrich::{extract_entities, metadata, correlate_facts, lemma};

// PERSON/ORG/GPE/LOC/PRODUCT-class surface forms, first-appearance order.
let ents = extract_entities("Dr. John Smith visited Cook County last week.");
// → ["John Smith", "Cook County"]

// lede's regex dates/amounts/urls + NER entities.
let md = metadata("Apple reported $5 billion on 2024-01-15.");

// Entity↔number facts (lede core regex facts re-attributed with NER entities).
let facts = correlate_facts("Apple grew. Apple reported revenue of $5 billion in 2024.");

// Rule-based lemmatizer.
assert_eq!(lemma("studies"), "study");
```

### Opt-in `pos` feature

```toml
lede-enrich = { version = "0.1", features = ["pos"] }
```

Adds a rule-based POS tagger (`pos_tag`) and a higher-recall, POS-anchored facts
path (`correlate_facts_pos`). Still no weights, no deps, no network.

## Guarantees & non-guarantees

- **Deterministic** within Rust: same input → same bytes, every run, every platform.
- **No Python↔Rust byte-parity promise** — output is spaCy-`sm`-*class*, not
  bit-identical to the Python companion (different algorithms by design),
  consistent with lede's optional-backend policy.
- **License-clean default**: ships no trained weights. The higher-accuracy
  averaged-perceptron path (NLTK/PTB weights) is a deferred opt-in that loads
  *user-supplied* weights — never bundled.

## License

Apache-2.0. Part of the [lede](https://github.com/yonk-labs/lede) project.
