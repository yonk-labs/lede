# Model Card — `lede-enrich` CRF NER (`ner.crfsuite.gz`)

This document covers the model bundled in the `crf` feature of `lede-enrich`.
It follows the minimal model card format: teacher, engine, corpus, label set,
fidelity, and licensing.

---

## Model summary

| Field        | Value |
|---|---|
| **Model type** | Linear-chain CRF (Conditional Random Field) |
| **Engine** | [`crfs`](https://crates.io/crates/crfs) 0.4.1 (MIT) |
| **Algorithm** | L2SGD — L2-regularized CRF via stochastic gradient (batch L-BFGS did not converge in practical time on this feature space with single-threaded training; L2SGD chosen for speed and reliability) |
| **Teacher** | spaCy `en_core_web_lg` 3.8.0 (MIT) |
| **Task** | Named entity recognition — 11 lexical types + O |
| **Languages** | English |
| **File** | `models/ner.crfsuite.gz` — 6.4 MB gzipped (16.7 MB raw) |

---

## Training corpus

- **Source:** English Wikipedia dump `20231101.en`
  ([Wikimedia Downloads](https://dumps.wikimedia.org/))
- **License:** [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/)
  — text is **not redistributed**; only the self-generated CRF weights ship
  with this crate (see Licensing section below)
- **Sampling:** Stratified tech-weighted split —
  tech / business / science / general categories
- **Scale:** ~400 articles → ~63,500 sentences;
  trained on a balanced ~21,000-sentence subsample

The teacher (`en_core_web_lg`) labelled each sentence; those labels were used
as training targets for the CRF. This is a knowledge-distillation setup —
the CRF learns to approximate the teacher's decisions from surface features
alone.

---

## Label set (11 lexical types)

| Label | Description |
|---|---|
| `PERSON` | People, fictional or real |
| `NORP` | Nationalities, religious, or political groups |
| `FAC` | Buildings, airports, highways, bridges |
| `ORG` | Companies, agencies, institutions |
| `GPE` | Countries, cities, states |
| `LOC` | Non-GPE locations (mountains, water bodies) |
| `PRODUCT` | Objects, vehicles, foods (not services) |
| `EVENT` | Named events, hurricanes, battles, etc. |
| `WORK_OF_ART` | Titles of books, songs, etc. |
| `LAW` | Named laws, bills, and legal documents |
| `LANGUAGE` | Any named language |

---

## Held-out fidelity vs. teacher

Evaluated on held-out Wikipedia sentences (not seen during training).
All scores are **fidelity to the teacher** (how closely the CRF reproduces
the teacher's labels), not ground-truth NER accuracy.

### Headline numbers

| Metric | Score |
|---|---|
| Untyped entity F1 (span recall vs. teacher) | **0.80** |
| Token-level accuracy | **0.95** |
| Gazetteer baseline (untyped, for comparison) | 0.55 |

The CRF beats the prior gazetteer-only baseline by 25 pp on untyped span F1.

### Per-type strict span F1 (type must match exactly)

| Type | Strict span F1 |
|---|---|
| NORP | 0.81 |
| GPE | 0.79 |
| LANGUAGE | 0.78 |
| LOC | 0.72 |
| PERSON | 0.70 |
| ORG | 0.65 |
| EVENT | 0.45 |
| WORK_OF_ART | 0.38 |
| PRODUCT | 0.28 |
| FAC | 0.26 |
| LAW | 0.08 |

---

## Performance (measured, release build)

Single-threaded, warm, averaged over 10,000 `extract_entities_typed` calls on
mixed-length sentences:

| Path | Latency / call | Throughput | Footprint | Runtime |
|---|---|---|---|---|
| Gazetteer (`extract_entities`, default) | ~1.5 µs | ~670k sent/s | ~0 (343-word lists) | pure Rust |
| **CRF (`extract_entities_typed`, this feature)** | **~92 µs** | **~11k sent/s** | 6.4 MB in-crate (gzipped) | pure Rust |
| Python spaCy (teacher) | ~5 ms¹ | ~200 sent/s | ~560 MB + Python | Python + spaCy |

- **Cold start:** ~36 ms one-time on the first typed call (gunzip + model load via `OnceLock`); amortized to zero thereafter.
- The CRF is **sub-millisecond (~92 µs)** — ~63× the gazetteer (the cost of the model) but ~50× faster and ~90× smaller than running Python spaCy.
- ¹ spaCy latency from the `lede-spacy` README (`en_core_web_sm`, post-warmup).

---

## Honest notes

- **Typed PERSON/ORG ceiling (~0.65–0.70)** reflects the difficulty of
  distilling a CNN spaCy model into a linear CRF. The gap is mostly *type
  confusion* (entities found but typed differently), not missed entities —
  untyped span recall is 0.80.
- **The CRF often labels more cleanly than its teacher.** `en_core_web_lg`
  occasionally over-labels or mis-types; the CRF generalises toward cleaner
  boundaries.
- **Lowercase-entity recall is not guaranteed.** The model relies heavily on
  capitalisation features (shape, `is_title`). Novel entities in all-lowercase
  text will often be missed.
- **Long-tail types are noisy** (EVENT 0.45, WORK_OF_ART 0.38, PRODUCT 0.28,
  FAC 0.26, LAW 0.08). These are sparse in the training corpus and are not
  suitable for precision-critical use cases without fine-tuning.
- **Domain:** English Wikipedia. Performance on other registers (legal, medical,
  informal text) is untested.

---

## Licensing

This crate is **dual-licensed by component:**

| Component | Licence |
|---|---|
| Source code (everything except the bundled model) | Apache-2.0 |
| Bundled model weights `ner.crfsuite.gz` | **CC-BY-SA-4.0** |

### The model weights are CC-BY-SA-4.0

`ner.crfsuite.gz` is a **CC-BY-SA-derived** artifact: it was trained from
labels over English Wikipedia text, which is CC-BY-SA 4.0. Rather than argue
whether self-generated weights are a "derivative work," we simply **license the
model under the same licence as its source — CC-BY-SA-4.0 — which satisfies the
ShareAlike clause outright.** No legal gray area:

- **Attribution:** the training text is English Wikipedia (dump `20231101.en`),
  © its contributors, CC-BY-SA 4.0 (https://creativecommons.org/licenses/by-sa/4.0/).
- **ShareAlike:** the model and any redistribution of it remain CC-BY-SA-4.0.
- The Wikipedia source text itself is **never redistributed** — only the learned
  parameter file, under the matching licence.

Downstream: using `lede-enrich` as a code dependency is Apache-2.0; redistributing
the bundled model (or a crate that embeds it) carries the CC-BY-SA-4.0 attribution
+ ShareAlike obligations for that file. The crate's Cargo `license` field is the
SPDX compound `Apache-2.0 AND CC-BY-SA-4.0` to reflect both.

### Teacher model licence

spaCy `en_core_web_lg` 3.8.0 is MIT-licensed. No spaCy weights are bundled
in this crate.

### Engine licence

`crfs` 0.4.1 is MIT-licensed.

---

## Reproducing the model

```bash
# Regenerate training corpus (requires Python + spaCy + Wikipedia dump)
cd lede-enrich/distill
python gen_gazetteers.py        # refresh CRF-feature gazetteers
python fetch_wiki_corpus.py     # download and label sentences (needs spaCy)

# Train
cd lede-enrich
cargo run --bin train_ner --features crf -- \
    --input distill/corpus.jsonl \
    --output models/ner.crfsuite

# Compress
gzip -k models/ner.crfsuite
```

See `distill/` for the full corpus-generation pipeline.
