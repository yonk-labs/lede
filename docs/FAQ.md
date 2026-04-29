# lede FAQ

Common questions about how lede picks sentences, what's tunable, and
when to use something else. For type signatures and the full primitive
catalog, see [`REFERENCE.md`](REFERENCE.md). For worked side-by-side
comparisons against Sumy and LLM APIs, see
[`comparison.md`](comparison.md).

---

## What are "the most important sentences"? How does scoring work?

Each sentence gets a composite score:

```
score = 0.60 × tfidf  +  0.25 × position  +  0.15 × length
```

All three components are normalized to `[0, 1]` per document. The
constants live in `src/lede/tfidf.py` — read them, change them, fork
them.

- **TF-IDF** rewards sentences whose terms are frequent in *this*
  sentence but rare across the rest of the document. Topic specificity.
  Stopwords are pre-filtered (a 43-word list, deliberately small to keep
  the cross-language fixture corpus manageable).
- **Position** uses a U-shape: first and last sentences score 1.0, the
  middle scores 0. This is the "don't bury the lede" prior — journalism
  structure puts the thesis first and the recap last. Same prior every
  classical extractive summarizer since Edmundson (1969) has used.
- **Length** plateaus at 10–30 words. Shorter sentences get penalized
  linearly (fragments rarely carry complete facts); longer ones decay to
  0 by 80 words (run-on lists embed poorly).

Selection is greedy knapsack: sort sentences by score descending, walk
the list adding sentences that fit the `max_length` character budget,
then re-sort the selected indices into original document order before
joining. Ties break by original position — stable and deterministic.

`mode="default"` adds four heuristics on top:

1. **Heading filter** — section titles get `score = -inf` and drop out
   of selection.
2. **Cue-phrase boost** — sentences starting with `held:`,
   `resolution:`, `decision:`, `finding:`, `key takeaway:`, `outcome:`,
   `ruling:`, `in summary`, `conclusion`, or `action item` get `+2.0`.
   Humans tag the important sentences; the scorer reads the tags.
3. **Digit bonus** — sentences containing a digit get `+0.3`. RAG-prep
   heuristic: numeric facts are usually the ones downstream callers want
   preserved.
4. **Section boost** — sentences under headings like `discussion`,
   `conclusion`, `held`, `resolution`, `key findings`, `summary`, or
   `decision` get `tfidf × 1.3`.

That's it. No model, no embeddings, no random tie-breaking.

## Can I tune what gets extracted?

Yes, at four levels — runtime kwargs, mode selection, source constants,
and pre/post-processing.

**Volume — how much to keep:**

```python
summarize(text, max_length=200)    # ~one sentence; headline-level
summarize(text, max_length=500)    # default; 2–3 sentences
summarize(text, max_length=2000)   # paragraph-level
```

Roughly linear: doubling the budget roughly doubles the number of
selected sentences. Output is always direct quotes; never paraphrased
compression.

**Mode — different extraction philosophy:**

```python
summarize(text, mode="default")    # v0.2 scorer with the four heuristics
summarize(text, mode="legacy")     # pure 60/25/15, no tweaks (v0.0.1 frozen)
summarize(text, mode="coverage")   # paragraph-aware sampling
```

Use `coverage` when documents don't follow journalistic structure —
academic papers with conclusions in section 4, chronological narratives,
technical reports. It guarantees per-section representation rather than
rewarding lead-and-recap.

**Query-driven mode — relevance instead of importance:**

```python
from lede import extract_keyword
extract_keyword(text, "pricing budget competitor", num_sentences=3)
```

Different question, different entry point. Instead of "what's the most
important?", this answers "what's most relevant to *these* keywords?"
Useful for search-augmented retrieval.

**Source-level constants — fork-and-edit territory:**

| Constant | Default | When to change |
|---|---|---|
| `_TFIDF_WEIGHT / _POSITION_WEIGHT / _LENGTH_WEIGHT` | `0.60 / 0.25 / 0.15` | Documents where position is unreliable (academic papers): drop position weight, raise TF-IDF |
| `_CUE_PHRASE_RE` | 10 cue tokens | Domain-specific tags: add `chief complaint:`, `assessment:`, `plan:` for clinical notes |
| `_SECTION_BOOST_HEADINGS` | 7 section names | Add `risks`, `mitigation`, `compliance` for security reports |
| `_STOPWORDS` | 43 words | Cross-language deployments may want a smaller or differently-curated set |
| `_TOKEN_RE` | `\b[a-z]{3,}\b` | Non-Latin scripts need a different tokenizer regex |

