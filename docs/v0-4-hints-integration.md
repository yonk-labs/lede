# lede v0.4 — hint-biased extraction (integration guide)

**Audience:** AI copilots, downstream agents, and humans integrating `lede` into another project.

**TL;DR:** Pass `hints=` to lede's ranking primitives to bias selection toward specific terms or phrases — useful for question-answering, targeted summarization, and "find the parts about X" use cases. Backward-compatible (no hints = same bytes as v0.3.0). Byte-identical Python ↔ Rust on the regex backend. Optional `lede-spacy` companion adds lemma / WordNet synonym / spaCy vector expansion.

This doc is the one-page integration brief. Deep references: `docs/REFERENCE.md` (full API contract), `docs/superpowers/specs/2026-05-21-hints-design.md` (design rationale), `docs/comparison.md` (versus Sumy and LLMs).

---

## 1. What `lede` is in one paragraph

`lede` is a deterministic extractive summarization library — Python and Rust, byte-identical on the regex backend. It picks the highest-signal sentences from a document using TF-IDF + position + length + a few defensive heuristics. No LLM calls in the core. Zero required runtime dependencies. Designed to be the unsexy infrastructure layer that runs before an LLM ever sees the text, so the LLM gets a 500-character lede instead of a 50,000-character document.

## 2. What v0.4 adds

The five ranking primitives plus a new sixth one all accept three optional kwargs that bias their output toward user-specified terms:

```python
summarize(text, hints=["John Smith", "county"], hint_focus=0.7, hint_mode="soft")
brief(text, hints=...)
extract.key_facts(text, hints=...)
extract.phrases(text, hints=...)
extract.correlate_facts(text, hints=...)
extract.top_terms(text, hints=...)       # NEW in v0.4
```

`hints` is a list of strings or a dict of `{term: weight}`. Phrases are matched as contiguous word-boundary sequences (case-insensitive). When `hints=None` (the default), every primitive's output is byte-identical to v0.3.0 — no caller is ever forced to change anything.

## 3. Install

```bash
pip install lede                          # core, zero deps
pip install "lede[wordforms]"             # +spelled-out numbers ("eight days")
pip install lede-spacy                    # +NER + lemma/similar expansion via spaCy
pip install "lede-spacy[synonyms]"        # +WordNet synonym expansion via nltk
```

Rust:

```toml
[dependencies]
lede = "0.4"          # zero non-stdlib deps except `regex`
```

## 4. Quickstart — the 80% case

```python
from lede import summarize

text = open("doc.txt").read()

# Backward-compatible — same as v0.3.0:
print(summarize(text).summary)

# Bias toward sentences mentioning John Smith and "county":
print(summarize(
    text,
    hints=["John Smith", "county"],
    hint_focus=0.7,        # 0.0=ignore, 1.0=all-hints, default 0.7
    hint_mode="soft",      # "soft" biases ranking; "hard" filters
).summary)
```

That's the whole feature for most callers. The rest of this doc is the cookbook.

## 5. Five worked examples

### 5.1 "Which county does John Smith live in?" — hard filter

```python
from lede import summarize

result = summarize(
    text,
    hints=["John Smith"],
    hint_focus=1.0,
    hint_mode="hard",     # only sentences mentioning John Smith are eligible
).summary
# → "John Smith lives in Cook County and runs a small business."
```

