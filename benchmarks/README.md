# Benchmarks

Scaffold for mission-brief **SC-006**: "fastest of {Python skimr, Rust skimr} within **2× of Sumy** wall-clock on an equivalent-algorithm benchmark." This directory is the harness; `results/` holds captured numbers.

## What's here

```
benchmarks/
├── corpus/               5 hand-crafted offline inputs (CRM note, news, minutes, spec)
├── harness.py            timing runner for skimr (tfidf, textrank) + Sumy (LexRank, TextRank, LSA)
└── results/              captured results, one file per run (results-YYYY-MM-DD.md)
```

## Running

```bash
pip install -e ".[textrank,bench]"                # Sumy + numpy + networkx
python benchmarks/harness.py                      # 100 iterations, default corpus
python benchmarks/harness.py --iterations 1000    # tighter P95 tails
python benchmarks/harness.py --output foo.md      # pick output path
python benchmarks/harness.py --json raw.json      # also dump raw measurements
```

Report lands in `benchmarks/results/results-YYYY-MM-DD.md` by default.

## What it measures

- **Wall-clock latency** per run, median and P95, in milliseconds.
- **Output length** in characters (sanity check — makes sure each summarizer produced non-trivial output).

Rust skimr columns are explicit `—` placeholders. Plan 2 fills them in.

## What it deliberately does not measure (yet)

- **Quality.** No ROUGE, no LLM-judge. Wall-clock + output-length only for now. Quality measurement lands once `skimr-neural` forces the issue.
- **Memory high-water mark.** Could add via `tracemalloc` if it matters.
- **Cold-start cost** (first import). Warmup run is discarded.
- **CI integration.** Wall-clock numbers in CI are noisy; run locally. Consider a dedicated runner class if CI capture ever matters.

## DC-004 / reproducibility

Cross-machine numbers are invalid. The harness captures a system fingerprint (CPU, cores, Python version, skimr + Sumy versions) in every results file so historical comparisons stay honest. Pin the target machine if you need a stable baseline.

## Corpus notes

Five inputs, 475 to 3,105 chars, written to cover distinct document shapes:

- `crm-note-short.txt` — shorter than the default 500-char budget, so skimr/tfidf short-circuits (passthrough). Useful for confirming the fast-path.
- `crm-note-long.txt` — CRM deep-dive with headers, multiple sections.
- `meeting-minutes.txt` — attendee list + discussion + action items.
- `news-article.txt` — editorial-style prose.
- `tech-spec.txt` — longest doc; headed sections, technical vocabulary.

None reference real companies, people, or identifiers. The corpus can be expanded without breaking existing results.

## Expected shape of results

On a modern desktop CPU:

| Summarizer | Typical P50 (ms) |
|---|---|
| `skimr/tfidf` | < 0.5 ms for inputs up to ~3 KB |
| `skimr/textrank` | 1–3 ms |
| `sumy/*` | 10–20 ms across backends |

skimr/tfidf is roughly 50–70× faster than the fastest Sumy backend in the current harness. SC-006's "within 2× of Sumy" bar is already cleared by Python alone on this hardware; the Rust port has headroom to spare.
