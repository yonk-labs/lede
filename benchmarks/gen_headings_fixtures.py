"""Generate v0.4.3 headings-override parity fixtures.

For each (corpus, case) pair, runs Python summarize() with the configured
headings args and writes input.txt / args.json / expected.txt under
fixtures/v0_4_3_headings/<corpus>__<case>/. The Rust walker
(rust/tests/fixtures.rs::v0_4_3_headings_byte_identical) byte-compares.

Run: python benchmarks/gen_headings_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lede import summarize  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_ROOT = ROOT / "fixtures" / "v0_4_3_headings"

# Deterministic supplied heading set; many won't match any given corpus body —
# that's intentional: the point is caller-supplied lines, not auto-detected ones.
HEADINGS = ["Introduction", "Summary", "Conclusion"]

# (case, keep_headings, include_toc, pin, headings, hints, mode, max_length)
CASES = [
    ("override_keep",   True,  False, None,       HEADINGS, None,       "default",  300),
    ("override_toc",    False, True,  None,       HEADINGS, None,       "default",  300),
    ("override_both",   True,  True,  None,       HEADINGS, None,       "default",  300),
    ("override_hints",  True,  False, None,       HEADINGS, ["county"], "default",  300),
    ("override_cov",    True,  False, None,       HEADINGS, None,       "coverage", 300),
    ("headings_noop",   False, False, None,       HEADINGS, None,       "default",  300),  # flags off -> no-op
    ("override_pin",    True,  False, ["PIN A"],  HEADINGS, None,       "default",  300),
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
        for case, keep, toc, pin, headings, hints, mode, max_len in CASES:
            base = OUT_ROOT / f"{name}__{case}"
            base.mkdir(parents=True, exist_ok=True)
            (base / "input.txt").write_text(text, encoding="utf-8")
            (base / "args.json").write_text(json.dumps({
                "headings": headings,
                "hints": hints,
                "include_toc": toc,
                "keep_headings": keep,
                "max_length": max_len,
                "mode": mode,
                "pin": pin,
            }, indent=2, sort_keys=True), encoding="utf-8")
            out = summarize(
                text, max_length=max_len, mode=mode, hints=hints,
                keep_headings=keep, include_toc=toc, pin=pin,
                headings=headings,
            ).summary
            (base / "expected.txt").write_text(out, encoding="utf-8")
            written += 1
    print(f"Wrote {written} headings fixtures.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
