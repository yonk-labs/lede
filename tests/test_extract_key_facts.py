import pytest

from skimr.extract import key_facts


def test_key_facts_returns_sentences_containing_stats():
    text = (
        "Unit tests pass at 94 percent coverage. "
        "The team saw 20 users onboard last quarter. "
        "Some unrelated prose without numbers. "
        "Deploy takes 5 minutes on average."
    )
    out = key_facts(text, max_facts=10)
    assert any("94 percent" in s for s in out)
    # 20 users is a count stat (see _COUNT_RE keyword list in stats.py)
    assert any("20 users" in s for s in out)
    assert any("5 minutes" in s for s in out)
    # Prose without stats should not appear
    assert not any("unrelated prose" in s for s in out)


def test_key_facts_respects_max_facts():
    text = "We saw 1 event. Then 2 events. Then 3 events. Then 4 events. Then 5 events."
    out = key_facts(text, max_facts=2)
    assert len(out) == 2


def test_key_facts_returns_document_order():
    """Output should be in the order sentences appear in the doc, not score order."""
    text = (
        "Revenue rose 40 percent in Q1. "
        "Middle sentence with no stat. "
        "Costs fell 12 percent over the year."
    )
    out = key_facts(text, max_facts=10)
    # If both fit, 40 percent appears before 12 percent (document order)
    q1_idx = next((i for i, s in enumerate(out) if "40 percent" in s), None)
    q4_idx = next((i for i, s in enumerate(out) if "12 percent" in s), None)
    assert q1_idx is not None and q4_idx is not None
    assert q1_idx < q4_idx


def test_key_facts_dedups_same_fact_across_sentences():
    """Two sentences restating the same stat value+type should not both appear."""
    text = (
        "We processed 50,000 events in the pilot. "
        "Later analysis confirmed 50,000 events were processed. "
        "Totally separate: 3 percent error rate was observed."
    )
    out = key_facts(text, max_facts=10)
    # Only one of the two '50,000 events' sentences should survive
    count = sum(1 for s in out if "50,000 events" in s)
    assert count == 1
    # The 3 percent sentence should still appear
    assert any("3 percent" in s for s in out)


def test_key_facts_word_forms_when_enabled():
    pytest.importorskip("text_to_num")
    text = "The project took eight days. Coverage improved to 94 percent."
    out = key_facts(text, max_facts=10, convert_word_names=True)
    assert any("eight days" in s for s in out)
    assert any("94 percent" in s for s in out)


def test_key_facts_empty_for_no_stats():
    text = "Just prose here. No numbers anywhere. Nothing to extract."
    assert key_facts(text) == ()
