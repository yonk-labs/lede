# lede — Primitive Reference

Deterministic, zero-dependency extractive primitives for text. Every primitive is pure, side-effect-free, and produces identical output from the Python and Rust implementations (regex backend only).

**Jump to:**
- [Top-level APIs](#top-level-apis) — `summarize`, `brief`
- [Hint biasing](#hint-biasing-v04) — `hints`, `hint_focus`, `hint_mode` on all ranking primitives (v0.4)
- [Extraction primitives](#extraction-primitives) — `outline`, `toc`, `stats`, `key_facts`, `metadata`, `phrases`, `correlate_facts`, `top_terms`
- [Utilities](#utilities) — `clean_text`, `strip_think`, `extract_keyword`
- [Backend selector](#backend-selector) — regex / spacy / auto
- [Optional extras](#optional-extras) — wordforms, yake, textrank, lede-spacy, lede-spacy[synonyms]
- [Choosing the right primitive](#choosing-the-right-primitive)

---

## Top-level APIs

### `lede.summarize(text, max_length=500, *, mode="default", attach=None, hints=None, hint_focus=0.7, hint_mode="soft") -> SummaryResult`

**Purpose:** compress a document to a character budget while preserving the most informative sentences. Think "minify" — the output is a shorter version of the source, suitable for LLM pre-processing, previews, or dense archival.

**Modes:**
- `"default"` — TF-IDF + position + length composite, heading-filtered (v0.2 scorer).
- `"legacy"` — keyword-frequency + position + length (pre-v0.2 scorer).
- `"coverage"` — paragraph-aware; tries to include one sentence per paragraph before greedy-filling.

**Attach:** pass a list of primitive names to include structured extractions alongside the summary text, e.g. `attach=["stats", "outline"]`. Returns `SummaryResult` with fields populated.

**Returns:** `SummaryResult` — a frozen dataclass with `.summary: str` plus optional `.stats`, `.outline`, `.metadata`, `.phrases`, `.correlated_facts` populated when the corresponding name appears in `attach=`. `str(r)` and `f"{r}"` evaluate to `.summary` so legacy callers expecting a string still work.

**When to use:** you have too much text and need less of it. The output preserves reading flow.

---

### `lede.brief(text, *, overview_max=0.35, max_facts=10, include_phrases=False, format="string", hints=None, hint_focus=0.7, hint_mode="soft") -> str | dict`

**Purpose:** produce a quick at-a-glance brief of what a document is about, what interesting facts it contains, and what else is in it. Think "reader brief" — a new reader should be able to decide in seconds whether the doc is worth reading in full.

**Composition:** `overview` (2–5 sentences via `summarize()`) + `key_facts` (up to N sentences containing numeric/named facts) + `toc` (section outline).

**Parameters:**
- `overview_max: float` — overview char budget as a fraction of source length. Default `0.35`. Clamped to `[0.05, 0.50]`.
- `max_facts: int` — max number of key-fact sentences. Default `10`.
- `include_phrases: bool` — append key phrases section. Default `False`.
- `format: "string" | "markdown" | "dict"` — output shape. Default `"string"` (plain text with section labels).

**Returns:**
- `"string"` (default) — plain text with section headers like `Overview:`, `Key facts:`, `Also in this doc:`.
- `"markdown"` — same sections rendered with `##` headers and bullet lists.
- `"dict"` — `{"overview": str, "key_facts": list[str], "toc": list[str], "phrases": list[str] | None}`.

**When to use:** caller wants to understand a document's shape without reading it. Email digest, file browser preview, document ingest pipeline.

**Design policy:** agnostic of document type. No heuristics for "this is a scientific paper so use the Abstract." The primitive just composes extraction results; callers can override any piece.

---

## Hint biasing (v0.4)

Optional `hints` kwargs on lede's ranking primitives bias selection toward
sentences, facts, phrases, or correlations that mention specific terms or phrases.

### Public API

The following primitives accept three new optional kwargs: `hints`, `hint_focus`,
and `hint_mode`:

- `lede.summarize`
- `lede.brief` (forwards to its internal `summarize`, `key_facts`, and `phrases` calls)
- `lede.extract.key_facts`
- `lede.extract.phrases`
- `lede.extract.correlate_facts`
- `lede.extract.top_terms` (also new in v0.4)

```python
from lede import summarize

result = summarize(
    text,
    hints=["John Smith", "county"],   # list[str] or dict[str, float]
    hint_focus=0.7,                   # budget split in [0.0, 1.0]
    hint_mode="soft",                 # "soft" or "hard"
).summary
```

### Backward compatibility

When `hints` is `None` (the default) on any primitive, no new code path runs and
output is byte-identical to v0.3.0. The v0.1 and v0.2 fixture walkers continue
to pass unchanged. Existing callers see no difference.

### Argument semantics

**`hints`** — `list[str]` or `dict[str, float]`.

- `list[str]`: each string is a hint term; all terms get weight `1.0`.
- `dict[str, float]`: keys are hint terms, values are numeric weights. Higher
  weights produce larger bonuses in soft mode.
- Multi-word phrases are allowed: `"John Smith"` matches sentences containing
  the substring "John Smith" as a whole (word-boundary delimited).

**`hint_focus`** — `float` in `[0.0, 1.0]`, default `0.7`.

Controls the fraction of the selection budget reserved for hint-matching
candidates. Budget unit depends on the primitive:

- `summarize` / `_summarize_with_hints`: character budget.
- `key_facts`: count budget (`round(max_facts * hint_focus)` → hint quota).
- `phrases` / `correlate_facts` / `top_terms`: no budget effect (no count
  cap in these primitives); `hint_focus` is validated but ignored in behavior.

Unused budget in either pool rolls over to the other pool:
- Unused hint-pool budget → plain pool (in all modes).
- Unused plain-pool budget → hint pool (soft mode only; hard mode does not
  draw extra from the plain pool into the hint pool).

**`hint_mode`** — `"soft"` (default) or `"hard"`.

- `"soft"`: hint-matching candidates receive a score bonus and are ranked
  higher, but non-matching candidates can still appear to fill the quota.
- `"hard"`: only hint-matching candidates are eligible for the hint-pool
  quota. The plain-pool quota still draws from all candidates.

### Matching rules

- **Case-insensitive**: `"John Smith"` matches `"john smith"`, `"JOHN SMITH"`, etc.
- **Word-boundary delimited**: `\b`-anchored — `"county"` does not match
  `"countries"`.
- **No Unicode normalization** (NFC/NFD) and no diacritic stripping: `"café"`
  does not match `"cafe"`.
- **No stemming or lemmatization** in the core matching. Use
  `lede_spacy.expand_hints` (see below) for that.
- **Substring match within a sentence** (or phrase, or correlation): the
  hint must appear as a complete word sequence in the target string.

For lemma, synonym, or vector-similarity expansion, use
`lede_spacy.expand_hints` before passing hints to any lede primitive:

```python
from lede import summarize
from lede_spacy import expand_hints

expanded = expand_hints(["counties"], kinds=("lemma",))
# expanded == ["counties", "county"]
result = summarize(text, hints=expanded, hint_focus=0.7).summary
```

### Validation

| Primitive | Raises `ValueError` when |
|---|---|
| `summarize` | `hint_focus` outside `[0.0, 1.0]`, `hint_mode` not `"soft"` / `"hard"`, `mode="legacy"` with non-None `hints` |
| `brief` | propagated from the internal primitive calls |
| `key_facts` | `hint_focus` outside `[0.0, 1.0]`, `hint_mode` not `"soft"` / `"hard"` |
| `phrases` | `hint_focus` outside `[0.0, 1.0]`, `hint_mode` not `"soft"` / `"hard"` |
| `correlate_facts` | `hint_focus` outside `[0.0, 1.0]`, `hint_mode` not `"soft"` / `"hard"` |
| `top_terms` | `hint_focus` outside `[0.0, 1.0]`, `hint_mode` not `"soft"` / `"hard"`, unknown entry in `kinds` |

### Per-primitive specifics

| Primitive | Match target | Budget unit | `hint_focus` has effect |
|---|---|---|---|
| `summarize` | sentence text | chars | yes — two-pool char budget split |
| `brief` | forwarded to sub-primitives | (each primitive's own) | yes — forwarded as-is |
| `key_facts` | sentence text | count (sentences) | yes — two-pool count quota |
| `phrases` | phrase string itself | n/a | no — no count cap |
| `correlate_facts` | `"{entity} {number}"` (OR semantics) | n/a | no — no count cap |
| `top_terms` | term string | n/a | no — no count cap |

### Parity contract

For the core regex backend, Python and Rust produce byte-identical output on
the same `(text, hints, hint_focus, hint_mode)` inputs for `summarize`,
`brief`, and `key_facts`. Enforced by the `v0_4_hints_byte_identical` fixture
walker (10 corpora × 14 hint configurations = 140 fixtures).

**Not parity-promised:**
- `phrases(backend='yake')` with hints — YAKE backend does not accept hints.
- `correlate_facts(backend='spacy')` with hints — spaCy backend does not
  accept hints.
- `top_terms` — Python-only in v0.4; Rust mirror deferred to v0.5.
- `lede_spacy.expand_hints` — Python-only by policy.

### Cross-runtime determinism note

Budget rounding uses integer math (`round_to_int`) to avoid divergence between
Python's `round()` (banker's rounding, round half to even) and Rust's
`f64::round()` (round half away from zero) on boundary values.

---

## Extraction primitives

All extraction primitives live under `lede.extract.*`. They're individually usable — `brief()` just composes them.

### `lede.extract.outline(text) -> tuple[Section, ...]`

**Purpose:** detect structural sections and return each with its most representative non-heading sentence.

**Section shape:** `Section(depth: int, name: str, representative_sentence: str)`.

**Detection patterns** (see `_headings.py`):
- Markdown ATX headings (`#`, `##`, `###`, …)
- ALL-CAPS lines up to 80 chars
- Short colon-labels on their own line (≤30 chars, trailing `:`)
- Bare title-case lines with no terminal punctuation (≤60 chars)
- Numbered-section prefixes (`1. Section Name`)
- Title-with-em-dash lines (`Title — Metadata` → heading name is `Title`)

**Notable non-detections** (v0.2):
- `Label: Subject` document headers like `Meeting: Platform Migration Planning` — the primitive doesn't currently extract the post-colon subject as a heading.
- Inline colon-labels like `Held: Section 412(b) ...` when content follows on the same line.
- Parenthetical-structured headings like `Reply from support (Kai T., day 1)`.

**When to use:** you want both the section structure AND a representative sentence for each. The representative is the highest-tfidf-composite non-heading sentence within the section's body.

---

### `lede.extract.toc(text) -> tuple[str, ...]` ⟵ **new in T16**

**Purpose:** lightweight table-of-contents — just the section names in document order.

**Equivalent to:** `tuple(s.name for s in outline(text))`. Separate primitive so callers who only want names don't pay for representative-sentence selection.

**When to use:** quick file listing, nav sidebar, document summary header.

---

### `lede.extract.stats(text, *, convert_word_names=False) -> tuple[Stat, ...]`

**Purpose:** extract numeric facts — money, percent, date, duration, count.

**Stat shape:** `Stat(value: str, unit: str, phrase: str, context_sentence: str, stat_type: str)`.

**Patterns by type:**
| `stat_type` | matches | examples |
|---|---|---|
| `money` | `$N[KMB]` or `N dollars/USD/EUR/…` | `$120K`, `45 dollars`, `100 EUR` |
| `percent` | `N% / N percent` | `94%`, `23 percent` |
| `date` | ISO `YYYY-MM-DD`, US `M/D/YYYY`, bare years 1900–2099 | `2026-04-15`, `4/15/2026`, `1975` |
| `duration` | `N seconds?/minutes?/…/years?` with hyphen or space separator | `30 days`, `90-day`, `two weeks` (with `convert_word_names=True`) |
| `count` | `N` + keyword from a known list (events, users, items, documents, tons per year, terabytes, basis points, …) | `50,000 events`, `2 terabytes per day`, `8 basis points`, `18 tons per year` |

**`convert_word_names=True`** (requires `lede[wordforms]` extra): pre-processes text with `text2num` to convert spelled-out numbers ("eight days" → "8 days") before regex scanning. Emitted `value` preserves the original word-form when possible.

**When to use:** you want structured numeric data points. Downstream: facts table, chart, fact-check scaffolding.

---

### `lede.extract.key_facts(text, *, max_facts=10, convert_word_names=False, hints=None, hint_focus=0.7, hint_mode="soft") -> tuple[str, ...]`

**Purpose:** return the N most interesting **sentences** containing numeric or named facts, as complete grammatical sentences (not tuples).

**Ranking heuristic:**
1. Any sentence containing at least one `Stat` is a candidate.
2. Score each candidate by: (sentence tfidf-composite) + (0.15 × stat_density). Stat density = stats in sentence / sentence length.
3. Deduplicate — if two candidates cover the same `(stat_type, normalized_value)`, keep the higher-scored one.
4. Return top `max_facts` in document order.

**When to use:** caller wants human-readable fact highlights. Pairs with `brief()`. Different from `stats()`: output is sentences, not structured tuples — more readable, less machine-parseable.

---

### `lede.extract.metadata(text, *, backend=None) -> Metadata`

**Purpose:** structured document metadata — dates, monetary amounts, URLs, and entities.

**Metadata shape:** `Metadata(dates: tuple[str, ...], amounts: tuple[str, ...], urls: tuple[str, ...], entities: tuple[str, ...])`.

**Field details:**
- `dates` — ISO + US-slashed forms (regex backend) and bare years (v0.2 broadening).
- `amounts` — same regex as `stats.money`.
- `urls` — `https?://[^\s<>"')]+`.
- `entities` — **empty on regex backend by architectural promise**. Populated only when `backend="spacy"` via lede-spacy (NER: PERSON / ORG / GPE / LOC / PRODUCT).

**When to use:** you want first-class access to dates / amounts / URLs without filtering `stats()`. Or entities (with spaCy backend).

---

### `lede.extract.phrases(text, keywords=None, *, backend=None, hints=None, hint_focus=0.7, hint_mode="soft") -> tuple[str, ...]`

**Purpose:** extract multi-word phrases (2–5 tokens).

**Backends** (see [Backend selector](#backend-selector)):
- `"regex"` (default) — all repeated 2–5-token n-grams between stopwords, count ≥ 2, sub-ngram-subsumed (drops shorter ngrams that appear only inside longer ones with equal count).
- `"spacy"` — `doc.noun_chunks`, lowercased, deduped, stopword-stripped leading tokens. Higher precision, lower recall.
- `"yake"` — YAKE statistical key-phrase ranking; returns top-K by score. Higher "salient phrase" quality, but diverges from a "repeated n-gram" gold definition.

**`keywords` parameter** (regex only): if provided, also include single-occurrence phrases containing one of the given keyword tokens. Useful when you know a domain term that may appear only once.

**Output:** lowercased, deduped, order preserved (regex/spacy) or score order (yake).

**When to use:** tag cloud, keyword index, topic snapshot. Choose backend by goal: "every repeated multi-word surface" → regex. "Named noun phrases" → spacy. "Salient key phrases" → yake.

---

### `lede.extract.correlate_facts(text, *, backend=None, convert_word_names=False, hints=None, hint_focus=0.7, hint_mode="soft") -> tuple[PhraseFact, ...]`

**Purpose:** pair repeated entities with their numeric facts, with an inferred polarity.

**PhraseFact shape:** `PhraseFact(entity: str, number: str, polarity: "growth" | "decline" | "absolute", sentence: str)`.

**Regex backend algorithm:**
1. Run `stats(text)` to enumerate digit-bearing facts.
2. For each stat's sentence, pick the most-frequent repeated non-stopword (or repeated phrase) as the candidate entity.
3. Infer polarity from cue words in the sentence: `grew`/`rose`/`increased` → `growth`; `fell`/`declined`/`dropped` → `decline`; else `absolute`.
4. Filter: keep only pairings whose entity appears in ≥ 2 distinct numeric facts.

**spaCy backend algorithm** (lede-spacy): same pairing shape, but uses NER + noun-chunks + dependency relations to identify entities. Higher recall on proper nouns, lower precision (over-pairs). No ≥2-facts filter.

**Known gold/primitive mismatch:** hand-labeled gold in `fixtures/extract/correlate/` often expects polarities inferred from verbs attached to single-mention entities (e.g. `risk register` mentioned once, labeled with both `growth` and `decline` polarities from a single sentence). Neither backend produces this without coreference + salience ranking. See `docs/extraction-gold-labeling.md:105` (Rule 5) and v0.3+ roadmap.

**When to use:** structured relation-ish data where the source has repeated entities with quantified claims. Fact-check scaffolding, KPI extraction from reports.

---

### `lede.extract.top_terms(text, *, n=10, kinds=("words", "phrases"), with_scores=False) -> tuple[str, ...] | tuple[TermScore, ...]` ⟵ **new in v0.4** (`with_scores` added v0.4.1)

**Purpose:** return the top-N salient terms (single words and/or multi-word phrases) ranked by a unified score.

**Composition:** combines per-document TF-IDF on single tokens (`"words"` kind) with multi-word phrase frequency from the same extractor as `extract.phrases` (`"phrases"` kind). Each kind's scores are normalized to `[0, 1]` before merging.

**Parameters:**
- `n: int` — cap on returned terms. Default 10.
- `kinds: tuple` — which candidate pools to use. Any non-empty subset of `("words", "phrases")`. Default both.
- `with_scores: bool` — when True, return `tuple[TermScore]` instead of `tuple[str]` (v0.4.1). Default False (bare strings, byte-for-byte the v0.4.0 behavior).
- `hints / hint_focus / hint_mode` — hint biasing kwargs (v0.4). See [Hint biasing](#hint-biasing-v04).

**Scoring:**
- Word score: `TF * IDF` (same formula as `summarize()`), normalized by max.
- Phrase score: `repetition_count × token_count`, normalized by max.
- Returned in score-descending order; ties broken alphabetically (deterministic).

**`with_scores=True` (v0.4.1):** returns `tuple[TermScore, ...]` in the identical ranked order, where `TermScore` is a `NamedTuple`:

```python
class TermScore(NamedTuple):
    term: str
    score: float   # the value that drove the ranking
    kind: str      # "word" | "phrase"
```

`TermScore` is tuple-unpackable (`for term, score, kind in result`) and name-accessible (`ts.term` / `ts.score` / `ts.kind`).

> **Score-calibration caveat.** Scores are normalized **within each kind independently** — a word at `1.0` and a phrase at `1.0` are each top-of-their-kind, not equal on a shared cross-kind scale. The unified interleaving by these per-kind-normalized values is a reasonable heuristic, not a globally-calibrated relevance score. In soft-hint mode the `hint_bonus` is added on top, so a matching term's `score` may exceed `1.0`. In hard-hint mode the `score` is the base value (no bonus added).

**Hint biasing:** soft mode adds `hint_bonus` to each candidate's score before ranking. Hard mode removes non-matching candidates entirely. `hint_focus` is validated but has no two-pool budget effect (no count cap before `n` truncation).

**Parity:** Python-only in v0.4/v0.4.1. Rust mirror (including `with_scores`) deferred to v0.5.

**When to use:** quick tag cloud, keyword index, topic snapshot that combines important single words with key phrases in one pass. Use `with_scores=True` when a downstream consumer needs the relevance score and word/phrase distinction per term. Use `extract.phrases` when you want only multi-word phrases, or `summarize()`'s TF-IDF machinery when you're building a summary rather than a term list.

---

## Utilities

### `lede.clean_text(text) -> str`

Markdown / filler / CRM-boilerplate stripper. Removes markdown syntax, signature footers, common boilerplate. Idempotent. Useful as a pre-processing step before `summarize()` or any extraction primitive when the source has heavy formatting noise.

### `lede.strip_think(text) -> str`

Removes `<think>…</think>` blocks from reasoning-model output. Useful when processing LLM traces that include hidden reasoning channels.

### `lede.extract_keyword(text, keywords) -> str`

Query-driven keyword-scored extraction. When the caller has a topic / query, returns the sentences most relevant to it (uses the v0.0.1 keyword-scoring algorithm). Different contract from `summarize()`, which has no query concept.

---

## Backend selector

Primitives that support multiple backends (`metadata`, `phrases`, `correlate_facts`) accept a `backend=` keyword and also respect a global default set via `lede.set_default_backend()`.

**Backend names:**
- `"regex"` — the zero-dependency default. **Only** backend that promises byte-identical Python ↔ Rust output.
- `"spacy"` — available when `lede-spacy` is imported. Python-only.
- `"yake"` — available for `phrases` when `lede[yake]` is installed. Python-only.
- `"auto"` — uses `"spacy"` if registered, else `"regex"`. Check `resolve(backend, primitive)` for dispatch details.

**`backend=None`** means "use the global default" (which is `"regex"` unless changed).

**Rust does NOT have a `backend=` argument.** The cross-language parity contract applies only to the regex backend. Any future Rust NLP layer would register under a different name (e.g. `"deepfrog"`) since it would be a different model.

---

## Optional extras

Install with `pip install lede[EXTRA]`:

| Extra | Pulls in | Enables |
|---|---|---|
| `wordforms` | `text2num>=3.0` | `convert_word_names=True` on `stats` / `correlate_facts`. Handles "eight days", "five thousand", etc. |
| `yake` | `yake>=0.4.8` | `backend="yake"` for `phrases`. Statistical key-phrase ranking. |
| `textrank` | `networkx>=3.0` | Optional TextRank scorer inside `summarize()`. |
| `dev` | `pytest`, `pytest-subtests` | Running the test suite. |
| `bench` | `sumy`, `numpy` | Running the benchmark comparisons. |

**Companion package:** `lede-spacy` (separate PyPI distribution) registers the `"spacy"` backend for `metadata`, `phrases`, and `correlate_facts` when imported. Pulls `spacy>=3.8` + `en_core_web_sm-3.8.0`. Also provides `lede_spacy.expand_hints` for hint expansion.

**`lede-spacy[synonyms]`** — additional extra on the companion package. Install with `pip install lede-spacy[synonyms]`. Pulls `nltk` and downloads the `wordnet` corpus. Required for `expand_hints(kinds=("synonyms",))`.

**`lede-spacy` with vectors** — `expand_hints(kinds=("similar",))` requires a vector-capable spaCy model. Install `en_core_web_md` or `en_core_web_lg` (`en_core_web_sm` has no vectors).

## Runtime parity

Every public function on the **regex backend** is byte-identical
between Python and Rust — that's the SC-C contract, enforced on every
push by `rust/tests/fixtures.rs::v0_2_extract_primitives_byte_identical`
(70 fixtures × 7 primitives) and `every_fixture_byte_identical` (the
v0.1 surface). Optional extras are intentionally asymmetric:

| Feature | Python | Rust | Why the asymmetry |
|---|---|---|---|
| Core `summarize` / `brief` / `extract.*` (regex backend) | ✅ | ✅ | The parity contract. Same input → same bytes from either runtime. |
| **`wordforms`** — spelled-out numbers ("eight days") | `[wordforms]` extra (text2num) | `--features wordforms` (same `text2num` crate) | Both bind the same Rust crate. Byte-identical parity. |
| **`textrank`** — graph-based PageRank summarizer | `[textrank]` extra (networkx) | ❌ not available | Feasible to add — `petgraph` ships PageRank, or a pure power-iteration impl is ~80 lines. Skipped in v0.2 because the regex backend is the parity contract and graph algos pull transitive deps. **Open an issue if you'd use a Rust `textrank` cargo feature.** |
| **`yake`** — statistical key-phrase extractor | `[yake]` extra | ❌ not available | No maintained Rust port of YAKE today. The algorithm is statistical (not ML), so a port is feasible but non-trivial. Open an issue if you'd consume one. |
| **spaCy NER** — entity extraction | `lede-spacy` companion package | ❌ not available, by design | Pure-Rust transformer NER requires shipping model weights and a heavy ML runtime (`rust-bert`/`tch-rs` are ONNX/torch-backed). That contradicts lede's "stdlib + regex only" Rust contract. Rust returns `Metadata.entities` as an empty `Vec` under the regex backend; callers needing NER from a Rust service should call out to a separate NER endpoint (Python lede-spacy or a hosted service). |
| Backend registry / `set_default_backend()` | ✅ | ❌ | Rust ships only the regex backend — no plug-in dispatch. |
| CLI binary | ✅ `lede` | ✅ `lede` | Same flags. UTF-8 reads on both. BrokenPipe handled. |

Bottom line: if your callers use only the regex backend, the two ports
are equivalent. Feature requests for Rust ports of textrank or yake
are welcome on GitHub Issues with the `rust-feature-parity` label.
spaCy NER on the Rust side will not be added inside `lede` (heavy
deps); a future `lede-rust-ner` companion crate could ship if there's
demand.

---

## Choosing the right primitive

| If you want… | Use |
|---|---|
| a shorter version of the same text | `summarize(text, max_length=N)` |
| a reader-friendly brief | `brief(text)` |
| just the section names | `toc(text)` |
| sections with representative content | `outline(text)` |
| structured numeric facts | `stats(text)` |
| sentences containing interesting facts | `key_facts(text)` |
| dates / amounts / URLs as lists | `metadata(text)` |
| people / orgs / places as lists | `metadata(text, backend="spacy")` |
| repeated multi-word phrases | `phrases(text)` (regex) |
| named noun phrases | `phrases(text, backend="spacy")` |
| ranked key phrases | `phrases(text, backend="yake")` |
| top salient words + phrases in one pass | `top_terms(text, n=10)` |
| entity → fact pairings | `correlate_facts(text)` (regex) |
| entity → fact pairings via dep-parse | `correlate_facts(text, backend="spacy")` |
| bias any primitive toward specific terms | add `hints=[…]` to `summarize`, `brief`, `key_facts`, `phrases`, `correlate_facts`, or `top_terms` |
| expand hints with lemmas / synonyms | `lede_spacy.expand_hints(hints, kinds=("lemma", "synonyms"))` |
| cleaned text (strip markdown / boilerplate) | `clean_text(text)` |
| stripped LLM reasoning channels | `strip_think(text)` |
| query-driven sentences | `extract_keyword(text, keywords)` |

---

## Guarantees

- **Deterministic:** same input → same output, every call, every runtime. No RNG, no ordering drift, no hash-iteration dependencies.
- **Zero required runtime deps** (regex backend): core primitives use only Python stdlib / Rust stdlib + `regex` crate.
- **Byte-identical Python ↔ Rust** for the regex backend across the fixture test suite. Optional backends make no parity promise.
- **No LLM calls in the core.** Never. Neural backends live in `lede-spacy` (companion) or future `lede-neural` (hypothetical), not in `lede` itself.
- **Sub-millisecond to low-ms latency** for all regex-backend primitives on typical documents (≤10 KB). See `benchmarks/quality/extraction-YYYY-MM-DD.md` for per-primitive timing.

## Scaling notes

lede is designed for the **per-chunk hot path** of a RAG / agent pipeline: typical inputs are sentence- to paragraph-sized (a few hundred to a few thousand chars). The benchmark suite at `benchmarks/quality/matrix-2026-04-26.md` reports across 10 corpora ranging 0.5 KB – 3 KB:

| method (regex backend) | avg p50 | max p50 |
|---|---|---|
| `summarize` (Python, default mode) | 0.42 ms | 0.62 ms |
| `summarize` (Rust, default mode) | 0.13 ms | 0.19 ms |
| `summarize(attach=…all 5…)` (Python) | 2.40 ms | 3.80 ms |
| Sumy LexRank/TextRank/LSA (Python) | 11–12 ms | 14–17 ms |

### Larger documents

Input handling is linear in document length on the regex backend, but two non-linear behaviors are worth knowing:

- **`extract.phrases`** counts repeated multi-word n-grams. Total work is `O(n)` in token count, but for a document with a long unbroken non-stop run the candidate-ngram set can grow large. Real English text breaks runs naturally; pathological inputs (URL slugs concatenated, base64-encoded blobs without whitespace) can spike memory.
- **`extract.stats`** with `convert_word_names=True` runs `text2num` over every sentence; `text2num` does its own scan + parse, adding linear-in-tokens overhead per sentence. The default flag-off path is the regex-only fast path.

### Documents with pathological inputs

ReDoS is bounded structurally:

- All numeric quantifiers in `extract.stats` regexes are bounded `\d{1,15}`.
- Sentences containing a 20+ digit unbroken run are skipped entirely (mirrored Python ↔ Rust). Real-world numeric tokens are well below this — 16-digit cards, 13-digit ISBN, 12-digit phone.
- A 100K-digit input that previously hung Python for 14 minutes now completes in ≤ 20 ms.

### Recommended chunking for very long inputs

For documents > 100 KB:

- Split at paragraph boundaries (`\n\n+`), feed each chunk through `summarize`/`brief`, then concatenate. lede is designed for this — that's exactly the chunkshop integration shape, see [`integration-memo.md`](integration-memo.md).
- Don't paste a multi-megabyte string and expect a 500-char summary to be useful. Pre-chunk first; lede is a primitive, not a document loader.

---

## Versioning

Current: `0.4.1` (Python) / `0.4.1` (Rust SemVer). v0.4 adds hint-biased extraction, the `top_terms` primitive, and `lede_spacy.expand_hints`. v0.4.1 adds `top_terms(with_scores=True)` returning `TermScore` records. See `CHANGELOG.md` for the full entry.

**v0.3.0** renamed `skimr` → `lede` (no behavior changes). **v0.2.0** added extraction primitives, backend selector, lede-spacy companion, and optional extras. v0.1.0 conceptually exists as "the TF-IDF summarizer that passed SC-A" but was never tagged.

---

## Where to look next

- **Spec** — [`docs/v0-2-design.md`](v0-2-design.md)
- **Gold-labeling protocol** — `docs/extraction-gold-labeling.md`
- **spaCy integration policy** — [`docs/lede-spacy-integration.md`](lede-spacy-integration.md)
- **Benchmarks** — `benchmarks/corpus/` (10 source docs) + `fixtures/extract/` (gold labels) + `benchmarks/quality/extraction-*.md` (latest eval)
- **Changelog** — [`../CHANGELOG.md`](../CHANGELOG.md)
