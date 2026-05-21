# Hint-biased extraction (v0.4)

**Status:** design approved, awaiting implementation plan
**Date:** 2026-05-21
**Target version:** 0.4.0
**Affected surfaces:** `lede` core (Python + Rust), `lede-spacy` companion

---

## 1. Purpose

Let callers pass a list of *hints* — words or short phrases — that bias
which sentences, facts, phrases, or correlations come out of lede's
ranking primitives. The motivating use case: a caller asks "what
county does John Smith live in?" and wants `summarize` / `key_facts`
to surface the sentences that mention `john`, `smith`, and `county`,
not a generic topical summary.

Hints must be *optional everywhere*. Existing callers who never pass
hints must see byte-identical output to today. This is non-negotiable.

## 2. Backward compatibility promise

When `hints is None` (the default) on every affected primitive, no
new code path executes and the output is byte-identical to v0.3.0.
This is verified by leaving the entire existing test corpus
unchanged. Every fixture in `fixtures/` and every fixture covered by
`every_fixture_byte_identical` and `v0_2_extract_primitives_byte_identical`
continues to pass without modification.

## 3. Scope

### In scope (v0.4)

Hint kwargs (`hints`, `hint_focus`, `hint_mode`) are added to:

- `lede.summarize`
- `lede.brief` (forwards to its internal `summarize` + `key_facts` calls)
- `lede.extract.key_facts`
- `lede.extract.phrases`
- `lede.extract.correlate_facts`

A companion `lede_spacy.expand_hints()` function lives in the
`lede-spacy` package for synonym and lemma expansion. It composes
with core — caller expands, then passes to lede.

### Not in scope (v0.4)

The following are explicitly out of scope and documented as such:

- `lede.extract.outline`, `lede.extract.toc`, `lede.extract.stats`,
  `lede.extract.metadata` — these are descriptive, not ranking.
  They do not gain hint kwargs. If a caller passes hints to one of
  them via `**kwargs`, the kwargs are silently ignored — they do not
  raise.
- Unicode normalization (NFC/NFD), diacritic stripping. `"café"`
  does not match `"cafe"` by design.
- Stemming or lemmatization in core matching. Belongs in
  `expand_hints(kinds=('lemma',))`, not in core.
- Cross-sentence hint propagation.
- Negation-aware hints (`"not John Smith"`).
- Regex hints in the core API. Adds parity risk; callers who want
  this can pre-filter sentences themselves.
- Auto-expansion in core. Stays in `lede-spacy` by policy.
- A diversity-aware overlap penalty between selected sentences.
- Per-primitive `hint_focus` overrides inside `brief()`. v0.4
  forwards a single `hint_focus` to both internal calls. Callers
  who want different values call the primitives directly.

## 4. Public API

### 4.1 `lede.summarize`

```python
def summarize(
    text: str,
    max_length: int = 500,
    *,
    mode: str = "default",
    attach: list[str] | tuple[str, ...] | None = None,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,         # ignored when hints is None
    hint_mode: str = "soft",         # "soft" | "hard"; ignored when hints is None
) -> SummaryResult
```

### 4.2 `lede.brief`

```python
def brief(
    text: str,
    *,
    overview_max: float = 0.35,
    max_facts: int = 10,
    include_phrases: bool = False,
    convert_word_names: bool | None = None,
    format: str = "string",
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
) -> str | dict
```

`brief()` forwards `hints`, `hint_focus`, `hint_mode` unchanged to
its internal `summarize()` and `key_facts()` calls. No bespoke logic.

### 4.3 `lede.extract.key_facts`

```python
def key_facts(
    text: str,
    *,
    max_facts: int = 10,
    convert_word_names: bool = False,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
) -> tuple[str, ...]
```

### 4.4 `lede.extract.phrases`

```python
def phrases(
    text: str,
    keywords: str | None = None,
    *,
    backend: str | None = None,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
) -> tuple[str, ...]
```

