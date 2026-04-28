"""Tests for lede.brief() — at-a-glance document brief composition primitive."""
import pytest

import lede


def test_brief_default_returns_string():
    text = (
        "# Introduction\n\nThis report covers Q1 performance.\n\n"
        "# Results\n\nRevenue grew 40 percent. Costs fell 10 percent. "
        "Team size reached 50 users.\n\n"
        "# Conclusion\n\nStrong quarter overall.\n"
    )
    out = lede.brief(text)
    assert isinstance(out, str)
    assert "Overview:" in out
    assert "Key facts:" in out
    assert "Also in this doc:" in out
    # Section names should be listed.
    assert "Introduction" in out
    assert "Results" in out
    assert "Conclusion" in out


def test_brief_dict_format():
    text = (
        "# Intro\n\nA document with stuff.\n\n"
        "# Details\n\nWe processed 1,000 events. 20 percent were retried.\n"
    )
    out = lede.brief(text, format="dict")
    assert isinstance(out, dict)
    assert set(out.keys()) == {"overview", "key_facts", "toc", "phrases"}
    assert isinstance(out["overview"], str)
    assert isinstance(out["key_facts"], list)
    assert isinstance(out["toc"], list)
    assert out["phrases"] is None  # include_phrases=False default


def test_brief_markdown_format():
    text = (
        "# Intro\n\nA document.\n\n"
        "# Details\n\nWe processed 1,000 events.\n"
    )
    out = lede.brief(text, format="markdown")
    assert isinstance(out, str)
    assert "## Overview" in out
    assert "## Also in this doc" in out
    # Bullet list formatting.
    assert "- Intro" in out
    assert "- Details" in out


def test_brief_include_phrases():
    text = (
        "# Section\n\n"
        "Customer support team handles deployment pipeline work. "
        "The customer support team reviews requests. "
        "Our deployment pipeline processes events. "
        "Customer support team also handles incidents.\n"
    )
    out = lede.brief(text, include_phrases=True, format="dict")
    assert out["phrases"] is not None
    assert len(out["phrases"]) > 0


def test_brief_skips_phrases_by_default():
    text = "Some text with phrases that repeat. Phrases that repeat make noise."
    out = lede.brief(text, format="dict")
    assert out["phrases"] is None


def test_brief_overview_max_clamped():
    text = "Short doc. Two sentences."
    # overview_max below floor — should still work without error.
    out = lede.brief(text, overview_max=0.01)
    assert isinstance(out, str)
    # overview_max above ceiling — still works.
    out = lede.brief(text, overview_max=0.99)
    assert isinstance(out, str)


def test_brief_invalid_format_raises():
    with pytest.raises(ValueError, match="format"):
        lede.brief("text", format="html")


def test_brief_auto_wordforms_when_available():
    """brief() should surface word-form numbers when text2num is installed."""
    pytest.importorskip("text_to_num")
    text = (
        "# Abstract\n\nWe tested on five thousand documents. Twelve lines of code.\n\n"
        "# Discussion\n\nResults were positive. Five thousand documents is a large corpus.\n"
    )
    out = lede.brief(text, format="dict")
    # key_facts should include at least one sentence with a word-form number.
    combined = " ".join(out["key_facts"])
    assert "five thousand" in combined or "twelve" in combined.lower()


def test_brief_handles_empty_text():
    out = lede.brief("")
    assert "Overview:" in out
    # key_facts / toc sections should be absent when empty.
    assert "Key facts:" not in out
    assert "Also in this doc:" not in out
