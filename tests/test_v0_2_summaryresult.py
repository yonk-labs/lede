"""SummaryResult + attach=... plumbing tests."""
import json
import pytest
from lede import format_extract, readable_report, summarize, ReadableReport, SummaryResult
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


def test_summaryresult_to_dict_json_and_markdown():
    r = summarize(
        "Revenue grew 23 percent in 2026. Costs were flat. Margins improved.",
        max_length=150,
        attach=["stats", "metadata"],
    )
    data = r.to_dict()
    assert data["summary"] == r.summary
    assert isinstance(data["stats"], list)
    assert data["metadata"]["dates"] == ["2026"]

    parsed = json.loads(r.to_json())
    assert parsed == data

    md = r.to_markdown()
    assert md.startswith("## Summary")
    assert "## Stats" in md
    assert "## Metadata" in md


def test_format_extract_for_primitive_results():
    from lede.extract import key_facts, metadata

    facts = key_facts("Revenue grew 23 percent. Costs were flat. Margins improved.")
    assert json.loads(format_extract("key_facts", facts, output="json")) == list(facts)
    assert format_extract("key_facts", facts, output="markdown").startswith("## Key Facts")

    m = metadata("Launch was on 2026-05-23.")
    assert "2026-05-23" in format_extract("metadata", m, output="markdown")


def test_format_extract_correlate_markdown_groups_sentence_once():
    rows = (
        PhraseFact("acme", "10", "growth", "Acme grew 10 percent and 20 users."),
        PhraseFact("acme", "20 users", "growth", "Acme grew 10 percent and 20 users."),
    )
    md = format_extract("correlate_facts", rows, output="markdown")
    assert md.count("Acme grew 10 percent and 20 users.") == 1
    assert "`acme` -> `10`" in md
    assert "`acme` -> `20 users`" in md


def test_format_extract_correlate_text_groups_sentence_once():
    rows = (
        PhraseFact("acme", "10", "growth", "Acme grew 10 percent and 20 users."),
        PhraseFact("acme", "20 users", "growth", "Acme grew 10 percent and 20 users."),
    )
    out = format_extract("correlate_facts", rows, output="text")
    assert out.count("Acme grew 10 percent and 20 users.") == 1
    assert "acme\t10\tgrowth" in out
    assert "acme\t20 users\tgrowth" in out


def test_readable_report_api_text_markdown_json():
    from lede import FactRecord, PromotionCandidate, ReportAttribute

    assert ReportAttribute.__name__ == "ReportAttribute"
    assert FactRecord.__name__ == "FactRecord"
    assert PromotionCandidate.__name__ == "PromotionCandidate"

    r = readable_report(
        "Revenue grew 23 percent. Costs fell 5 percent. Acme Corp paid $10.",
        max_length=2000,
        max_facts=5,
    )
    assert isinstance(r, ReadableReport)
    assert "Revenue grew" in r.summary.summary
    assert r.key_facts
    assert r.stats

    text = r.to_text()
    assert "Facts and Important Details" in text
    assert "Lede key facts:" in text

    md = r.to_markdown()
    assert md.startswith("## Summary")
    assert "## Facts and Important Details" in md
    assert "spaCy" not in md

    data = json.loads(r.to_json())
    assert "summary" in data
    assert "key_facts" in data
    assert "attributes" in data
    assert "fact_records" in data
    assert "promotion_candidates" in data
    assert "search_text" in data


def test_readable_report_extracts_structured_attribute_candidates():
    text = """# Snyder v. United States

**Docket Number:** 23-108
**Citation:** 603 U.S. ___ (2024)
**Term:** 2023
**Petitioner:** James E. Snyder
**Respondent:** United States of America

Justice Ketanji Brown Jackson authored a dissenting opinion.
"""
    r = readable_report(text, max_length=2000, max_facts=5)
    data = json.loads(r.to_json())

    assert data["attributes"]["docket_number"]["value"] == "23-108"
    assert data["attributes"]["docket_number"]["type"] == "identifier"
    assert data["attributes"]["citation"]["value"] == "603 U.S. ___ (2024)"
    assert data["attributes"]["citation"]["type"] == "citation"
    assert data["attributes"]["term"]["value"] == "2023"
    assert data["attributes"]["term"]["type"] == "year"
    assert data["attributes"]["petitioner"]["value"] == "James E. Snyder"
    assert {
        "path": "lede_report.attributes.term.value",
        "key": "term",
        "value_type": "year",
        "promote": True,
        "confidence": 0.99,
    } in data["promotion_candidates"]
    assert any(row["predicate"] == "term" and row["object"] == "2023" for row in data["fact_records"])
    assert "Term: 2023" in data["search_text"]

    md = r.to_markdown()
    assert "### Structured Metadata Candidates" in md
    assert "### Important Detail Records" in md
    assert "### Promotion Candidates" not in md
    assert "### Fact Records" not in md
    assert "lede_report.attributes.term.value" not in md


def test_readable_report_spacy_backend_adds_entity_fact_records():
    pytest.importorskip("lede_spacy")
    r = readable_report(
        "Acme Corp paid $10 in 2024. Revenue grew 23 percent.",
        backend="spacy",
        max_length=2000,
        max_facts=5,
    )
    assert r.spacy_metadata is not None
    assert "Acme Corp" in r.spacy_metadata.entities
    assert any(row.fact_type == "entity_number" for row in r.fact_records)


def test_readable_report_compacts_long_spacy_contexts():
    long_context = " ".join(["structured markdown context"] * 40)
    r = ReadableReport(
        summary=SummaryResult("Short summary."),
        spacy_facts=(PhraseFact("context", "40", "absolute", long_context),),
    )

    md = r.to_markdown()
    assert "### spaCy Entity-Fact Links" in md
    assert len(md) < len(long_context)
    assert "..." in md


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