### 4.5 `lede.extract.correlate_facts`

```python
def correlate_facts(
    text: str,
    *,
    backend: str | None = None,
    convert_word_names: bool = False,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
) -> tuple[PhraseFact, ...]
```

### 4.6 Argument semantics

`hints`:
- `None` (default) → no new code path runs; output byte-identical to today.
- `list[str]` → every hint has implicit weight 1.0.
- `dict[str, float]` → per-hint weights. Iteration order is irrelevant because the hint-bonus formula is a sum (order-invariant).
- `[]` is treated identically to `None`.

`hint_focus` ∈ `[0.0, 1.0]` — a **budget split**:

| Value | Result |
|---|---|
| `0.0` | Entire budget runs plain composite (hints effectively ignored). |
| `0.5` | Half the budget from the hint pool, half from plain. |
| `0.7` (default) | 70% from hint pool, 30% from plain. |
| `1.0` | Entire budget from the hint pool. |

`hint_mode` ∈ `{"soft", "hard"}`:
- `"soft"` (default) — hint pool uses bonus-augmented ranking. Hint-bearing items usually win but no guarantee. Never fails.
- `"hard"` — hint pool hard-filters to items with ≥1 hint match. At `hint_focus=1.0` this replaces the previously-discussed `require=True` flag.

### 4.7 Validation

- `mode='legacy'` with non-None `hints` → `ValueError("hints not supported in legacy mode")`. Legacy stays frozen.
- `hint_focus` outside `[0.0, 1.0]` → `ValueError`.
- `hint_mode` not in `{"soft", "hard"}` → `ValueError`.
- `hints` not in `{None, list, dict}` → `TypeError`.
- Empty-string or all-whitespace entries in `hints` → silently dropped.

### 4.8 Per-primitive budget unit

| Primitive | Budget unit | Split formula |
|---|---|---|
| `summarize` | chars (`max_length`) | `hint_budget = round_to_int(max_length * hint_focus)`; `normal_budget = max_length - hint_budget` |
| `key_facts` | count (`max_facts`) | `hint_quota = round_to_int(max_facts * hint_focus)`; `normal_quota = max_facts - hint_quota` |
| `phrases` | count (internal cap) | same count split |
| `correlate_facts` | count (internal cap) | same count split |

`round_to_int` is defined in §6.2 as portable integer-math rounding
to avoid Python/Rust divergence on half-values.

## 5. Matching semantics

### 5.1 Preprocessing per hint

1. Strip leading/trailing whitespace.
2. Collapse internal whitespace runs to single space.
3. Lowercase via `str.lower()` (ASCII-safe; identical to the existing `_TOKEN_RE` pipeline in `tfidf.py:58`).
4. Drop hints that are empty after step 1.

### 5.2 Match against a sentence/phrase

1. Lowercase the target text using the same rules as step 3 above.
2. For each hint `h`, count non-overlapping matches of the regex
   `\b{re.escape(h)}\b` against the lowercased target.

### 5.3 Examples

| Hint | Target | Matches |
|---|---|---|
| `"smith"` | `"John Smith lives there"` | 1 |
| `"smith"` | `"the smiths arrived"` | 0 (no token boundary) |
| `"smith"` | `"blacksmith works late"` | 0 (no boundary) |
| `"john smith"` | `"John Smith Sr. is here"` | 1 |
| `"john smith"` | `"John P. Smith arrived"` | 0 (middle initial breaks contiguity) |
| `"O'Brien"` | `"O'Brien arrived"` | 1 (`\b` works at both ends; apostrophe is non-word) |
| `"state-of-the-art"` | `"state-of-the-art design"` | 1 |

### 5.4 Per-primitive match target

- `summarize` / `key_facts`: match against the candidate sentence string.
- `phrases`: match against the phrase string itself (not the source sentence).
- `correlate_facts`: a correlation matches if **either the entity name or the fact value** contains a hint via the standard match. OR-wise.

