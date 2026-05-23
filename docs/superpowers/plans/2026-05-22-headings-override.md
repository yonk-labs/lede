# Caller-supplied `headings=` override — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a `headings: Sequence[str] | None = None` kwarg to `lede.summarize` that, when provided, replaces auto heading-detection for `keep_headings`/`include_toc` — letting callers supply known heading lines (e.g. from chunk metadata). Python + Rust byte-identical; default-off = byte-identical to v0.4.2.

**Architecture:** The override only affects *rendering* (which lines are treated as headings), never *selection*. So `_select_for_mode` is untouched. The work lives in `_pins.py` (`render_with_pins` + `prepend_blocks` gain a `headings` param and an override code path) and the `summarize` wiring in `tfidf.py`, mirrored in Rust.

**Spec:** `docs/superpowers/specs/2026-05-22-headings-override-design.md` (§4.3 is the authoritative algorithm).

---

## File structure

| File | Change |
|---|---|
| `src/lede/_pins.py` | `render_with_pins`/`prepend_blocks` gain `headings`; new `_render_override(...)` helper for §4.3 + `render_toc_from_list(...)` |
| `src/lede/tfidf.py` | `summarize` gains `headings` kwarg; threads to render funcs; legacy-reject includes `headings` |
| `rust/src/pins.rs` | mirror: `headings` params + override path |
| `rust/src/tfidf.rs` | `PinOpts.headings: Vec<String>`; thread through `summarize_with_pins` |
| `benchmarks/gen_headings_fixtures.py` | new generator |
| `rust/tests/fixtures.rs` | `v0_4_3_headings_byte_identical` walker |
| `tests/test_headings_override.py`, `rust/tests/headings_override.rs` | unit tests |
| `docs/REFERENCE.md`, `docs/whats-new-0.4.md`, `CHANGELOG.md`, `examples/`, version files | docs + 0.4.3 bump |

---

## SLICE 1 — Python

### Task 1: TOC-from-list + override renderer in `_pins.py`

**Files:** Modify `src/lede/_pins.py`; Test `tests/test_headings_override.py` (create).

- [ ] **Step 1: Write failing tests**

```python
# tests/test_headings_override.py
from lede._pins import render_toc_from_list, render_with_pins


def test_render_toc_from_list_dedupes_preserves_order():
    assert render_toc_from_list(["A", "B", "A", "C"]) == "A\nB\nC"


def test_override_keep_headings_title_unmatched_and_interleave():
    sentences = [
        "Syllabus",
        "The Court held X.",
        "Opinion of the Court",
        "The reasoning is Y.",
        "Costs were Z.",
    ]
    selected = [1, 3, 4]
    body, pinned = render_with_pins(
        sentences, selected,
        keep_headings=True, include_toc=False, pin=None,
        text="\n".join(sentences),
        headings=["Syllabus", "Opinion of the Court", "Dissent"],
    )
    # title (Syllabus, matched at 0 -> top, dedup), unmatched block (Dissent),
    # then body with Opinion interleaved before sentence 3.
    assert body == (
        "Syllabus\n"
        "Dissent\n"
        "The Court held X.\n"
        "Opinion of the Court\n"
        "The reasoning is Y. Costs were Z."
    )
    assert pinned == ("Syllabus", "Dissent", "Opinion of the Court")


def test_override_toc_block():
    sentences = ["Body one here is long enough.", "Body two also."]
    body, pinned = render_with_pins(
        sentences, [0, 1],
        keep_headings=False, include_toc=True, pin=None,
        text="x", headings=["Syllabus", "Opinion", "Dissent"],
    )
    assert body == "Syllabus\nOpinion\nDissent\n\nBody one here is long enough. Body two also."
    assert pinned == ()  # keep_headings off -> no pinned_headings


def test_override_none_falls_back_to_auto():
    # headings=None must behave exactly like v0.4.2 auto path
    sentences = ["# Title", "Body sentence one here.", "## Sub", "Body two here now."]
    a = render_with_pins(sentences, [1, 3], keep_headings=True, include_toc=False, pin=None, text="\n".join(sentences))
    b = render_with_pins(sentences, [1, 3], keep_headings=True, include_toc=False, pin=None, text="\n".join(sentences), headings=None)
    assert a == b
```

- [ ] **Step 2: Run, expect failure**

Run: `.venv/bin/python -m pytest tests/test_headings_override.py -v`
Expected: FAIL — `render_toc_from_list` / `headings` kwarg missing.

- [ ] **Step 3: Implement in `src/lede/_pins.py`**

