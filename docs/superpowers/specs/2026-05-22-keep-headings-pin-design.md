# Optional heading & pin retention in `summarize` (v0.5)

**Status:** design approved, awaiting implementation plan
**Date:** 2026-05-22
**Target version:** 0.5.0
**Affected surfaces:** `lede` core (Python + Rust)

---

## 1. Purpose

Let callers force structurally important lines — section headings,
the document title, a caption — to survive extraction and appear in
the summary output. lede's default scorer deliberately filters
headings *out* (scores them `-inf`) while using the nearest enclosing
heading as a positional signal. For some downstream consumers the
heading is the single most load-bearing line: it frames every fact
under it.

The motivating use case is chunkshop's hierarchy chunker, where the
chunk heading (e.g. a figure caption) is prepended to
`embedded_content` at ingest. A re-measure showed that prepending the
deduped heading to the *summary output* lifted facts retention
0.36 → 0.72 and caption retention 0.03 → 0.90 for ~+110 tokens —
because lede, being extractive, otherwise compresses the prepended
caption right back out.

chunkshop can (and will) ship this in its own Fast-mode recipe today.
This spec is the optional, general lede-side feature: pinning is a
common extractive-summary need (titles, headings) and worth offering
once, cleanly, to every lede caller.

## 2. Backward compatibility promise

All new kwargs default to off (`keep_headings=False`,
`include_toc=False`, `pin=None`). When all three are at their
defaults, no new code path executes and output is byte-identical to
v0.4.0 — in **both** Python and Rust. This is verified by leaving the
entire existing test corpus and every fixture unchanged
(`every_fixture_byte_identical`,
`v0_2_extract_primitives_byte_identical`).

Pinning is 100% optional. This is non-negotiable.

## 3. Scope

### In scope (v0.5)

Three new keyword-only kwargs on `lede.summarize`:

| kwarg | type / default | behavior |
|---|---|---|
| `keep_headings` | `bool = False` | Pins the document title (depth-1 heading, if present) plus the nearest enclosing heading above each *selected* sentence. Deduped, interleaved in document order. |
| `include_toc` | `bool = False` | Prepends a full outline block (from `lede.extract.outline`) as a table of contents. Independent of `keep_headings`. |
| `pin` | `Sequence[str] \| None = None` | Caller-supplied lines forced verbatim, prepended in given order. lede stays heading-agnostic. |

`SummaryResult` gains one field:

- `pinned_headings: tuple[str, ...]` — the heading lines injected by
  `keep_headings` (empty tuple when `keep_headings=False` or no
  headings were pinned). Caller-supplied `pin` lines and the TOC block
  are **not** listed here; this field reflects only auto-detected
  headings. Aids debugging and gives the parity walker an assertable
  surface.

Rust mirror in `rust/src/tfidf.rs`, reusing `rust/src/headings.rs`
(`is_heading`, `heading_name`, `md_depth`). New parity fixtures via
`benchmarks/gen_parity_fixtures.py`; the fixture walker enforces
byte-identical output on the opted-in path.

### Not in scope (v0.5)

- A separate `keep_title` kwarg. The title is the depth-1 heading and
  is folded into `keep_headings` (decision 4.1).
- Document-order placement of `pin` lines. Arbitrary caller strings
  have no reliable position in the source, so they prepend as a block
  (decision 4.2).
- `keep_headings` / `include_toc` / `pin` on `lede.brief` or the
  `lede.extract.*` primitives. This spec adds them to `summarize`
  only. (`brief` may forward them in a later version; out of scope
  now.)
- Pinning in `mode="legacy"`. Rejected with `ValueError`, mirroring
  how `hints` treats legacy (decision 4.4).
- Truncation or length-capping of pinned content. Pins are added on
  top of `max_length` verbatim (section 5). A pathologically long
  pin is the caller's responsibility.

## 4. Behavioral decisions

### 4.1 Title folds into `keep_headings`