This rule preserves what each primitive is conceptually about. A
phrase named "Cook County" should rank higher when the user hints
`"county"` even if the source sentence containing that phrase is
otherwise un-hint-bearing.

### 5.5 Documented limitations

- No Unicode normalization. `"café"` ≠ `"café"`.
- No diacritic stripping. `"jose"` does not match `"José"`.
- No stemming. `"smith"` does not match `"smiths"` — use
  `lede_spacy.expand_hints(kinds=('lemma',))` if you want this.

## 6. Scoring math

### 6.1 Constants

```
_HINT_BASE_WEIGHT = 0.5    # per-hint additive bonus unit
_HINT_MATCH_CAP   = 3      # max matches counted per hint per sentence
```

`_HINT_BASE_WEIGHT = 0.5` puts a single hint match roughly between
the existing digit bonus (`+0.3`) and cue-phrase bonus (`+2.0`) in
the default-mode scorer (`tfidf.py:220-228`). A meaningful nudge
without dominating the composite.

`_HINT_MATCH_CAP = 3` borrows BM25 saturation logic: past three
occurrences of the same hint in one sentence, the sentence is
repetitive, not relevant.

### 6.2 Portable integer-math rounding

Python 3's `round` uses banker's rounding (`round(2.5) == 2`); Rust's
`f64::round` uses round-half-away-from-zero (`2.5_f64.round() == 3`).
With `hint_focus=0.5` and odd `max_length`, the two would disagree
on the budget split by one character.

Mitigation: do not use either language's built-in float `round` for
the budget split. Implement `round_to_int(value, focus)` as integer
math, identical in both languages:

```python
# Python reference implementation
def round_to_int(value: int, focus: float) -> int:
    # Represent focus as numerator/10000 to keep deterministic
    num = int(focus * 10000)
    den = 10000
    return (value * num + den // 2) // den
```

```rust
// Rust mirror
fn round_to_int(value: i64, focus: f64) -> i64 {
    let num = (focus * 10000.0) as i64;
    let den: i64 = 10000;
    (value * num + den / 2) / den
}
```

The `focus * 10000` step is the only floating-point op; both
languages produce identical integers for the documented set of
`hint_focus` values (0.0, 0.5, 0.7, 1.0). For arbitrary user-supplied
floats, the rounding to int truncates predictably the same way in
both runtimes (IEEE 754 double semantics are identical).

### 6.3 Hint bonus per sentence

Used in soft mode and as the ranking key inside the hard-filtered pool:

```
hint_bonus(sentence, hints) =
    sum over each hint h:
        min(count_of(h, sentence), _HINT_MATCH_CAP)
            * weight(h)
            * _HINT_BASE_WEIGHT
```

Where `weight(h)` is `1.0` for list inputs and `hints[h]` for dict
inputs. `count_of(h, sentence)` is the §5.2 match count.

### 6.4 Soft-mode score

One pool, no filter:

```
hint_score(i) = default_composite_score(i) + hint_bonus(sentences[i], hints)
```

`default_composite_score` is the existing `_composite_score_default`
(or coverage equivalent). Cue-phrase, digit, section, and
heading-filter bonuses all still apply.

### 6.5 Hard-mode score

Two pools, hard filter on the hint pool:

```
hint_pool_score(i) =
    -inf                  if hint_bonus(sentences[i], hints) == 0
    hint_score(i)         otherwise

plain_pool_score(i) = default_composite_score(i)
```

### 6.6 Two-pool selection algorithm

`greedy_select(score, budget, exclude)` mirrors the existing selector
in `tfidf.py:274-287`: sort indices by `(-score, original_position)`,
then walk the sorted list and accept any sentence whose length fits
in the remaining budget. Indices in `exclude` are skipped. Returns
the set of selected indices.

