# Optional heading & pin retention in `summarize` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add three default-off kwargs to `lede.summarize` — `keep_headings`, `include_toc`, `pin` — that force structurally important lines (section headings, the document title, a TOC, caller-supplied lines) to survive extraction, with Python↔Rust byte-identical parity.

**Architecture:** The weaving is mode-agnostic — it post-processes `(sentences, selected_indices)`. When `keep_headings=False` the body is the *exact* string the existing scorer produces (so `pin`/`include_toc` only prepend blocks, no selection refactor needed). When `keep_headings=True` we need the selected sentence indices, so the three selection paths (default, coverage, hints) each grow an index-returning variant that the existing string functions call (a pure refactor — byte-identical). Pinned content is added on top of `max_length`. All new kwargs default off → byte-identical to v0.4.1.

**Tech Stack:** Python 3 (stdlib only), Rust (stdlib + `regex`), JSON parity fixtures driven by `serde_json` in the Rust walker.

**Spec:** `docs/superpowers/specs/2026-05-22-keep-headings-pin-design.md`

---

## File structure

| File | Responsibility | Change |
|---|---|---|
| `src/lede/_types.py` | `SummaryResult` dataclass | add `pinned_headings: tuple[str, ...] = ()` |
| `src/lede/_pins.py` | **new** — pure weaving/rendering of headings, TOC, pins | create |
| `src/lede/tfidf.py` | selection + public `summarize`; expose index-returning selectors | modify |
| `src/lede/coverage.py` | coverage selection; expose index-returning selector | modify |
| `src/lede/extract/outline.py` | TOC source (already exists) | read-only |
| `rust/src/types.rs` | `SummaryResult` struct | add `pinned_headings: Vec<String>` |
| `rust/src/pins.rs` | **new** — Rust mirror of `_pins.py` | create |
| `rust/src/tfidf.rs` | selection + `summarize`; expose index selectors | modify |
| `rust/src/coverage.rs` | coverage selection index variant | modify |
| `rust/src/lib.rs` | register `mod pins;` | modify |
| `benchmarks/gen_pin_fixtures.py` | **new** — generate parity fixtures | create |
| `rust/tests/fixtures.rs` | **new** walker `v0_4_2_pins_byte_identical` | modify |
| `tests/test_pins.py` | **new** Python unit tests | create |
| `rust/tests/pins.rs` | **new** Rust unit tests | create |

---

## SLICE 1 — default mode (Python)

### Task 1: Add `pinned_headings` to `SummaryResult`

**Files:**
- Modify: `src/lede/_types.py:62-72`
- Test: `tests/test_pins.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pins.py
from lede._types import SummaryResult


def test_summary_result_has_pinned_headings_default_empty():
    r = SummaryResult(summary="hi")
    assert r.pinned_headings == ()
    assert str(r) == "hi"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_pins.py::test_summary_result_has_pinned_headings_default_empty -v`
Expected: FAIL — `TypeError`/`AttributeError` (field missing).

- [ ] **Step 3: Add the field**

In `src/lede/_types.py`, inside `SummaryResult`, add the field after `correlated_facts`:

```python
@dataclass(frozen=True)
class SummaryResult:
    summary: str
    stats: tuple[Stat, ...] | None = None
    outline: tuple[Section, ...] | None = None
    metadata: Metadata | None = None
    phrases: tuple[str, ...] | None = None
    correlated_facts: tuple[PhraseFact, ...] | None = None
    pinned_headings: tuple[str, ...] = ()

    def __str__(self) -> str:
        return self.summary
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_pins.py -v`
Expected: PASS.

- [ ] **Step 5: Run full suite to confirm no regression**

Run: `.venv/bin/python -m pytest -q`
Expected: all existing tests pass (new field is optional with a default).

- [ ] **Step 6: Commit**

```bash
git add src/lede/_types.py tests/test_pins.py
git commit -m "feat(types): add pinned_headings field to SummaryResult"
```

---

### Task 2: Heading-location helpers

**Files:**
- Create: `src/lede/_pins.py`
- Test: `tests/test_pins.py`

These three pure helpers locate headings by index in a sentence list. They are the only new "what is a heading" logic; they reuse `is_heading`/`heading_name`/`md_depth` from `_headings.py`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pins.py  (append)
from lede._pins import (
    nearest_heading_map,
    document_title_index,
    render_toc,
)


def test_nearest_heading_map_points_to_enclosing_heading():
    sentences = ["# Title", "Body one.", "## Sub", "Body two."]
    # index of the most recent heading sentence above each sentence, or None
    assert nearest_heading_map(sentences) == [None, 0, None, 2]


def test_document_title_index_depth1_at_start():
    assert document_title_index(["# Title", "Body."]) == 0


def test_document_title_index_none_when_body_precedes():
    assert document_title_index(["Body first.", "# Title"]) is None


def test_document_title_index_none_when_first_heading_not_depth1():
    assert document_title_index(["## Sub", "Body."]) is None


def test_render_toc_indents_by_depth():
    text = "# Top\n\nBody about the top matter here.\n\n## Sub\n\nMore body content follows here.\n"
    # outline() yields Sections; render_toc indents (depth-1)*2 spaces
    toc = render_toc(text)
    assert "Top" in toc
    assert "  Sub" in toc  # depth 2 => 2-space indent
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pins.py -v`
Expected: FAIL — `ModuleNotFoundError: lede._pins`.

- [ ] **Step 3: Create `src/lede/_pins.py`**

```python
"""v0.4.2 heading/pin retention helpers (pure, deterministic).

Locates headings by index in a sentence list and renders pinned content.
Reuses lede._headings for all "what is a heading" logic; adds no new
heading detection. The Rust mirror is rust/src/pins.rs.
"""
from __future__ import annotations

from lede._headings import is_heading, heading_name, md_depth


