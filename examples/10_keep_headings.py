"""Example 10 — Heading & pin retention in summarize.

The v0.4.2 `keep_headings`, `include_toc`, and `pin` kwargs let callers
weave document structure back into the extractive summary.  Headings
interleave at their original positions; pinned lines and a table-of-contents
prepend in order; all pinned content is additive (does not consume the
`max_length` budget).

Run: python examples/10_keep_headings.py
"""
from lede import summarize


DOC = """# Quarterly Review

## Revenue

The company posted record revenue of $12 million in Q3.
Revenue grew 18 percent year-over-year.
New product lines drove most of the increase.

## Operations

Headcount rose to 210 employees across four offices.
Supply-chain delays were resolved in September.
Warehouse capacity is now at 85 percent utilization.

## Outlook

Management forecasts 8 percent growth in Q4.
Figure 3: Q3 revenue by region shows the North region leading.
The board meets in November to review capital allocation.
"""


def main() -> None:
    print("=" * 60)
    print("summarize() — keep_headings=True")
    print("=" * 60)
    r = summarize(DOC, max_length=300, keep_headings=True)
    print(r.summary)
    print()
    print("pinned_headings:", r.pinned_headings)
    print()

    print("=" * 60)
    print("summarize() — pin a specific line verbatim")
    print("=" * 60)
    r2 = summarize(
        DOC,
        max_length=300,
        pin=["Figure 3: Q3 revenue by region"],
    )
    print(r2.summary)
    print()

    print("=" * 60)
    print("summarize() — keep_headings=True + include_toc=True")
    print("=" * 60)
    r3 = summarize(DOC, max_length=300, keep_headings=True, include_toc=True)
    print(r3.summary)


if __name__ == "__main__":
    main()
