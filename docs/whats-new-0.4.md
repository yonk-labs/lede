# What's New in lede 0.4.0 → 0.4.2

`lede` is a **deterministic, zero-dependency extractive summarizer** (Python
stdlib + a byte-identical Rust mirror). No LLM calls, no network, same input →
same bytes on every runtime. The 0.4.x line added three composable
capabilities on top of the core `summarize` / `extract.*` API, all **opt-in
and backward-compatible** — omit the new kwargs and output is byte-identical to
0.3.0.

For the full public API contract see [`REFERENCE.md`](REFERENCE.md). For the
hint-integration deep dive see
[`v0-4-hints-integration.md`](v0-4-hints-integration.md).

## Install

```bash
pip install "lede==0.4.2"                 # core, zero-dep
pip install "lede-spacy==0.4.2"           # optional spaCy companion (hint expansion)
pip install "lede-spacy[synonyms]==0.4.2" # adds WordNet/nltk for synonym expansion
# Rust: lede = "0.4.2" on crates.io
```

## The three pillars

1. **0.4.0 — Hint-biased extraction**: steer selection toward terms you care about.
2. **0.4.1 — Scored `top_terms`**: get salient words/phrases *with* relevance scores.
3. **0.4.2 — Heading & pin retention**: force document structure (titles, headings, captions) to survive extraction.

---

## 1. Hint-biased extraction (0.4.0)

**What it does:** Bias which sentences/facts/phrases come out toward terms you
supply. Turns a generic topical summary into a query-focused one.

**Where:** `hints`, `hint_focus`, `hint_mode` kwargs on `summarize`, `brief`,
`extract.key_facts`, `extract.phrases`, `extract.correlate_facts`,
`extract.top_terms`.

- `hints: list[str] | dict[str, float]` — terms to bias toward (list → weight
  1.0; dict → weighted). Matching is case-insensitive, word-boundary-delimited;
  no stemming.
- `hint_focus: float = 0.7` — fraction of the selection budget reserved for
  hint-matching candidates (chars for `summarize`, count for `key_facts`).
- `hint_mode: "soft" | "hard"` — `soft` (default) adds a bonus and reorders
  without excluding non-matches; `hard` restricts the pool to matching
  candidates only.

```python
from lede import summarize

text = open("case_file.txt").read()

# "What county does John Smith live in?" — bias toward those terms.
r = summarize(text, hints=["John Smith", "county"], hint_focus=0.7)
print(r.summary)   # sentences mentioning Smith/county float to the top

# Weighted + hard mode: only sentences that match a hint are eligible.
r = summarize(text, hints={"john smith": 2.0, "county": 1.0}, hint_mode="hard")
```

**Use cases:** query-focused summaries, RAG chunk summaries steered by the
user's question, pulling the relevant facts out of a long document,
entity-centric digests.

**Optional hint expansion (lede-spacy):** expand a hint into
morphological/semantic variants *before* passing it to lede (lede core stays
zero-dep; expansion is composed by the caller):

```python
from lede import summarize
from lede_spacy import expand_hints

terms = expand_hints(["counties"], kinds=("lemma",))      # -> ["counties", "county"]
r = summarize(text, hints=terms, hint_focus=0.7)
```

Three strategies: `"lemma"` (any spaCy model), `"synonyms"` (WordNet, needs
`lede-spacy[synonyms]`), `"similar"` (word-vectors, needs
`en_core_web_md`/`_lg`). Precision ordering: **lemma = safest, synonyms =
sense-ambiguous, similar = most aggressive/noisiest** (md is noisy; lg is
better).

---

## 2. Scored `top_terms` (0.4.1)

**What it does:** Returns the most salient words and phrases in one unified
ranking — optionally with the relevance score and word/phrase label, in a
single call.

**API:** `extract.top_terms(text, *, n=10, kinds=("words", "phrases"),
with_scores=False, hints=..., hint_focus=..., hint_mode=...)`

- `with_scores=False` (default) → `tuple[str, ...]` (byte-identical to 0.4.0).
- `with_scores=True` → `tuple[TermScore, ...]`, where `TermScore` is a
  `NamedTuple(term, score, kind)`.

```python
from lede.extract import top_terms

# Plain ranked terms
top_terms(text, n=5)
# -> ('revenue', 'q3 earnings', 'margin', 'guidance', 'supply chain')

# With scores + kind
for term, score, kind in top_terms(text, n=5, with_scores=True):
    print(f"{score:.3f}  {kind:6}  {term}")
# 1.000  word    revenue
# 0.812  phrase  q3 earnings
# ...
```

**Important:** scores are normalized **within each kind independently** — a
word at `1.0` and a phrase at `1.0` are each top-of-their-kind, *not* equal on a
shared scale. Treat as per-kind salience, not a global composite.

**Use cases:** tag/keyword extraction, building facets or filters, feeding a
ranked term list to a downstream ranker, deciding which terms to turn into
hints.

> Note: `top_terms` is **Python-only** in 0.4.x; the Rust mirror is deferred to
> 0.5.

---

## 3. Heading & pin retention (0.4.2)

**The problem it solves:** lede is extractive, so headings, titles, and
captions normally get compressed *out* of the summary — even though they're
often the most load-bearing lines (a section heading frames every fact under
it). 0.4.2 lets you force them back in.