def nearest_heading_map(sentences: list[str]) -> list[int | None]:
    """For each sentence index, the index of the most recent heading
    sentence at or before it, or None if no heading precedes it.

    A heading's own entry is None (headings are never selected, so the
    value is unused; None keeps the rule "the heading above me")."""
    out: list[int | None] = []
    current: int | None = None
    for i, s in enumerate(sentences):
        if is_heading(s):
            out.append(None)
            current = i
        else:
            out.append(current)
    return out


def document_title_index(sentences: list[str]) -> int | None:
    """Index of the document title: a depth-1 heading appearing before
    any body sentence. None if the first sentence-ish line is body, or
    the first heading is not markdown depth 1."""
    for i, s in enumerate(sentences):
        if is_heading(s):
            return i if md_depth(s) == 1 else None
        return None
    return None


def render_toc(text: str) -> str:
    """Render a table of contents from the document outline. Each
    section name on its own line, indented (depth-1)*2 spaces."""
    from lede.extract.outline import outline

    lines: list[str] = []
    for section in outline(text):
        indent = "  " * max(0, section.depth - 1)
        lines.append(f"{indent}{section.name}")
    return "\n".join(lines)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pins.py -v`
Expected: PASS (all 6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/lede/_pins.py tests/test_pins.py
git commit -m "feat(pins): heading-location and TOC-render helpers"
```

---

### Task 3: The weaving renderer

**Files:**
- Modify: `src/lede/_pins.py`
- Test: `tests/test_pins.py`

`render_with_pins` is the pure core: given the sentence list, the selected indices (sorted ascending), and the three flags, it produces the final string and the `pinned_headings` tuple.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pins.py  (append)
from lede._pins import render_with_pins


def _sentences():
    # title at 0, heading at 2, heading at 5
    return [
        "# Quarterly Report",
        "Revenue rose sharply this quarter overall.",
        "## Revenue",
        "Revenue grew twelve percent year over year.",
        "Costs were flat across the period.",
        "## Risks",
        "Supply chain risk remains elevated this year.",
    ]


def test_keep_headings_interleaves_and_pins_title():
    s = _sentences()
    selected = [1, 3, 6]  # body sentences under title, Revenue, Risks
    body, pinned = render_with_pins(
        s, selected, keep_headings=True, include_toc=False, pin=None, text="\n".join(s)
    )
    assert pinned == ("# Quarterly Report", "## Revenue", "## Risks")
    assert body == (
        "# Quarterly Report\n"
        "Revenue rose sharply this quarter overall.\n"
        "## Revenue\n"
        "Revenue grew twelve percent year over year.\n"
        "## Risks\n"
        "Supply chain risk remains elevated this year."
    )


def test_keep_headings_false_joins_with_space():
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1, 3], keep_headings=False, include_toc=False, pin=None, text="\n".join(s)
    )
    assert pinned == ()
    assert body == "Revenue rose sharply this quarter overall. Revenue grew twelve percent year over year."


def test_pin_prepends_block_before_body():
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1], keep_headings=False, include_toc=False,
        pin=["Figure 3: Q3 revenue by region"], text="\n".join(s),
    )
    assert pinned == ()
    assert body == (
        "Figure 3: Q3 revenue by region\n\n"
        "Revenue rose sharply this quarter overall."
    )


def test_ordering_pin_then_toc_then_body():
    s = _sentences()
    body, _ = render_with_pins(
        s, [1], keep_headings=False, include_toc=True,
        pin=["PINNED LINE"], text="\n".join(s),
    )
    assert body.startswith("PINNED LINE\n\n")
    # TOC block (section names) sits between pin and body
    assert "Quarterly Report" in body.split("\n\n")[1]
    assert body.split("\n\n")[-1] == "Revenue rose sharply this quarter overall."


def test_title_not_double_emitted_when_also_enclosing_heading():
    # selected sentence 1 sits directly under the title (heading_of[1] == 0).
    s = _sentences()
    body, pinned = render_with_pins(
        s, [1], keep_headings=True, include_toc=False, pin=None, text="\n".join(s)
    )
    # title appears exactly once
    assert pinned == ("# Quarterly Report",)
    assert body.count("# Quarterly Report") == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_pins.py -k render_with_pins -v`
Expected: FAIL — `ImportError: cannot import name 'render_with_pins'`.

- [ ] **Step 3: Implement `render_with_pins` in `src/lede/_pins.py`**

Append:

```python
from collections.abc import Sequence


