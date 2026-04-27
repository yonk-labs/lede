"""Edge-case fixture tests — multibyte, ReDoS bait, large input, smart quotes.

Locks in the AAT-021 / PR-011 robustness work: every primitive should
return without panicking, deterministically, within a reasonable time
budget, on inputs that previously broke things (multi-byte UTF-8 near
stat tokens, 50K-digit ReDoS bait, 1 MB documents, CP1252-style
"smart" quotes).
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from skimr import brief, summarize
from skimr.extract import (
    correlate_facts,
    key_facts,
    metadata,
    outline,
    phrases,
    stats,
    toc,
)


FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "edge_cases"


def _load(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


PRIMITIVES = [
    ("stats", lambda t: stats(t)),
    ("outline", lambda t: outline(t)),
    ("toc", lambda t: toc(t)),
    ("metadata", lambda t: metadata(t)),
    ("phrases", lambda t: phrases(t)),
    ("correlate_facts", lambda t: correlate_facts(t)),
    ("key_facts", lambda t: key_facts(t)),
    ("summarize", lambda t: summarize(t, max_length=300).summary),
    ("brief_string", lambda t: brief(t)),
    ("brief_dict", lambda t: brief(t, format="dict")),
]


@pytest.mark.parametrize("name,fn", PRIMITIVES)
def test_multibyte_no_panic(name, fn):
    """Accented Latin, CJK, emoji adjacent to stat/heading tokens."""
    text = _load("multibyte.txt")
    out = fn(text)
    # Fail criterion: an exception inside fn() — pytest catches it.
    # We don't assert specific content because most primitives are
    # heuristic; we just want "doesn't panic" coverage.
    assert out is not None


@pytest.mark.parametrize("name,fn", PRIMITIVES)
def test_smart_quotes_no_panic(name, fn):
    """CP1252-shape smart quotes + em/en-dashes."""
    text = _load("cp1252_smart_quotes.txt")
    out = fn(text)
    assert out is not None


@pytest.mark.parametrize("name,fn", PRIMITIVES)
def test_redos_bait_within_budget(name, fn):
    """50K-digit unbroken run followed by ' tons' — the AAT/prod-ready
    canonical ReDoS regression. Every primitive must return in well
    under a second."""
    text = _load("redos_input.txt")
    t0 = time.perf_counter()
    out = fn(text)
    elapsed = (time.perf_counter() - t0) * 1000
    # 1 second is generous — the original bug took 224 s. Any primitive
    # that takes more than this on the bait input has regressed.
    assert elapsed < 1000, f"{name} took {elapsed:.0f}ms on ReDoS bait"
    assert out is not None


@pytest.mark.parametrize("name,fn", PRIMITIVES)
def test_large_1mb_within_budget(name, fn):
    """~1 MB input — every primitive should be linear-ish in input size.
    Budget chosen with headroom; if anything is quadratic we'll see it."""
    text = _load("large_1mb.txt")
    t0 = time.perf_counter()
    out = fn(text)
    elapsed = (time.perf_counter() - t0) * 1000
    assert elapsed < 30_000, f"{name} took {elapsed:.0f}ms on 1MB input"
    assert out is not None


@pytest.mark.parametrize("name,fn", PRIMITIVES)
def test_determinism_5_runs(name, fn):
    """Same input 5 times must return the same bytes (or equal value).
    Catches accidental hash-iteration / RNG / set-ordering leaks."""
    text = _load("multibyte.txt")
    first = fn(text)
    for _ in range(4):
        again = fn(text)
        assert again == first, f"{name} returned different output on rerun"
