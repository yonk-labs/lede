# Spec: where (and whether) spaCy fits in skimr

**Status:** Decision pending. Local-only T9 commit `7341132` parked — not pushed.
**Author:** Claude (drafted at human request, 2026-04-21)
**Scope:** Decide the architectural home for spaCy in the skimr ecosystem. Does not decide whether to use it — only where.

## The question

Should spaCy live inside the `skimr` package (gated by a `[ner]` extra), inside a sibling companion package, or not at all? And what does skimr need to expose either way?

## Context

skimr's existing contract (`CLAUDE.md`, mission brief):

- Zero required runtime deps on the core extractive path.
- Deterministic, cross-language byte-identical output between Python and Rust for the core algorithms.
- "LLM/neural summarization is out of core forever (companion package at most)."

The last line is the constraint to reckon with. spaCy is a neural NLP pipeline (statistical taggers + CNN parser + NER model). Not a generative LLM, but a neural processor — and the model is ~12 MB of weights that run inference per document.

## What spaCy could actually do in skimr

Before picking a home, be concrete about which primitives would benefit. Cross-referencing v0.2 plan tasks:

| Primitive | spaCy capability | Would it help? | Plan design |
|---|---|---|---|
| `summarize()` sentence split | `Sentencizer` | Marginally; regex already covers the 95% case | Regex, frozen for Rust parity |
| `summarize()` tokenize | `Tokenizer` | Marginally; `\b[a-z]{3,}\b` is sufficient | Regex, frozen for Rust parity |
| `summarize()` scoring | Word vectors, embeddings | Yes, but kills determinism | TF-IDF + position + length, frozen |
| `extract.outline()` | Nothing specific | No | Regex heading detection, shipped in T6 |
| `extract.stats()` | `Matcher`-based number/date extraction | Overlaps regex; not meaningfully better | Regex, shipped in T7 |
| `extract.metadata().dates/amounts/urls` | `Matcher` | Marginally; regex is fine | Regex, shipped in T8 |
| **`extract.metadata().entities`** | **NER (`doc.ents`)** | **Yes, materially. Hard to match with regex.** | Field exists, empty by design; T9 populates |
| `extract.phrases()` (T10) | `noun_chunks` + scoring | **Yes, materially.** See below. | Regex (runs of non-stopword tokens) for baseline |
| `extract.correlate_facts()` (T11) | Dependency parser | **Yes, materially.** See below. | Regex proximity + cue words for baseline |

**Revised conclusion:** spaCy would augment THREE primitives, not one. The first-pass analysis underestimated T10 and T11 because the plan locked them into regex-only from the start, but that was a parity-motivated choice — not a "regex is sufficient" choice. On quality, spaCy beats the regex baseline for all three.

This broadens the scale of the question. We are debating a real NLP enhancement layer, not a one-field fill-in.

### Why spaCy helps T10 and T11

**T10 `extract.phrases()`**. The plan heuristic — "runs of non-stopword tokens length 2-5 that appear >1 time" — is a crude surrogate for key-phrase extraction. It catches `"vector database"` but misses `"the new pipeline"` (because `new` may or may not be a stopword), conflates plural/singular forms, and produces garbage n-grams whenever stopwords cluster unusually.

- **spaCy alternative:** `doc.noun_chunks` yields syntactically valid noun phrases (`"the new pipeline"`, `"the ingest path"`, `"data loss during cutover"`) directly. Combined with frequency scoring, gives much cleaner output.
- **Pure-Python alternative:** RAKE or YAKE. Both are deterministic, stdlib-only, and extract real key phrases using co-occurrence/statistical features. RAKE scores phrases by degree/frequency of co-occurring non-stopword words. YAKE uses casing + position + term frequency + relatedness. Either would beat the plan's "runs-of-tokens" heuristic on quality without going neural.
- **Three-way choice for T10:** (1) plan heuristic — trivial, low quality, Rust-parity trivial; (2) RAKE/YAKE — deterministic, better quality, Python-only (no Rust parity); (3) spaCy noun_chunks — best quality, neural, Python-only.

