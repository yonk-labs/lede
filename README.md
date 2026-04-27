# skimr

[![tests](https://github.com/yonk-labs/skimr/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/yonk-labs/skimr/actions/workflows/test.yml)
[![rust](https://github.com/yonk-labs/skimr/actions/workflows/rust.yml/badge.svg?branch=main)](https://github.com/yonk-labs/skimr/actions/workflows/rust.yml)
[![zero-deps](https://github.com/yonk-labs/skimr/actions/workflows/zero-deps.yml/badge.svg?branch=main)](https://github.com/yonk-labs/skimr/actions/workflows/zero-deps.yml)
[![skimr-spacy](https://github.com/yonk-labs/skimr/actions/workflows/skimr-spacy.yml/badge.svg?branch=main)](https://github.com/yonk-labs/skimr/actions/workflows/skimr-spacy.yml)
[![release](https://img.shields.io/github/v/release/yonk-labs/skimr?label=release&color=blue)](https://github.com/yonk-labs/skimr/releases/latest)
[![license](https://img.shields.io/badge/license-Apache--2.0-green)](LICENSE)
[![python](https://img.shields.io/badge/python-3.10%2B-blue)](pyproject.toml)
[![rust](https://img.shields.io/badge/rust-1.85%2B-orange)](rust/Cargo.toml)

**A deterministic, zero-dependency text-shrinker for the layer in front of an LLM.**

Python + Rust library + CLI. Reads a document, returns a summary in sub-millisecond time plus optional structured facts (numbers, dates, sections, entities, entity↔number correlations) that you'd otherwise extract in a second pass. Same input → same bytes from either runtime, every time.

### What problem this solves

Modern AI apps push more text through more LLM calls than is healthy. Every long prompt, every chunk-embed, every tool result that gets re-summarized — that's tokens spent and latency burned. The 2026 enterprise narrative is that preprocessing/compression in front of the model is a 40–94% cost lever ([Maxim](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/), [Morph](https://www.morphllm.com/llm-cost-optimization)) — but the libraries that do that preprocessing are mostly:

- **Heavyweight** (Sumy + nltk; rust-bert + ONNX) — multi-MB installs, slow startup
- **Non-deterministic** (LLM-call-as-summarizer) — different bytes on the same input across calls/days/models
- **Single-runtime** (Sumy is Python-only; Go has `tldr`; Node has fragmentary npm packages) — you ship a different summarizer in each tier of your stack
- **Just a summary** — when what you actually need for RAG is the summary *plus* the dates / amounts / URLs / entities you'd otherwise grep out yourself

skimr is the small, boring, deterministic primitive for this hot path: **stdlib-only Python and stdlib+regex-only Rust, byte-identical output across both, sub-ms on the core path, sub-5 ms with all five structured-extract enrichments attached.**

### Who this is for

- **RAG-prep pipelines** — chunk → skimr → embed. One call gives you the focused summary to embed *plus* the dates/amounts/entities for the metadata column. See [`docs/integration-memo.md`](docs/integration-memo.md) for the chunkshop integration design.
- **MCP / agent middleware** — intercept tool output, drop a `clean_text` + `summarize(max_length=500)` in front of the model. Costs ~0.4 ms; saves a tool result from blowing the context window.
- **Polyglot stacks** — Python data tier + Rust service tier + (eventually) Node frontend. One library, one fixture corpus, byte-identical output.
- **Eval / replay** — deterministic output means snapshot tests don't drift. Same input = same bytes today, next year, on the next maintainer's laptop.

### Why not just call Claude / GPT / Cohere?

Use the LLM if you want the *highest* quality summary and you can pay 500–5000 ms per doc and accept that two calls return different bytes. Use skimr (or alongside it) when you want:

- **Sub-millisecond, on-device, zero-API-cost** — fits a hot path the LLM can't.
- **Deterministic** — required for snapshot tests, regression harnesses, and audit trails.
- **An honest preprocessor** — drop skimr in front of the LLM call; it's a 40–94% token-cut at the input layer with zero quality cost on the LLM's downstream summary, and it produces structured fields the LLM would otherwise have to be prompted to extract.

### Why not Sumy / TextRank / LexRank / "I'll just use re.findall"?

| Alternative | When to use it | When skimr wins |
|---|---|---|
| **Sumy** (Python, 3.7k★) — algorithm catalog: LSA, LexRank, TextRank, Luhn, Edmundson, KL-Sum | You want a specific classical algorithm (LSA, KL-Sum) and Python only | You want sub-ms latency (skimr default 0.42 ms p50 vs Sumy 11–12 ms across the [10-corpus benchmark](benchmarks/quality/matrix-2026-04-26.md)), Python ↔ Rust parity, structured enrichments in one call, or zero deps |
| **JesusIslam/tldr** (Go, LexRank), **rust-bert** (Rust, abstractive BART) | You're Go-only or want abstractive on-device | You want one summarizer that produces identical output across Python and Rust, or you don't want to ship 400 MB of model weights |
| **`re.findall(r"\d+%")` + a sentence splitter** | One-off scripts | You want this to keep working when the input contains UTF-8 emoji, 50 K-digit pathological strings, abbreviation edge-cases, em-dash titles, and 9 other things you didn't think of. The fixtures + tests are the value. |
| **LLM-as-summarizer** (Claude / GPT / Cohere) | Highest quality, latency and cost are fine | Hot path, deterministic output requirement, snapshot tests, regulated environment, or you want skimr in *front* of the LLM as a 50% input-token-cutter |

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

Full v0.2 design contract: [`docs/v0-2-design.md`](docs/v0-2-design.md). Original algorithmic spec: [`SUMMARIZATION.md`](SUMMARIZATION.md) (with `extractive_functions.md` for the PL/pgSQL reference). Primitive catalog: [`docs/REFERENCE.md`](docs/REFERENCE.md). Method × corpus benchmark: [`benchmarks/quality/matrix-2026-04-26.md`](benchmarks/quality/matrix-2026-04-26.md). For a worked side-by-side comparison vs Sumy and LLM APIs, see [`docs/comparison.md`](docs/comparison.md).

## License

Apache-2.0.
