# lede-enrich/distill

Python distillation harness that runs spaCy `en_core_web_sm` over a corpus of
article text and emits **silver entity labels** as UTF-8 **byte spans**. These
silver labels are consumed by Task 8 (Rust CRF trainer) to train `lede-enrich`'s
NER model.

## Why byte offsets?

Rust string slicing is byte-based (`&str` indices are byte offsets). spaCy
returns character offsets. For ASCII text they coincide, but any non-ASCII
character (accented letters, em-dashes, non-Latin scripts — pervasive in
Wikipedia article text) causes misalignment if char offsets are passed directly
to Rust. The harness converts spaCy's char offsets to UTF-8 byte offsets via:

```python
def to_byte(char_rel: int) -> int:
    return len(stext[:char_rel].encode("utf-8"))
```

This is verified by the smoke test: `sentence_text.encode("utf-8")[start:end].decode("utf-8")`
must recover the exact entity surface form.

## Input format

A JSONL file (one JSON object per line):

```json
{"id": 1, "text": "Full article text here..."}
```

The `id` field is not emitted to the output — only `text` is processed. Source
text is **never committed** to this repository; only the span labels feed the
Rust trainer.

## Output format (`silver.jsonl`)

One JSON object per sentence:

```json
{"text": "<sentence text>", "ents": [{"start": 0, "end": 6, "label": "ORG"}]}
```

- `start` / `end` — sentence-relative UTF-8 **byte** offsets
- `label` — one of the 11 lexical entity types (see `LEXICAL` below)

## The `LEXICAL` set

Only these 11 spaCy entity types are kept (numeric/temporal types are excluded
as noise for lexical NER):

| Label | Description |
|---|---|
| `PERSON` | People, including fictional |
| `NORP` | Nationalities or religious/political groups |
| `FAC` | Facilities (airports, buildings, highways) |
| `ORG` | Organizations |
| `GPE` | Countries, cities, states |
| `LOC` | Non-GPE locations (mountain ranges, bodies of water) |
| `PRODUCT` | Objects, vehicles, foods (not services) |
| `EVENT` | Named events (battles, elections, hurricanes) |
| `WORK_OF_ART` | Titles of books, songs, etc. |
| `LAW` | Named laws and legal documents |
| `LANGUAGE` | Named languages |

## Usage

```bash
# From lede-enrich/distill/
../../.venv/bin/python label_corpus.py \
    --input articles.jsonl \
    --output silver.jsonl \
    [--model en_core_web_sm]
```

## `corpus_manifest.json` (Task 7)

Task 7 produces a `corpus_manifest.json` listing the article IDs and their
bucket assignments from the pinned Wikipedia dump. This file **is committed**
to the repository — it is the reproducibility anchor (spec AC-5): anyone can
regenerate `articles.jsonl` from it using `build_manifest.py` with the same
pinned dump. The `articles.jsonl` derived from the manifest is **not**
committed (source text is never stored in the repo).

## Gitignored outputs

- `*.silver.jsonl` — generated silver labels
- `articles.jsonl` — fetched article text (never committed)
