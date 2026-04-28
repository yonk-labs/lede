"""Optional [wordforms] extra — recognize spelled-out numbers.

Requires:
    pip install -e ".[wordforms]"

By default extract.stats only matches digit forms (`5 days`, `1,234
events`). With convert_word_names=True the text2num crate scans for
spelled-out forms ("five thousand documents") and surfaces them as
Stats with the original word-form text preserved in `value` / `phrase`.

Run: python examples/07_wordforms_numbers.py
"""
import sys

try:
    import text_to_num  # noqa: F401  — confirms the [wordforms] extra is present
except ImportError:
    print("This example requires the [wordforms] extra.", file=sys.stderr)
    print('    pip install -e ".[wordforms]"', file=sys.stderr)
    sys.exit(1)

from lede.extract import stats

DOC = """
Retention was seven years after account closure. The new regime
extended this to thirteen months for SMB and twenty-four months for
enterprise. Five thousand documents were re-classified during the
transition. Two hundred and forty users opted out.
"""


def main() -> None:
    # Default: digit-only match. None of the word-form numbers above surface.
    facts_off = stats(DOC)
    print(f"--- stats(text)  [convert_word_names off, default] ---")
    print(f"    found {len(facts_off)} stats")
    for s in facts_off:
        print(f"    [{s.stat_type:8s}] {s.value!r}")
    print()

    # convert_word_names=True: text2num kicks in.
    facts_on = stats(DOC, convert_word_names=True)
    print(f"--- stats(text, convert_word_names=True)  [requires [wordforms]] ---")
    print(f"    found {len(facts_on)} stats")
    for s in facts_on:
        print(f"    [{s.stat_type:8s}] {s.value!r}")


if __name__ == "__main__":
    main()
