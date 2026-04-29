# Tutorial: Using lede

A walk-through of lede's main features. Each lesson shows a snippet,
the actual output, and what to change to see how the output changes.
Real outputs from `lede` v0.2.1 — nothing fabricated.

The same Apollo 11 paragraph (~945 chars) is used throughout so you
can compare lessons directly:

> The Apollo 11 mission landed humans on the Moon for the first time.
> NASA launched the Saturn V rocket from Kennedy Space Center on July
> 16, 1969, carrying astronauts Neil Armstrong, Buzz Aldrin, and
> Michael Collins. Four days later, Armstrong and Aldrin descended to
> the lunar surface in the Eagle lunar module while Collins remained
> in lunar orbit aboard the Columbia command module. Armstrong became
> the first person to walk on the Moon at 02:56 UTC on July 21, 1969,
> declaring "That's one small step for a man, one giant leap for
> mankind." Aldrin joined him 19 minutes later. The astronauts spent
> 21 hours and 36 minutes on the lunar surface, collecting 21.5
> kilograms of lunar material before returning to Columbia. The
> mission splashed down in the Pacific Ocean on July 24, 1969,
> completing an 8-day journey that fulfilled President Kennedy's
> 1961 goal of landing a man on the Moon and returning him safely
> to Earth before the decade ended.

You can paste it into a `text` variable in any of the snippets below.

## Setup

```bash
pip install lede
```

Verify:

```bash
python -c "import lede; print(lede.__version__)"
# 0.3.0
```

For Rust the equivalent is `cargo add lede` (library) or `cargo install lede` (CLI). The CLI binary lands on `$PATH` as `lede`. Throughout this guide, **every Python lesson works identically in Rust on the regex backend** unless explicitly noted as Python-only at the bottom of the lesson.

For development from a checkout, see [`CONTRIBUTING.md`](../CONTRIBUTING.md).

## Lesson 1 — your first summary

```python
from lede import summarize

r = summarize(text, max_length=400)
print(r.summary)
```

Returns a `SummaryResult`. The `.summary` field is a string of sentences pulled directly from `text` — never paraphrased.

> The Apollo 11 mission landed humans on the Moon for the first time. The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.

That's the topic sentence and the closing recap — a real "first-and-last" skim. Both verbatim from the source.

**🦀 Rust** (same input, byte-identical output):

```rust
let r = lede::summarize(text, 400, lede::Mode::Default);
println!("{}", r.summary);
```

## Lesson 2 — change the budget

`max_length` is a soft upper bound on output character count. lede picks the highest-scoring sentences that fit.

| `max_length` | Output | Length |
|---|---|---|
| **200** | "The Apollo 11 mission landed humans on the Moon for the first time." | 67 chars |
| **400** | (the lesson 1 output) | 293 chars |
| **800** | adds: launch detail, Armstrong's first step, the 21:36 surface stay, the 21.5 kg of material | 776 chars |

Try it:

```python
for budget in [200, 400, 800]:
    r = summarize(text, max_length=budget)
    print(f"--- {budget} chars budget, {len(r.summary)} chars output ---")
    print(r.summary)
    print()
```

The smaller the budget, the more the topic sentence dominates. The larger the budget, the more secondary detail sneaks in.

## Lesson 3 — pick the right mode

`mode=` selects how sentences get scored.

| Mode | What it does | Best for |
|---|---|---|
| `"default"` | TF-IDF + position + length, plus heading filter, cue-phrase boost, digit bonus, section weight | most documents (the v0.2 default) |
| `"legacy"` | TF-IDF + position + length only — no v0.2 tweaks. Byte-identical to v0.0.1 | reproducing pre-v0.2 fixtures |
| `"coverage"` | Paragraph-aware: tries to land at least one sentence per paragraph | docs where breadth across sections matters more than top-scoring single sentences |

```python
for mode in ["default", "legacy", "coverage"]:
    r = summarize(text, max_length=400, mode=mode)
    print(f"--- mode={mode!r}, {len(r.summary)} chars ---")
    print(r.summary)
```

On the Apollo 11 paragraph, `default` and `legacy` produce the same result (the C1 tweaks happen to not move anything for this input). `coverage` is shorter (67 chars) because the input is one paragraph — the per-paragraph pass can only pick once.

