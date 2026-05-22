"""Generate v0.4.2 heading/pin parity fixtures.

For each (corpus, case) pair, runs Python summarize() with the configured
pin args and writes input.txt / args.json / expected.txt under
fixtures/v0_4_2_pins/<corpus>__<case>/. The Rust walker
(rust/tests/fixtures.rs::v0_4_2_pins_byte_identical) byte-compares.

Run: python benchmarks/gen_pin_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lede import summarize  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_ROOT = ROOT / "fixtures" / "v0_4_2_pins"

# (case, keep_headings, include_toc, pin, hints, mode, max_length)
CASES = [
    ("headings_default",     True,  False, None,        None,        "default",  300),
    ("headings_coverage",    True,  False, None,        None,        "coverage", 300),
    ("headings_hints",       True,  False, None,        ["county"],  "default",  300),
    ("toc_only",             False, True,  None,        None,        "default",  300),
    ("pin_only",             False, False, ["PINNED A", "PINNED B"], None, "default", 300),
    ("all_three",            True,  True,  ["PINNED A"], None,       "default",  300),
    ("headings_off_control", False, False, None,        None,        "default",  300),
]


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    if not corpora:
        print(f"no corpora in {CORPUS_DIR}", file=sys.stderr)
        return 1
    written = 0
    for corpus_path in corpora:
        name = corpus_path.stem
        text = corpus_path.read_text(encoding="utf-8")
        for case, keep, toc, pin, hints, mode, max_len in CASES:
            base = OUT_ROOT / f"{name}__{case}"
            base.mkdir(parents=True, exist_ok=True)
            (base / "input.txt").write_text(text, encoding="utf-8")
            (base / "args.json").write_text(json.dumps({
                "keep_headings": keep,
                "include_toc": toc,
                "pin": pin,
                "hints": hints,
                "mode": mode,
                "max_length": max_len,
            }, indent=2, sort_keys=True), encoding="utf-8")
            out = summarize(
                text, max_length=max_len, mode=mode, hints=hints,
                keep_headings=keep, include_toc=toc, pin=pin,
            ).summary
            (base / "expected.txt").write_text(out, encoding="utf-8")
            written += 1
    print(f"Wrote {written} pin fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