**T11 `extract.correlate_facts()`**. Plan: pair each `Stat` with the nearest phrase in the same sentence. Polarity via cue-word regex (`grew`, `declined`, `fell`). This is rough: it loses negation (`"Revenue didn't grow"` reads as growth), misses subject-object relationships (`"Revenue grew while costs fell 5%"` may incorrectly pair `costs` with `Revenue`), and can't resolve pronouns.

- **spaCy alternative:** dependency parser identifies the SUBJECT of the verb whose OBJECT is the number. `"Revenue grew 23%"` → `nsubj(revenue, grew)`, `obj(23%, grew)` — direct, principled pairing. Negation is a labeled edge in the dep tree (`neg`), so polarity handling becomes robust. Coreference resolution is not in `en_core_web_sm` by default, but `en_core_web_trf` adds it if we upgrade.
- **Pure-Python alternative:** not really. Without a parser you're stuck with proximity heuristics plus cue-word regex. Quality ceiling is low.
- **Two-way choice for T11:** (1) plan heuristic — rough; (2) spaCy dep parser — much better, Python-only.

### Augmentation vs. replacement

The right framing is **augmentation, not replacement**. skimr's core keeps the regex baselines (so the zero-dep path still works). The companion package provides drop-in higher-quality implementations of the same three primitives. Users opt in:

- Zero-dep install: regex baseline for entities (empty), phrases (token runs), correlate (proximity + cue words).
- Companion install: spaCy-powered NER for entities, noun_chunks + scoring for phrases, dep-parsed triples for correlate_facts.

This is what "don't reinvent the wheel" means in practice — not "replace skimr with a spaCy wrapper," but "let spaCy power the enrichments where it materially helps, while preserving the deterministic regex path for users who need it."

## What NER buys us that regex can't

Rough quality ceiling for a regex-heuristic entity extractor (capitalized-word sequences + org-suffix gazetteer like "Inc/LLC/Corp" + place-name gazetteer):

- Precision ~70% on news text
- Recall ~60% on news text
- Fails on multi-word orgs like "Johnson Education Co" (misses "Education" as part of the span)
- False-positives on sentence-initial capitalization ("The", "Revenue", etc.)
- No distinction between PERSON/ORG/GPE without a full gazetteer

spaCy `en_core_web_sm`:

- F1 ~85–90% on well-edited prose
- Handles multi-word entities and unknown org/person names
- Labels PERSON/ORG/GPE/LOC/PRODUCT correctly most of the time

The delta is material for a RAG-prep primitive where entity accuracy directly affects downstream retrieval. "Don't reinvent the wheel" is the right instinct here — a regex gazetteer won't come close.

## The backend-selector pattern (orthogonal to placement)

Before picking a placement, notice that the choice of **where spaCy lives** is independent of **how the user picks it**. The user's intuition — "a setting: use spaCy vs use regex" — is the right UX primitive, and it works under any of the placement options below. The setting pattern looks roughly like:

```python
from skimr.extract import metadata, phrases, correlate_facts

# Per-call override (always available, explicit):
m = metadata(text, backend="regex")   # force regex baseline
m = metadata(text, backend="spacy")   # raises ImportError if spaCy layer not installed
m = metadata(text, backend="auto")    # spaCy if available, else regex

# Global default (set once):
import skimr
skimr.set_default_backend("spacy")    # or "regex", or "auto"
m = metadata(text)                    # uses the default
# Per-call still wins:
m = metadata(text, backend="regex")   # forces regex even when default is spaCy
```

Three backend values:

- `"regex"` — the deterministic zero-dep path. Always works. `entities=()`, phrases via token-run heuristic, correlate via proximity.
- `"spacy"` — the neural path. Requires spaCy layer installed. NER populates entities, noun_chunks populate phrases, dep-parsed triples populate correlate_facts.
- `"auto"` (default): `"spacy"` if the layer is importable, else `"regex"`. Graceful degradation.

Starting default is worth deciding up front — `"auto"` is friendliest, `"regex"` best honors the zero-dep founding identity. I'd recommend defaulting to `"regex"` and making `"auto"` opt-in via `skimr.set_default_backend("auto")` at process start. Users who want neural get it with one line of setup; the zero-dep promise stays honest for everyone else.

### How the backend dispatch works under each placement

The setting layer is cheap: a registry of backend functions per primitive, populated either by skimr itself (option A) or by an external package registering itself on import (option B).