```
hint_budget   = round_to_int(max_length, hint_focus)
normal_budget = max_length - hint_budget

selected_hint   = greedy_select(hint_pool_score,  hint_budget,   exclude={})
selected_normal = greedy_select(plain_pool_score, normal_budget, exclude=selected_hint)

# Rollover unused budget so we don't leave it on the floor.

unused_hint = hint_budget - chars_used_by(selected_hint)
if unused_hint > 0:
    extra = greedy_select(plain_pool_score, unused_hint,
                          exclude = selected_hint | selected_normal)
    selected_normal |= extra

unused_normal = normal_budget - chars_used_by(selected_normal)
if unused_normal > 0 and hint_mode == "soft":
    # In soft mode, leftover can fall back to the bonus ranking.
    # In hard mode, never roll normal -> hint; hard mode's promise
    # is "at most hint_focus of the budget is non-hint".
    extra = greedy_select(hint_pool_score, unused_normal,
                          exclude = selected_hint | selected_normal)
    selected_hint |= extra

selected = sorted(selected_hint | selected_normal)
return ' '.join(sentences[i] for i in selected)
```

For count-budgeted primitives (`key_facts`, `phrases`,
`correlate_facts`), substitute count for chars throughout. The
algorithm shape is identical.

### 6.7 Edge cases

- `hint_focus = 0.0` → `hint_budget = 0`. The hint pool never runs.
  Output is identical to `hints=None` path.
- `hint_focus = 1.0` → `normal_budget = 0`. Only the hint pool runs.
  In hard mode with zero matches, falls back through the existing
  `_truncate` path (or empty tuple for count-budgeted primitives).
- `_MIN_BUDGET_FOR_SENTENCES` and `_MIN_SENTENCES` checks happen
  before any of the two-pool logic. Small inputs still truncate the
  same way they do today.

### 6.8 Mode interaction

- `mode='default'` and `mode='coverage'` accept `hints`. The coverage
  scorer follows the same two-pool template using its own composite
  as `default_composite_score`.
- `mode='legacy'` rejects `hints` per §4.7.

## 7. `lede-spacy.expand_hints()`

### 7.1 Location

`packages/lede-spacy/src/lede_spacy/_expand.py`, exported from
`lede_spacy/__init__.py` alongside the existing `extract_entities`
and `warmup`.

### 7.2 Signature

```python
def expand_hints(
    hints: list[str] | dict[str, float],
    *,
    kinds: tuple[str, ...] = ("lemma",),
    top_k: int = 5,
    expand_weight: float = 0.5,
) -> list[str] | dict[str, float]:
```

### 7.3 Composition pattern

```python
from lede import summarize
from lede_spacy import expand_hints

hints = expand_hints(["county", "John Smith"], kinds=("lemma", "synonyms"))
result = summarize(text, hints=hints, hint_focus=0.7, hint_mode="soft")
```

lede core does not know expansion happened. The boundary stays
surgical.

### 7.4 Behavior per `kind`

| `kind` | Source | Deps | Behavior |
|---|---|---|---|
| `"lemma"` | spaCy lemmatizer | already required (`spacy>=3.8`, `en_core_web_sm`) | For each hint, tokenize with spaCy, lemmatize each token, rejoin with single spaces, then emit both the original and the lemmatized form. Deduplicated at the end, so a hint whose tokens all lemmatize to themselves (typical for proper nouns) emits a single entry. |
| `"synonyms"` | WordNet via `nltk` | new `[synonyms]` extra: `nltk>=3.8` + WordNet data | For each single-token hint, emit up to `top_k` synonyms. Multi-token hints pass through unchanged. |
| `"similar"` | spaCy word vectors | requires user-installed `en_core_web_md` or `_lg` | For each single-token hint, emit up to `top_k` highest-cosine tokens. Multi-token hints pass through unchanged. |

### 7.5 Type fidelity

