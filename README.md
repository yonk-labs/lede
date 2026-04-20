# skimr

**Deterministic extractive summarization — zero runtime dependencies.**

Python + Rust library + CLI that shrinks text before it hits an LLM, cache, or preview. Same algorithm, reproducible output, sub-millisecond latency, byte-identical across runtimes.

## Install

```bash
pip install skimr                    # default: zero deps
pip install "skimr[textrank]"        # adds optional networkx-based TextRank mode
```

From source:

```bash
git clone https://github.com/<YOUR-ORG>/skimr.git
cd skimr
pip install -e ".[dev]"
```

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

| Mode | When to use | Deps |
|---|---|---|
| `tfidf` (default) | "Give me the most important N chars of this document" | stdlib only |
| `keyword` | "Give me sentences relevant to these keywords" | stdlib only |
| `clean_text` | Strip markdown, filler, CRM boilerplate | stdlib only |
| `strip_think` | Remove `<think>…</think>` from reasoning-model output | stdlib only |
| `textrank` | Graph-based extractive on long docs | requires `[textrank]` extra |

## Design Notes

- **Deterministic.** Same input → same bytes, every time. No random tie-breaking.
- **Zero-dep default.** Stdlib only. TextRank is opt-in.
- **Cross-runtime parity.** Shared fixture corpus under `fixtures/` is the contract. Python and Rust produce byte-identical output for every fixture; the `rust/tests/fixtures.rs` walker asserts this on every CI push.
- **Extractive, not abstractive.** No LLM calls. For abstractive summarization, use a different tool.

Full spec: [`SUMMARIZATION.md`](SUMMARIZATION.md) and [`extractive_functions.md`](extractive_functions.md).
Project scope: [`skill-output/mission-brief/Mission-Brief-skimr.md`](skill-output/mission-brief/Mission-Brief-skimr.md).

## License

Apache-2.0.
