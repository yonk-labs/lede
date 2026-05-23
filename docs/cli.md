# lede CLI Reference

The Python package installs a `lede` command. It reads a UTF-8 file path or
stdin and writes to stdout. Text output is the default; Markdown and JSON are
first-class output modes.

```bash
lede [FILE] --mode MODE [OPTIONS]
cat doc.md | lede --mode key_facts --output json
```

## Output formats

```bash
lede doc.md --output text       # default
lede doc.md --output markdown   # renderable report
lede doc.md --output json       # machine-readable payload
```

For summaries, JSON is the full `SummaryResult`: `summary`, optional
attachments, and `pinned_headings`. For extraction modes, JSON is the native
primitive result converted to plain lists/dicts.

## Summary modes

```bash
lede doc.md                         # same as --mode tfidf
lede doc.md --mode coverage         # paragraph-aware selection
lede doc.md --mode legacy           # old scorer, frozen for compatibility
lede doc.md --max-chars 1200
```

Attachments ride along in one pass:

```bash
lede doc.md --attach stats,metadata --output json
lede doc.md --attach all --output markdown
```

`--attach all` expands to `stats`, `outline`, `metadata`, `phrases`, and
`correlated_facts`.

## Hints

Hints bias ranking toward terms you care about.

```bash
lede doc.md --hint "pricing" --hint "competitor"
lede doc.md --hints "pricing,competitor" --hint-focus 0.8
lede doc.md --hint-weight "pricing=2.0,competitor=1.0" --hint-mode hard
```

Use `--expand-hints` when `lede-spacy` is installed:

```bash
lede doc.md --hint counties --expand-hints lemma
lede doc.md --hint county --expand-hints lemma,synonyms
lede doc.md --hint county --expand-hints similar --vector-model en_core_web_md
```

## Headings and pins

```bash
lede doc.md --keep-headings
lede doc.md --include-toc
lede doc.md --pin "Figure 3: Q3 revenue by region"
lede doc.md --keep-headings --heading "OPINION OF THE COURT" --heading "HELD"
lede doc.md --include-toc --headings-file headings.txt
```

Pinned content is added on top of `--max-chars`; the character budget governs
only the extractive body.

## Brief mode

```bash
lede doc.md --mode brief
lede doc.md --mode brief --output markdown
lede doc.md --mode brief --output json --include-phrases --max-facts 5
```

`brief` composes summary + key facts + table of contents. JSON maps to the
library's `brief(format="dict")`.

## Report mode

`report` is the human-readable combined mode. It produces:

- a 2000-character lede summary by default,
- headings and TOC retained,
- lede key facts, stats, and metadata,
- structured metadata candidates from obvious `Label: value` fields,
- compact important detail records in text/Markdown,
- promotion candidates with stable JSON paths in JSON output,
- spaCy entities, noun phrases, and entity-fact links only when requested with `--backend spacy` or `--backend auto`.

```bash
lede doc.md --mode report --output markdown
lede doc.md --mode report --backend spacy --output markdown
lede doc.md --mode report --backend spacy --output text
lede doc.md --mode report --backend spacy --output json
```

For metadata-aware ingest, prefer JSON. Text and Markdown include compact
facts/details for humans, while JSON keeps verbose machine-only fields such as
full `fact_records` and `promotion_candidates`.

```bash
lede doc.md --mode report --output json
```

The JSON includes `attributes`, `fact_records`, `promotion_candidates`, and
`search_text`. For example, `**Term:** 2023` becomes
`attributes.term.value == "2023"` and a promotion candidate at
`lede_report.attributes.term.value`.

Useful knobs:

```bash
lede doc.md --mode report --max-chars 3000 --max-facts 60
lede doc.md --mode report --backend regex      # explicit lede-only report
lede doc.md --mode report --heading "OPINION OF THE COURT"
```

API equivalent:

```python
from lede import readable_report

r = readable_report(text, max_length=2000, max_facts=40)
r.to_markdown()
r.to_text()
r.to_json()

with_spacy = readable_report(text, max_length=2000, max_facts=40, backend="spacy")
```

## Extraction modes

```bash
lede doc.md --mode stats
lede doc.md --mode key_facts --max-facts 5
lede doc.md --mode metadata --output json
lede doc.md --mode outline --output markdown
lede doc.md --mode toc
lede doc.md --mode phrases
lede doc.md --mode correlate_facts
lede doc.md --mode top_terms --top 20 --scores
```

`facts` is an alias for `key_facts`.

## spaCy backend

Install:

```bash
pip install lede-spacy
python -m spacy download en_core_web_sm
```

Use:

```bash
lede doc.md --mode metadata --backend spacy --output json
lede doc.md --mode phrases --backend spacy
lede doc.md --mode correlate_facts --backend spacy --output markdown
```

`--backend auto` uses spaCy when registered and falls back to regex. `--use-spacy`
is a shortcut for `--backend spacy`.

## Utilities

```bash
lede raw.md --mode clean_text
echo "<think>notes</think>Visible answer." | lede --mode strip_think
lede notes.txt --mode keyword --keywords "pricing budget" --top 3
```

## Python equivalents

```python
from lede import summarize
from lede.extract import key_facts, metadata, top_terms

r = summarize(text, attach=["stats", "metadata"], hints=["pricing"])
r.to_markdown()
r.to_json()

key_facts(text, max_facts=5, hints=["latency"])
metadata(text, backend="spacy")
top_terms(text, n=20, with_scores=True)
```