- `list[str]` in → `list[str]` out.
- `dict[str, float]` in → `dict[str, float]` out. Expansion terms
  receive `expand_weight * source_weight`. On collision (a term
  generated from multiple sources), the maximum weight wins.

### 7.6 Determinism

- Lemma: spaCy's lemmatizer is deterministic given the model.
- Synonyms: WordNet output sorted by `(synset_position, lemma_name)`
  after dedup. Frozen ordering across runs.
- Similar: sorted by `(-similarity, token_text)`. Deterministic tiebreak.
- Final dedup: casefold-and-strip; first-seen casing preserved.

### 7.7 Errors

- `kinds` contains `"synonyms"` but `nltk` not importable →
  `ImportError("install with: pip install lede-spacy[synonyms]")`
- WordNet data missing → attempt `nltk.download('wordnet', quiet=True)`
  once with a single-line stderr message. If the download fails
  (offline), raise with manual-install instructions.
- `kinds` contains `"similar"` but the loaded model has no vectors →
  `RuntimeError("expand_hints(kinds=('similar',)) requires en_core_web_md or _lg")`
- Unknown `kind` → `ValueError`.
- Empty input → empty output of matching shape.

### 7.8 Caching

- Reuse the spaCy `nlp` instance via the existing lede-spacy warmup.
  No new init path.
- nltk WordNet loads once per process, lazily on first synonyms call.

### 7.9 Parity contract