```python
# src/skimr/extract/_backends.py (sketch)
from typing import Callable

_REGISTRY: dict[str, dict[str, Callable]] = {"regex": {}, "spacy": {}}

def register(backend: str, primitive: str, fn: Callable) -> None:
    _REGISTRY.setdefault(backend, {})[primitive] = fn

def resolve(backend: str, primitive: str) -> Callable:
    if backend == "auto":
        return _REGISTRY["spacy"].get(primitive) or _REGISTRY["regex"][primitive]
    try:
        return _REGISTRY[backend][primitive]
    except KeyError as e:
        raise ImportError(
            f"backend={backend!r} not registered for {primitive}. "
            f"Install skimr-spacy or pip install 'skimr[spacy]'."
        ) from e
```

Under option A, skimr's own `_ner.py` / phrase module / correlate module register themselves into `"spacy"` lazily. Under option B, the companion package does the registration on its own import:

```python
# skimr_spacy/__init__.py (option B)
from skimr.extract._backends import register
from ._ner import extract_entities
from ._phrases import extract_phrases
from ._correlate import correlate_facts
register("spacy", "entities", extract_entities)
register("spacy", "phrases", extract_phrases)
register("spacy", "correlate_facts", correlate_facts)
```

After `import skimr_spacy` once, the `"spacy"` backend is live and `backend="spacy"` / `backend="auto"` work. No monkey-patching, no global surgery — just a registry the user filled by importing the companion.

## Placement options

### A. Inside skimr, gated by `[ner]` extra

What the current T9 commit does. `src/skimr/extract/_ner.py` ships in the `skimr` distribution; `metadata()` does `from . import _ner` behind a try/except; `pyproject.toml` has `[project.optional-dependencies] ner = ["spacy>=3.8,<3.9", "en-core-web-sm @ ..."]`.

- ✅ One-command install: `pip install "skimr[ner]"`
- ✅ Simple user mental model
- ❌ Neural code lives inside skimr's source tree — violates the "never inside skimr itself" rule as written
- ❌ `skimr.extract._ner` import path is reachable from any skimr install, gated only at the spacy-is-importable level
- ❌ If spaCy releases a major version (4.0) with breaking changes, skimr has to cut a release to keep up

### B. Companion package `skimr-ner`

Separate Python distribution. skimr stays regex-only and exposes a hook for entity injection:

```python
# in skimr core
from typing import Callable, Protocol

class EntityExtractor(Protocol):
    def __call__(self, text: str) -> tuple[str, ...]: ...

def metadata(text: str, *, entity_extractor: EntityExtractor | None = None) -> Metadata:
    entities = entity_extractor(text) if entity_extractor else ()
    return Metadata(dates=..., amounts=..., urls=..., entities=entities)
```

`skimr-ner` (separate package, separate repo or subdir) ships `skimr_ner.extract_entities` and a convenience wrapper:

```python
# in skimr-ner
import skimr_ner  # implements EntityExtractor protocol
from skimr.extract import metadata

m = metadata(text, entity_extractor=skimr_ner.extract_entities)
# or: skimr_ner.configure_global()  if we want implicit wiring
```

- ✅ Honors the rule: zero neural code in skimr itself
- ✅ skimr-ner can iterate independently (new spaCy versions, different backends like stanza/flair)
- ✅ Third parties could ship `skimr-flair`, `skimr-stanza`, `skimr-llmner` on the same protocol
- ❌ Two packages to maintain; extra release overhead
- ❌ Users have to learn the wiring (`entity_extractor=skimr_ner.extract_entities` or a configure step)
- ❌ Slightly more setup friction than option A

### C. No NER anywhere; `Metadata.entities` stays reserved/empty

skimr never ships NER. `Metadata.entities` remains `tuple[str, ...] = ()` as a reserved field. Users who want entities call their own NER and set the field themselves:

```python
m = metadata(text)  # entities=()
user_entities = my_ner_code(text)
m = dataclasses.replace(m, entities=user_entities)
```

- ✅ Purest adherence to the rule
- ✅ Zero maintenance burden on skimr
- ❌ Every user reinvents the wheel — exactly what the user wants to avoid
- ❌ `Metadata.entities` field is dead weight if nobody populates it