There is no separate `keep_title`. When `keep_headings=True` and the
document has a depth-1 heading at its start, that title is pinned at
the top of the output in addition to section headings above selected
sentences. Rationale: the title is "almost always wanted" and a
separate kwarg adds surface for little gain.

### 4.2 `pin` prepends as a block; headings interleave

- **Section headings** (`keep_headings`) interleave in document order,
  immediately before their section's surviving sentences.
- **`pin` lines** prepend as a block, in the order given, verbatim.
- **TOC** (`include_toc`) prepends as a block.

Ordering when multiple are active, top to bottom:
`pin` block → TOC block → body (with title + interleaved section
headings).

### 4.3 No-op safety

`keep_headings=True` on a document with no detected headings produces
output byte-identical to the default (`keep_headings=False`) — there
is nothing to pin, and `pinned_headings` is the empty tuple.

### 4.4 Mode interaction

- Allowed in `mode="default"` and `mode="coverage"` (both filter
  headings, so both benefit).
- Rejected in `mode="legacy"` with `ValueError`
  (`"keep_headings/pin not supported in legacy mode"`), mirroring
  `hints`.

### 4.5 Combines with hints

Body selection runs first — hinted or not — then headings above
whatever got selected are pinned. The two features are orthogonal and
compose without special-casing.

## 5. Placement & budget

Pinned content is **added on top** of `max_length`. `max_length`
governs only the extractive body; the body is selected exactly as it
is today (for the given `mode`/`hints`), and pinned content is woven in
afterward. Consequence: total output length may exceed `max_length`
by the pinned characters. This guarantees pins always survive, which
is the entire point of the feature.

Deduplication: a heading is pinned at most once. If the document title
is also the nearest enclosing heading of a selected sentence, it
appears once (at the top), not twice.

Determinism: headings are pinned in document order; dedup preserves
first occurrence. No ordering depends on hash iteration, locale, or
tie-break randomness.

## 6. API examples

```python
from lede import summarize

# Section headings + title woven into the summary.
r = summarize(text, max_length=500, keep_headings=True)
r.summary           # body with title + enclosing headings interleaved
r.pinned_headings   # ("# Quarterly Report", "## Revenue", ...)

# Caller pins a known caption verbatim (chunkshop's path).
r = summarize(text, max_length=500, pin=["Figure 3: Q3 revenue by region"])

# Full TOC prepended, plus headings woven in.
r = summarize(text, max_length=500, keep_headings=True, include_toc=True)

# Composes with hints.
r = summarize(text, hints=["revenue"], keep_headings=True)
```

## 7. Testing

**Python (`tests/`)**
- Each kwarg in isolation: `keep_headings`, `include_toc`, `pin`.
- Title folding: depth-1 title pinned at top with `keep_headings=True`.
- Dedup: title that is also a selected sentence's enclosing heading
  appears once.
- No-op: `keep_headings=True` on heading-less text == default output.
- Budget-on-top: output exceeds `max_length` by exactly the pinned
  chars; body unchanged vs. `keep_headings=False`.
- Combos: `keep_headings + include_toc + pin`; `keep_headings + hints`.
- Ordering: `pin` block → TOC → body.
- Legacy rejection: `mode="legacy"` with any pin kwarg raises
  `ValueError`.
- Coverage mode: `keep_headings=True` works under `mode="coverage"`.
- `pinned_headings` field correctness.

**Rust (`rust/tests/`)**
- Mirror tests for each kwarg, dedup, no-op, ordering, legacy
  rejection.

**Parity (`fixtures/` + `rust/tests/fixtures.rs`)**
- New fixtures exercising `keep_headings` and `pin`, regenerated via
  `benchmarks/gen_parity_fixtures.py`; walker green = Python ↔ Rust
  byte-identical on the opted-in path.
- Existing fixtures unchanged = default path still byte-identical to
  v0.4.0.

## 8. Open questions

None at design time. Decisions 4.1–4.5 resolve the choices surfaced
during brainstorming.
