# v0.4 hint-path microbench — 2026-05-21

Measured on the 10-corpus benchmark set. 50 iterations per (case, corpus). 1 unrecorded warmup per (case, corpus). `max_length=500`. SC-B gate: p50 ≤ 250 ms.

## Latency by hint configuration

| case | min ms | p50 ms | p95 ms | mean ms |
|---|---|---|---|---|
| no-hints | 0.086 | 0.410 | 0.545 | 0.373 |
| 1-hint soft | 0.098 | 0.430 | 0.573 | 0.404 |
| 2-hint soft | 0.101 | 0.455 | 0.622 | 0.428 |
| 5-hint soft | 0.114 | 0.506 | 0.664 | 0.469 |
| 5-hint hard, focus=1.0 | 0.113 | 0.501 | 0.672 | 0.463 |
| phrase soft (2 multi-word) | 0.105 | 0.464 | 0.616 | 0.427 |
| 10-hint weighted dict soft | 0.133 | 0.607 | 0.802 | 0.560 |

## Observations

- **No-hints path is unchanged** at v0.4. Same p50 as v0.3 (0.39 ms in the v0.4 matrix run; 0.41 ms in this run — within run-to-run jitter). Byte-identical output verified by the existing v0.1 + v0.2 fixture walkers continuing to pass.
- **Hint cost is linear in hint count.** Adding one hint adds ~5% to p50. Going from 1 to 10 hints adds ~40%. The per-hint cost is dominated by the lowercased-sentence regex search (`\b{hint}\b`), which is O(sentence length) and uses cached compiled patterns.
- **Soft vs hard has equivalent cost.** Both run the same per-sentence bonus computation; hard mode only swaps the score sentinel for non-matching sentences (`-inf`) — no extra work.
- **Phrase hints cost roughly the same as token hints.** Multi-word hints compile a slightly longer regex but `\b` boundary checks dominate either way.
- **SC-B gate (250 ms p50)** is not in danger. Worst-case observed is 0.61 ms — about 400x under the budget.

## Backward-compat sanity

```
summarize(text, max_length=500).summary == summarize(text, max_length=500, hints=None).summary
```

Verified True on `meeting-minutes.txt` (the v0_4_hints_byte_identical walker covers all 10 corpora × 14 hint configurations and confirms byte equality between Python and Rust runtime output).

## Reproducing

```bash
.venv/bin/python <<'EOF'
import statistics, time
from pathlib import Path
from lede import summarize

CORPUS = Path("benchmarks/corpus")
ITERS = 50

cases = [
    ("no-hints", dict()),
    ("5-hint soft", dict(hints=["report", "meeting", "council", "budget", "decision"], hint_focus=0.7, hint_mode="soft")),
    # ...
]

for name, kwargs in cases:
    samples = []
    for txt_path in sorted(CORPUS.glob("*.txt")):
        text = txt_path.read_text()
        summarize(text, max_length=500, **kwargs)  # warmup
        for _ in range(ITERS):
            t0 = time.perf_counter()
            summarize(text, max_length=500, **kwargs)
            samples.append((time.perf_counter() - t0) * 1000)
    samples.sort()
    print(f"{name}: p50 {statistics.median(samples):.3f} ms")
EOF
```

## Not measured (deferred to v0.5)

- Rust-side hint-path latency. The `cargo bench` infrastructure isn't wired up for hints yet — the Rust integration tests verify correctness but not throughput. Adding a `criterion`-based bench would be a v0.5 task.
- Memory footprint of the regex cache in `_hints.py`. Each unique hint compiles one pattern; on a process with thousands of distinct hints, the cache grows unbounded. Not a concern at realistic hint counts.
- Hint expansion via `lede_spacy.expand_hints()`. The lemma + WordNet calls add fixed overhead (~10ms per call dominated by spaCy/nltk init); expansion is typically done once at session start so this isn't on the hot path.