def render_with_pins(
    sentences: list[str],
    selected: list[int],
    *,
    keep_headings: bool,
    include_toc: bool,
    pin: Sequence[str] | None,
    text: str,
) -> tuple[str, tuple[str, ...]]:
    """Weave pinned content around the extractive body.

    Returns (output_string, pinned_headings). `selected` must be sorted
    ascending. Headings interleave in document order; the title (if any)
    is pinned at the top; `pin` lines and the TOC prepend as blocks in
    the order pin -> toc -> body. Deterministic: dedup preserves first
    occurrence; no ordering depends on hashing or locale."""
    pinned_headings: list[str] = []

    if keep_headings:
        heading_of = nearest_heading_map(sentences)
        title_idx = document_title_index(sentences)
        emitted: set[int] = set()
        out_lines: list[str] = []
        buf: list[str] = []

        def flush() -> None:
            if buf:
                out_lines.append(" ".join(buf))
                buf.clear()

        if title_idx is not None:
            out_lines.append(sentences[title_idx])
            emitted.add(title_idx)
            pinned_headings.append(sentences[title_idx])

        for s_idx in selected:
            h = heading_of[s_idx]
            if h is not None and h not in emitted:
                flush()
                out_lines.append(sentences[h])
                emitted.add(h)
                pinned_headings.append(sentences[h])
            buf.append(sentences[s_idx])
        flush()
        body = "\n".join(out_lines)
    else:
        body = " ".join(sentences[i] for i in selected)

    blocks: list[str] = []
    if pin:
        blocks.append("\n".join(pin))
    if include_toc:
        toc_text = render_toc(text)
        if toc_text:
            blocks.append(toc_text)
    blocks.append(body)
    output = "\n\n".join(b for b in blocks if b)
    return output, tuple(pinned_headings)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_pins.py -v`
Expected: PASS (all tests in file).

- [ ] **Step 5: Commit**

```bash
git add src/lede/_pins.py tests/test_pins.py
git commit -m "feat(pins): render_with_pins weaver (headings/toc/pin)"
```

---

### Task 4: Index-returning default selector

**Files:**
- Modify: `src/lede/tfidf.py:385-435`
- Test: existing suite (refactor must stay byte-identical)

Refactor `_summarize_default` to delegate selection to `_select_default`, which returns `(sentences, selected)` or `None` for early-return paths.

- [ ] **Step 1: Add `_select_default` above `_summarize_default` in `src/lede/tfidf.py`**

```python
def _select_default(
    text: str, max_length: int
) -> tuple[list[str], list[int]] | None:
    """Return (sentences, selected_indices_sorted) for default-mode
    selection, or None when an early-return path applies (empty input,
    sub-sentence budget, or fewer than _MIN_SENTENCES sentences)."""
    if not text:
        return None
    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return None
    prepared = _separate_heading_lines(text)
    sentences = split_sentences(prepared)
    if len(sentences) < _MIN_SENTENCES:
        return None
    section_map = _build_section_map(sentences)
    scores = _composite_score_default(sentences, section_map)
    indices_by_score = sorted(
        range(len(sentences)),
        key=lambda i: (-scores[i], i),
    )
    selected: list[int] = []
    used = 0
    separator = " "
    for idx in indices_by_score:
        if scores[idx] == float("-inf"):
            continue
        sentence = sentences[idx]
        needed = len(sentence) + (len(separator) if selected else 0)
        if used + needed <= max_length:
            selected.append(idx)
            used += needed
    if not selected:
        return None
    selected.sort()
    return sentences, selected
```

- [ ] **Step 2: Rewrite `_summarize_default` to use it**

Replace the body of `_summarize_default` with:

```python
def _summarize_default(text: str, max_length: int = 500) -> str:
    """v0.2 default scorer — mirrors _summarize_legacy with the default scorer.

    Headings are dropped from candidates (score = -inf), cue-phrase sentences
    are boosted by +2.0, digit-bearing sentences get +0.3, and sentences
    under high-signal section headings have tfidf * 1.3.
    """
    if not text:
        return ""
    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return _truncate(text, max_length)
    sel = _select_default(text, max_length)
    if sel is None:
        # Mirror legacy early-return semantics: short docs return as-is
        # when they fit, else truncate.
        prepared = _separate_heading_lines(text)
        sentences = split_sentences(prepared)
        if len(sentences) < _MIN_SENTENCES and len(text) <= max_length:
            return text
        return _truncate(text, max_length)
    sentences, selected = sel
    return " ".join(sentences[i] for i in selected)
```

> NOTE: this preserves the exact original branch order. The original returned `text` only when `len(sentences) < _MIN_SENTENCES and len(text) <= max_length`, otherwise truncated; and truncated when `selected` was empty. `_select_default` returns None in all three cases, so the fallback block reproduces them identically.

- [ ] **Step 3: Run the full Python suite — byte-identical refactor**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL pass (this is a pure refactor; any failure means the selection changed).

- [ ] **Step 4: Commit**

```bash
git add src/lede/tfidf.py
git commit -m "refactor(tfidf): extract _select_default returning indices"
```

---

### Task 5: Wire pin kwargs into public `summarize` (default + legacy reject)

**Files:**
- Modify: `src/lede/tfidf.py:441-561` (signature, validation, dispatch, result build)
- Test: `tests/test_pins.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_pins.py  (append)
import pytest
from lede import summarize

_DOC = (
    "# Quarterly Report\n\n"
    "Revenue rose sharply this quarter across every region we serve.\n\n"
    "## Revenue\n\n"
    "Revenue grew twelve percent year over year to record levels.\n"
    "Operating costs stayed essentially flat across the whole period.\n\n"
    "## Risks\n\n"
    "Supply chain risk remains elevated heading into the next year.\n"
)


def test_default_off_is_unchanged():
    assert summarize(_DOC, max_length=200).summary == summarize(_DOC, max_length=200, keep_headings=False, pin=None).summary


def test_keep_headings_pins_title_and_sections():
    r = summarize(_DOC, max_length=200, keep_headings=True)
    assert r.summary.startswith("# Quarterly Report")
    assert "# Quarterly Report" in r.pinned_headings


def test_keep_headings_added_on_top_of_budget():
    base = summarize(_DOC, max_length=200, keep_headings=False).summary
    pinned = summarize(_DOC, max_length=200, keep_headings=True).summary
    # pinned output is longer (headings added on top); body sentences still present
    assert len(pinned) >= len(base)


def test_pin_lines_survive_verbatim():
    r = summarize(_DOC, max_length=200, pin=["Figure 3: revenue by region"])
    assert r.summary.startswith("Figure 3: revenue by region")


def test_no_heading_doc_keep_headings_is_noop():
    plain = "Alpha beta gamma delta epsilon zeta eta. " * 20
    assert summarize(plain, max_length=150, keep_headings=True).summary == summarize(plain, max_length=150).summary


