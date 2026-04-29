# lede ↔ spaCy integration

**Status:** Shipped in v0.3.0. The companion lives at
[`packages/lede-spacy/`](../packages/lede-spacy/) and on PyPI as
[`lede-spacy`](https://pypi.org/project/lede-spacy/).

This doc covers *why the split exists*, *how to use it*, and *how the
backend-selector contract works* for anyone shipping a similar companion
(`lede-stanza`, `lede-flair`, etc.). The source of truth for install +
usage detail is
[`packages/lede-spacy/README.md`](../packages/lede-spacy/README.md) —
this doc is the policy.

## Why spaCy isn't in lede core

lede's founding contract is **zero required runtime dependencies +
byte-identical Python ↔ Rust output on the regex backend**. spaCy can't
satisfy either:

- ~50 MB `en_core_web_sm` model weights aren't zero-dep.
- spaCy is Python-only. No Rust port of the actual models exists, so any
  spaCy-derived output is unreachable from the Rust runtime.
- spaCy pulls NumPy / Cython / blis / thinc into the dep graph — fine
  for a deliberate opt-in, painful for a default install.

But spaCy *materially* improves three of lede's primitives, and the
regex ceiling is real:

| Primitive | Regex backend ceiling | What spaCy adds |
|---|---|---|
| `metadata().entities` | always `()` — regex can't do NER | PERSON / ORG / GPE from `doc.ents` |
| `phrases()` | repeated multi-word n-grams; conflates `"the new pipeline"` with `"new pipeline"` | syntactically-grounded `noun_chunks`, count-filtered |
| `correlate_facts()` | proximity + cue-word regex; fragile on negation and single-mention entities | `DependencyMatcher` walks the parse tree → entity↔number pairs even for once-mentioned entities |

The split lets both populations win: zero-dep callers keep regex;
callers who want NER `pip install lede-spacy`.

## Install

```bash
pip install lede-spacy
python -m spacy download en_core_web_sm
```

The first command pulls `lede>=0.3.0` and `spacy>=3.8,<3.9`. The second
pulls the ~50 MB model. PyPI doesn't allow direct-URL deps, so the model
is a separate step — this is the convention spaCy itself uses.

From source, in this repo:

```bash
pip install -e packages/lede-spacy
python -m spacy download en_core_web_sm
```

## Use

```python
import lede_spacy                          # side-effect: registers "spacy" backend
from lede.extract import metadata, phrases, correlate_facts

# Per-call backend choice
m = metadata(text, backend="spacy")        # spaCy NER populates entities
m = metadata(text, backend="regex")        # forces zero-dep path
m = metadata(text, backend="auto")         # spaCy if registered, else regex

# Or set the process-wide default once
import lede
lede.set_default_backend("auto")
m = metadata(text)                         # uses spaCy if lede_spacy was imported

# Pre-load the model (avoids the ~50 ms first-call hit)
from lede_spacy import warmup
warmup()
```

Latency budget: ~5 ms after warmup, ~50 ms first call (cold model load),
vs sub-millisecond for the regex backend.

For a worked side-by-side example on real prose (11 entities pulled
from one paragraph), see
[`packages/lede-spacy/README.md`](../packages/lede-spacy/README.md#side-by-side-the-same-input-both-backends).

## How the backend selector works

`lede.extract._backends` is a small registry keyed by
`(backend, primitive)`:

```python
# lede core registers the regex baseline on its own import:
register("regex", "metadata",         _regex_metadata)
register("regex", "phrases",          _regex_phrases)
register("regex", "correlate_facts",  _regex_correlate)

# A companion registers itself on its own import
# (packages/lede-spacy/src/lede_spacy/__init__.py):
register("spacy", "metadata",         spacy_metadata)
register("spacy", "phrases",          spacy_phrases)
register("spacy", "correlate_facts",  spacy_correlate_facts)
```

Resolution rules:

- `backend="regex"` — always available (lede itself registers it). This
  is the default.
- `backend="spacy"` — available iff `lede_spacy` was imported in this
  process. Else `ImportError` with a hint to install the companion.
- `backend="auto"` — tries `"spacy"` first, falls back to `"regex"`.
  Good for libraries that want best-available without hard-coding.

`lede.set_default_backend(name)` changes the process-wide default;
per-call `backend=` still wins.

The mechanism is intentionally additive: importing `lede_spacy`
registers without monkey-patching, without modifying `lede.extract`
modules, without surgery on existing call sites. Callers who pass no
`backend=` kwarg see no behavior change.

## Building your own companion

The contract for shipping `lede-stanza`, `lede-flair`, `lede-llmner`,
etc.:

1. Import `lede.extract._backends.register` at package import time.
2. Register one or more `(backend_label, primitive)` pairs. Standard
   primitives are `metadata`, `phrases`, `correlate_facts`; lede core
   may add more later.
3. Each registered fn accepts `(text: str, **opts)` and returns the
   same shape as the regex baseline (`Metadata`,
   `tuple[str, ...]`, `tuple[PhraseFact, ...]`).
4. Ship as a separate distribution; depend on `lede>=0.3.0`.

No coordination with lede core is required to add a new backend label.

## Cross-runtime parity policy

lede's parity contract is per-backend, not per-primitive:

- The **regex** backend is byte-identical across Python and Rust. The
  fixture corpus + walker (`rust/tests/fixtures.rs`) enforces this on
  every CI push.
- The **spacy** backend is **Python-only and not on the parity
  contract**. There is no Rust spaCy port. Calling
  `metadata(text, backend="spacy")` in Python and any Rust call are not
  promised to produce the same output, and they don't.
- Future runtime-specific neural companions register under their own
  labels — a hypothetical `lede-rust-deepfrog` would register as
  `"deepfrog"`, `lede-js-compromise` as `"compromise"`. We don't pretend
  two different neural models produce identical output.

What lede core will not do:

- Claim `"spacy"` backend output is stable across spaCy or model
  versions. `en_core_web_sm` 3.8.0 → 3.9.0 can shift entity boundaries.
- Add a `backend=` kwarg to Rust primitives until Rust has a real second
  backend to dispatch to. A one-option enum is noise.

## See also

- [`packages/lede-spacy/README.md`](../packages/lede-spacy/README.md) —
  full install + usage + worked examples (the user-facing source of truth)
- [`docs/REFERENCE.md`](REFERENCE.md) — primitive type signatures and the
  per-feature runtime parity matrix
- [`src/lede/extract/_backends.py`](../src/lede/extract/_backends.py) —
  the registry implementation, ~70 lines
