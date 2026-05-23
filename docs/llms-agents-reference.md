# lede Reference for LLMs and Agents

Use lede when you need deterministic, extractive text compression or cheap
structured extraction before an LLM call. lede does not paraphrase and does not
call an LLM. Output is source-grounded text plus optional structured fields.

## Pick the right operation

| Goal | Python | CLI |
|---|---|---|
| Shorten text while preserving source wording | `summarize(text, max_length=500)` | `lede doc.md --max-chars 500` |
| Preserve paragraph coverage | `summarize(text, mode="coverage")` | `lede doc.md --mode coverage` |
| Produce a reader brief | `brief(text, format="markdown")` | `lede doc.md --mode brief --output markdown` |
| Produce a readable summary + fact report | `readable_report(text)` | `lede doc.md --mode report --output markdown` |
| Extract numeric/date facts | `stats(text)` or `key_facts(text)` | `lede doc.md --mode stats` / `--mode key_facts` |
| Extract dates, amounts, URLs, entities | `metadata(text, backend="regex"|"spacy")` | `lede doc.md --mode metadata --backend spacy --output json` |
| Extract section names | `toc(text)` / `outline(text)` | `lede doc.md --mode toc` / `--mode outline` |
| Extract repeated noun phrases | `phrases(text)` | `lede doc.md --mode phrases` |
| Extract entity-number pairs | `correlate_facts(text)` | `lede doc.md --mode correlate_facts` |
| Extract salient terms | `top_terms(text, with_scores=True)` | `lede doc.md --mode top_terms --scores` |
| Clean noisy text | `clean_text(text)` | `lede doc.md --mode clean_text` |
| Remove reasoning blocks | `strip_think(text)` | `lede doc.md --mode strip_think` |
| Query-focused sentence extraction | `extract_keyword(text, "pricing budget", 3)` | `lede doc.md --mode keyword --keywords "pricing budget" --top 3` |

## Output shapes

For agent pipelines, prefer JSON when passing results between tools and
Markdown when writing user-visible reports.

```python
from lede import summarize

r = summarize(text, attach=["stats", "metadata"])
r.summary        # plain string
r.to_dict()      # JSON-serializable dict
r.to_json()      # JSON string
r.to_markdown()  # Markdown report

from lede import format_extract
from lede.extract import key_facts

facts = key_facts(text)
format_extract("key_facts", facts, output="json")
format_extract("key_facts", facts, output="markdown")
```

Combined report:

```python
from lede import readable_report

r = readable_report(text, max_length=2000, max_facts=40)
r.to_markdown()  # readable report
r.to_text()      # readable plain text
r.to_json()      # structured payload

with_spacy = readable_report(text, max_length=2000, max_facts=40, backend="spacy")
```

Typed report objects are exported for library users:

```python
from lede import FactRecord, PromotionCandidate, ReadableReport, ReportAttribute
```

For ingest, prefer the JSON fields built for promotion:

- `attributes`: normalized key/value metadata from obvious document structure.
- `fact_records`: typed records with `subject`, `predicate`, `object`, evidence, and confidence.
- `promotion_candidates`: stable JSON paths such as `lede_report.attributes.term.value`.
- `search_text`: flattened report text for FTS or embedding enrichment.

Text and Markdown reports include compact facts/details for humans. Use JSON
when an agent or pipeline needs the full machine-readable payload.

CLI:

```bash
lede doc.md --mode report --output markdown
lede doc.md --mode report --backend spacy --output markdown
```

```bash
lede doc.md --attach stats,metadata --output json
lede doc.md --attach all --output markdown
```

`brief()` has its own format knob:

```python
brief(text, format="string")
brief(text, format="markdown")
brief(text, format="dict")
```

## Summary knobs

| Knob | Type | Default | Use when |
|---|---|---|---|
| `max_length` / `--max-chars` | int | `500` | Control extractive body size. |
| `mode` | `"default"`, `"coverage"`, `"legacy"` | `"default"` | Use `coverage` for multi-paragraph docs; `legacy` only for old snapshot compatibility. |
| `attach` / `--attach` | list | `None` | Need structured fields in the same call. |
| `keep_headings` / `--keep-headings` | bool | `False` | Headings should survive extraction. |
| `include_toc` / `--include-toc` | bool | `False` | Need a section list prepended. |
| `pin` / `--pin` | list[str] | `None` | Force exact lines into output. |
| `headings` / `--heading`, `--headings-file` | list[str] | `None` | You already know heading text or auto-detection misses it. |

