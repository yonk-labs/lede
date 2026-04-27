"""Recommended pattern for very long documents.

skimr is a per-chunk primitive, not a document loader. For inputs >
100 KB, paragraph-chunk first, summarize each chunk, then reassemble.
This is also the integration shape for chunkshop and similar RAG
pipelines — see docs/integration-memo.md.

Run: python examples/05_chunked_pipeline.py
"""
import re

from skimr import summarize

# Pretend this is a 200 KB document. We'll simulate with a multi-paragraph
# string that's small enough to fit in this example file.
LONG_DOC = """
Q3 2024 financial review.

Revenue grew 23 percent year-over-year to $4.2M, beating consensus by
roughly 7 percent. The growth came primarily from the enterprise
segment, where ACV expanded 41 percent on the back of three Fortune
500 wins.

The SMB segment saw mixed results. Top-of-funnel signups remained
strong but conversion to paid declined from 4.8% to 3.6% after the
November pricing change. Net revenue retention in this cohort dropped
from 102% to 96%.

Operating expenses grew 18 percent year-over-year, well below revenue
growth, which expanded gross margin from 71% to 78%. The biggest driver
was the cache-rewrite project shipped in September, which cut
infrastructure cost by 31% on the hot path.

Headcount grew by 4 to 28 total. Sales added 2 (one enterprise AE, one
SMB SDR); engineering added 2 (one platform, one ML). Two enterprise
deals slipped from Q3 to Q4 due to extended security reviews; both
are expected to close by 2024-12-15.

Risks for Q4: SOC2 Type II report blocking $1.4M in pipeline, single-
maintainer key infrastructure (chunkshop), and three engineers on PTO
over the holidays leaving on-call coverage thin. Mitigation plans for
each are documented in the Q4 OKR doc.
"""


def chunk_by_paragraph(text: str) -> list[str]:
    """Paragraphs are blank-line-delimited; very short paras are noise."""
    parts = re.split(r"\n\s*\n+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) >= 50]


def main() -> None:
    chunks = chunk_by_paragraph(LONG_DOC)
    print(f"Document split into {len(chunks)} paragraphs.")
    print()

    # Summarize each paragraph independently with a small char budget.
    # In a real RAG pipeline you'd embed each chunk's summary separately.
    paragraph_summaries: list[str] = []
    paragraph_stats: list[dict] = []
    for i, chunk in enumerate(chunks):
        r = summarize(chunk, max_length=140, mode="default", attach=["stats"])
        paragraph_summaries.append(r.summary)
        paragraph_stats.append({
            "chunk_id": i,
            "summary": r.summary,
            "stats": [(s.stat_type, s.value) for s in r.stats],
        })
        print(f"-- chunk {i} ({len(chunk)} chars) --")
        print(f"   summary: {r.summary[:100]!r}")
        print(f"   stats: {[(s.stat_type, s.value) for s in r.stats]}")
    print()

    # Reassemble — for a doc-level brief, summarize the joined summaries.
    doc_level = summarize(
        " ".join(paragraph_summaries),
        max_length=300,
        mode="default",
    )
    print("--- doc-level brief from paragraph summaries ---")
    print(doc_level.summary)


if __name__ == "__main__":
    main()
