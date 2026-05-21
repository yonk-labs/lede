"""Example 08 — Hint-biased extraction.

Pass `hints` to bias lede's ranking primitives toward sentences mentioning
specific terms or phrases. Useful for question-answering use cases like
"which county does John Smith live in?"

Run: python examples/08_hints.py
"""
from lede import summarize, brief
from lede.extract import key_facts, phrases


TEXT = (
    "The town council met on Tuesday. "
    "John Smith presented his case to the assembly. "
    "Smith argued for lower property taxes. "
    "The council voted to defer the decision. "
    "Cook County is the second-most populous county in Illinois. "
    "Local farmers expressed concern about water rights. "
    "The next meeting is scheduled for the third of next month. "
    "John Smith lives in Cook County and runs a small business."
)


def main() -> None:
    print("=" * 60)
    print("summarize() — no hints (baseline)")
    print("=" * 60)
    print(summarize(TEXT, max_length=200).summary)
    print()

    print("=" * 60)
    print("summarize() — soft hints (John Smith, county)")
    print("=" * 60)
    print(summarize(
        TEXT,
        max_length=200,
        hints=["John Smith", "county"],
        hint_focus=0.7,
        hint_mode="soft",
    ).summary)
    print()

    print("=" * 60)
    print("summarize() — hard filter (only John Smith sentences)")
    print("=" * 60)
    print(summarize(
        TEXT,
        max_length=200,
        hints=["John Smith"],
        hint_focus=1.0,
        hint_mode="hard",
    ).summary)
    print()

    print("=" * 60)
    print("key_facts() — hint-biased toward 'county' (5 facts)")
    print("=" * 60)
    facts = key_facts(TEXT, max_facts=5, hints=["county"], hint_focus=0.5)
    for f in facts:
        print(f"    - {f}")
    print()

    print("=" * 60)
    print("phrases() — reranked by hints=['county']")
    print("=" * 60)
    p = phrases(TEXT, hints=["county"], hint_mode="soft")
    for phrase in p[:5]:
        print(f"    {phrase!r}")
    print()

    print("=" * 60)
    print("brief() with hints (dict format)")
    print("=" * 60)
    result = brief(
        TEXT,
        max_facts=5,
        hints=["John Smith", "county"],
        hint_focus=0.7,
        format="dict",
    )
    print(f"    overview: {result['overview'][:80]}...")
    print(f"    key_facts count: {len(result['key_facts'])}")


if __name__ == "__main__":
    main()
