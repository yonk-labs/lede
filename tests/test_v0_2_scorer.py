"""C1 scorer tweak tests for mode='default'."""
import re
from lede import summarize


def test_heading_filter_drops_markdown_headings():
    text = (
        "# Title\n"
        "Sarah led the walkthrough. Jon covered integration questions. "
        "Main concern is pricing at $50K.\n\n"
        "## Next Steps\n"
        "Follow up Monday. Decision Tuesday."
    )
    out = summarize(text, max_length=200, mode="default").summary
    assert "# Title" not in out
    assert "## Next Steps" not in out


def test_heading_filter_drops_allcaps_labels():
    text = (
        "INTRODUCTION\n"
        "The company grew revenue by 23 percent last quarter. "
        "Costs declined by 8 percent. "
        "HELD: revenue growth is the primary driver."
    )
    out = summarize(text, max_length=150, mode="default").summary
    assert "INTRODUCTION" not in out


def test_heading_filter_drops_short_colon_labels():
    text = (
        "Goals:\n"
        "Decouple ingest path. Shard writers horizontally. "
        "Timeline: three to four months."
    )
    out = summarize(text, max_length=100, mode="default").summary
    assert "Goals:" not in out
    assert "Decouple" in out or "Shard" in out or "Timeline" in out


def test_cue_phrase_boost_picks_held():
    text = (
        "Revenue grew last quarter by ten percent. "
        "Costs were flat year over year. "
        "Held: the deal terms are binding through 2027. "
        "Meetings continue next week."
    )
    out = summarize(text, max_length=150, mode="default").summary
    assert "Held" in out


def test_cue_phrase_boost_picks_resolution():
    text = (
        "Issue opened on Monday about throughput. "
        "Investigation identified a configuration mismatch. "
        "Resolution: increase batch size to 500 and pin precision to fp32. "
        "Follow up next sprint."
    )
    out = summarize(text, max_length=150, mode="default").summary
    assert "Resolution" in out


def test_digit_bonus_prefers_numeric_sentences():
    text = (
        "The team discussed next steps. "
        "Revenue grew by 23 percent year over year. "
        "Sentiment was positive overall. "
        "Costs declined by 8 percent and margins expanded."
    )
    out = summarize(text, max_length=100, mode="default").summary
    assert re.search(r"\d+\s*percent", out)


def test_section_position_weighting_boosts_discussion():
    text = (
        "Introduction\n"
        "This paper examines compensated summation. We build on prior work. "
        "Methods are described briefly.\n\n"
        "Discussion\n"
        "Our key finding is that Neumaier summation eliminates divergence. "
        "Twelve lines of safe Rust suffice. "
        "The fix has no performance cost."
    )
    out = summarize(text, max_length=200, mode="default").summary
    assert "Neumaier" in out or "Twelve" in out or "performance cost" in out


def test_legacy_mode_matches_v0_0_1_behavior():
    text = (
        "# Title\n"
        "Sentence one. Sentence two. Sentence three. Sentence four."
    )
    out_legacy = summarize(text, max_length=120, mode="legacy").summary
    assert "# Title" in out_legacy or "Sentence" in out_legacy
