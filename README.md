# skimr

**Deterministic extractive summarization — zero runtime dependencies.**

Python + Rust library + CLI that shrinks text before it hits an LLM, cache, or preview. Same algorithm, reproducible output, sub-millisecond latency, byte-identical across runtimes.

### Why not Sumy / TextRank / LexRank?

Use Sumy if you want the algorithm catalog (LSA, LexRank, TextRank, Luhn, Edmundson, KL-Sum…). Use skimr if you want:

- **Sub-millisecond latency in the default path** — skimr `mode=default` runs at 0.42 ms p50 across the [10-corpus benchmark](benchmarks/quality/matrix-2026-04-26.md); Sumy LexRank/TextRank/LSA all sit at 11–12 ms p50. ~30× headroom on the same hardware.
- **Byte-identical Python ↔ Rust core path** — same fixture corpus, same output bytes from either runtime, verified on every push by `rust/tests/fixtures.rs`.
- **Structured RAG-prep in one call** — `summarize(attach=["stats", "outline", "metadata", "phrases", "correlated_facts"])` returns the summary plus pre-extracted facts, sections, dates, amounts, URLs, and entity↔number correlations. No second pass.
- **Zero dependencies on the default install** — Python stdlib only; Rust stdlib + `regex` only. Optional extras (`[ner]` / `[wordforms]` / `[yake]` / `[textrank]`) are opt-in.

## What's new in v0.2

skimr v0.2 is the RAG-prep primitive: one call returns a summary plus structured enrichments that ride along.

```python
from skimr import summarize

r = summarize(
    doc_text,
    max_length=500,
    mode="default",   # also "coverage" (paragraph-aware) or "legacy" (v0.0.1 bytes)
    attach=["stats", "outline", "metadata", "phrases", "correlated_facts"],
)

r.summary            # str (also: str(r) / f"{r}")
r.stats              # tuple[Stat, ...]      — numeric facts with context
r.outline            # tuple[Section, ...]   — section headings + key sentence
r.metadata           # Metadata(dates, amounts, urls, entities)
r.phrases            # tuple[str, ...]       — repeated multi-word phrases
r.correlated_facts   # tuple[PhraseFact, ...]— entity ↔ number/polarity pairs
```

Or call any primitive standalone:

```python
from skimr.extract import stats, outline, metadata, phrases, correlate_facts, toc, key_facts
```

There's also `skimr.brief(text)` for a paste-ready at-a-glance brief (overview + key facts + table of contents) in `string`, `markdown`, or `dict` form.

**Latency:** core path stays sub-millisecond; full enrichment with all five attachments runs in ~2-4 ms p50 per document. See [`benchmarks/quality/matrix-2026-04-26.md`](benchmarks/quality/matrix-2026-04-26.md) for the full method × corpus matrix and the comparison against Sumy LexRank/TextRank/LSA.

### Optional extras

```bash
pip install -e ".[wordforms]"
```

Adds spelled-out number support to `stats()` and `correlate_facts()` (`"five thousand documents"` → a `Stat`). Available as the `wordforms` cargo feature on the Rust side, which binds to the same Rust crate so output stays byte-identical.

```bash
pip install -e ".[yake]"
```

Registers a `backend="yake"` for `phrases()` — salient-phrase ranking instead of the default repeated-n-gram heuristic. Python only.

```bash
pip install -e ".[textrank]"
```

Enables `summarize_textrank` for graph-based extractive on long docs (Python-only, requires `networkx`).

For spaCy-backed `Metadata.entities` (PERSON / ORG / GPE), install the companion package from `packages/skimr-spacy/` and the spaCy model:

```bash
pip install -e packages/skimr-spacy
python -m spacy download en_core_web_sm
```

Importing `skimr_spacy` registers itself as a backend; `extract.metadata(text, backend="spacy")` then populates `entities`. The Rust port does not ship NER by design — `entities` stays empty under the regex backend in either runtime.

### Known v0.2 gates

`extract.phrases` and `extract.correlate_facts` ship with documented gold-vs-primitive design mismatches and are tracked for v0.3+. The other three primitives (`stats`, `outline`, `metadata`) all clear the SC-D quality gate (recall ≥ 0.85, precision ≥ 0.80) under the format-tolerant match rule. See [`docs/REFERENCE.md`](docs/REFERENCE.md) and [`benchmarks/quality/extraction-2026-04-26.md`](benchmarks/quality/extraction-2026-04-26.md).

