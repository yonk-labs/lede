"""Markdown and JSON output helpers for API callers.

Run:
    python examples/12_output_formats.py
"""
from lede import summarize


DOC = """# Launch Notes

Acme Corp launched the cache rewrite on 2026-05-23.
Latency fell by 40 percent after rollout.
Revenue grew 12 percent in the same period.
The platform team will keep a seven-day canary before full rollout.
"""


def main() -> None:
    r = summarize(
        DOC,
        max_length=300,
        attach=["stats", "metadata"],
        keep_headings=True,
    )

    print("to_markdown()")
    print(r.to_markdown())
    print()

    print("to_json()")
    print(r.to_json())
    print()

    print("to_dict() keys")
    print(sorted(r.to_dict().keys()))


if __name__ == "__main__":
    main()
