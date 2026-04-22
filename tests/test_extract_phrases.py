"""extract.phrases tests."""
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