Forking these doesn't break the parity contract — as long as you mirror
the same constants on the Rust side, the fixture walker catches drift
on every CI push.

**Pre-processing — clean the input before scoring:**

```python
clean_text(text)         # strip markdown, CRM boilerplate, signature blocks
strip_think(raw_llm)     # remove <think>...</think> blocks from reasoning-model output
```

Both run in microseconds. Useful when the input is dirty (forwarded
emails, marked-up wiki dumps, reasoning-model traces) and you don't
want the noise contributing to TF-IDF.

## Can I extract structured facts alongside the summary?

Yes. The `attach=` kwarg returns enrichments without changing the
summary text:

```python
summarize(text, max_length=500, attach=["stats", "outline", "metadata", "phrases", "correlated_facts"])
```

Sub-5 ms with all five attached. Each adds a structured field to
`SummaryResult`:

| Attachment | What you get |
|---|---|
| `stats` | Numeric facts with sentence context (`Stat(value="$2.4M", unit="USD", stat_type="amount", ...)`) |
| `outline` | Section headings + the highest-scoring sentence per section |
| `metadata` | Dates, amounts, URLs, entities (entities populated only with the spaCy backend) |
| `phrases` | Repeated multi-word phrases |
| `correlated_facts` | Entity↔number pairs with polarity |

This is where lede stops being "just a summarizer" and becomes a
RAG-prep primitive — one call returns the focused summary to embed
*plus* the metadata-column fields you'd otherwise grep out yourself.

## What does "deterministic" actually buy me?

Four properties that matter for production and audit:

1. **Snapshot tests don't drift.** Same input → same bytes, every run,
   every version, every machine. Pin a behavior to a commit hash and
   regression-test against it.
2. **Diff-based code review works.** When the scorer changes, the diff
   in extracted output is a finite, reviewable thing.
3. **Audit trails are honest.** "This sentence was selected because
   TF-IDF was 0.82, position was 0.6, length was 1.0, plus the digit
   bonus" is a defensible answer. "The model decided" is not.
4. **Cross-runtime parity.** Python and Rust produce byte-identical
   output for every fixture in the corpus. Same summarizer in your data
   tier and your service tier — not two implementations that "should
   match."

If determinism doesn't matter to your use case, an LLM probably gives
better quality. lede is for the workloads where it does.

## How do I audit a specific sentence selection?

Per-sentence component scores are introspectable. Nothing is hidden:

```python
from lede.tfidf import _composite_score_default, _build_section_map
from lede.sentences import split_sentences

sents = split_sentences(text)
scores = _composite_score_default(sents, _build_section_map(sents))
for s, score in zip(sents, scores):
    print(f"{score:7.3f}  {s[:80]}")
```

The output ranks every candidate sentence with its score. If a reviewer
disputes a selection, the trail is open: read 400 lines of source, look
at the score, identify which signal won. Compare to the LLM equivalent,
where the answer is essentially "the model decided."

## When is this the wrong tool?

Three categories.

**You need abstractive compression.** lede only deletes; it never
rewrites. If reviewers want synonyms collapsed, redundant phrasing
removed, or prose paraphrased for brevity, you need an LLM downstream.

**You need semantic understanding.** "Revenue grew 23%" and "Sales
rose nearly a quarter" describe the same fact in different words; lede
sees no connection. If domain language and synonym handling matter
more than determinism — medical-term normalization where "MI" and
"myocardial infarction" need to map together, for instance — you need
NLP that understands meaning. The companion `lede-spacy` partially
helps for entity↔number relationships via dependency parsing, but the
core scorer is sentence-local.

**You need cross-document or temporal reasoning.** TF-IDF is computed
within a single input. Questions like "how did revenue change across
these 12 quarterly reports?" are not what extractive summarization
answers.

For those workloads, use an LLM. lede is meant to sit *in front of*
the LLM call — strip boilerplate, surface candidate sentences, attach
structured facts, then hand a smaller prompt to the model. It's a
preprocessor, not a competitor.

## Why extractive instead of LLM summarization?

Both are useful. They're not competing for the same job.

LLM summarization wins on quality. It can paraphrase, collapse
synonyms, restructure ideas, and produce something more readable than
what was actually written. It also takes 500–5000 ms, costs money per
call, returns different bytes every time you call it, and has no
provenance trail you can defend in audit.