## Install

skimr is not yet on PyPI — install from source:

```bash
git clone git@github.com:yonk-labs/skimr.git
cd skimr
pip install -e .                     # default: zero deps
pip install -e ".[textrank]"         # adds networkx-based TextRank mode
pip install -e ".[wordforms]"        # adds spelled-out number recognition
pip install -e ".[yake]"             # adds YAKE phrases backend
pip install -e packages/skimr-spacy  # adds spaCy-backed entities (companion)
```

PyPI / crates.io publication is tracked for a later release.

## Quick Start

```python
from skimr import summarize, clean_text, strip_think, extract_keyword

text = open("long_doc.md").read()

# Default: TF-IDF + position + length, 500-char budget
summary = summarize(text, max_length=500)

# Query-driven: top-3 sentences relevant to keywords
relevant = extract_keyword(text, "pricing budget competitor", num_sentences=3)

# Strip markdown, filler, CRM boilerplate before passing to an LLM
cleaned = clean_text(text)

# Remove <think>...</think> blocks from reasoning-model output
from anthropic import Anthropic  # or openai, etc.
raw = ...  # LLM response
visible = strip_think(raw)
```

## CLI

```bash
# Summarize a file (TF-IDF default, 500-char budget)
skimr long_doc.md

# Query-driven extractive
skimr long_doc.md --mode keyword --keywords "pricing budget" --top 3

# Pipe stdin
cat long_doc.md | skimr --mode tfidf --max-chars 1000

# Strip boilerplate only
skimr raw_note.txt --mode clean_text

# Strip reasoning blocks
echo "<think>...</think>Real answer." | skimr --mode strip_think
```

## Rust

A Rust port lives at [`rust/`](rust/). It produces **byte-identical output** to the Python implementation for every fixture in [`fixtures/`](fixtures/) — the contract for cross-runtime parity.

### Install from source

```bash
git clone https://github.com/yonk-labs/skimr.git
cd skimr/rust
cargo build --release
# binary at target/release/skimr
```

### Library usage

```rust
use skimr::{summarize, clean_text, strip_think, extract_keyword};

let summary = summarize("long document...", 500);
let cleaned = clean_text("**bold** and _underlined_");
let visible = strip_think("<think>...</think>Real answer.");
let focused = extract_keyword("demo notes...", "pricing budget", 3);
```

### Rust CLI

Same flags as the Python CLI:

```bash
./target/release/skimr long_doc.md --mode tfidf --max-chars 500
./target/release/skimr long_doc.md --mode keyword --keywords "pricing budget" --top 3
```

Dependencies: `regex` crate only. No other runtime deps.

## Modes

| Mode | When to use | Where | Deps |
|---|---|---|---|
| `tfidf` (default) | "Give me the most important N chars of this document" | CLI + library | stdlib only |
| `keyword` | "Give me sentences relevant to these keywords" | CLI + library | stdlib only |
| `clean_text` | Strip markdown, filler, CRM boilerplate | CLI + library | stdlib only |
| `strip_think` | Remove `<think>…</think>` from reasoning-model output | CLI + library | stdlib only |
| `textrank` | Graph-based extractive on long docs | library only (`from skimr.textrank import summarize_textrank`) | requires `[textrank]` extra |

## Design Notes

- **Deterministic.** Same input → same bytes, every time. No random tie-breaking.
- **Zero-dep default.** Stdlib only. TextRank is opt-in.
- **Cross-runtime parity.** Shared fixture corpus under `fixtures/` is the contract. Python and Rust produce byte-identical output for every fixture; the `rust/tests/fixtures.rs` walker asserts this on every CI push.
- **Extractive, not abstractive.** No LLM calls. For abstractive summarization, use a different tool.

Full spec: [`SUMMARIZATION.md`](SUMMARIZATION.md) and [`extractive_functions.md`](extractive_functions.md).
Project scope: [`skill-output/mission-brief/Mission-Brief-skimr.md`](skill-output/mission-brief/Mission-Brief-skimr.md).

## License

Apache-2.0.
