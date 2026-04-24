"""extract.phrases tests."""
import pytest

from skimr.extract import phrases


def test_phrases_finds_repeated_multiword_terms():
    text = (
        "The customer support team evaluated the deployment pipeline. "
        "The deployment pipeline is critical to the customer support team."
    )
    r = phrases(text)
    joined = " | ".join(r)
    assert "deployment pipeline" in joined
    assert "customer support" in joined


def test_phrases_ignores_singletons():
    text = "This unique term shows up only once elsewhere never again."
    r = phrases(text)
    # No multi-word phrase repeats, so nothing comes back
    assert r == ()


def test_phrases_keywords_include_hits():
    text = "Revenue grew. Costs fell. Margins expanded."
    r = phrases(text, keywords="revenue")
    assert any("revenue" in p.lower() for p in r)


def test_phrases_empty_input():
    assert phrases("") == ()


# -------- T13f: YAKE-backed phrases backend (optional dep) --------

def test_phrases_yake_backend_returns_ranked_phrases():
    """T13f: backend='yake' returns a non-empty tuple of lowercased phrases."""
    pytest.importorskip("yake")
    text = (
        "Deterministic byte-identical output across runtimes is a hard requirement. "
        "Prior work on cross-language parity has focused on string encoding. "
        "Byte-identical output matters for reproducible pipelines. "
        "Cross-language parity has been a focus."
    )
    out = phrases(text, backend="yake")
    assert isinstance(out, tuple)
    assert len(out) > 0
    assert all(isinstance(p, str) for p in out)
    assert all(p == p.lower() for p in out)


def test_phrases_yake_backend_without_dep_raises():
    """T13f: backend='yake' without yake installed raises helpful ImportError."""
    try:
        import yake  # noqa: F401
    except ImportError:
        with pytest.raises(ImportError, match="yake"):
            phrases("some text", backend="yake")
    else:
        pytest.skip("yake is installed; helpful error can't be triggered")


def test_phrases_yake_is_deterministic():
    """T13f: YAKE output is stable across repeat calls on the same input."""
    pytest.importorskip("yake")
    text = (
        "Determinism matters. Deterministic output matters more. "
        "Repeatable determinism beats randomness."
    )
    out1 = phrases(text, backend="yake")
    out2 = phrases(text, backend="yake")
    assert out1 == out2