### D. Constitution amendment + option A

Keep the current T9 design (`skimr[ner]` extra, `_ner.py` inside skimr) but explicitly amend the "no neural in core" rule to carve out an exception for optional extras. Document: neural models are allowed in skimr's source tree when gated by a PyPI extra and imported lazily via try/except. Run `/constitution --amend` to record the amendment.

- ✅ Ships T9 as-written, no refactoring
- ✅ Rule becomes explicit about the exception rather than being silently violated
- ❌ Dilutes the "zero-dep extractive primitive" identity that skimr was founded on
- ❌ Sets precedent: other neural features (sentence embeddings for better scoring, etc.) can now argue the same exception
- ❌ Downstream users who assumed "skimr is regex-only" have a surprise waiting in the extras

## Recommendation

**Option B (companion package) + the backend-selector pattern above.** Rename from `skimr-ner` to **`skimr-spacy`** to reflect that it covers entities, phrases, and correlate_facts — not just NER.

Reasons:

1. **The rule was written with this exact situation in mind.** "Companion package at most" is the policy; this is the canonical case for it.
2. **The backend-selector pattern gives users the exact "setting" they want** — `backend="regex" | "spacy" | "auto"` — without coupling skimr's source tree to spaCy.
3. **The registry hook costs very little** — one `_backends.py` registry module (~40 lines) plus a `backend` kwarg on three primitives. No runtime dependency.
4. **Extensibility.** Any third party can ship `skimr-stanza`, `skimr-flair`, `skimr-llmner` that register into the same `"spacy"` slot — or new slots like `"stanza"`, `"flair"`. The contract is the registry API.
5. **Honest packaging.** `pip install skimr` keeps the zero-dep promise. `pip install skimr-spacy` pulls skimr + spaCy + en_core_web_sm via the direct-URL pin we already worked out. One command, no monkey-patching.
6. **skimr-spacy can live in this same repo** as `packages/skimr-spacy/pyproject.toml` with its own wheel. Two distributions, one repo. Minimal maintenance overhead.

If the answer is option A or D instead, the T9 commit `7341132` is ready to push (but doesn't have the backend-selector layer yet — we'd still want that). If it's B or C, roll back T9 and restart the work with the skimr-spacy split in mind.

## Proposed shape for option B

### In skimr core (small change)

- New `src/skimr/extract/_backends.py` — the registry sketched above (`register`, `resolve`, `set_default_backend`). ~40 lines.
- `metadata()`, `phrases()`, `correlate_facts()` each gain a `backend: str = "regex"` kwarg. Default is `"regex"` so zero-dep installs behave exactly as today.
- Regex implementations of each primitive register themselves into the `"regex"` slot at module load.
- `skimr.set_default_backend(name)` is the one-line opt-in for users who want `"spacy"` or `"auto"` without passing kwargs everywhere.
- Remove `_ner.py`, remove the `[ner]` extra from `pyproject.toml`, remove NER tests from skimr's own test suite (they move to the companion).
- Keep `Metadata.entities`, `SummaryResult.phrases`, `SummaryResult.correlated_facts` field shapes as-is.

### In new `skimr-spacy` package

- `packages/skimr-spacy/pyproject.toml`: `name = "skimr-spacy"`, `dependencies = ["skimr>=0.2.0.dev0", "spacy>=3.8,<3.9", "en-core-web-sm @ https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl"]`.
- `skimr_spacy/__init__.py` imports the three backend implementations and calls `register("spacy", ...)` for each at module load.
- `skimr_spacy/_ner.py` — PERSON/ORG/GPE/LOC/PRODUCT via `doc.ents`.
- `skimr_spacy/_phrases.py` — `doc.noun_chunks` scored by frequency + first-position heuristic.
- `skimr_spacy/_correlate.py` — walks dep tree to pair subjects with number-valued objects; `neg` edge flips polarity.
- `skimr_spacy/_warmup.py` — exposes `warmup()` so callers can pre-load the model.
- Own test suite in `packages/skimr-spacy/tests/`.

### User-facing install story

```bash
# Zero-dep path (the default). Regex backend only.
pip install skimr

# Neural enrichment included. One command, no separate model download.
pip install skimr-spacy   # pulls skimr + spaCy + en_core_web_sm
```

