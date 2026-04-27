# skimr — Primitive Reference

Deterministic, zero-dependency extractive primitives for text. Every primitive is pure, side-effect-free, and produces identical output from the Python and Rust implementations (regex backend only).

**Jump to:**
- [Top-level APIs](#top-level-apis) — `summarize`, `brief`
- [Extraction primitives](#extraction-primitives) — `outline`, `toc`, `stats`, `key_facts`, `metadata`, `phrases`, `correlate_facts`
- [Utilities](#utilities) — `clean_text`, `strip_think`, `extract_keyword`
- [Backend selector](#backend-selector) — regex / spacy / auto
- [Optional extras](#optional-extras) — wordforms, yake, textrank, skimr-spacy
- [Choosing the right primitive](#choosing-the-right-primitive)

---

## Top-level APIs

### `skimr.summarize(text, max_length=500, *, mode="default", attach=None) -> SummaryResult`

**Purpose:** compress a document to a character budget while preserving the most informative sentences. Think "minify" — the output is a shorter version of the source, suitable for LLM pre-processing, previews, or dense archival.

**Modes:**
- `"default"` — TF-IDF + position + length composite, heading-filtered (v0.2 scorer).
- `"legacy"` — keyword-frequency + position + length (pre-v0.2 scorer).
- `"coverage"` — paragraph-aware; tries to include one sentence per paragraph before greedy-filling.

**Attach:** pass a list of primitive names to include structured extractions alongside the summary text, e.g. `attach=["stats", "outline"]`. Returns `SummaryResult` with fields populated.

**Returns:** `SummaryResult` — a frozen dataclass with `.summary: str` plus optional `.stats`, `.outline`, `.metadata`, `.phrases`, `.correlated_facts` populated when the corresponding name appears in `attach=`. `str(r)` and `f"{r}"` evaluate to `.summary` so legacy callers expecting a string still work.

**When to use:** you have too much text and need less of it. The output preserves reading flow.

---

### `skimr.brief(text, *, overview_max=0.35, max_facts=10, include_phrases=False, format="string") -> str | dict`

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

## Extraction primitives

All extraction primitives live under `skimr.extract.*`. They're individually usable — `brief()` just composes them.

### `skimr.extract.outline(text) -> tuple[Section, ...]`

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

### `skimr.extract.toc(text) -> tuple[str, ...]` ⟵ **new in T16**

**Purpose:** lightweight table-of-contents — just the section names in document order.

**Equivalent to:** `tuple(s.name for s in outline(text))`. Separate primitive so callers who only want names don't pay for representative-sentence selection.

**When to use:** quick file listing, nav sidebar, document summary header.

---

### `skimr.extract.stats(text, *, convert_word_names=False) -> tuple[Stat, ...]`

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

**`convert_word_names=True`** (requires `skimr[wordforms]` extra): pre-processes text with `text2num` to convert spelled-out numbers ("eight days" → "8 days") before regex scanning. Emitted `value` preserves the original word-form when possible.

**When to use:** you want structured numeric data points. Downstream: facts table, chart, fact-check scaffolding.

---

### `skimr.extract.key_facts(text, *, max_facts=10, convert_word_names=False) -> tuple[str, ...]` ⟵ **new in T16**

**Purpose:** return the N most interesting **sentences** containing numeric or named facts, as complete grammatical sentences (not tuples).

**Ranking heuristic:**
1. Any sentence containing at least one `Stat` is a candidate.
2. Score each candidate by: (sentence tfidf-composite) + (0.15 × stat_density). Stat density = stats in sentence / sentence length.
3. Deduplicate — if two candidates cover the same `(stat_type, normalized_value)`, keep the higher-scored one.
4. Return top `max_facts` in document order.

**When to use:** caller wants human-readable fact highlights. Pairs with `brief()`. Different from `stats()`: output is sentences, not structured tuples — more readable, less machine-parseable.

---

### `skimr.extract.metadata(text, *, backend=None) -> Metadata`

**Purpose:** structured document metadata — dates, monetary amounts, URLs, and entities.

**Metadata shape:** `Metadata(dates: tuple[str, ...], amounts: tuple[str, ...], urls: tuple[str, ...], entities: tuple[str, ...])`.

**Field details:**
- `dates` — ISO + US-slashed forms (regex backend) and bare years (v0.2 broadening).
- `amounts` — same regex as `stats.money`.
- `urls` — `https?://[^\s<>"')]+`.
- `entities` — **empty on regex backend by architectural promise**. Populated only when `backend="spacy"` via skimr-spacy (NER: PERSON / ORG / GPE / LOC / PRODUCT).

**When to use:** you want first-class access to dates / amounts / URLs without filtering `stats()`. Or entities (with spaCy backend).

---

### `skimr.extract.phrases(text, keywords=None, *, backend=None) -> tuple[str, ...]`

**Purpose:** extract multi-word phrases (2–5 tokens).

**Backends** (see [Backend selector](#backend-selector)):
- `"regex"` (default) — all repeated 2–5-token n-grams between stopwords, count ≥ 2, sub-ngram-subsumed (drops shorter ngrams that appear only inside longer ones with equal count).
- `"spacy"` — `doc.noun_chunks`, lowercased, deduped, stopword-stripped leading tokens. Higher precision, lower recall.
- `"yake"` — YAKE statistical key-phrase ranking; returns top-K by score. Higher "salient phrase" quality, but diverges from a "repeated n-gram" gold definition.

**`keywords` parameter** (regex only): if provided, also include single-occurrence phrases containing one of the given keyword tokens. Useful when you know a domain term that may appear only once.

**Output:** lowercased, deduped, order preserved (regex/spacy) or score order (yake).

**When to use:** tag cloud, keyword index, topic snapshot. Choose backend by goal: "every repeated multi-word surface" → regex. "Named noun phrases" → spacy. "Salient key phrases" → yake.

---

### `skimr.extract.correlate_facts(text, *, backend=None, convert_word_names=False) -> tuple[PhraseFact, ...]`

**Purpose:** pair repeated entities with their numeric facts, with an inferred polarity.

**PhraseFact shape:** `PhraseFact(entity: str, number: str, polarity: "growth" | "decline" | "absolute", sentence: str)`.

**Regex backend algorithm:**
1. Run `stats(text)` to enumerate digit-bearing facts.
2. For each stat's sentence, pick the most-frequent repeated non-stopword (or repeated phrase) as the candidate entity.
3. Infer polarity from cue words in the sentence: `grew`/`rose`/`increased` → `growth`; `fell`/`declined`/`dropped` → `decline`; else `absolute`.
4. Filter: keep only pairings whose entity appears in ≥ 2 distinct numeric facts.

**spaCy backend algorithm** (skimr-spacy): same pairing shape, but uses NER + noun-chunks + dependency relations to identify entities. Higher recall on proper nouns, lower precision (over-pairs). No ≥2-facts filter.

**Known gold/primitive mismatch:** hand-labeled gold in `fixtures/extract/correlate/` often expects polarities inferred from verbs attached to single-mention entities (e.g. `risk register` mentioned once, labeled with both `growth` and `decline` polarities from a single sentence). Neither backend produces this without coreference + salience ranking. See `docs/extraction-gold-labeling.md:105` (Rule 5) and v0.3+ roadmap.

**When to use:** structured relation-ish data where the source has repeated entities with quantified claims. Fact-check scaffolding, KPI extraction from reports.

---

## Utilities

### `skimr.clean_text(text) -> str`

Markdown / filler / CRM-boilerplate stripper. Removes markdown syntax, signature footers, common boilerplate. Idempotent. Useful as a pre-processing step before `summarize()` or any extraction primitive when the source has heavy formatting noise.

### `skimr.strip_think(text) -> str`

Removes `<think>…</think>` blocks from reasoning-model output. Useful when processing LLM traces that include hidden reasoning channels.

### `skimr.extract_keyword(text, keywords) -> str`

Query-driven keyword-scored extraction. When the caller has a topic / query, returns the sentences most relevant to it (uses the v0.0.1 keyword-scoring algorithm). Different contract from `summarize()`, which has no query concept.

---

## Backend selector

Primitives that support multiple backends (`metadata`, `phrases`, `correlate_facts`) accept a `backend=` keyword and also respect a global default set via `skimr.set_default_backend()`.

**Backend names:**
- `"regex"` — the zero-dependency default. **Only** backend that promises byte-identical Python ↔ Rust output.
- `"spacy"` — available when `skimr-spacy` is imported. Python-only.
- `"yake"` — available for `phrases` when `skimr[yake]` is installed. Python-only.
- `"auto"` — uses `"spacy"` if registered, else `"regex"`. Check `resolve(backend, primitive)` for dispatch details.

**`backend=None`** means "use the global default" (which is `"regex"` unless changed).

**Rust does NOT have a `backend=` argument.** The cross-language parity contract applies only to the regex backend. Any future Rust NLP layer would register under a different name (e.g. `"deepfrog"`) since it would be a different model.

---

## Optional extras

Install with `pip install skimr[EXTRA]`:

| Extra | Pulls in | Enables |
|---|---|---|
| `wordforms` | `text2num>=3.0` | `convert_word_names=True` on `stats` / `correlate_facts`. Handles "eight days", "five thousand", etc. |
| `yake` | `yake>=0.4.8` | `backend="yake"` for `phrases`. Statistical key-phrase ranking. |
| `textrank` | `networkx>=3.0` | Optional TextRank scorer inside `summarize()`. |
| `dev` | `pytest`, `pytest-subtests` | Running the test suite. |
| `bench` | `sumy`, `numpy` | Running the benchmark comparisons. |

**Rust equivalents:** built with `--features FEATURE`:
- `wordforms` — pulls the Rust `text2num = "2.6"` crate. Gates `stats_with_options(text, StatsOptions { convert_word_names: true })`.
- No `yake` feature in Rust (yake is Python-only; use the regex backend or skimr-spacy noun-chunks when running from Rust).

**Companion package:** `skimr-spacy` (separate PyPI distribution) registers the `"spacy"` backend for `metadata`, `phrases`, and `correlate_facts` when imported. Pulls `spacy>=3.8` + `en_core_web_sm-3.8.0`.

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
| entity → fact pairings | `correlate_facts(text)` (regex) |
| entity → fact pairings via dep-parse | `correlate_facts(text, backend="spacy")` |
| cleaned text (strip markdown / boilerplate) | `clean_text(text)` |
| stripped LLM reasoning channels | `strip_think(text)` |
| query-driven sentences | `extract_keyword(text, keywords)` |

---

## Guarantees

- **Deterministic:** same input → same output, every call, every runtime. No RNG, no ordering drift, no hash-iteration dependencies.
- **Zero required runtime deps** (regex backend): core primitives use only Python stdlib / Rust stdlib + `regex` crate.
- **Byte-identical Python ↔ Rust** for the regex backend across the fixture test suite. Optional backends make no parity promise.
- **No LLM calls in the core.** Never. Neural backends live in `skimr-spacy` (companion) or future `skimr-neural` (hypothetical), not in `skimr` itself.
- **Sub-millisecond to low-ms latency** for all regex-backend primitives on typical documents (≤10 KB). See `benchmarks/quality/extraction-YYYY-MM-DD.md` for per-primitive timing.

## Scaling notes

skimr is designed for the **per-chunk hot path** of a RAG / agent pipeline: typical inputs are sentence- to paragraph-sized (a few hundred to a few thousand chars). The benchmark suite at `benchmarks/quality/matrix-2026-04-26.md` reports across 10 corpora ranging 0.5 KB – 3 KB:

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

- Split at paragraph boundaries (`\n\n+`), feed each chunk through `summarize`/`brief`, then concatenate. skimr is designed for this — that's exactly the chunkshop integration shape, see [`integration-memo.md`](integration-memo.md).
- Don't paste a multi-megabyte string and expect a 500-char summary to be useful. Pre-chunk first; skimr is a primitive, not a document loader.

---

## Versioning

Current: `0.2.0.dev0` (Python) / `0.2.0-dev.0` (Rust SemVer). v0.2 adds extraction primitives, backend selector, skimr-spacy companion, and optional `wordforms` / `yake` extras. v0.2.0 tags when T14 comparison matrix + T15 release sign-off land.

v0.1.0 conceptually exists as "the TF-IDF summarizer that passed SC-A" but was never tagged — the project pivoted into v0.2 before releasing it.

---

## Where to look next

- **Spec** — [`docs/v0-2-design.md`](v0-2-design.md)
- **Gold-labeling protocol** — `docs/extraction-gold-labeling.md`
- **spaCy integration policy** — [`docs/skimr-spacy-integration.md`](skimr-spacy-integration.md)
- **Benchmarks** — `benchmarks/corpus/` (10 source docs) + `fixtures/extract/` (gold labels) + `benchmarks/quality/extraction-*.md` (latest eval)
- **Changelog** — [`../CHANGELOG.md`](../CHANGELOG.md)