Try it on a multi-paragraph document and you'll see `coverage` spread sentences across sections while `default` clusters around the highest-signal section.

**🦀 Rust:** `lede::Mode::{Default, Legacy, Coverage}` are the three values.

## Lesson 4 — find sentences relevant to a query

If you have a topic in mind, `extract_keyword` ranks sentences by relevance instead of importance.

```python
from lede import extract_keyword

print(extract_keyword(text, "Moon Armstrong", num_sentences=2))
```

> Armstrong became the first person to walk on the Moon at 02:56 UTC on July 21, 1969, declaring "That's one small step for a man, one giant leap for mankind." Aldrin joined him 19 minutes later.
> The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.

Change the query, get a different ranking:

```python
print(extract_keyword(text, "Pacific splashdown", num_sentences=2))
```

> The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.
> The Apollo 11 mission landed humans on the Moon for the first time.

Now the splashdown sentence ranks first. The score combines keyword-match count with three bonuses (length > 200 chars, presence of digits, causal/analytical vocabulary).

**🦀 Rust:** `lede::extract_keyword(text, keywords, num_sentences)`.

## Lesson 5 — get structured facts alongside the summary

This is the v0.2 differentiator. Pass `attach=[…]` to `summarize` and get the summary plus pre-extracted structured fields, in one call.

```python
r = summarize(text, max_length=400, attach=["stats", "metadata"])
r.summary             # str — the same as before
r.stats               # tuple[Stat, ...] — numeric facts with sentence context
r.metadata.dates      # ('1969', '1961')
r.metadata.amounts    # ()
r.metadata.urls       # ()
```

`r.stats` holds 8 entries on this input — dates, durations:

```
date: 1969
date: 1969
duration: 19 minutes
duration: 21 hours
duration: 36 minutes
date: 1969
...
```

Each `Stat` has `value`, `unit`, `phrase` (the ±25-char context), and `context_sentence` (the full source sentence). Add more attachments as you need them:

```python
r = summarize(text, max_length=400, attach=[
    "stats", "outline", "metadata", "phrases", "correlated_facts",
])
```

Each new attachment costs <1 ms. The full set runs in ~2-4 ms p50 across the [10-corpus benchmark](../benchmarks/quality/matrix-2026-04-26.md).

**🦀 Rust:** `summarize_with_attach(text, max_length, mode, &AttachOpts { stats: true, outline: true, ... })`.

## Lesson 6 — produce a paste-ready brief

`brief()` composes summarize + key_facts + toc into one artifact. Three output formats:

```python
from lede import brief

print(brief(text, format="markdown"))
```

> ## Overview
>
> The Apollo 11 mission landed humans on the Moon for the first time. The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.
>
> ## Key facts
>
> - Four days later, Armstrong and Aldrin descended to the lunar surface in the Eagle lunar module while Collins remained in lunar orbit aboard the Columbia command module.
> - The astronauts spent 21 hours and 36 minutes on the lunar surface, collecting 21.5 kilograms of lunar material before returning to Columbia.
> - The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.

Other formats: `format="string"` (plain-text with `Overview:` / `Key facts:` labels) and `format="dict"` (structured Python dict for programmatic use).

**🦀 Rust:** `lede::brief(text)` for the default; `lede::brief_with_options(text, BriefOptions { format: BriefFormat::Markdown, .. })` to pick a format.

## Lesson 7 — call any primitive standalone

If you only want the section names, the dates, or the key facts — skip `summarize` and call the primitive directly.

```python
from lede.extract import toc, phrases, key_facts, stats, metadata

toc(text)            # ('section names',)  — empty for this Apollo paragraph (no headings)
phrases(text)        # ('lunar surface',)  — repeated multi-word n-grams
key_facts(text, max_facts=3)
# (
#   'The astronauts spent 21 hours and 36 minutes on the lunar surface, collecting 21.5 kilograms of lunar material before returning to Columbia.',
#   "The mission splashed down in the Pacific Ocean on July 24, 1969, completing an 8-day journey that fulfilled President Kennedy's 1961 goal of landing a man on the Moon and returning him safely to Earth before the decade ended.",
# )
```

Each primitive lives at `lede.extract.<name>` and works on its own — useful when you only need one piece per chunk.