`hint_mode="hard"` + `hint_focus=1.0` is the filter combo. Use it when you want only hint-bearing content (drops the rest entirely). If no sentence matches any hint, the output is a truncation fallback (never empty if the input wasn't empty).

### 5.2 "Mostly about networking, but keep some breadth" — soft mix

```python
result = summarize(
    text,
    hints=["networking", "tcp", "packet"],
    hint_focus=0.7,        # ~70% of the char budget biased toward hints
    hint_mode="soft",      # bonus on top of normal scoring; no filter
).summary
```

The two-pool selector spends 70% of `max_length` on hint-biased ranking and 30% on the normal composite — so you get focused content with a sanity tail of context.

### 5.3 Per-hint weights — emphasize one term over others

```python
result = summarize(
    text,
    hints={
        "John Smith":  2.0,   # weighted 2x
        "county":      1.0,
        "tax":         0.5,
    },
    hint_focus=0.7,
).summary
```

Dict input maps `term → weight`. The hint bonus formula is `min(count, 3) * weight * 0.5` per sentence — so heavier weights pull harder. Cap-at-3 prevents spammy sentences from running away with the ranking.

### 5.4 Key facts about a specific person

```python
from lede.extract import key_facts

facts = key_facts(
    text,
    max_facts=10,
    hints=["John Smith"],
    hint_focus=0.5,        # half the facts MUST mention John Smith, half are top-rated overall
    hint_mode="hard",
)
for f in facts:
    print(f"  - {f}")
```

For count-budgeted primitives (`key_facts`, `top_terms`), `hint_focus` is a count split. `hint_focus=0.5` with `max_facts=10` means up to 5 hint-bearing facts plus up to 5 from the normal ranking, deduped.

### 5.5 Top salient terms — new primitive in v0.4

```python
from lede.extract import top_terms

terms = top_terms(text, n=10)
# → ('john smith', 'cook county', 'council', 'meeting', 'taxes', ...)
```

`top_terms` combines single-word TF-IDF with multi-word phrase frequency into a unified ranked list. Use `kinds=("words",)` or `kinds=("phrases",)` to restrict. Accepts the same hint kwargs as the other primitives. Python-only in v0.4; Rust mirror lands in v0.5.

## 6. Optional: expand hints with lemmas, synonyms, or similar words

If you also install `lede-spacy`, you get an expansion helper:

```python
from lede import summarize
from lede_spacy import expand_hints

# Lemma: "counties" → ["counties", "county"], "running" → ["running", "run"]
hints = expand_hints(["counties"], kinds=("lemma",))

# Synonyms via WordNet (needs lede-spacy[synonyms]):
hints = expand_hints(["car"], kinds=("synonyms",), top_k=5)
# → ["car", "auto", "automobile", "machine", "motorcar"]

# Combine both:
hints = expand_hints(
    {"car": 2.0},                      # dict input, dict output
    kinds=("lemma", "synonyms"),
    top_k=3,
    expand_weight=0.5,                 # expansion terms at half the original weight
)

result = summarize(text, hints=hints, hint_focus=0.7).summary
```

`lede-spacy.expand_hints()` is Python-only by design. The lede Rust crate has no equivalent — Rust callers either expand hints themselves or pass literal strings.

## 7. Hint argument shape reference

| Arg | Shape | Default | Meaning |
|---|---|---|---|
| `hints` | `list[str]` or `dict[str, float]` or `None` | `None` | Terms/phrases to bias toward. None → no change vs v0.3.0. |
| `hint_focus` | `float` in `[0.0, 1.0]` | `0.7` | Budget split. 0=ignore, 0.5=half, 1.0=only hint pool. Validated even when no behavioral effect (`phrases`, `correlate_facts`). |
| `hint_mode` | `"soft"` or `"hard"` | `"soft"` | Soft: bonus on ranking, no guarantee. Hard: filter (only hint-matching items eligible). |

**Matching rules:**
- Case-insensitive (`str.lower()` on both sides).
- Word-boundary (`\b...\b`) — `"smith"` does NOT match `"blacksmith"` or `"smiths"`.
- Multi-word hints are contiguous — `"John Smith"` matches `"John Smith Sr."` but NOT `"John P. Smith"`.
- No Unicode normalization — `"café"` does not match `"cafe"`. Pre-normalize the input if you need this.
- No stemming — use `lede_spacy.expand_hints(kinds=("lemma",))` for that.

**Validation errors:**
- `mode="legacy"` with non-None `hints` → `ValueError("hints not supported in legacy mode")`
- `hint_focus` outside `[0.0, 1.0]` → `ValueError`
- `hint_mode` not in `{"soft", "hard"}` → `ValueError`
- `hints=[]` or all-whitespace strings → treated as `None` (silent, no error)

## 8. Per-primitive specifics

| Primitive | Match target | Budget unit | `hint_focus` effect |
|---|---|---|---|
| `summarize` | sentence | chars (`max_length`) | budget split |
| `brief` | passthrough | (forwards to internal calls) | budget split |
| `extract.key_facts` | sentence | count (`max_facts`) | count split, dedup preserved across pools |
| `extract.phrases` | the phrase string itself | (uncapped) | accepted but no behavioral effect — use `hint_mode` to control |
| `extract.correlate_facts` | OR of entity name AND fact value | (uncapped) | same as `phrases` |
| `extract.top_terms` | word OR phrase string | count (`n`) | count split |

`outline`, `toc`, `stats`, `metadata` do **not** accept hint kwargs — they're descriptive, not ranking.

## 9. Backward compatibility

When `hints` is `None` (the default), the no-hints code path is byte-identical to v0.3.0. Verified by:
- Every existing test in the v0.1 + v0.2 suite passes unchanged.
- The v0.1 + v0.2 fixture walkers (which enforce Python ↔ Rust byte-identical output across 100s of fixtures) remain green.

You can drop v0.4 into any v0.3.x deployment with zero behavioral change. Then opt into hints incrementally.

## 10. Cross-runtime parity

The Python and Rust core produce **byte-identical output** on the same `(text, hints, hint_focus, hint_mode)` inputs. Enforced by the `v0_4_hints_byte_identical` fixture walker covering 140 fixtures (10 corpora × 14 hint configurations).

**Not parity-promised:**
- `phrases(backend="yake")` with hints — yake is an opt-in Python-only extra.
- `correlate_facts(backend="spacy")` with hints — spaCy backend is Python-only.
- `lede_spacy.expand_hints()` — Python-only by policy.

If you need byte-identical output, stick to the default (`regex`) backend on both runtimes.

## 11. Composition with LLMs (the intended use case)

```python
from lede import summarize
from lede_spacy import expand_hints

# Step 1: caller has a question — "what county does John Smith live in?"
# Extract noun-ish terms from the question and expand them.
question = "What county does John Smith live in?"
hints = expand_hints(
    ["John Smith", "county"],
    kinds=("lemma", "synonyms"),
)

# Step 2: bias lede's extraction toward those terms — gets the right
# sentences out of a 50KB document in ~10ms, deterministic, no API call.
lede_chunk = summarize(
    doc_text,
    max_length=2000,
    hints=hints,
    hint_focus=0.8,
    hint_mode="soft",
).summary

# Step 3: hand the chunk to your LLM with the original question.
# The LLM sees ~2KB of relevant context instead of 50KB.
llm_answer = llm.chat(
    prompt=f"Question: {question}\n\nContext:\n{lede_chunk}\n\nAnswer:",
)
```

This is the v0.4 design intent: lede pre-filters; the LLM reasons. The deterministic chunk means the LLM's behavior is reproducible across runs, and you save 25x on input tokens.

## 12. Examples in the repo

- `examples/08_hints.py` — every hint mode demonstrated on a council-minutes document
- `examples/09_top_terms.py` — the new `top_terms` primitive
- `examples/01_quickstart.py` ... `07_wordforms_numbers.py` — backward-compatible, all still run

Run any of them: `python examples/<file>.py`.

## 13. Where to dig deeper

- **API contract** → `docs/REFERENCE.md` — every signature, every error, every kwarg.
- **Design rationale** → `docs/superpowers/specs/2026-05-21-hints-design.md` — why these choices over alternatives.
- **Comparison to other tools** → `docs/comparison.md` — lede + hints vs Sumy vs LLMs with worked examples.
- **lede-spacy integration** → `docs/lede-spacy-integration.md` — `expand_hints` deep-dive.
- **Changelog** → `CHANGELOG.md` — every change in v0.4 with rationale.

## 14. When NOT to use hints

- **Generic summarization** (you don't know what's interesting): use plain `summarize(text)`. Hints add complexity for no benefit.
- **Open-ended natural language questions** ("explain the cultural impact of this"): hints won't help; you need an LLM.
- **Fuzzy matching** ("anything semantically similar to 'tax'"): hints are literal-match; use `lede_spacy.expand_hints(kinds=("synonyms","similar"))` first to widen the net.
- **Cross-document retrieval** (BM25/RAG style): lede is per-document. Use a vector store for the retrieval step; lede for the summarize step after retrieval.

---

**Version:** v0.4.0
**License:** Apache-2.0
**Repo:** https://github.com/yonk-labs/lede

Pass this doc to any agent or developer who needs to integrate lede v0.4 — it's intentionally self-contained.
