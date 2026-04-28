"""lede — 30-second tour of the v0.1 utility surface.

Shows the four functions that have been stable since v0.0.1:
  summarize, clean_text, strip_think, extract_keyword.

Run: python examples/01_quickstart.py
"""
from lede import summarize, clean_text, strip_think, extract_keyword

DOC = """
**Q3 RECAP**

Revenue grew 23 percent year-over-year to $4.2M, with paid seats up
1,250 from the prior quarter. Churn ticked up to 4.1% — primarily
in the SMB segment after the November pricing change. Two enterprise
deals slipped from Q3 to Q4 due to extended security reviews; both are
expected to close by 2024-12-15. Engineering shipped 17 features and
closed 230 issues. The team grew by 4 to 28 total headcount.
"""


def main() -> None:
    print("=" * 60)
    print("summarize() — default TF-IDF + position + length, 200-char budget")
    print("=" * 60)
    r = summarize(DOC, max_length=200)
    print(r.summary)
    print()

    print("=" * 60)
    print("extract_keyword() — sentences relevant to a query, ranked")
    print("=" * 60)
    print(extract_keyword(DOC, "churn pricing", num_sentences=2))
    print()

    print("=" * 60)
    print("clean_text() — strip markdown / filler / boilerplate")
    print("=" * 60)
    print(clean_text("**Bold** _italic_ — see attached. Also: revenue grew 23%."))
    print()

    print("=" * 60)
    print("strip_think() — remove <think>...</think> reasoning blocks")
    print("=" * 60)
    print(strip_think(
        "<think>I need to consider the tradeoffs here.</think>"
        "Revenue grew 23 percent."
    ))


if __name__ == "__main__":
    main()