**API:** three default-off kwargs on `summarize`, plus a new result field.

- `keep_headings: bool = False` — auto-detects structural headings and weaves
  them into the output: the **document title** (the first structural heading at
  the start — any style, not just Markdown) is pinned at the top; each selected
  sentence's **nearest enclosing heading** is re-inserted above it, in document
  order, deduped. *Detection is best-effort — see the caveat below.*
- `include_toc: bool = False` — prepends a full table of contents (indented by
  depth).
- `pin: Sequence[str] | None = None` — caller-supplied lines forced **verbatim**
  into the output.
- `SummaryResult.pinned_headings: tuple[str, ...]` — the auto-detected headings
  that were injected (empty otherwise; `pin` lines and TOC are not listed here).

**Layout & budget rules:**

- Output order: **`pin` block → TOC block → body** (with title + interleaved
  headings).
- Pinned content is **additive** — it does *not* consume `max_length`; the
  budget governs only the extractive body, so pins are guaranteed to survive
  (output may exceed `max_length` by the pinned chars).
- Works in `default` and `coverage` modes and **composes with `hints`**;
  rejected in `legacy` mode (`ValueError`).
- Default-off → byte-identical to 0.4.1.

```python
from lede import summarize

doc = """# Quarterly Review

## Revenue
The company posted record revenue of $12M in Q3. Revenue grew 18% YoY.

## Risks
Supply chain risk remains elevated heading into Q4.
"""

# Headings woven into the extractive body
r = summarize(doc, max_length=300, keep_headings=True)
print(r.summary)
# # Quarterly Review
# ## Revenue
# The company posted record revenue of $12M in Q3. Revenue grew 18% YoY.
# ## Risks
# Supply chain risk remains elevated heading into Q4.
print(r.pinned_headings)
# ('# Quarterly Review', '## Revenue', '## Risks')

# Force a specific caption to survive, verbatim
r = summarize(doc, max_length=300, pin=["Figure 3: Q3 revenue by region"])
# -> "Figure 3: Q3 revenue by region\n\n<body>"

# Title + headings + a prepended TOC, biased toward "revenue"
r = summarize(doc, max_length=300, keep_headings=True, include_toc=True, hints=["revenue"])
```

### Heading detection is best-effort (important caveat)

`keep_headings` / `include_toc` use lede's structural heading detector, which is
**convention-bound, not a general parser**. It reliably catches Markdown `#`
lines, ALL-CAPS lines, simple Title-Case lines, `N. Name` numbering, and
trailing-colon labels. It **misses** headings with mid-line punctuation
(`Results & Discussion`, `Cost-Benefit Analysis`, `Section 2: Scope`),
dotted-decimal/roman numbering (`1.2 Scope`, `IV. Methods`), lowercase starts
(`iOS Integration`), setext underlines (`====`), and many domain-specific
caption-style headings.

> Real-world example: on a corpus of SCOTUS opinions (caption-style headings),
> `lede.toc()` returned empty for every document — the auto-detector simply
> doesn't recognize those headings.

A missed heading is treated as ordinary body text: it won't be pinned or
positioned, and sentences beneath it may be grouped under the previous detected
heading. **When auto-detection fails, or when you already know the heading text
(e.g. it lives in chunk metadata), use `pin=[…]`** — it forces exact lines in
verbatim, independent of detection. This is the robust path for non-Markdown
sources.

**Use cases:** RAG retrieval where the chunk heading/caption is the key signal
(the originating use case — prepending the deduped heading to the summary
lifted fact retention ~0.36 → 0.72 in testing); doc-structure-preserving
previews; summaries that need a title or section context to be intelligible;
pinning a known label (figure caption, ticket ID, doc title) that must never be
dropped.

---

## lede-spacy `similar` fix (shipped in 0.4.2)

`expand_hints(kinds=("similar",))` previously **always crashed** (it hardcoded
`en_core_web_sm`, which has no word vectors). Now `_nlp()` is model-selectable
(cache keyed by model), loading a vector-capable model for the `similar` kind
while keeping `sm` the default for everything else. Override via
`LEDE_SPACY_VECTOR_MODEL` (default `en_core_web_md`).

```python
from lede_spacy import expand_hints
expand_hints(["king"], kinds=("similar",), top_k=5)   # now returns neighbors instead of raising
```

(Caveat: vector-neighbor quality on `en_core_web_md` is noisy; `en_core_web_lg`
is recommended if you lean on `similar`.)

---

## Cross-cutting guarantees

- **Backward compatible:** omit every new kwarg → byte-identical to the prior
  version. Verified by fixture walkers.
- **Python ↔ Rust byte-identical:** `summarize` with hints (0.4.0) and with
  heading/pin (0.4.2) are enforced by parity fixtures in CI (`v0_4_hints`,
  `v0_4_2_pins`). *(Exception: `top_terms` / `with_scores` is Python-only until
  0.5.)*
- **Deterministic:** no randomness, no hash-iteration-order or locale
  dependence.
- **Composable:** hints + `keep_headings` + `pin` + `include_toc` all stack in
  one `summarize` call.

**One-line mental model:** `hints` steer *what* gets selected,
`keep_headings`/`pin`/`include_toc` guarantee *structure* survives selection,
and `top_terms(with_scores=True)` tells you *which terms matter* (and what to
feed back in as hints).
