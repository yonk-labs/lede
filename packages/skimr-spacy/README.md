# skimr-spacy

spaCy-powered enrichment backend for [skimr](https://github.com/yonk-labs/skimr).
Registers itself as the `"spacy"` backend for skimr's enrichment primitives on
import.

**Python-only. Output is not identical to skimr's zero-dep regex path and is
not portable across runtimes** (see skimr's spaCy integration spec for the
cross-language policy).

## Install

```bash
pip install skimr-spacy
```

Installs `skimr`, `spacy>=3.8,<3.9`, and the pinned `en_core_web_sm` 3.8.0
model in one step. No separate `python -m spacy download` required.

## Use

```python
import skimr_spacy  # side-effect: registers 'spacy' backend into skimr
from skimr.extract import metadata, phrases

m = metadata("Sarah Jones visited Johnson Education Co.", backend="spacy")
# m.entities == ('Sarah Jones', 'Johnson Education Co')
# m.dates / m.amounts / m.urls populated identically to backend="regex"

# phrases() also accepts backend="spacy" — uses doc.noun_chunks for
# syntactically-grounded noun phrases instead of the regex n-gram emitter.
p = phrases(
    "The customer support team evaluated the deployment pipeline. "
    "The deployment pipeline is critical to the customer support team.",
    backend="spacy",
)
```

The `regex` and `spacy` phrase backends are **not byte-identical by design**:
the regex backend emits every 2–5 token contiguous n-gram within non-stopword
runs, while spaCy returns syntactically grounded noun phrases — typically
fewer, larger, and more meaningful. Both satisfy the same API contract.

Or set the backend once:

```python
import skimr
import skimr_spacy
skimr.set_default_backend("auto")  # spaCy if imported, else regex
```

Pre-load the model to avoid a ~50ms first-call cost:

```python
from skimr_spacy import warmup
warmup()
```

## Scope

Day one: entity extraction for `metadata()`. Phrase extraction for
`phrases()` and dep-parsed fact correlation for `correlate_facts()` land
alongside those primitives in the skimr core plan.
