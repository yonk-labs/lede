# lede — runnable examples

Each script is self-contained — drop into a fresh lede install and run.
None of them require optional extras unless explicitly noted.

## Setup

```bash
pip install lede
git clone https://github.com/yonk-labs/lede.git    # only needed to access the example scripts
cd lede
```

## Examples

| Script | What it shows | Extras needed |
|---|---|---|
| [`01_quickstart.py`](01_quickstart.py) | The 30-second tour: `summarize`, `clean_text`, `strip_think`, `extract_keyword`. | none |
| [`02_rag_prep.py`](02_rag_prep.py) | The v0.2 differentiator: one `summarize(attach=…)` call returns a summary plus structured stats / outline / metadata / phrases / correlated facts in sub-5 ms. | none |
| [`03_brief.py`](03_brief.py) | `lede.brief()` — paste-ready document brief in `string`, `markdown`, and `dict` formats. | none |
| [`04_extract_primitives.py`](04_extract_primitives.py) | Calling each `lede.extract.*` primitive standalone. | none |
| [`05_chunked_pipeline.py`](05_chunked_pipeline.py) | Recommended pattern for documents > 100 KB: paragraph-chunk → lede → reassemble. | none |
| [`06_with_spacy_entities.py`](06_with_spacy_entities.py) | Optional `lede-spacy` companion — adds `Metadata.entities` (PERSON / ORG / GPE) via spaCy. | `pip install lede-spacy && python -m spacy download en_core_web_sm` |
| [`07_wordforms_numbers.py`](07_wordforms_numbers.py) | Optional `[wordforms]` extra — `"five thousand documents"` surfaces as a `Stat`. | `pip install "lede[wordforms]"` |
| [`08_hints.py`](08_hints.py) | v0.4 hints: bias summarize, brief, key_facts, and phrases toward specific terms. Demos soft vs. hard hint modes. | none |
| [`09_top_terms.py`](09_top_terms.py) | v0.4 `extract.top_terms` primitive — return top-N salient single words and phrases, with optional hint-biased reranking. | none |

## Running

```bash
python examples/01_quickstart.py
python examples/02_rag_prep.py
# ...etc
```

Each example prints its output to stdout and exits 0 on success. They're
also run by CI to ensure they don't drift from the API.