def test_legacy_mode_rejects_pin_kwargs():
    with pytest.raises(ValueError, match="legacy"):
        summarize(_DOC, max_length=200, mode="legacy", keep_headings=True)
    with pytest.raises(ValueError, match="legacy"):
        summarize(_DOC, max_length=200, mode="legacy", pin=["x"])
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_pins.py -k "summarize or keep or pin or legacy or noop or budget or default_off" -v`
Expected: FAIL — `summarize() got an unexpected keyword argument 'keep_headings'`.

- [ ] **Step 3: Update `summarize` signature and add the pin path**

In `src/lede/tfidf.py`, change the signature (add three kwargs after `hint_mode`):

```python
def summarize(
    text: str,
    max_length: int = 500,
    *,
    mode: str = "default",
    attach: list[str] | tuple[str, ...] | None = None,
    hints: list[str] | dict[str, float] | None = None,
    hint_focus: float = 0.7,
    hint_mode: str = "soft",
    keep_headings: bool = False,
    include_toc: bool = False,
    pin: "Sequence[str] | None" = None,
) -> SummaryResult:
```

Add `from collections.abc import Sequence` to the imports at the top of the file (near the other imports).

Immediately after `processed_hints = preprocess_hints(hints)` (line ~511), add pin validation and compute a `pins_active` flag:

```python
    pins_active = bool(keep_headings) or bool(include_toc) or bool(pin)
    if pins_active and mode == "legacy":
        raise ValueError("keep_headings/include_toc/pin not supported in legacy mode")
```

Then, replace the existing body-dispatch block so the pin path runs when `pins_active`. The simplest correct structure: compute `summary_text` exactly as today, then build `pinned_headings`, then render. Insert this AFTER the existing `if processed_hints: ... elif mode == ...: summary_text = ...` block computes `summary_text`:

```python
    pinned_headings: tuple[str, ...] = ()
    if pins_active:
        if keep_headings:
            sel = _select_for_mode(text, max_length, mode, processed_hints,
                                   hint_focus, hint_mode)
        else:
            sel = None
        if sel is not None:
            sentences, selected = sel
            summary_text, pinned_headings = render_with_pins(
                sentences, selected,
                keep_headings=keep_headings, include_toc=include_toc,
                pin=pin, text=text,
            )
        else:
            # keep_headings off, or early-return path: body unchanged,
            # only pin/toc blocks prepend.
            summary_text, pinned_headings = render_with_pins(
                [], [], keep_headings=False, include_toc=include_toc,
                pin=pin, text=text,
            )
            # render_with_pins([],[]...) yields just the blocks + empty body;
            # restore the real body in the last block position:
            summary_text = _prepend_blocks(summary_text_body=summary_text_existing,
                                           include_toc=include_toc, pin=pin, text=text)
```

> The inline restore above is awkward. Use this cleaner helper instead — add `_prepend_blocks` to `_pins.py` (Task 5a) and call it. See Step 3a.

- [ ] **Step 3a: Add `_prepend_blocks` to `src/lede/_pins.py`**

```python
def prepend_blocks(
    body: str,
    *,
    include_toc: bool,
    pin: "Sequence[str] | None",
    text: str,
) -> str:
    """Prepend pin and TOC blocks (in that order) to an already-rendered
    body string. Used when keep_headings is off but pin/include_toc are
    on, so the body must stay byte-identical to the non-pinned scorer."""
    blocks: list[str] = []
    if pin:
        blocks.append("\n".join(pin))
    if include_toc:
        toc_text = render_toc(text)
        if toc_text:
            blocks.append(toc_text)
    if body:
        blocks.append(body)
    return "\n\n".join(b for b in blocks if b)
```

- [ ] **Step 3b: Replace the awkward dispatch in `summarize` with the clean version**

After `summary_text` is computed by the existing block, add:

```python
    pinned_headings: tuple[str, ...] = ()
    if pins_active:
        sel = (
            _select_for_mode(text, max_length, mode, processed_hints,
                             hint_focus, hint_mode)
            if keep_headings else None
        )
        if sel is not None:
            sentences, selected = sel
            summary_text, pinned_headings = render_with_pins(
                sentences, selected,
                keep_headings=True, include_toc=include_toc,
                pin=pin, text=text,
            )
        elif include_toc or pin:
            summary_text = prepend_blocks(
                summary_text, include_toc=include_toc, pin=pin, text=text
            )
        # keep_headings requested but sel is None (no-op path): summary_text
        # already equals the plain body; nothing to weave.
```

Add imports near the top of `tfidf.py`:

```python
from lede._pins import render_with_pins, prepend_blocks
```

- [ ] **Step 3c: Add `_select_for_mode` dispatcher to `tfidf.py`** (default only for now; coverage/hints land in Slice 2 — they return None until then so `keep_headings` is a safe no-op for those modes)

```python
def _select_for_mode(
    text: str,
    max_length: int,
    mode: str,
    processed_hints,
    hint_focus: float,
    hint_mode: str,
) -> tuple[list[str], list[int]] | None:
    """Dispatch to the mode-appropriate index-returning selector.
    Slice 1 implements default mode; coverage and hints land in Slice 2."""
    if processed_hints:
        return None  # Slice 2
    if mode == "coverage":
        return None  # Slice 2
    return _select_default(text, max_length)
