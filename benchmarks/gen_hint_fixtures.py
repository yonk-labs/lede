"""Generate v0.4 hint-biased extraction parity fixtures.

For each (corpus, hint-case) pair, runs Python summarize() with the
configured hints and writes:
  fixtures/v0_4_hints/<corpus>__<case>/
    input.txt    — corpus text
    args.json    — hint configuration
    expected.txt — Python summarize() output

The Rust parity walker (rust/tests/fixtures.rs::v0_4_hints_byte_identical
in T13) loads each fixture, runs Rust summarize_with_hints with the same
args, and byte-compares.

Run: python benchmarks/gen_hint_fixtures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lede import summarize  # noqa: E402


CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_ROOT = ROOT / "fixtures" / "v0_4_hints"


CASES: list[tuple[str, object, float, str, int, str]] = [
    # (case_name, hints, hint_focus, hint_mode, max_length, mode)
    ("none",            None,                                       0.7, "soft", 300, "default"),
    ("empty_list",      [],                                         0.7, "soft", 300, "default"),
    ("focus_zero",      ["county"],                                 0.0, "soft", 300, "default"),
    ("focus_one_soft",  ["county"],                                 1.0, "soft", 300, "default"),
    ("focus_one_hard",  ["smith"],                                  1.0, "hard", 300, "default"),
    ("focus_half_soft", ["county"],                                 0.5, "soft", 300, "default"),
    ("focus_half_hard", ["smith"],                                  0.5, "hard", 300, "default"),
    ("phrase_soft",     ["john smith"],                             0.7, "soft", 300, "default"),
    ("phrase_hard",     ["john smith"],                             1.0, "hard", 300, "default"),
    ("multi_list",      ["smith", "county"],                        0.7, "soft", 300, "default"),
    ("multi_dict",      {"john smith": 2.0, "county": 1.0},         0.7, "soft", 300, "default"),
    ("nomatch_hard",    ["xyzzy"],                                  1.0, "hard", 300, "default"),
    ("cap_saturation",  ["smith"],                                  0.5, "soft", 500, "default"),
    ("odd_budget_half", ["county"],                                 0.5, "soft", 301, "default"),
]


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    if not corpora:
        print(f"no corpora in {CORPUS_DIR}", file=sys.stderr)
        return 1

    written = 0
    for corpus_path in corpora:
        corpus_name = corpus_path.stem
        text = corpus_path.read_text(encoding="utf-8")
        for case_name, hints, focus, mode_hint, max_len, mode in CASES:
            base = OUT_ROOT / f"{corpus_name}__{case_name}"
            base.mkdir(parents=True, exist_ok=True)
            (base / "input.txt").write_text(text, encoding="utf-8")
            (base / "args.json").write_text(json.dumps({
                "hints": hints,
                "hint_focus": focus,
                "hint_mode": mode_hint,
                "max_length": max_len,
                "mode": mode,
            }, indent=2, sort_keys=True), encoding="utf-8")
            summary = summarize(
                text,
                max_length=max_len,
                mode=mode,
                hints=hints,
                hint_focus=focus,
                hint_mode=mode_hint,
            ).summary
            (base / "expected.txt").write_text(summary, encoding="utf-8")
            written += 1

    print(f"Wrote {written} hint fixtures across {len(corpora)} corpora x {len(CASES)} cases.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
