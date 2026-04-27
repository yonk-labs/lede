# skimr — runnable examples

Each script is self-contained — drop into a fresh skimr install and run.
None of them require optional extras unless explicitly noted.

## Setup

```bash
git clone git@github.com:yonk-labs/skimr.git
cd skimr
pip install -e .
```

## Examples

| Script | What it shows | Extras needed |
|---|---|---|
| [`01_quickstart.py`](01_quickstart.py) | The 30-second tour: `summarize`, `clean_text`, `strip_think`, `extract_keyword`. | none |
| [`02_rag_prep.py`](02_rag_prep.py) | The v0.2 differentiator: one `summarize(attach=…)` call returns a summary plus structured stats / outline / metadata / phrases / correlated facts in sub-5 ms. | none |
| [`03_brief.py`](03_brief.py) | `skimr.brief()` — paste-ready document brief in `string`, `markdown`, and `dict` formats. | none |
| [`04_extract_primitives.py`](04_extract_primitives.py) | Calling each `skimr.extract.*` primitive standalone. | none |
| [`05_chunked_pipeline.py`](05_chunked_pipeline.py) | Recommended pattern for documents > 100 KB: paragraph-chunk → skimr → reassemble. | none |
| [`06_with_spacy_entities.py`](06_with_spacy_entities.py) | Optional `skimr-spacy` companion — adds `Metadata.entities` (PERSON / ORG / GPE) via spaCy. | `pip install -e packages/skimr-spacy && python -m spacy download en_core_web_sm` |
| [`07_wordforms_numbers.py`](07_wordforms_numbers.py) | Optional `[wordforms]` extra — `"five thousand documents"` surfaces as a `Stat`. | `pip install -e ".[wordforms]"` |

## Running

```bash
python examples/01_quickstart.py
python examples/02_rag_prep.py
# ...etc
```

Each example prints its output to stdout and exits 0 on success. They're
also run by CI to ensure they don't drift from the API.