```

- [ ] **Step 3d: Build the result with `pinned_headings`**

Find where `summarize` constructs `SummaryResult(...)` (after the `attach` block) and add `pinned_headings=pinned_headings` to the constructor call.

- [ ] **Step 4: Run the pin tests**

Run: `.venv/bin/python -m pytest tests/test_pins.py -v`
Expected: PASS. (`test_no_heading_doc_keep_headings_is_noop` passes because `_select_default` returns a selection with no headings, so weaving emits no heading lines — output equals the plain body.)

> If `test_no_heading_doc_keep_headings_is_noop` fails because weaving with `keep_headings=True` joins body sentences with `\n` instead of ` `: that is expected divergence. FIX by making the no-op truly byte-identical — in `render_with_pins`, when `keep_headings=True` but `pinned_headings` ends up empty AND no title, the body must join with `" "`. Add at the end of the `keep_headings` branch: `if not pinned_headings: body = " ".join(sentences[i] for i in selected)`. Re-run.

- [ ] **Step 5: Run the full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL pass (defaults-off path untouched).

- [ ] **Step 6: Commit**

```bash
git add src/lede/tfidf.py src/lede/_pins.py tests/test_pins.py
git commit -m "feat(summarize): keep_headings/include_toc/pin kwargs (default mode)"
```

---

### Task 6: Export surface + REFERENCE doc note

**Files:**
- Modify: `src/lede/__init__.py` (only if `summarize`'s docstring/signature is re-exported; verify `SummaryResult` already exported)
- Modify: `docs/REFERENCE.md` (add a "Heading & pin retention" subsection under `summarize`)
- Modify: `src/lede/tfidf.py` (extend `summarize` docstring)

- [ ] **Step 1: Extend the `summarize` docstring** — add an Args entry for `keep_headings`, `include_toc`, `pin`, and a short "Heading & pin retention (v0.4.2)" paragraph mirroring the "Hint biasing (v0.4)" block. State: all default off → byte-identical; pins added on top of `max_length`; legacy mode rejects them.

- [ ] **Step 2: Add REFERENCE.md subsection** under the `summarize` contract documenting the three kwargs, the ordering (pin → TOC → body), the budget-on-top rule, and the `pinned_headings` field.

- [ ] **Step 3: Verify exports**

Run: `.venv/bin/python -c "from lede import summarize; from lede._types import SummaryResult; print(SummaryResult(summary='x').pinned_headings)"`
Expected: prints `()`.

- [ ] **Step 4: Commit**

```bash
git add docs/REFERENCE.md src/lede/tfidf.py src/lede/__init__.py
git commit -m "docs: document keep_headings/include_toc/pin on summarize"
```

---

## SLICE 2 — coverage + hints composition (Python)

### Task 7: Index-returning coverage selector

**Files:**
- Modify: `src/lede/coverage.py:49-110`
- Modify: `src/lede/tfidf.py` (`_select_for_mode` coverage branch)
- Test: `tests/test_pins.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pins.py (append)
def test_keep_headings_works_in_coverage_mode():
    r = summarize(_DOC, max_length=200, mode="coverage", keep_headings=True)
    assert r.summary.startswith("# Quarterly Report")
    assert "# Quarterly Report" in r.pinned_headings
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_pins.py::test_keep_headings_works_in_coverage_mode -v`
Expected: FAIL — coverage path returns None in `_select_for_mode`, so no title is pinned (summary won't start with the heading).

- [ ] **Step 3: Add `select_coverage_indices` to `src/lede/coverage.py`**

Read the existing `summarize_coverage` selection loop and factor the index selection into a function returning `(sentences, selected_sorted) | None`, exactly mirroring how Task 4 did it for default. `summarize_coverage` then joins. Run the full suite to confirm the coverage refactor is byte-identical.

```bash
.venv/bin/python -m pytest -q
```

- [ ] **Step 4: Wire it into `_select_for_mode`** — replace the coverage `return None` with:

```python
    if mode == "coverage":
        from lede.coverage import select_coverage_indices
        return select_coverage_indices(text, max_length)
```

- [ ] **Step 5: Run pin tests + full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS including the new coverage test.

- [ ] **Step 6: Commit**

```bash
git add src/lede/coverage.py src/lede/tfidf.py tests/test_pins.py
git commit -m "feat(pins): keep_headings support in coverage mode"
```

---

### Task 8: Index-returning hints selector

**Files:**
- Modify: `src/lede/tfidf.py` (`_summarize_with_hints` → factor `_select_with_hints`)
- Modify: `src/lede/tfidf.py` (`_select_for_mode` hints branch)
- Test: `tests/test_pins.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pins.py (append)
def test_keep_headings_composes_with_hints():
    r = summarize(_DOC, max_length=200, hints=["revenue"], keep_headings=True)
    assert r.summary.startswith("# Quarterly Report")
    assert "## Revenue" in r.pinned_headings
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest tests/test_pins.py::test_keep_headings_composes_with_hints -v`
Expected: FAIL — hints path returns None in `_select_for_mode`.

- [ ] **Step 3: Factor `_select_with_hints`** out of `_summarize_with_hints`: everything up to the final `selected = sorted(...)` becomes `_select_with_hints(...) -> (sentences, selected) | None` (None on the early-return/empty-selection paths). `_summarize_with_hints` calls it and joins with `" "`.

- [ ] **Step 4: Run full suite — byte-identical refactor**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL pass (the existing `tests/` hint tests guard byte-identity).

- [ ] **Step 5: Wire into `_select_for_mode`** — replace the `if processed_hints: return None` with:

```python
    if processed_hints:
        return _select_with_hints(
            text, max_length, mode=mode, hints=processed_hints,
            hint_focus=hint_focus, hint_mode=hint_mode,
        )
