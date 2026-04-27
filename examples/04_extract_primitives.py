"""Each `skimr.extract.*` primitive called standalone.

Same primitives that `summarize(attach=…)` composes — but for callers
that want to run just one (e.g. only stats extraction, or only the
outline for a chunking heuristic).

Run: python examples/04_extract_primitives.py
"""
from skimr.extract import (
    correlate_facts,
    key_facts,
    metadata,
    outline,
    phrases,
    stats,
    toc,
)

DOC = """
Project skimr — 2024 status report

## Performance

Throughput improved from 230 docs/sec to 4,800 docs/sec (~21× faster).
Memory usage dropped 47%. p50 latency now sits at 0.42 ms; Sumy
TextRank for comparison runs at 11.6 ms p50 on the same corpus.

## Adoption

Three internal teams shipped pipelines on top of skimr in Q3:
chunkshop (RAG ingest), notebot (note summarization), and the demo
preview service. Combined throughput across all three: 1.2 million
documents per day.

## Risks

Single-maintainer project; bus factor is 1. Mitigation plan documented
in MAINTAINERS.md.
"""


def main() -> None:
    print(f"--- outline() — {len(outline(DOC))} sections")
    for sec in outline(DOC):
        print(f"    depth={sec.depth} name={sec.name!r}")
        print(f"    repr:  {sec.representative_sentence[:80]!r}")
    print()

    print(f"--- toc() — {len(toc(DOC))} section names")
    for name in toc(DOC):
        print(f"    {name!r}")
    print()

    print(f"--- stats() — {len(stats(DOC))} numeric facts")
    for s in stats(DOC):
        print(f"    [{s.stat_type:8s}] {s.value!r}")
    print()

    print("--- metadata() — dates/amounts/urls (regex backend)")
    md = metadata(DOC)
    print(f"    dates:    {md.dates}")
    print(f"    amounts:  {md.amounts}")
    print(f"    urls:     {md.urls}")
    print()

    print(f"--- phrases() — repeated n-grams ({len(phrases(DOC))})")
    for p in phrases(DOC)[:6]:
        print(f"    {p!r}")
    print()

    print(f"--- key_facts() — sentences ranked by stat density ({len(key_facts(DOC))})")
    for f in key_facts(DOC):
        print(f"    - {f[:80]!r}")
    print()

    print(f"--- correlate_facts() — entity ↔ number pairs ({len(correlate_facts(DOC))})")
    for cf in correlate_facts(DOC):
        print(f"    {cf.entity!r}  ←→  {cf.number}  [{cf.polarity}]")


if __name__ == "__main__":
    main()
