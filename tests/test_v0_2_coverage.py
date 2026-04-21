"""C2 coverage mode tests."""
from skimr import summarize


def test_coverage_picks_one_per_paragraph():
    text = (
        "Para one sentence A is here. Para one sentence B is here.\n\n"
        "Para two sentence A is here. Para two sentence B is here.\n\n"
        "Para three sentence A is here. Para three sentence B is here."
    )
    r = summarize(text, max_length=500, mode="coverage")
    assert r.summary.count("Para one") == 1
    assert r.summary.count("Para two") == 1
    assert r.summary.count("Para three") == 1


def test_coverage_respects_budget():
    paras = [f"Paragraph number {i} content sentence goes here with stuff." for i in range(6)]
    text = "\n\n".join(paras)
    r = summarize(text, max_length=200, mode="coverage")
    assert len(r.summary) <= 220


def test_coverage_ignores_tiny_paragraphs():
    text = (
        "Tiny.\n\n"
        "This second paragraph has enough characters to count here. "
        "And another sentence. "
        "And a third to pick from.\n\n"
        "Ok."
    )
    r = summarize(text, max_length=200, mode="coverage")
    assert "Tiny" not in r.summary
    assert "second paragraph" in r.summary or "another" in r.summary or "third" in r.summary


def test_coverage_splits_ends_support_ticket_style():
    text = (
        "Ticket opened about ingest hang after upgrade. "
        "Job hangs indefinitely with no error output.\n\n"
        "Investigation revealed that the new embedder attempts a model download. "
        "Air-gapped batch nodes cannot reach HuggingFace.\n\n"
        "Resolution: pin precision to fp32 and disable downloads. "
        "Ticket closed after overnight job completed in 19 minutes."
    )
    r = summarize(text, max_length=400, mode="coverage")
    assert "Ticket" in r.summary or "hang" in r.summary
    assert "Resolution" in r.summary or "closed" in r.summary
