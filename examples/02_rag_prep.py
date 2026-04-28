"""lede v0.2 — RAG-prep primitive in one call.

Shows the v0.2 differentiator: `summarize(attach=…)` returns a summary
plus structured stats / outline / metadata / phrases / correlated
facts in sub-5 ms per document. RAG pipelines that previously needed a
second pass over the chunk (run a fact extractor, run a metadata
extractor) can now do it all in one call.

Run: python examples/02_rag_prep.py
"""
from lede import summarize

CHUNK = """
Cohort retention dropped from 78% to 71% between the Q2 and Q3 cohorts,
with the largest drop concentrated in users on the legacy free tier
who joined between 2024-03-01 and 2024-05-31. The new pricing scheme
shipped on 2024-06-12 raised the floor from $0 to $9/month for the
free tier and added a 14-day trial gate. Revenue per active user grew
from $14 to $18 over the same period — net positive — but board
expressed concern about top-of-funnel collapse. Mitigation plan
includes a $5 starter tier launching in November and a partnership
with Acme Corp to bundle lede access with their existing 250,000 user
base.
"""


def main() -> None:
    r = summarize(
        CHUNK,
        max_length=300,
        mode="default",
        attach=["stats", "outline", "metadata", "phrases", "correlated_facts"],
    )

    print("=" * 60)
    print("Summary (the .summary field — what an embedder would consume)")
    print("=" * 60)
    print(r.summary)
    print()

    print("=" * 60)
    print(f"Stats ({len(r.stats)} found)")
    print("=" * 60)
    for s in r.stats:
        print(f"  [{s.stat_type:8s}] {s.value!r:20s} unit={s.unit}")
        print(f"             phrase: {s.phrase[:60]!r}")
    print()

    print("=" * 60)
    print(f"Outline ({len(r.outline)} sections)")
    print("=" * 60)
    for sec in r.outline:
        print(f"  depth={sec.depth} name={sec.name!r}")
    print()

    print("=" * 60)
    print("Metadata (regex backend — entities empty by design; see 06_)")
    print("=" * 60)
    md = r.metadata
    print(f"  dates:    {md.dates}")
    print(f"  amounts:  {md.amounts}")
    print(f"  urls:     {md.urls}")
    print(f"  entities: {md.entities}  # empty without lede-spacy")
    print()

    print("=" * 60)
    print(f"Phrases ({len(r.phrases)} repeated multi-word phrases)")
    print("=" * 60)
    for p in r.phrases[:8]:
        print(f"  {p!r}")
    print()

    print("=" * 60)
    print(f"Correlated facts ({len(r.correlated_facts)} entity ↔ number pairs)")
    print("=" * 60)
    for f in r.correlated_facts:
        print(f"  {f.entity!r}  ←→  {f.number}  [{f.polarity}]")


if __name__ == "__main__":
    main()