```

- [ ] **Step 6: Run pin tests + full suite**

Run: `.venv/bin/python -m pytest -q`
Expected: PASS including `test_keep_headings_composes_with_hints`.

- [ ] **Step 7: Commit**

```bash
git add src/lede/tfidf.py tests/test_pins.py
git commit -m "feat(pins): keep_headings composes with hints"
```

---

## SLICE 3 — Rust mirror

### Task 9: `pinned_headings` field + `pins.rs` helpers

**Files:**
- Modify: `rust/src/types.rs:16-22` and the `bare` constructor (`:33`)
- Create: `rust/src/pins.rs`
- Modify: `rust/src/lib.rs` (add `pub mod pins;`)
- Test: `rust/tests/pins.rs` (create)

- [ ] **Step 1: Add the field to `SummaryResult`**

In `rust/src/types.rs`, add `pub pinned_headings: Vec<String>,` to the struct, and `pinned_headings: Vec::new(),` to every constructor (`bare` and any `Default`/literal builds — grep `SummaryResult {` to find them all, including `tfidf.rs:520`).

Run: `cd rust && cargo build`
Expected: compiles after all constructors updated.

- [ ] **Step 2: Write failing Rust unit tests**

```rust
// rust/tests/pins.rs
use lede::pins::{document_title_index, nearest_heading_map, render_with_pins};

fn sentences() -> Vec<String> {
    [
        "# Quarterly Report",
        "Revenue rose sharply this quarter overall.",
        "## Revenue",
        "Revenue grew twelve percent year over year.",
        "Costs were flat across the period.",
        "## Risks",
        "Supply chain risk remains elevated this year.",
    ]
    .iter()
    .map(|s| s.to_string())
    .collect()
}

#[test]
fn nearest_heading_map_matches_python() {
    let s = sentences();
    assert_eq!(
        nearest_heading_map(&s),
        vec![None, Some(0), None, Some(2), Some(2), None, Some(5)]
    );
}

#[test]
fn document_title_index_depth1_at_start() {
    let s = sentences();
    assert_eq!(document_title_index(&s), Some(0));
}

#[test]
fn render_keep_headings_interleaves() {
    let s = sentences();
    let (body, pinned) = render_with_pins(&s, &[1, 3, 6], true, false, None, &s.join("\n"));
    assert_eq!(
        pinned,
        vec!["# Quarterly Report", "## Revenue", "## Risks"]
    );
    assert_eq!(
        body,
        "# Quarterly Report\nRevenue rose sharply this quarter overall.\n## Revenue\nRevenue grew twelve percent year over year.\n## Risks\nSupply chain risk remains elevated this year."
    );
}
```

- [ ] **Step 3: Run to verify failure**

Run: `cd rust && cargo test --test pins`
Expected: FAIL — `pins` module/functions not found.

- [ ] **Step 4: Implement `rust/src/pins.rs`** mirroring `_pins.py` exactly. Signature:

```rust
//! v0.4.2 heading/pin retention. Mirror of src/lede/_pins.py. Byte-identical
//! output is enforced by rust/tests/fixtures.rs::v0_4_2_pins_byte_identical.

use crate::headings::{is_heading, md_depth};

pub fn nearest_heading_map(sentences: &[String]) -> Vec<Option<usize>> {
    let mut out = Vec::with_capacity(sentences.len());
    let mut current: Option<usize> = None;
    for (i, s) in sentences.iter().enumerate() {
        if is_heading(s) {
            out.push(None);
            current = Some(i);
        } else {
            out.push(current);
        }
    }
    out
}

pub fn document_title_index(sentences: &[String]) -> Option<usize> {
    for (i, s) in sentences.iter().enumerate() {
        if is_heading(s) {
            return if md_depth(s) == 1 { Some(i) } else { None };
        }
        return None;
    }
    None
}

pub fn render_toc(text: &str) -> String {
    let sections = crate::extract::outline::outline(text);
    sections
        .iter()
        .map(|sec| {
            let indent = "  ".repeat(sec.depth.saturating_sub(1));
            format!("{indent}{}", sec.name)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

#[allow(clippy::too_many_arguments)]
pub fn render_with_pins(
    sentences: &[String],
    selected: &[usize],
    keep_headings: bool,
    include_toc: bool,
    pin: Option<&[String]>,
    text: &str,
) -> (String, Vec<String>) {
    let mut pinned_headings: Vec<String> = Vec::new();
    let body: String;
    if keep_headings {
        let heading_of = nearest_heading_map(sentences);
        let title_idx = document_title_index(sentences);
        let mut emitted = std::collections::HashSet::new();
        let mut out_lines: Vec<String> = Vec::new();
        let mut buf: Vec<String> = Vec::new();
        if let Some(t) = title_idx {
            out_lines.push(sentences[t].clone());
            emitted.insert(t);
            pinned_headings.push(sentences[t].clone());
        }
        for &s_idx in selected {
            if let Some(h) = heading_of[s_idx] {
                if !emitted.contains(&h) {
                    if !buf.is_empty() {
                        out_lines.push(buf.join(" "));
                        buf.clear();
                    }
                    out_lines.push(sentences[h].clone());
                    emitted.insert(h);
                    pinned_headings.push(sentences[h].clone());
                }
            }
            buf.push(sentences[s_idx].clone());
        }
        if !buf.is_empty() {
            out_lines.push(buf.join(" "));
        }
        if pinned_headings.is_empty() {
            // no-op byte-identity with the plain scorer
            body = selected.iter().map(|&i| sentences[i].clone()).collect::<Vec<_>>().join(" ");
        } else {
            body = out_lines.join("\n");
        }
    } else {
        body = selected.iter().map(|&i| sentences[i].clone()).collect::<Vec<_>>().join(" ");
    }

    let mut blocks: Vec<String> = Vec::new();
    if let Some(p) = pin {
        if !p.is_empty() {
            blocks.push(p.join("\n"));
        }
    }
    if include_toc {
        let toc_text = render_toc(text);
        if !toc_text.is_empty() {
            blocks.push(toc_text);
        }
    }
    if !body.is_empty() {
        blocks.push(body);
    }
    (blocks.join("\n\n"), pinned_headings)
}

pub fn prepend_blocks(body: &str, include_toc: bool, pin: Option<&[String]>, text: &str) -> String {
    let mut blocks: Vec<String> = Vec::new();
    if let Some(p) = pin {
        if !p.is_empty() {
            blocks.push(p.join("\n"));
        }
    }
    if include_toc {
        let toc_text = render_toc(text);
        if !toc_text.is_empty() {
            blocks.push(toc_text);
        }
    }
    if !body.is_empty() {
        blocks.push(body.to_string());
    }
    blocks.join("\n\n")
}
```

Add `pub mod pins;` to `rust/src/lib.rs` (near the other `pub mod` lines).

- [ ] **Step 5: Run Rust unit tests**

Run: `cd rust && cargo test --test pins`
Expected: PASS.

- [ ] **Step 6: clippy + fmt**

Run: `cd rust && cargo clippy --all-targets -- -D warnings && cargo fmt --check`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add rust/src/types.rs rust/src/pins.rs rust/src/lib.rs rust/tests/pins.rs
git commit -m "feat(rust): pinned_headings field + pins module"
```

---

### Task 10: Rust index selectors + pin opts on `summarize`

**Files:**
- Modify: `rust/src/tfidf.rs` (`select_default` returning indices; `summarize_with_attach`/new pin entry)
- Modify: `rust/src/coverage.rs` (index selector)
- Test: `rust/tests/pins.rs`

- [ ] **Step 1: Factor `select_default`** in `rust/src/tfidf.rs` returning `Option<(Vec<String>, Vec<usize>)>`, mirroring Task 4. `summarize_default` calls it and joins. Run `cargo test` to confirm byte-identity (existing fixture walkers guard this).

- [ ] **Step 2: Add a pin-aware options struct + entry point.** Define:

```rust
#[derive(Debug, Clone, Default)]
pub struct PinOpts {
    pub keep_headings: bool,
    pub include_toc: bool,
    pub pin: Vec<String>,
}
```

Add `pub fn summarize_with_pins(text: &str, max_length: usize, mode: Mode, hints: &SummarizeOpts, pins: &PinOpts) -> SummaryResult` that:
- computes the plain `summary` for the mode (reusing `summarize_with_hints`/`summarize_default`/coverage),
- if `keep_headings`, calls the matching index selector (`select_default` / coverage / hints) and `render_with_pins`,
- else if `include_toc || !pin.is_empty()`, calls `prepend_blocks`,
- sets `pinned_headings` on the result.

- [ ] **Step 3: Write/extend Rust test** asserting `summarize_with_pins` pins the title for the sample doc; run `cargo test --test pins`.

- [ ] **Step 4: clippy + fmt + full Rust suite**

Run: `cd rust && cargo test && cargo test --features wordforms && cargo clippy --all-targets -- -D warnings && cargo fmt --check`
Expected: clean + green.

- [ ] **Step 5: Commit**

```bash
git add rust/src/tfidf.rs rust/src/coverage.rs rust/tests/pins.rs
git commit -m "feat(rust): summarize_with_pins + index selectors"
```

---

## SLICE 4 — parity fixtures + docs + version

### Task 11: Parity fixture generator + walker

**Files:**
- Create: `benchmarks/gen_pin_fixtures.py`
- Modify: `rust/tests/fixtures.rs` (new walker `v0_4_2_pins_byte_identical`)
- Create (generated): `fixtures/v0_4_2_pins/<corpus>__<case>/{input.txt,args.json,expected.txt}`

- [ ] **Step 1: Create `benchmarks/gen_pin_fixtures.py`** (mirror `gen_hint_fixtures.py`)

```python
"""Generate v0.4.2 heading/pin parity fixtures.

For each (corpus, case) pair, runs Python summarize() with the configured
pin args and writes input.txt / args.json / expected.txt under
fixtures/v0_4_2_pins/<corpus>__<case>/. The Rust walker
(rust/tests/fixtures.rs::v0_4_2_pins_byte_identical) byte-compares.

Run: python benchmarks/gen_pin_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lede import summarize  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_ROOT = ROOT / "fixtures" / "v0_4_2_pins"

# (case, keep_headings, include_toc, pin, hints, mode, max_length)
CASES = [
    ("headings_default",     True,  False, None,        None,        "default",  300),
    ("headings_coverage",    True,  False, None,        None,        "coverage", 300),
    ("headings_hints",       True,  False, None,        ["county"],  "default",  300),
    ("toc_only",             False, True,  None,        None,        "default",  300),
    ("pin_only",             False, False, ["PINNED A", "PINNED B"], None, "default", 300),
    ("all_three",            True,  True,  ["PINNED A"], None,       "default",  300),
    ("headings_off_control", False, False, None,        None,        "default",  300),
]


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    if not corpora:
        print(f"no corpora in {CORPUS_DIR}", file=sys.stderr)
        return 1
    written = 0
    for corpus_path in corpora:
        name = corpus_path.stem
        text = corpus_path.read_text(encoding="utf-8")
        for case, keep, toc, pin, hints, mode, max_len in CASES:
            base = OUT_ROOT / f"{name}__{case}"
            base.mkdir(parents=True, exist_ok=True)
            (base / "input.txt").write_text(text, encoding="utf-8")
            (base / "args.json").write_text(json.dumps({
                "keep_headings": keep,
                "include_toc": toc,
                "pin": pin,
                "hints": hints,
                "mode": mode,
                "max_length": max_len,
            }, indent=2, sort_keys=True), encoding="utf-8")
            out = summarize(
                text, max_length=max_len, mode=mode, hints=hints,
                keep_headings=keep, include_toc=toc, pin=pin,
            ).summary
            (base / "expected.txt").write_text(out, encoding="utf-8")
            written += 1
    print(f"Wrote {written} pin fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Generate fixtures**

Run: `.venv/bin/python benchmarks/gen_pin_fixtures.py`
Expected: prints "Wrote N pin fixtures."; `fixtures/v0_4_2_pins/` populated.

- [ ] **Step 3: Add the Rust walker to `rust/tests/fixtures.rs`** (mirror `v0_4_hints_byte_identical`, parsing the pin args and calling `summarize_with_pins`):

```rust
#[test]
fn v0_4_2_pins_byte_identical() {
    use lede::Mode;
    use lede::hints::HintMode;
    use lede::tfidf::{summarize_with_pins, PinOpts, SummarizeOpts};
    use serde_json::Value;
    use std::fs;

    let dir = fixtures_root().join("v0_4_2_pins");
    assert!(dir.is_dir(), "missing fixtures directory: {}", dir.display());

    let mut fixture_dirs: Vec<_> = fs::read_dir(&dir)
        .expect("read v0_4_2_pins dir")
        .filter_map(Result::ok)
        .map(|e| e.path())
        .filter(|p| p.is_dir())
        .collect();
    fixture_dirs.sort();
    assert!(!fixture_dirs.is_empty(), "no fixtures in {}", dir.display());

    let mut failures = Vec::new();
    for fixture in &fixture_dirs {
        let text = fs::read_to_string(fixture.join("input.txt")).expect("input.txt");
        let args: Value =
            serde_json::from_str(&fs::read_to_string(fixture.join("args.json")).expect("args.json"))
                .expect("parse args.json");
        let expected = fs::read_to_string(fixture.join("expected.txt")).expect("expected.txt");

        let max_length = args["max_length"].as_u64().expect("max_length") as usize;
        let mode = match args["mode"].as_str().unwrap_or("default") {
            "coverage" => Mode::Coverage,
            "legacy" => Mode::Legacy,
            _ => Mode::Default,
        };
        let hints: Vec<(String, f64)> = match &args["hints"] {
            Value::Array(arr) => arr
                .iter()
                .filter_map(|v| v.as_str().map(|s| (s.to_string(), 1.0)))
                .collect(),
            _ => vec![],
        };
        let pin: Vec<String> = match &args["pin"] {
            Value::Array(arr) => arr
                .iter()
                .filter_map(|v| v.as_str().map(str::to_string))
                .collect(),
            _ => vec![],
        };
        let hint_opts = SummarizeOpts { hints, hint_focus: 0.7, hint_mode: HintMode::Soft };
        let pin_opts = PinOpts {
            keep_headings: args["keep_headings"].as_bool().unwrap_or(false),
            include_toc: args["include_toc"].as_bool().unwrap_or(false),
            pin,
        };
        let actual = summarize_with_pins(&text, max_length, mode, &hint_opts, &pin_opts).summary;
        if actual.as_bytes() != expected.as_bytes() {
            failures.push(format!(
                "{}: bytes differ\n  expected ({}): {:?}\n  actual ({}): {:?}",
                fixture.file_name().and_then(|s| s.to_str()).unwrap_or("<?>"),
                expected.len(), expected, actual.len(), actual,
            ));
        }
    }
    assert!(
        failures.is_empty(),
        "v0_4_2_pins parity FAILED ({} of {}):\n\n{}",
        failures.len(), fixture_dirs.len(), failures.join("\n\n")
    );
}
```

- [ ] **Step 4: Run the walker**

Run: `cd rust && cargo test --test fixtures v0_4_2_pins_byte_identical`
Expected: PASS. If any mismatch: it is a real Python↔Rust divergence — fix the Rust `pins.rs`/selector, NOT the fixture.

- [ ] **Step 5: Confirm the existing parity walkers still pass**

Run: `cd rust && cargo test --test fixtures`
Expected: `every_fixture_byte_identical`, `v0_2_extract_primitives_byte_identical`, `v0_4_hints_byte_identical`, and the new walker all green.

- [ ] **Step 6: Commit**

```bash
git add benchmarks/gen_pin_fixtures.py fixtures/v0_4_2_pins rust/tests/fixtures.rs
git commit -m "test(parity): v0.4.2 heading/pin fixtures + Rust walker"
```

---

### Task 12: Example script + CHANGELOG + version bump to 0.4.2

**Files:**
- Create: `examples/10_keep_headings.py`
- Modify: `CHANGELOG.md`
- Modify: `pyproject.toml:7`, `rust/Cargo.toml:3`, `packages/lede-spacy/pyproject.toml:7`
- Modify: `CLAUDE.md` Status line

- [ ] **Step 1: Create `examples/10_keep_headings.py`** — a runnable script (matching the style of `examples/08_hints.py`) showing `keep_headings=True`, `pin=[...]`, and `include_toc=True`, printing `.summary` and `.pinned_headings`. CI smoke-tests `examples/`, so it must run clean and exit 0.

- [ ] **Step 2: Run the example**

Run: `.venv/bin/python examples/10_keep_headings.py`
Expected: prints output, exits 0.

- [ ] **Step 3: Add a CHANGELOG entry** under a new `## 0.4.2` heading: the three kwargs, `pinned_headings` field, budget-on-top, default-off byte-identity, Python↔Rust parity.

- [ ] **Step 4: Bump versions** to `0.4.2` in the three manifests; update `CLAUDE.md` Status line to mention v0.4.2 heading/pin retention.

- [ ] **Step 5: Full verification gate**

Run, expecting all green:
```bash
.venv/bin/python -m pytest -q
cd packages/lede-spacy && ../../.venv/bin/python -m pytest -q && cd ../..
cd rust && cargo test && cargo test --features wordforms && cargo clippy --all-targets -- -D warnings && cargo fmt --check && cd ..
.venv/bin/python benchmarks/gen_pin_fixtures.py   # idempotent — no diff after commit
git status --porcelain fixtures/v0_4_2_pins        # expect empty (fixtures already committed & deterministic)
```

- [ ] **Step 6: Commit**

```bash
git add examples/10_keep_headings.py CHANGELOG.md pyproject.toml rust/Cargo.toml packages/lede-spacy/pyproject.toml CLAUDE.md
git commit -m "release: v0.4.2 — optional heading/pin retention in summarize"
```

---

## Self-review notes

- **Spec coverage:** keep_headings (T2-T5,T9-T10), include_toc (T3,T9), pin (T3,T5,T9), title fold (T2 `document_title_index`, T3 weave), pin-block placement (T3 `prepend_blocks`/blocks order), no-op safety (T5 Step 4 note + render guard), legacy rejection (T5), coverage (T7), hints compose (T8), `pinned_headings` field (T1,T9), parity fixtures (T11), budget-on-top (T5 test), docs (T6,T12), version 0.4.2 (T12).
- **Determinism:** every selector sorts indices ascending; dedup uses first-occurrence via an `emitted` set keyed by index; no hashing/locale dependence in ordering.
- **Byte-identity guard:** Tasks 4, 7, 8, 10 Step 1 are pure refactors validated by running the *existing* suites/fixture walkers before any pin behavior is added.
- **Type consistency:** `render_with_pins` / `prepend_blocks` / `nearest_heading_map` / `document_title_index` / `render_toc` names identical across `_pins.py` and `pins.rs`; `PinOpts`/`SummarizeOpts` are the Rust option structs.