Add `render_toc_from_list`:
```python
def render_toc_from_list(headings: "Sequence[str]") -> str:
    """TOC block from caller-supplied headings: deduped (first wins),
    given order, one per line, no indentation."""
    seen: set[str] = set()
    out: list[str] = []
    for h in headings:
        if h not in seen:
            seen.add(h)
            out.append(h)
    return "\n".join(out)
```

Add the override renderer:
```python
def _render_keep_headings_override(
    sentences: list[str],
    selected: list[int],
    headings: "Sequence[str]",
) -> tuple[str, list[str]]:
    """§4.3: render body using caller-supplied headings instead of auto-detection.
    Returns (body, pinned_headings_list)."""
    # 1. dedupe preserving order
    seen: set[str] = set()
    H: list[str] = []
    for h in headings:
        if h not in seen:
            seen.add(h)
            H.append(h)

    # 2. match each heading to first unclaimed body sentence (stripped-equality)
    matched_pos: dict[str, int] = {}
    claimed: set[int] = set()
    for h in H:
        hs = h.strip()
        for i, s in enumerate(sentences):
            if i in claimed:
                continue
            if s.strip() == hs:
                matched_pos[h] = i
                claimed.add(i)
                break
    pos_to_heading = {idx: h for h, idx in matched_pos.items()}
    matched_indices = sorted(matched_pos.values())

    pinned: list[str] = []
    out_lines: list[str] = []
    buf: list[str] = []
    emitted_idx: set[int] = set()
    emitted_text: set[str] = set()

    def flush() -> None:
        if buf:
            out_lines.append(" ".join(buf))
            buf.clear()

    # 3. title = H[0] at top; suppress its body position if matched
    title = H[0] if H else None
    if title is not None:
        out_lines.append(title)
        pinned.append(title)
        emitted_text.add(title)
        if title in matched_pos:
            emitted_idx.add(matched_pos[title])

    # 4. unmatched headings (excluding the title) as a leading block, given order
    for h in H:
        if h in emitted_text:
            continue
        if h not in matched_pos:
            out_lines.append(h)
            pinned.append(h)
            emitted_text.add(h)

    # 5. interleave matched headings before their section's selected sentences
    def nearest_matched(s_idx: int) -> int | None:
        best: int | None = None
        for mi in matched_indices:
            if mi <= s_idx:
                best = mi
            else:
                break
        return best

    for s_idx in selected:
        mi = nearest_matched(s_idx)
        if mi is not None and mi not in emitted_idx:
            flush()
            h = pos_to_heading[mi]
            out_lines.append(h)
            pinned.append(h)
            emitted_idx.add(mi)
            emitted_text.add(h)
        buf.append(sentences[s_idx])
    flush()

    return "\n".join(out_lines), pinned
```

Modify `render_with_pins` signature to add `headings: "Sequence[str] | None" = None` (keyword, after `text`), and at the top of the `if keep_headings:` branch, dispatch to the override when provided:
```python
    if keep_headings:
        if headings:
            body, pinned_list = _render_keep_headings_override(sentences, selected, headings)
            pinned_headings = pinned_list
        else:
            # ... existing auto-detection branch unchanged ...
```
Restructure so the existing auto branch is the `else`. Keep the no-op guard (empty pinned → plain join) for the AUTO branch only; in override mode `pinned_headings` always has at least the title when `H` is non-empty.

Modify the block-assembly tail: when `include_toc` and `headings` provided, use `render_toc_from_list(headings)` instead of `render_toc(text)`:
```python
    if include_toc:
        toc_text = render_toc_from_list(headings) if headings else render_toc(text)
        if toc_text:
            blocks.append(toc_text)
```

- [ ] **Step 4: Run tests, expect pass**

Run: `.venv/bin/python -m pytest tests/test_headings_override.py -v`
Expected: PASS.

- [ ] **Step 5: Full suite (no regression)**

Run: `.venv/bin/python -m pytest -q`
Expected: ALL pass (existing pin tests unaffected — `headings` defaults None).

- [ ] **Step 6: Commit**

```bash
git add src/lede/_pins.py tests/test_headings_override.py
git commit -m "feat(pins): caller-supplied headings override renderer"
```

---

### Task 2: `prepend_blocks` headings + `summarize` wiring

**Files:** Modify `src/lede/_pins.py` (`prepend_blocks`), `src/lede/tfidf.py`; Test `tests/test_headings_override.py`.

- [ ] **Step 1: Write failing tests**

