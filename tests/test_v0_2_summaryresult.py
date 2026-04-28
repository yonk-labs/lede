"""SummaryResult + attach=... plumbing tests."""
import pytest
from lede import summarize, SummaryResult
from lede.extract import Stat, Section, Metadata, PhraseFact


def test_summaryresult_str_returns_summary():
    r = summarize("Hello world. This is a test sentence.", max_length=100)
    assert str(r) == r.summary
    assert f"{r}" == r.summary


def test_attach_none_returns_bare():
    r = summarize("Sentence one. Sentence two. Sentence three.", max_length=80)
    assert isinstance(r, SummaryResult)
    assert r.stats is None
    assert r.outline is None
    assert r.metadata is None
    assert r.phrases is None
    assert r.correlated_facts is None


def test_attach_stats_populates_field():
    r = summarize("Revenue grew 23 percent last quarter. Costs were flat.",
                  max_length=150, attach=["stats"])
    assert r.stats is not None
    assert isinstance(r.stats, tuple)


def test_attach_outline_populates_field():
    r = summarize("# Title\nFirst sentence. Second sentence.",
                  max_length=150, attach=["outline"])
    assert r.outline is not None
    assert isinstance(r.outline, tuple)


def test_attach_metadata_populates_field():
    r = summarize("Sentence.", max_length=100, attach=["metadata"])
    assert r.metadata is not None
    # Metadata is a dataclass, not a tuple
    assert hasattr(r.metadata, "dates")


def test_attach_phrases_populates_field():
    r = summarize("Sentence A. Sentence B.", max_length=100, attach=["phrases"])
    assert r.phrases is not None
    assert isinstance(r.phrases, tuple)


def test_attach_correlated_facts_populates_field():
    r = summarize("Sentence A. Sentence B.", max_length=100, attach=["correlated_facts"])
    assert r.correlated_facts is not None
    assert isinstance(r.correlated_facts, tuple)


def test_attach_all_populates_everything():
    r = summarize(
        "Sentence A. Sentence B. Sentence C.", max_length=100,
        attach=["stats", "outline", "metadata", "phrases", "correlated_facts"],
    )
    assert r.stats is not None
    assert r.outline is not None
    assert r.metadata is not None
    assert r.phrases is not None
    assert r.correlated_facts is not None


def test_attach_rejects_unknown_key():
    with pytest.raises(ValueError, match="unknown attach"):
        summarize("text", max_length=50, attach=["nonexistent"])


def test_dataclasses_are_frozen():
    s = Stat(value="23%", unit="percent", phrase="revenue grew 23%",
             context_sentence="Revenue grew 23%.", stat_type="percent")
    with pytest.raises(Exception):
        s.value = "other"  # frozen dataclass

    sec = Section(depth=1, name="Results", representative_sentence="Revenue grew.")
    with pytest.raises(Exception):
        sec.name = "other"

    pf = PhraseFact(entity="revenue", number="23%", polarity="growth", sentence="Revenue grew 23%.")
    with pytest.raises(Exception):
        pf.entity = "other"


def test_stubs_return_empty_for_now():
    """Stub primitives return empty collections. Real impls land in T6-T11."""
    from lede.extract import stats, outline, phrases, correlate_facts
    assert stats("Any text") == ()
    assert outline("Any text") == ()
    assert phrases("Any text") == ()
    assert correlate_facts("Any text") == ()
