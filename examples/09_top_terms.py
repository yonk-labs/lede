"""Example 09 — Top salient terms (words + phrases).

The v0.4 `extract.top_terms` primitive returns the top-N salient terms from
a document, mixing single-word TF-IDF scores with multi-word phrase frequency.

Run: python examples/09_top_terms.py
"""
from lede.extract import top_terms


TEXT = (
    "The Acme Corporation announced quarterly earnings on Tuesday. "
    "Acme Corporation reported revenue of $12 million, up 15 percent. "
    "CEO Jane Doe credited the rise to new product launches. "
    "The Acme Corporation board meets next Tuesday to approve dividends. "
    "Jane Doe will present the annual strategy at the board meeting. "
    "Acme Corporation employs 450 staff across three offices. "
    "Revenue from new products grew by 23 percent year-over-year."
)


def main() -> None:
    print("=" * 60)
    print("top_terms() — defaults (words + phrases, n=10)")
    print("=" * 60)
    for t in top_terms(TEXT):
        print(f"    - {t!r}")
    print()

    print("=" * 60)
    print("top_terms(kinds=('words',)) — single words only (n=5)")
    print("=" * 60)
    for t in top_terms(TEXT, n=5, kinds=("words",)):
        print(f"    - {t!r}")
    print()

    print("=" * 60)
    print("top_terms(kinds=('phrases',)) — multi-word phrases only (n=5)")
    print("=" * 60)
    for t in top_terms(TEXT, n=5, kinds=("phrases",)):
        print(f"    - {t!r}")
    print()

    print("=" * 60)
    print("top_terms() — hint-biased (soft) toward jane doe (n=5)")
    print("=" * 60)
    for t in top_terms(TEXT, n=5, hints=["jane doe"], hint_mode="soft"):
        print(f"    - {t!r}")
    print()

    print("=" * 60)
    print("top_terms() — hard filter (only acme-bearing terms, n=5)")
    print("=" * 60)
    for t in top_terms(
        TEXT,
        n=5,
        hints=["acme"],
        hint_focus=1.0,
        hint_mode="hard",
    ):
        print(f"    - {t!r}")


if __name__ == "__main__":
    main()