```python
# tests/test_headings_override.py (append)
import pytest
from lede import summarize

_DOC = (
    "Syllabus\n\n"
    "The Court held that the statute is constitutional under precedent.\n\n"
    "Opinion of the Court\n\n"
    "The reasoning rests on the commerce clause and prior rulings here.\n"
)


def test_summarize_headings_override_keep_headings():
    r = summarize(_DOC, max_length=300, keep_headings=True,
                  headings=["Syllabus", "Opinion of the Court", "Dissent"])
    assert r.summary.startswith("Syllabus")
    assert "Dissent" in r.pinned_headings           # unmatched still survives
    assert "Opinion of the Court" in r.pinned_headings


def test_summarize_headings_override_toc():
    r = summarize(_DOC, max_length=300, include_toc=True,
                  headings=["Syllabus", "Opinion", "Dissent"])
    assert r.summary.startswith("Syllabus\nOpinion\nDissent\n\n")


def test_headings_without_flags_is_noop():
    base = summarize(_DOC, max_length=300).summary
    assert summarize(_DOC, max_length=300, headings=["Syllabus"]).summary == base


def test_headings_default_none_byte_identical():
    assert summarize(_DOC, max_length=300, keep_headings=True).summary == \
           summarize(_DOC, max_length=300, keep_headings=True, headings=None).summary


def test_legacy_rejects_headings():
    with pytest.raises(ValueError, match="legacy"):
        summarize(_DOC, max_length=300, mode="legacy", headings=["X"], include_toc=True)
```

- [ ] **Step 2: Run, expect failure** (`summarize() got an unexpected keyword argument 'headings'`).

- [ ] **Step 3: Implement**

In `src/lede/_pins.py`, give `prepend_blocks` a `headings` param and use the list-TOC when provided:
```python
def prepend_blocks(body, *, include_toc, pin, text, headings=None):
    blocks = []
    if pin:
        blocks.append("\n".join(pin))
    if include_toc:
        toc_text = render_toc_from_list(headings) if headings else render_toc(text)
        if toc_text:
            blocks.append(toc_text)
    if body:
        blocks.append(body)
    return "\n\n".join(b for b in blocks if b)
```

In `src/lede/tfidf.py` `summarize`:
- Add `headings: "Sequence[str] | None" = None` to the signature (after `pin`).
- Update `pins_active`: `pins_active = bool(keep_headings) or bool(include_toc) or bool(pin) or bool(headings)`.
  - BUT per spec §4.3 edge: `headings` alone (both flags off) is a no-op. So keep the legacy-reject keyed on `pins_active`, but in the pin post-processing, `headings` only acts through `keep_headings`/`include_toc`. Since `headings` alone shouldn't change output, ensure the post-processing leaves `summary_text` unchanged when only `headings` is set: the `if sel ... elif include_toc or pin:` branch already won't fire for headings-only (keep_headings False, include_toc False, pin None) — good, so `headings`-only is a natural no-op. Confirm `pins_active` including `headings` doesn't cause the legacy-reject to wrongly fire for a `headings`-only default-mode call — it only raises in legacy mode, which is acceptable (passing `headings` in legacy is rejected; fine).
- Thread `headings` into both calls:
```python
        if sel is not None:
            sentences, selected = sel
            summary_text, pinned_headings = render_with_pins(
                sentences, selected, keep_headings=True,
                include_toc=include_toc, pin=pin, text=text, headings=headings,
            )
        elif include_toc or pin:
            summary_text = prepend_blocks(
                summary_text, include_toc=include_toc, pin=pin, text=text, headings=headings,
            )
```

- [ ] **Step 4: Run tests** → PASS. **Step 5: Full suite** → no regression.

- [ ] **Step 6: Commit**

```bash
git add src/lede/_pins.py src/lede/tfidf.py tests/test_headings_override.py
git commit -m "feat(summarize): headings= override kwarg (default mode + toc)"
```

---

### Task 3: docstring + REFERENCE

- [ ] Extend `summarize` docstring with the `headings` Args entry + a short note (override replaces auto-detection; flat TOC; §4.3 placement). Add a `headings`-override paragraph to the REFERENCE "Heading & pin retention" section. Run `.venv/bin/python -m pytest -q` (docstring is code). Commit `docs: document headings= override`.

---

## SLICE 2 — Rust mirror

### Task 4: `PinOpts.headings` + override in `pins.rs`

**Files:** `rust/src/pins.rs`, `rust/src/tfidf.rs` (`PinOpts`), `rust/tests/headings_override.rs`.

- [ ] **Step 1: Write failing Rust unit test** mirroring Task 1's `test_override_keep_headings_title_unmatched_and_interleave` (same sentences/headings/expected body + pinned). Use `lede::pins::render_with_pins` (new arg) — see Step 3 for the signature.