Pinned headings, TOC, and `pin` lines are added on top of `max_length`; they do
not consume the summary body budget.

## Hint knobs

Hints bias ranking toward specific terms or phrases. Use them for targeted
summaries, question-focused previews, and extracting facts about a known topic.

```python
summarize(text, hints=["pricing", "competitor"], hint_focus=0.8)
key_facts(text, hints={"latency": 2.0, "cache": 1.0}, hint_mode="hard")
top_terms(text, hints=["security"], hint_mode="soft", with_scores=True)
```

```bash
lede doc.md --hint pricing --hint competitor --hint-focus 0.8
lede doc.md --mode key_facts --hint-weight "latency=2.0,cache=1.0" --hint-mode hard
```

| Knob | Meaning |
|---|---|
| `hints` / `--hint`, `--hints` | List of terms or phrases. |
| `hint_focus` / `--hint-focus` | Fraction of budget reserved for hint-matching candidates. |
| `hint_mode="soft"` | Bias matching candidates upward; still allows non-matches. |
| `hint_mode="hard"` | Restrict the hint pool to candidates with a hint match. |
| `--hint-weight TERM=WEIGHT` | Weighted hint dictionary from the CLI. |

Core hint matching is case-insensitive and word-boundary delimited. It does not
stem, lemmatize, strip accents, or normalize Unicode.

## spaCy and hint expansion

Install:

```bash
pip install lede-spacy
python -m spacy download en_core_web_sm
```

Python:

```python
import lede_spacy
from lede.extract import metadata
from lede_spacy import expand_hints

metadata(text, backend="spacy")  # entities populated
hints = expand_hints(["counties"], kinds=("lemma",))
summarize(text, hints=hints)
```

CLI:

```bash
lede doc.md --mode metadata --backend spacy --output json
lede doc.md --hint counties --expand-hints lemma
```

Expansion kinds:

| Kind | Requires | Notes |
|---|---|---|
| `lemma` | `lede-spacy` + spaCy model | Adds lemmatized forms. |
| `synonyms` | `lede-spacy[synonyms]` | WordNet synonyms via nltk. |
| `similar` | vector model such as `en_core_web_md` | Uses spaCy word vectors. |

spaCy output is Python-only and not part of the Python ↔ Rust byte-identity
contract.

## Backend selector

Backends apply to `metadata`, `phrases`, and `correlate_facts`.

| Backend | Behavior |
|---|---|
| `regex` | Default, zero-dep, parity with Rust. |
| `spacy` | Requires importing/installing `lede_spacy`; adds NER/noun chunks/dep parse. |
| `auto` | Use spaCy if registered, otherwise regex. |

Python:

```python
import lede_spacy
import lede

lede.set_default_backend("auto")
metadata(text)  # spaCy if registered, regex otherwise
metadata(text, backend="regex")  # per-call override
```

CLI:

```bash
lede doc.md --mode metadata --backend auto --output json
```

## Extraction primitive knobs

| Primitive | Important knobs |
|---|---|
| `stats` | `convert_word_names=True` recognizes spelled-out numbers; requires `lede[wordforms]`. |
| `key_facts` | `max_facts`, `convert_word_names`, all hint knobs. |
| `metadata` | `backend`. |
| `phrases` | `keywords`, `backend`, all hint knobs on regex backend. |
| `correlate_facts` | `backend`, `convert_word_names` on regex backend, all hint knobs on regex backend. |
| `top_terms` | `n`, `kinds=("words", "phrases")`, `with_scores`, all hint knobs. |
| `brief` | `overview_max`, `max_facts`, `include_phrases`, `format`, all hint knobs. |

## Recommended agent patterns

RAG chunk metadata:

```python
r = summarize(chunk, max_length=500, attach=["stats", "metadata", "outline"])
payload = r.to_dict()
embed_text = r.summary
```

Question-focused compression:

```python
r = summarize(doc, max_length=800, hints=query_terms, hint_focus=0.8)
```

User-visible report:

```python
report = summarize(doc, attach=["stats", "metadata"], keep_headings=True).to_markdown()
```

Shell pipeline:

```bash
cat tool-output.txt | lede --mode brief --output json
```

## Caveats

- lede is extractive. It quotes source sentences; it does not synthesize.
- Use JSON for tool-to-tool communication; use Markdown for final human reports.
- The regex backend is the deterministic parity path. spaCy and TextRank are
  Python-only optional paths.
- `legacy` mode rejects hints, heading retention, TOC, pins, and caller-supplied
  headings.
- `top_terms` is Python-only in the current 0.4 series.
