"""lede.brief() — paste-ready document brief in three formats.

Composes summarize + key_facts + toc into one artifact. Useful for
email digests, file browser previews, or a compact citation block in
a chat message.

Run: python examples/03_brief.py
"""
from lede import brief

DOC = """
# Engineering Status — November 2024

## Highlights

Shipped 17 features and closed 230 issues. Team grew by 4 to 28
headcount. p99 latency dropped from 850 ms to 420 ms after the cache
rewrite.

## Risks

Two enterprise deals are blocked on the SOC2 Type II report, expected
2024-12-15. Three engineers on PTO over the holidays; on-call
coverage is thin.

## Next quarter

Plan to ship the new chunking algorithm by 2025-01-31 and the
multi-region failover by 2025-02-28. Hiring two more SREs.
"""


def main() -> None:
    print("=" * 60)
    print('brief(format="string") — plain text, section labels')
    print("=" * 60)
    print(brief(DOC))
    print()

    print("=" * 60)
    print('brief(format="markdown") — markdown headers + bullets')
    print("=" * 60)
    print(brief(DOC, format="markdown"))
    print()

    print("=" * 60)
    print('brief(format="dict") — structured payload for programmatic use')
    print("=" * 60)
    d = brief(DOC, format="dict")
    print(f"  overview:  {len(d['overview'])} chars")
    print(f"  key_facts: {len(d['key_facts'])} items")
    for f in d["key_facts"]:
        print(f"             - {f[:70]!r}")
    print(f"  toc:       {len(d['toc'])} sections")
    for s in d["toc"]:
        print(f"             - {s!r}")


if __name__ == "__main__":
    main()