- [ ] **Step 2: Run `cd rust && cargo test --test headings_override`** → fail (signature/missing).

- [ ] **Step 3: Implement in `rust/src/pins.rs`**

Add `render_toc_from_list(headings: &[String]) -> String` (dedupe-preserve-order, join `\n`). Add `render_keep_headings_override(sentences: &[String], selected: &[usize], headings: &[String]) -> (String, Vec<String>)` mirroring `_render_keep_headings_override` exactly (same dedup, stripped-equality match via `s.trim() == h.trim()`, title-at-top with dedup, unmatched block, nearest-matched interleave). Add a `headings: Option<&[String]>` param to `render_with_pins` and `prepend_blocks`; dispatch to the override when `Some(non-empty)`, else the existing auto path; use `render_toc_from_list` for the TOC when headings provided.

- [ ] **Step 4: `cargo test --test headings_override`** → pass.

### Task 5: thread `headings` through `summarize_with_pins`

- [ ] Add `pub headings: Vec<String>` to `PinOpts` (in `rust/src/tfidf.rs`). In `summarize_with_pins`, compute `let headings_slice = if pin_opts.headings.is_empty() { None } else { Some(pin_opts.headings.as_slice()) };` and pass to `render_with_pins`/`prepend_blocks`. Update `pins_active` to include `!pin_opts.headings.is_empty()`. Add a unit test for the public `summarize_with_pins` override path.
- [ ] `cd rust && cargo test && cargo test --features wordforms && cargo clippy --all-targets -- -D warnings && cargo fmt --check` → all green/clean.
- [ ] Commit `feat(rust): headings override in PinOpts + pins`.

---

## SLICE 3 — parity fixtures + release

### Task 6: parity fixtures + walker

- [ ] Create `benchmarks/gen_headings_fixtures.py` (mirror `gen_pin_fixtures.py`). Cases per corpus (args include a `headings` list): `override_keep` (keep_headings + headings, some matched some not), `override_toc` (include_toc + headings), `override_both`, `override_hints` (keep_headings + headings + hints=["court"]), `headings_noop` (headings set, flags off). args.json includes `headings`, `keep_headings`, `include_toc`, `pin`, `hints`, `mode`, `max_length`.
- [ ] Run `.venv/bin/python benchmarks/gen_headings_fixtures.py` → populates `fixtures/v0_4_3_headings/`.
- [ ] Add `v0_4_3_headings_byte_identical` walker to `rust/tests/fixtures.rs` (mirror `v0_4_2_pins_byte_identical`, parse `headings` array into `PinOpts.headings`).
- [ ] `cd rust && cargo test --test fixtures` → all FIVE walkers green. If divergence: fix Rust to match Python (likely the override match/order logic), never edit fixtures.
- [ ] Commit `test(parity): v0.4.3 headings-override fixtures + walker`.

### Task 7: example + CHANGELOG + version 0.4.3

- [ ] Add `examples/11_headings_override.py` (runnable, exits 0): chunkshop-style `headings=` with `keep_headings` and with `include_toc`.
- [ ] CHANGELOG `[0.4.3]` entry; bump `pyproject.toml` + `rust/Cargo.toml` (and `packages/lede-spacy/pyproject.toml` for lockstep) `0.4.2 → 0.4.3`; update `CLAUDE.md` Status line; `cd rust && cargo build` to refresh `Cargo.lock`.
- [ ] Verification gate: `.venv/bin/python -m pytest -q`; `cd packages/lede-spacy && ../../.venv/bin/python -m pytest -q` (spaCy now installed); `cd rust && cargo test && cargo test --features wordforms && cargo clippy --all-targets -- -D warnings && cargo fmt --check`; regenerate fixtures and confirm `git status --porcelain fixtures/v0_4_3_headings` is empty (deterministic).
- [ ] Commit `release: v0.4.3 — caller-supplied headings= override`.

---

## Self-review notes

- Coverage: TOC-from-list (T1/T4), override §4.3 algorithm (T1/T4), summarize wiring + no-op + legacy reject (T2/T5), docstring/REFERENCE (T3), parity (T6), release (T7).
- Determinism: dedupe preserves first-occurrence; matching is first-unclaimed exact stripped-equality; `nearest_matched` scans sorted matched indices. No hashing/locale ordering.
- `headings=None` path is byte-identical (auto branch unchanged) — guarded by existing walkers + `test_headings_default_none_byte_identical`.
- Names identical Python↔Rust: `render_toc_from_list`, `render_keep_headings_override` (`_render_*` private in Python), `render_with_pins`/`prepend_blocks` gain `headings`.
