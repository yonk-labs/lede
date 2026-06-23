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

### Typed NER (`crf` feature)

The `crf` feature bundles a trained CRF model (6.4 MB gzipped) that extends
entity extraction with 11 lexical type labels: `PERSON`, `NORP`, `FAC`, `ORG`,
`GPE`, `LOC`, `PRODUCT`, `EVENT`, `WORK_OF_ART`, `LAW`, `LANGUAGE`.

```toml
lede-enrich = { version = "0.2", features = ["crf"] }
```

```rust
use lede_enrich::extract_entities_typed;

let ents = extract_entities_typed(
    "Amazon was founded by Jeff Bezos in Seattle.",
);
// → [("Amazon", "ORG"), ("Jeff Bezos", "PERSON"), ("Seattle", "GPE")]
```

**Honest expectations:**

- Typed labels and novel-entity recall are solid for well-capitalised,
  Wikipedia-register text. High-frequency types (GPE, NORP, LANGUAGE) land at
  F1 0.78–0.81 vs. the teacher; PERSON and ORG at ~0.65–0.70.
- Lowercase-entity recall is **not guaranteed** — the model relies heavily on
  capitalisation features.
- Long-tail types (EVENT, WORK_OF_ART, PRODUCT, FAC, LAW) are noisy and
  should not be used for precision-critical applications without fine-tuning.
- The bundled model is **CC-BY-SA-4.0** (trained on Wikipedia text; ShareAlike
  honoured by licensing the model the same way). The crate's code is Apache-2.0.
  See [`models/MODEL_CARD.md`](models/MODEL_CARD.md) and
  [`models/LICENSE-MODEL.md`](models/LICENSE-MODEL.md) for provenance, the
  per-type F1 table, and training setup.

### Opt-in `pos` feature

```toml
lede-enrich = { version = "0.2", features = ["pos"] }
```

Adds a rule-based POS tagger (`pos_tag`) and a higher-recall, POS-anchored facts
path (`correlate_facts_pos`). Still no weights, no deps, no network.

## Guarantees & non-guarantees

- **Deterministic** within Rust: same input → same bytes, every run, every platform.
- **No Python↔Rust byte-parity promise** — output is spaCy-`sm`-*class*, not
  bit-identical to the Python companion (different algorithms by design),
  consistent with lede's optional-backend policy.
- **License-clean default**: the default build ships no trained weights and is
  pure Apache-2.0. The opt-in `crf` feature bundles a CC-BY-SA-4.0 model (below).

## License

- **Code:** Apache-2.0.
- **Bundled CRF model** (`models/ner.crfsuite.gz`, only with the `crf` feature):
  **CC-BY-SA-4.0** — a CC-BY-SA-derived artifact (trained on Wikipedia), licensed
  to match its source. See [`models/LICENSE-MODEL.md`](models/LICENSE-MODEL.md).

SPDX: `Apache-2.0 AND CC-BY-SA-4.0`. Part of the [lede](https://github.com/yonk-labs/lede) project.
