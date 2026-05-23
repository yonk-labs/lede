# Caller-supplied `headings=` override on `summarize` (v0.4.3)

**Status:** design approved, awaiting implementation plan
**Date:** 2026-05-22
**Target version:** 0.4.3
**Affected surfaces:** `lede` core (Python + Rust)

---

## 1. Purpose

`keep_headings` / `include_toc` (v0.4.2) rely on lede's auto heading detector
(`is_structural_heading`), which is convention-bound and misses many real-world
non-Markdown headings. Confirmed in production: on a SCOTUS-opinion corpus
(caption-style headings) `lede.toc()` returned empty for every document, so the
`include_toc` arm degenerated.

This spec adds a caller-supplied override: when the caller already knows the
heading lines (e.g. they live in chunk metadata, as in chunkshop), they pass
them directly and lede uses them verbatim — bypassing auto-detection entirely.
This is the deterministic path for documents lede can't auto-parse.

It does **not** modify `is_structural_heading` (that broadening is a separate,
higher-risk effort gated on benchmark data). This feature is additive and
parity-safe.

## 2. Backward compatibility promise

New kwarg `headings` defaults to `None`. When `headings is None`, no new code
path executes and output is byte-identical to v0.4.2 — in both Python and Rust.
Verified by leaving the existing test corpus and all fixture walkers unchanged.

## 3. Scope

### In scope (v0.4.3)

One new keyword-only kwarg on `lede.summarize`:

| kwarg | type / default | behavior |
|---|---|---|
| `headings` | `Sequence[str] \| None = None` | Caller-supplied heading lines (verbatim). When non-empty, they **replace** auto-detection for `keep_headings` and `include_toc`. Ignored when both flags are off. |

No new `SummaryResult` field — `pinned_headings` already carries the injected
headings (now sourced from the override when provided).

Rust mirror: `PinOpts` gains a `headings: Vec<String>` field; `render_with_pins`
+ `prepend_blocks` consume it. New parity fixtures.

### Not in scope (v0.4.3)

- Broadening `is_structural_heading` (the #3 effort — separate, gated on
  benchmark data, 0.5.0-class because it changes default output).
- `headings=` on `brief` or the `extract.*` primitives. `summarize` only.
- Fuzzy / substring matching of supplied headings to body lines. Matching is
  exact (stripped-equality) only (§4.3).
- Per-heading depth/level metadata. Supplied headings are a flat ordered list;
  the TOC renders them flat (no indentation) in given order.

## 4. Behavioral decisions

### 4.1 Override replaces auto-detection (when provided)

When `headings` is non-empty, `keep_headings` and `include_toc` use ONLY the
supplied list — `is_structural_heading` / `document_title_index` /
`outline()`-derived TOC are not consulted. Rationale: the override exists
precisely because auto-detection failed; mixing the two is unpredictable.

When `headings` is `None` or empty, behavior is exactly v0.4.2 (auto-detection).

### 4.2 `include_toc` + `headings`

The TOC block is the supplied headings, deduped (first occurrence wins),
in given order, one per line, **no indentation** (the override is a flat list;
depth is unknown). Replaces the `outline()`-derived TOC.

### 4.3 `keep_headings` + `headings` — matching and placement

1. Dedupe `headings` preserving first-occurrence order → `H`.
2. For each `h` in `H`, locate the first body sentence whose stripped text
   equals `h.strip()` and is not already claimed → that sentence index is a
   "matched heading position". Matching is exact stripped-equality, no
   substring/fuzzy.
3. **Title:** `H[0]` is always pinned at the very top of the body. If `H[0]`
   also matched a body position, that position is suppressed (no double-emit).
4. **Unmatched headings** (those with no body position), excluding the title
   already emitted, are emitted next, in given order, as a leading block — so
   every supplied heading survives even if it never appears in the body.
5. **Interleave pass:** walk the selected sentences in document order; before a
   sentence, if its nearest preceding matched-heading position has not been
   emitted, emit that heading. Then emit the sentence. Consecutive body
   sentences in a section join with a single space; headings start new lines.
6. `pinned_headings` = every heading actually emitted, in emission order
   (title first, then unmatched block, then interleaved). All of `H` is
   guaranteed present.

Edge: if `H` is non-empty but `keep_headings=False` and `include_toc=False`,
`headings` has no effect (documented no-op).

### 4.4 Budget, modes, composition

- Same as v0.4.2: pinned content is added **on top** of `max_length`; block
  order is `pin` → TOC → body; works in `default`/`coverage`, composes with
  `hints`, rejected in `legacy` (the legacy rejection now also triggers when
  `headings` is supplied alongside the flags).
- `headings` composes with `pin`: `pin` lines still prepend as the first block.

## 5. API examples

```python
from lede import summarize

# chunkshop-style: heading came from chunk metadata, not detectable in text.
r = summarize(
    chunk_text,
    max_length=500,
    keep_headings=True,
    headings=["Syllabus", "Opinion of the Court"],
)
r.pinned_headings  # ("Syllabus", "Opinion of the Court")

# Caller-supplied TOC (fixes the SCOTUS toc()-empty case):
r = summarize(text, include_toc=True, headings=["Syllabus", "Opinion", "Dissent"])
# TOC block = "Syllabus\nOpinion\nDissent" prepended before the body.

# Auto-detection still the default when headings is omitted:
r = summarize(markdown_doc, keep_headings=True)   # unchanged v0.4.2 behavior
```

## 6. Parity & testing

- Rust `PinOpts` gains `headings: Vec<String>`; `render_with_pins` /
  `prepend_blocks` take the override; `summarize_with_pins` threads it.
- New fixtures `fixtures/v0_4_3_headings/<corpus>__<case>` exercising:
  `headings` + `keep_headings` (all matched / none matched / mixed),
  `headings` + `include_toc`, `headings` + both, `headings` ignored (flags
  off), `headings` + `hints`. Walker `v0_4_3_headings_byte_identical`.
- Existing walkers (`every_fixture`, `v0_2`, `v0_4_hints`, `v0_4_2_pins`)
  unchanged = `headings=None` path byte-identical.
- Python unit tests for each §4.3 step (title-at-top, dedup, unmatched-block,
  interleave, no-op when flags off, legacy rejection).

## 7. Open questions

None. §4 resolves the matching/placement choices.