**🦀 Rust:** `lede::extract::stats::stats(text)`, `lede::extract::outline::toc(text)`, etc.

## Lesson 8 — clean text and strip reasoning blocks

Two utilities for prepping input before it hits an LLM (or after, if the LLM is a reasoning model that emitted `<think>` blocks).

```python
from lede import clean_text, strip_think

clean_text("**Bold** _italic_ — see the attached. Just wanted to follow up. Revenue grew 23% in Q3.")
# 'bold italic — see the attached. follow up. revenue grew 23% in q3.'
```

`clean_text` strips markdown, filler words, filler phrases, and CRM boilerplate; lowercases and normalizes whitespace.

```python
strip_think("<think>internal reasoning here</think>The visible answer.")
# 'The visible answer.'
```

`strip_think` removes `<think>…</think>` blocks (Qwen3, DeepSeek-R1, etc.) and trims surrounding whitespace.

**🦀 Rust:** `lede::clean_text(text)` and `lede::strip_think(text)` — same names, same bytes.

## Lesson 9 — features that work on Python only

Some extras don't have a Rust equivalent in lede (yet). The decision whether to add a Rust port is documented per feature in [`docs/REFERENCE.md` § Runtime parity](REFERENCE.md#runtime-parity).

### `[wordforms]` — spelled-out numbers

```bash
pip install "lede[wordforms]"
```

```python
stats("Five thousand documents reviewed in eight days.", convert_word_names=True)
# (Stat(value='Five thousand', unit='documents', stat_type='count', ...),
#  Stat(value='eight days', unit='day', stat_type='duration', ...))
```

**🦀 Rust:** has parity. Build with `--features wordforms`. Both Python's `[wordforms]` extra and Rust's `wordforms` cargo feature bind to the same `text2num` crate, so output is byte-identical.

### `[textrank]` — graph-based summarizer

```bash
pip install "lede[textrank]"
```

```python
from lede.textrank import summarize_textrank
summarize_textrank(text, num_sentences=3)
```

**🦀 Rust: not available.** A pure-Rust port (using `petgraph`'s built-in PageRank or a 100-line power-iteration impl) is feasible — the `pagerank` and `petgraph` crates exist — but it hasn't been added because the regex backend is the parity contract, and graph algorithms in Rust pull non-trivial transitive deps. If you want this in Rust, file an issue tagged `rust-feature-parity` and we'll discuss a `textrank` cargo feature.

### `[yake]` — statistical key-phrase extractor

```bash
pip install "lede[yake]"
```

```python
phrases(text, backend="yake")
```

**🦀 Rust: not available.** No mature Rust port of the YAKE algorithm exists today. A port is feasible — the algorithm is statistical, not ML-based — but it's non-trivial work and lede's regex `phrases()` already covers the most common case (repeated multi-word n-grams). Open an issue if you'd consume a Rust YAKE.

### spaCy NER — named-entity extraction

```bash
pip install lede-spacy
python -m spacy download en_core_web_sm
```

```python
import lede_spacy  # registers backends as a side effect
from lede.extract import metadata
m = metadata("Acme Corp signed with lede Labs in San Francisco.", backend="spacy")
m.entities  # ('Acme Corp', 'lede Labs', 'San Francisco')
```

**🦀 Rust: not available, by design.** Pure-Rust transformer NER requires shipping model weights and a heavy ML runtime (`rust-bert` is ONNX/torch-backed; `tch-rs` ports PyTorch). Both contradict lede's "stdlib + regex only" Rust contract. The Rust port returns `Metadata.entities` as an empty `Vec` under the regex backend, by design. Callers who need NER from a Rust service should call out to a separate NER service (Python lede-spacy, or a hosted NER endpoint).

## What to read next

- [`docs/REFERENCE.md`](REFERENCE.md) — full primitive catalog with type signatures.
- [`docs/comparison.md`](comparison.md) — lede vs Sumy vs LLM API with worked examples and timings.
- [`docs/integration-memo.md`](integration-memo.md) — how lede fits into a larger RAG pipeline (chunkshop integration design).
- [`docs/v0-2-design.md`](v0-2-design.md) — design contract: SC-A through SC-F acceptance tests.
- [`examples/`](../examples/) — runnable scripts mirroring most of these lessons.
