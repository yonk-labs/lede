"""Example 11 — Caller-supplied headings= override in summarize.

The v0.4.3 ``headings=`` kwarg lets callers pass heading lines that
auto-detection would miss — caption-style labels, all-caps section titles,
or headings extracted from chunk metadata.  When non-empty, these lines
replace the auto-detector for both ``keep_headings`` and ``include_toc``.

Use case: SCOTUS opinions and similar legal/regulatory documents use
caption-style headings ("I.", "BACKGROUND", "DISCUSSION") that the
Markdown-oriented auto-detector never matches.  Callers can run
``lede.extract.toc()`` first, discover an empty result, then supply the
known heading lines via ``headings=`` to get structured output anyway.

Run: python examples/11_headings_override.py
"""
from lede import summarize


# Caption-style headings — no Markdown ``#`` prefix, so auto-detection
# returns nothing.  One heading ("CONCLUSION") does not appear in the body
# text; it still survives as a leading block in the output.
DOC = """BACKGROUND

The Federal Communications Commission adopted new broadband rules in 2024.
The rules require providers to disclose speeds, latency, and fees upfront.
Consumer advocates praised the transparency requirements.

DISCUSSION

Broadband providers challenged the rules in the D.C. Circuit.
The court applied Loper Bright scrutiny to the agency's statutory authority.
The commission argued the 2017 rollback did not strip its rulemaking power.

FINDINGS

The agency exceeded its authority under the revised statutory interpretation.
Three of the five judges agreed on the jurisdictional question.
The dissent argued the majority read the statute too narrowly.
"""

SUPPLIED_HEADINGS = ["BACKGROUND", "DISCUSSION", "FINDINGS", "CONCLUSION"]


def main() -> None:
    print("=" * 60)
    print("summarize() — keep_headings=True + headings= override")
    print("=" * 60)
    r = summarize(
        DOC,
        max_length=300,
        keep_headings=True,
        headings=SUPPLIED_HEADINGS,
    )
    print(r.summary)
    print()
    print("pinned_headings:", r.pinned_headings)
    print()

    print("=" * 60)
    print("summarize() — include_toc=True + headings= override")
    print("=" * 60)
    r2 = summarize(
        DOC,
        max_length=300,
        include_toc=True,
        headings=SUPPLIED_HEADINGS,
    )
    print(r2.summary)


if __name__ == "__main__":
    main()