```python
# Without the companion — always works, always regex
from skimr.extract import metadata
m = metadata(text)
# m.entities == ()  (regex has no entity extractor)
# m.dates/amounts/urls populated as before

# With the companion — user picks the backend
import skimr_spacy  # side-effect: registers "spacy" backends into skimr's registry
from skimr.extract import metadata

m = metadata(text, backend="spacy")   # spaCy NER populates entities
m = metadata(text, backend="regex")   # force the zero-dep path even though spaCy is installed
m = metadata(text, backend="auto")    # spaCy if registered, else regex — good for libraries

# Or set once and forget
import skimr
skimr.set_default_backend("auto")
m = metadata(text)  # uses spaCy if skimr_spacy was imported, else regex

# One-time pre-load to avoid the ~50ms first-call cost
from skimr_spacy import warmup
warmup()
```

## Cross-language implications — Rust and JS

spaCy is Python-only. There is no Rust port and no mainstream JS port of the actual spaCy models. That changes what the `backend=` parameter means across runtimes, and what we promise.

**Policy for cross-language parity under the backend selector:**

- The **`"regex"` backend** continues to honor skimr's byte-identical parity contract across Python, Rust, and any future JS port. This is the only path skimr's tests assert parity on.
- The **`"spacy"` backend is Python-only**. Rust does not gain a `backend=` kwarg on `metadata()` at this time — there is only one backend in Rust, so the parameter would be meaningless. Calling `skimr.extract.metadata(text, backend="spacy")` in Python and the Rust equivalent are not promised to produce the same output.
- Any future runtime-specific neural layer is treated as its **own separate backend**, not a "spaCy equivalent":
  - **JS**: a future companion like `skimr-js-compromise` (using `compromise.js`, rule-based) or `skimr-js-wink` (wink-nlp) would register under a backend label like `"compromise"` or `"wink"`, not `"spacy"`.
  - **Rust**: a future companion using a native crate like `deepfrog` or `lindera` would register under a label like `"native_ner"` or `"deepfrog"`, not `"spacy"`.

This keeps the contract honest: `backend="regex"` is reproducible everywhere; any neural backend name is specific to a runtime and a companion, and we don't pretend two different neural models produce the same output.

**What skimr core must avoid:**

- Do NOT claim the `"spacy"` backend output is stable across skimr versions. spaCy model updates change entity boundaries and labels between `en_core_web_sm` releases.
- Do NOT promise `skimr_spacy.extract_entities(text)` == hypothetical-JS-compromise output. They're different backends by design.
- Do NOT add the `backend=` kwarg to Rust `metadata()` until Rust has a real second backend to offer. A one-option enum is just noise.

**Documentation implication:** the README for skimr-spacy should lead with "Python-only. Output is not identical to the zero-dep regex path and is not portable across runtimes."

## Open questions for the user

1. **In-repo vs separate repo.** Does `skimr-spacy` live at `packages/skimr-spacy/` in this repo (simpler maintenance, shared CI) or at `yonk-labs/skimr-spacy` (stricter decoupling, separate release cadence)?
2. **Default backend.** `"regex"` (safest — zero-dep identity preserved), `"auto"` (friendliest — neural when installed, regex when not), or something else? I lean `"regex"` with `set_default_backend("auto")` as a one-liner opt-in.
3. **Ship the registry hook now, even without the companion?** If yes, v0.2 gets the `backend=` kwarg and registry in skimr core; skimr-spacy ships later. If no, the kwarg and companion ship together as one effort, but skimr entities/phrases/correlate land as regex-only in v0.2.
4. **Scope of skimr-spacy.** All three primitives (entities, phrases, correlate_facts) from day one, or start with entities and add the others later? Entities alone is the minimum viable. Correlate benefits most from dep-parser, so adding it has high ROI.
5. **Constitution.** Option B keeps the "no neural in core" rule intact. If you'd rather go with option A or D, we run `/constitution --amend` to document the exception explicitly.

## What happens next

- You pick A / B / C / D (or a variant).
- I roll back or keep the T9 commit accordingly.
- Plan doc gets the T9 scope rewritten to match.
- RESUME.md reflects the decision.

No code changes on this file's behalf until you pick.
