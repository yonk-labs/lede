"""Tests for lede.extract._backends — the pluggable backend registry.

Validates registry basics, default behavior, per-call override, and
auto-fallback. These run against lede core alone; lede-spacy is NOT
assumed to be importable.
"""
import pytest

import lede
from lede.extract import metadata
from lede.extract import _backends


@pytest.fixture(autouse=True)
def _restore_default():
    """Guarantee no test leaks a mutated default backend into siblings."""
    saved = _backends.get_default_backend()
    # Snapshot registered backends so optional backends (yake, spacy) survive
    # dummy-backend cleanup.
    saved_backends = {
        name: dict(fns) for name, fns in _backends._REGISTRY.items()
    }
    yield
    # Restore default and original registry state — drops any dummy backends
    # tests may have registered.
    _backends._DEFAULT = saved
    _backends._REGISTRY.clear()
    for name, fns in saved_backends.items():
        _backends._REGISTRY[name] = dict(fns)


def test_register_and_resolve_dummy_backend():
    """register + resolve round-trip on a dummy backend/primitive."""
    def _dummy(_text: str) -> str:
        return "dummy-result"

    _backends.register("dummy", "metadata", _dummy)
    fn = _backends.resolve("dummy", "metadata")
    assert fn is _dummy
    assert fn("anything") == "dummy-result"


def test_default_backend_is_regex_at_import():
    """Zero-dep identity: regex is the default backend out of the box."""
    assert _backends.get_default_backend() == "regex"


def test_metadata_regex_backend_regression():
    """backend='regex' preserves the T8 behavior: dates/amounts/urls populated, entities empty."""
    m = metadata(
        "Signed 2025-06-14 for $120K; see https://example.com/docs for details.",
        backend="regex",
    )
    assert "2025-06-14" in m.dates
    assert any("120K" in a for a in m.amounts)
    assert "https://example.com/docs" in m.urls
    assert m.entities == ()


def test_metadata_spacy_backend_missing_raises_import_error():
    """Without lede-spacy imported, backend='spacy' raises ImportError with guidance."""
    with pytest.raises(ImportError) as excinfo:
        metadata("anything", backend="spacy")
    msg = str(excinfo.value)
    assert "spacy" in msg
    assert "lede-spacy" in msg


def test_metadata_auto_falls_back_to_regex():
    """backend='auto' picks regex when only regex is registered (no lede-spacy)."""
    m = metadata(
        "Paid $50 on 2026-01-01 via https://pay.example.com.",
        backend="auto",
    )
    assert "2026-01-01" in m.dates
    assert m.entities == ()


def test_set_default_backend_affects_default_but_not_explicit_call():
    """Process-wide default changes default calls; per-call backend= still wins."""
    lede.set_default_backend("auto")
    # Default call now routes through 'auto' — still regex since no spacy.
    m_default = metadata("On 2025-06-14 we shipped.")
    assert "2025-06-14" in m_default.dates
    # Per-call override wins even when default is 'auto'.
    m_explicit = metadata("On 2025-06-14 we shipped.", backend="regex")
    assert "2025-06-14" in m_explicit.dates


def test_set_default_backend_rejects_unknown_name():
    """Unknown backend names are rejected with ValueError at set-time."""
    with pytest.raises(ValueError) as excinfo:
        lede.set_default_backend("no_such_backend")
    assert "no_such_backend" in str(excinfo.value)
