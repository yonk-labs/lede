# lede-spacy

spaCy-powered enrichment backend for [lede](https://github.com/yonk-labs/lede).
Adds proper named-entity recognition (PERSON / ORG / GPE) and richer
phrase / fact extraction by registering itself as the `"spacy"` backend
for `lede.extract.metadata`, `lede.extract.phrases`, and
`lede.extract.correlate_facts`.

| | regex backend (default in `lede`) | spaCy backend (this package) |
|---|---|---|
| Entities (PERSON / ORG / GPE) | always empty | populated from `en_core_web_sm` |
| Phrases | repeated multi-word n-grams | syntactically-grounded noun chunks (still count-filtered) |
| Correlate facts | regex pattern → entity↔number | dependency-parse → wider net of entity↔number relationships |
| Latency | sub-millisecond | ~5 ms after warmup, ~50 ms first call (model load) |
| Determinism | byte-identical Python ↔ Rust | spaCy is deterministic but Python-only and not byte-comparable to Rust |
| Install footprint | stdlib only | `spacy>=3.8` + `en_core_web_sm` (~50 MB model) |

## When you actually want this

lede's regex backend covers the majority of structured-extract use cases for
free — dates, amounts, URLs, numeric facts with sentence context, and
repeated-phrase mining all work with zero dependencies. **You want
lede-spacy specifically when you need named entities** — people,
companies, places — pulled out of arbitrary text. That's where the regex
backend explicitly returns nothing.

You also get richer `correlate_facts` (the dep-parser walks the syntax
tree to find entity↔number relationships even for entities mentioned
once, where the regex backend requires repetition).

## Side-by-side: the same input, both backends

```python
from lede.extract import metadata
import lede_spacy  # side effect: registers the 'spacy' backend
```

The text:

> Acme Corp announced today a partnership with Yonk Labs to integrate
> deterministic summarization into their RAG pipeline. The deal,
> brokered by CEO Lin Wu and signed in San Francisco on 2024-11-15,
> covers $2.4M in annual licensing through 2027. Sarah Jones from
> Acme's engineering team and Marcus Chen from Yonk Labs will lead
> the joint integration. The first deployment is targeted for European
> customers, including teams in London, Berlin, and Paris.

### `backend="regex"` (lede default — zero-dep)

```python
m = metadata(text)
m.dates     # ('2024-11-15', '2027')
m.amounts   # ('$2.4M',)
m.urls      # ()
m.entities  # ()    ← regex backend returns nothing here
```

The regex backend caught the structured stuff (ISO date, year, dollar
amount). It can't do entities — that's not a regex job.

### `backend="spacy"` (this package)

```python
m = metadata(text, backend="spacy")
m.dates     # ('2024-11-15', '2027')        — same regex stage runs
m.amounts   # ('$2.4M',)                    — same regex stage runs
m.urls      # ()                            — same regex stage runs
m.entities  # ('Acme Corp', 'Yonk Labs', 'RAG', 'Lin Wu',
            #  'San Francisco', 'Sarah Jones', 'Acme',
            #  'Marcus Chen', 'London', 'Berlin', 'Paris')
```

11 entities pulled out of the same input. PERSON ('Lin Wu', 'Sarah
Jones', 'Marcus Chen'), ORG ('Acme Corp', 'Yonk Labs', 'Acme', 'RAG'),
GPE ('San Francisco', 'London', 'Berlin', 'Paris'). The dates / amounts /
URLs columns are unchanged — spaCy backend runs the same regex stages
*plus* the spaCy NER stage on top.

### Use case: `correlate_facts` finds different relationships

For some inputs the two backends produce *different but overlapping* fact
relationships. From the same paragraph above:

```python
correlate_facts(text)                        # regex: 2 pairs anchored on Acme Corp
correlate_facts(text, backend="spacy")       # spaCy: 4 pairs, also catches Yonk Labs and customer churn
```

The dep-parser approach catches relationships the regex misses,
especially for entities that appear once. (And vice versa — sometimes the
regex backend catches a pattern the dep-parser doesn't. The two are
complementary, not strictly better/worse. Switch backend per call if you
need it.)

## Use this when…

- Your callers want **PERSON / ORG / GPE entities** in the output. Default lede can't help.
- You want richer entity-number correlations on documents where each entity is mentioned once.
- You're already running spaCy in your pipeline and want to consolidate.
- Latency budgets are in the 5–50 ms range per chunk, not sub-millisecond.

## Don't use this when…

- You need **byte-identical Python ↔ Rust output**. spaCy is Python-only and isn't on the parity contract.
- You're on a sub-millisecond hot path. spaCy is ~5 ms per call after warmup, ~50 ms first call.
- You don't actually need entities. The default lede regex backend already handles dates / amounts / URLs / numeric facts with sentence context.
- You're shipping lede inside a constrained environment (Lambda cold-start, embedded, no-egress) — the 50 MB `en_core_web_sm` model has real cost.
- You can't tolerate spaCy's transitive dependency graph (NumPy, Cython, blis, thinc, etc.) in your env.

## Install

```bash
pip install lede-spacy
python -m spacy download en_core_web_sm
```

The first command pulls `lede` and `spacy>=3.8,<3.9`. The second pulls
the ~50 MB `en_core_web_sm` 3.8.0 model. PyPI does not allow direct-URL
dependencies, so the model is a separate install step (the same
convention spaCy itself uses).

If you want a single reproducible install, pin the model wheel from
`requirements.txt`:

```
lede-spacy==0.4.3
https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl
```

From source (in the lede repo):

```bash
pip install -e packages/lede-spacy
python -m spacy download en_core_web_sm
```

## Use

```python
import lede_spacy            # side-effect: registers the "spacy" backend
from lede.extract import metadata, phrases, correlate_facts

# Per-call backend override:
m = metadata(text, backend="spacy")

# Or set the global default once:
import lede
lede.set_default_backend("auto")   # spaCy if registered, else regex
```

Pre-load the model once at startup to avoid the ~50 ms first-call model
load:

```python
from lede_spacy import warmup
warmup()
```

## Performance

| call | latency (typical) |
|---|---|
| First call (cold model) | 50–80 ms |
| Subsequent calls (warm) | ~5 ms |
| Default lede regex backend (for comparison) | <1 ms |

Run `from lede_spacy import warmup; warmup()` at app startup to pay the
50 ms once instead of on the first user request.

## What's registered

When you `import lede_spacy`, three backends register themselves into
`lede.extract._backends`:

| lede primitive | spaCy backend |
|---|---|
| `metadata(text, backend="spacy")` | runs regex `dates`/`amounts`/`urls` + spaCy NER for `entities` |
| `phrases(text, backend="spacy")` | `doc.noun_chunks` filtered to repeated multi-word chunks (matches the regex backend's count semantics) |
| `correlate_facts(text, backend="spacy")` | DepMatcher-based entity↔number pairing |

The `regex` backend stays the default — `import lede_spacy` is purely
additive. Existing callers using `backend="regex"` (or no `backend=`
kwarg) see no behavior change.

## Expanding hints (v0.4)

`expand_hints()` widens a hint list with related terms so lede's hint biasing
casts a broader net. Three kinds:

| `kind` | Source | Extra install |
|---|---|---|
| `"lemma"` (default) | spaCy lemmatizer | none — uses `en_core_web_sm` already required |
| `"synonyms"` | WordNet via nltk | `pip install lede-spacy[synonyms]` |
| `"similar"` | spaCy word vectors | `en_core_web_md` or `_lg` model |

```python
from lede import summarize
from lede_spacy import expand_hints

hints = expand_hints(["counties"], kinds=("lemma", "synonyms"))
# → ["counties", "county", "parish", "borough", "shire", ...]

result = summarize(text, hints=hints, hint_focus=0.7).summary
```

`expand_hints` is Python-only; the Rust crate has no equivalent.

## Determinism + parity

spaCy is deterministic per-version: `en_core_web_sm` 3.8.0 produces the
same entities for the same input on every call. **It is not on lede's
Python ↔ Rust parity contract**, by design. The Rust port has no spaCy
equivalent and `Metadata.entities` stays empty under any Rust call. See
[`docs/lede-spacy-integration.md`](https://github.com/yonk-labs/lede/blob/main/docs/lede-spacy-integration.md)
for the cross-language policy.

If you need NER from a Rust service today: call out to a Python
lede-spacy worker, or to a hosted NER endpoint. A future
`lede-rust-ner` companion crate is on the roadmap if there's demand —
file an issue.

## License

Apache-2.0, same as lede.
