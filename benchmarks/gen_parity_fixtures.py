"""Generate v0.2 extract-primitive parity fixtures.

For each (corpus, primitive) pair, runs the Python primitive and writes
the canonical text representation (`lede._parity.format_*`) to
`fixtures/extract-parity/<primitive>/<corpus>/{input,expected}.txt`.

The Rust parity walker (`rust/tests/fixtures.rs`) loads each fixture,
runs the Rust primitive on the same input, formats with
`lede::parity::format_*`, and byte-compares.

Run: ``python benchmarks/gen_parity_fixtures.py``

Re-run after any primitive output change. Commit the regenerated
fixtures.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from lede import _parity  # noqa: E402
from lede.extract import (  # noqa: E402
    correlate_facts,
    key_facts,
    metadata,
    outline,
    phrases,
    stats,
    toc,
    top_terms,
)


CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_ROOT = ROOT / "fixtures" / "extract-parity"

# (primitive name, callable that takes text and returns the structured output,
#  formatter that turns the structured output into canonical text).
PRIMITIVES = [
    ("stats", stats, _parity.format_stats),
    ("outline", outline, _parity.format_outline),
    ("toc", toc, _parity.format_toc),
    ("metadata", metadata, _parity.format_metadata),
    ("phrases", phrases, _parity.format_phrases),
    ("correlate_facts", correlate_facts, _parity.format_correlate_facts),
    ("key_facts", key_facts, _parity.format_key_facts),
    ("top_terms", top_terms, _parity.format_top_terms),
]


def main() -> int:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    if not corpora:
        print(f"no corpora in {CORPUS_DIR}", file=sys.stderr)
        return 1

    written = 0
    for primitive_name, fn, formatter in PRIMITIVES:
        prim_dir = OUT_ROOT / primitive_name
        prim_dir.mkdir(parents=True, exist_ok=True)
        for corpus_path in corpora:
            corpus_name = corpus_path.stem
            text = corpus_path.read_text(encoding="utf-8")

            fixture_dir = prim_dir / corpus_name
            fixture_dir.mkdir(parents=True, exist_ok=True)

            (fixture_dir / "input.txt").write_text(text, encoding="utf-8")
            (fixture_dir / "expected.txt").write_text(formatter(fn(text)), encoding="utf-8")
            written += 1

    print(f"Wrote {written} parity fixtures across {len(PRIMITIVES)} primitives.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