**None.** lede-spacy is Python-only by policy (CLAUDE.md: "Optional
Python-only backends make no parity promise"). The Rust binary has
no equivalent. Rust callers either expand hints themselves or pass
literal hint lists.

## 8. Cross-runtime parity

### 8.1 The promise

For the **core regex backend** of every affected primitive
(`summarize`, `brief`, `key_facts`, `phrases(backend='regex')`,
`correlate_facts(backend='regex')`), when called with the same
`text`, `hints`, `hint_focus`, `hint_mode`, Python and Rust produce
byte-identical output.

Same rule that governs the existing v0.1 and v0.2 fixture walkers.

### 8.2 Enforcement mechanism

A third gate is added to `rust/tests/fixtures.rs`:

```rust
#[test]
fn v0_4_hints_byte_identical() {
    for fixture in read_fixtures("fixtures/v0_4_hints/") {
        let python_output = fs::read_to_string(&fixture.expected_path)?;
        let rust_output   = lede::summarize_with_hints(...);
        assert_eq!(python_output.as_bytes(), rust_output.as_bytes());
    }
}
```

### 8.3 Fixture generator

`benchmarks/gen_hint_fixtures.py` (modeled on the existing
`benchmarks/gen_parity_fixtures.py`) emits fixture pairs covering:

- Empty/None hints (must equal the no-hints output — backward-compat sanity check).
- Single-token soft, single-token hard.
- Phrase soft, phrase hard.
- Multiple hints with list and dict shapes.
- `hint_focus` at `0.0`, `0.5`, `0.7`, `1.0`.
- Rollover cases: hard mode with zero matches; soft mode with full budget spillover.
- Edge: cap saturation (sentence with 5+ occurrences of one hint).

### 8.4 Not parity-promised

- `phrases(backend='yake')` with hints — yake is an opt-in extra
  with no parity contract today; no contract added with hints.
- `correlate_facts(backend='spacy')` with hints — spacy is opt-in;
  no parity contract.
- `lede_spacy.expand_hints` — Python-only by design (§7.9).

### 8.5 Cross-runtime risk surface

1. **`re.escape` vs `regex::escape`** — identical on ASCII. Test
   fixture covers a few non-ASCII edge characters; document any
   divergence in `docs/REFERENCE.md`.
2. **`\b` semantics** — Python `re` and Rust `regex` both default to
   `[A-Za-z0-9_]` word characters. Identical when input is
   lowercased ASCII (preprocessing in §5.1 ensures this).
3. **Dict iteration order** — order-invariant by §6.3 (sum).
4. **Floating-point summation order** — bonuses summed in iteration
   order over the hint sequence. Tested explicitly.
5. **Budget rounding** — handled by `round_to_int` in §6.2.

## 9. Testing strategy

### 9.1 Core Python (`tests/test_hints.py`)

New file. Covers:

- Backward compat: existing suite passes unchanged. No-hint paths produce identical bytes.
- Token match: case-insensitive, word-boundary, no substring leakage.
- Phrase match: contiguous, exact-token semantics.
- List vs dict input shapes; per-hint weights affect ranking.
- `hint_focus` at 0.0, 0.5, 0.7, 1.0 — verify expected budget splits.
- `hint_mode` soft vs hard — verify guarantee vs no-guarantee semantics.
- Rollover: hard mode with zero matches falls back to plain; soft mode rolls leftover both ways.
- Cap saturation: 5 occurrences of one hint score the same as 3.
- `mode='legacy'` + hints → `ValueError`.
- `hint_focus` out of range → `ValueError`.
- `hint_mode` not in `{"soft", "hard"}` → `ValueError`.
- Empty/whitespace hints silently dropped; `hints=[]` ≡ `hints=None`.
- Integer-math rounding: odd `max_length` with `hint_focus=0.5` produces consistent budget.

### 9.2 Core Rust (`rust/tests/hints.rs`)

Mirror of `test_hints.py`. Same matrix, same expected results,
same validation errors.

### 9.3 Cross-runtime parity

- `fixtures/v0_4_hints/` — new fixture directory.
- `benchmarks/gen_hint_fixtures.py` — fixture generator.
- `rust/tests/fixtures.rs` gets the `v0_4_hints_byte_identical` gate.

### 9.4 Companion (`packages/lede-spacy/tests/test_expand_hints.py`)

- Lemma expansion: `"counties"`→`"county"`; `"running"`→`"run"`; `"smiths"`→`"smith"`.
- Synonyms: snapshot tests on a stable hint set; tolerate WordNet additions by asserting subset, not exact equality.
- Similar: skipped if `md`/`lg` model not installed; otherwise asserts non-empty deterministic output.
- Dict shape: `expand_weight=0.5` propagates correctly; max-wins-on-collision verified.
- Multi-word hints pass through unchanged.
- Empty list and empty dict round-trip cleanly.
- End-to-end composition: `summarize(text, hints=expand_hints(["county"], kinds=("lemma",)))` runs without error.

### 9.5 CI

Existing four workflows (`tests`, `zero-deps`, `rust`, `lede-spacy`)
cover everything once the new tests land. No new workflow needed.

## 10. Documentation deliverables

### 10.1 Per-symbol docstrings

Each of `lede.summarize`, `lede.brief`, `lede.extract.key_facts`,
`lede.extract.phrases`, `lede.extract.correlate_facts` gets a new
"Hint biasing" paragraph in its docstring with:

- What the three new kwargs do.
- The default behavior (no hints = identical to today).
- A worked example.
- Cross-reference to `lede_spacy.expand_hints` for synonym expansion.

`lede_spacy.expand_hints` gets a full docstring covering all three
`kinds`, deps, errors, and a composition example.

### 10.2 Project docs

- `docs/REFERENCE.md` — new section "Hint biasing" before "Extract primitives". Documents the public API contract, validation rules, the rounding-determinism note, the parity contract scope, and the explicit list of what is not parity-promised.
- `docs/v0-2-design.md` — add a top-of-file pointer to this spec.
- `docs/lede-spacy-integration.md` — append a new section on `expand_hints`, the `[synonyms]` extra, and WordNet auto-download.
- `docs/comparison.md` — add a fourth worked example showing hint-biased extraction ("John Smith's county") alongside the existing Sumy and LLM comparisons.
- `README.md` — add a one-paragraph "Targeted summarization with hints" subsection with a 6-line example.
- `CHANGELOG.md` — new `## [0.4.0]` entry listing the new kwargs, the `lede-spacy[synonyms]` extra, and the explicit backward-compat promise.

### 10.3 Companion docs

- `packages/lede-spacy/README.md` — new "Expanding hints" section with the three `kinds` and a composition example.

## 11. Success criteria

- **SC-1** Every existing test in `tests/`, `rust/tests/`, and `packages/lede-spacy/tests/` passes unchanged.
- **SC-2** New Python tests in `tests/test_hints.py` cover the matrix in §9.1 and pass.
- **SC-3** New Rust tests in `rust/tests/hints.rs` cover the matrix in §9.2 and pass.
- **SC-4** `v0_4_hints_byte_identical` fixture walker is green: every fixture in `fixtures/v0_4_hints/` produces identical bytes from Python and Rust.
- **SC-5** `mode='legacy'` with hints raises `ValueError`. Verified by test.
- **SC-6** Backward compat: calling any affected primitive with `hints=None` (or no `hints` kwarg) produces output that is byte-identical to v0.3.0 on every existing fixture.
- **SC-7** `lede_spacy.expand_hints` is exported, tested per §9.4, and composes end-to-end with `lede.summarize`.
- **SC-8** All documentation deliverables in §10 are written and committed.
- **SC-9** `cargo clippy --all-targets -- -D warnings` and `cargo fmt --check` pass.
- **SC-10** All four CI workflows (`tests`, `zero-deps`, `rust`, `lede-spacy`) pass on the branch.

## 12. Constraints

### Always
- Maintain byte-identical Python↔Rust parity for the regex backend.
- Preserve backward compatibility: no `hints` kwarg → today's output.
- Use deterministic algorithms; no random tie-breaking; no hash-iteration-order dependence.
- Add tests before or alongside implementation.

### Ask first
- Any change to the existing `_composite_score_legacy` formula. Hints attach on top of the default-mode scorer; legacy must stay frozen.
- Any addition of a runtime dependency to core `lede` (the zero-dep promise stands).
- Any new public name in the `lede` namespace beyond the kwargs documented here.

### Never
- Add LLM calls to core. Extractive only.
- Make existing fixtures byte-different. The v0.1 and v0.2 walkers stay green.
- Skip the parity walker. The `v0_4_hints_byte_identical` gate is required.
- Use language-built-in `round` on floats for the budget split. Use the integer-math `round_to_int` from §6.2.

## 13. Drift checkpoints

- **DC-1 (before any code)** Re-read §2 and §4. Backward compat must hold: every existing test passes without modification.
- **DC-2 (after Python core lands)** Run `.venv/bin/python -m pytest -q`. All ~230 existing tests must pass alongside the new hint tests. If any existing test fails, stop — the no-hints path was disturbed.
- **DC-3 (after Rust core lands)** Run `cd rust && cargo test`. All existing tests must pass.
- **DC-4 (before parity fixtures)** Confirm `round_to_int` produces identical integers in Python and Rust for `hint_focus ∈ {0.0, 0.3, 0.5, 0.7, 1.0}` and `max_length ∈ {99, 100, 101, 500, 501}`. Print and compare.
- **DC-5 (after parity fixtures)** Run `cd rust && cargo test --test fixtures`. All three gates green: v0.1, v0.2, v0.4.
- **DC-6 (before merge)** Re-read §10 and confirm every documentation deliverable is committed.

## 14. Open questions

None at this time. All design decisions resolved during the
2026-05-21 brainstorm session.

## 15. Related docs

- `docs/REFERENCE.md` — public API contract; updated by this spec.
- `docs/v0-2-design.md` — v0.2 design spec; this is the v0.4 sibling.
- `docs/lede-spacy-integration.md` — companion-package policy.
- `docs/integration-memo.md` — chunkshop integration contract; hint biasing is directly relevant to their use case.
- `CLAUDE.md` — invariants this spec must honor.