Extractive summarization wins on cost, latency, determinism, and
provenance. lede produces output in 0.4 ms on the Python core path,
0.13 ms in Rust. Same bytes today, same bytes in a year. Every
sentence in the output appears verbatim in the source — never
hallucinated, never paraphrased, never made up.

The right answer is usually both: lede in front of the LLM call as a
preprocessor that cuts input tokens 40–94%, then the LLM does the
final synthesis. See [`comparison.md`](comparison.md) for measured
side-by-side timings.

## How does this compare to Sumy, LexRank, TextRank?

Sumy is the closest comparison — same family of classical extractive
algorithms. It ships LSA, LexRank, TextRank, Luhn, Edmundson, and
KL-Sum as a Python catalog.

| | lede | Sumy |
|---|---|---|
| Latency (10-corpus p50) | 0.42 ms | 11–12 ms |
| Runtimes | Python + Rust, byte-identical | Python only |
| Default deps | stdlib only | nltk + numpy |
| Algorithms | TF-IDF + position + length | LSA, LexRank, TextRank, Luhn, Edmundson, KL-Sum |
| Structured enrichments | Yes — stats / outline / metadata / phrases | No — summary text only |

Use Sumy when you want a specific classical algorithm (LSA, KL-Sum)
and Python is fine. Use lede when you want sub-millisecond latency,
Python ↔ Rust parity, structured enrichments in the same call, or zero
required dependencies.

LexRank and TextRank as algorithms are graph-based — they build a
sentence-similarity graph and run eigenvector centrality (LexRank) or
PageRank (TextRank). Higher quality on some inputs, more dependencies,
harder to audit ("why did this sentence get high centrality?" requires
inspecting the full graph). lede's TF-IDF + position + length is
simpler to defend.

For pathological inputs and worked examples, see
[`comparison.md`](comparison.md).

## Why isn't named-entity recognition built in?

Two reasons, both deliberate.

**The dependency cost.** Real NER means shipping ~50 MB of model
weights (spaCy's `en_core_web_sm`) and pulling NumPy / Cython / blis /
thinc into the dependency graph. That breaks lede's zero-dep promise
for callers who just want sentence selection.

**The parity contract.** spaCy is Python-only. There's no Rust port of
the actual models. If lede core shipped NER, Python and Rust would
diverge — and the byte-identical contract is the differentiator
against every other summarizer in the space.

The compromise: NER ships as a separate package, `lede-spacy`, that
registers as the `"spacy"` backend for `metadata`, `phrases`, and
`correlate_facts`. Install it when you want it; lede core stays
honest. See [`lede-spacy-integration.md`](lede-spacy-integration.md)
for the full integration policy.

## Is the output stable across versions?

`mode="legacy"` is byte-frozen since v0.0.1. The fixture corpus +
walker (`rust/tests/fixtures.rs`) asserts this on every CI push;
breaking it is a release-blocker.

`mode="default"` is the active scorer and *can* change between minor
versions when a heuristic improves. When it does, the change is in the
CHANGELOG, the fixture corpus is regenerated, and the parity walker
catches any Python ↔ Rust drift before merge.

If you need bytes pinned across versions for audit, use `mode="legacy"`
and pin a specific lede version in your dependency manifest. The
legacy scorer will not change.

## Does it handle non-English text?

Partially. The tokenizer regex (`\b[a-z]{3,}\b`) and stopword list (43
English function words) assume Latin script and English. Non-Latin
scripts (Chinese, Arabic, Cyrillic) need a different `_TOKEN_RE`. Other
European languages with Latin script work but get worse scoring because
their stopwords aren't filtered.

This is a deliberate scope choice — keeping the cross-language fixture
corpus byte-stable across Python and Rust is hard enough with one
language. Multi-language support is on the roadmap behind a
`_TOKEN_RE` / `_STOPWORDS` selector, but landed-in-core multi-language
isn't on the v0.3 plan.

## See also

- [`README.md`](../README.md) — install + quick start
- [`REFERENCE.md`](REFERENCE.md) — full primitive catalog with type signatures
- [`guide.md`](guide.md) — feature-by-feature tutorial
- [`comparison.md`](comparison.md) — side-by-side worked examples vs Sumy and LLM APIs
- [`lede-spacy-integration.md`](lede-spacy-integration.md) — companion-package integration policy
