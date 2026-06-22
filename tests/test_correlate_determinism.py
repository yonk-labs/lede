"""Regression: correlate_facts must be deterministic across PYTHONHASHSEED.

The regex correlate once iterated a ``set()`` of candidate phrases, so when a
sentence contained two repeated phrases the chosen entity depended on hash
iteration order (PYTHONHASHSEED) — different output per process, and a flaky
Python<->Rust parity walker. See ``lede/extract/correlate.py``.

This is a hash-seed determinism guard: it runs the primitive in fresh
subprocesses under many seeds and asserts a single, stable output. (A bug that
only flips under some seeds is caught with high probability across this many.)
"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "benchmarks" / "corpus" / "scotus-opinion.txt"

# scotus-opinion is a known trigger: a numeric sentence containing two repeated
# phrases ("civil penalties" and "new limit").
_SNIPPET = (
    "import sys; sys.path.insert(0, 'src');"
    "from lede.extract import correlate_facts;"
    "t = open(r'{path}', encoding='utf-8').read();"
    "print([(f.entity, f.number, f.polarity) for f in correlate_facts(t)])"
).format(path=CORPUS)


def test_correlate_facts_deterministic_across_hash_seeds():
    assert CORPUS.exists(), f"missing corpus: {CORPUS}"
    outputs = set()
    for seed in range(20):
        env = {**os.environ, "PYTHONHASHSEED": str(seed)}
        result = subprocess.run(
            [sys.executable, "-c", _SNIPPET],
            cwd=ROOT,
            env=env,
            capture_output=True,
            text=True,
            check=True,
        )
        outputs.add(result.stdout.strip())
    assert len(outputs) == 1, (
        "correlate_facts is nondeterministic across PYTHONHASHSEED:\n"
        + "\n".join(sorted(outputs))
    )
