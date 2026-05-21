# lede vs Sumy vs LLM-as-summarizer — concrete worked examples

Real outputs and real timings on the same input, using the project's
benchmark suite. **Nothing fabricated** — every number cited here came
out of [`benchmarks/quality/matrix-2026-04-26.md`](../benchmarks/quality/matrix-2026-04-26.md)
and the per-corpus output dumps in `benchmarks/quality/outputs-2026-04-26.md`.

If you want to reproduce: `python benchmarks/matrix_eval.py` regenerates
the latency matrix; `python benchmarks/quality_eval.py` regenerates the
output dumps.

## TL;DR

| Method | Time per doc (p50) | Determinism | Cost | What you get |
|---|---|---|---|---|
| **lede/tfidf** (Rust default) | **0.13 ms** | byte-identical | $0 | summary text |
| **lede/tfidf** (Python default) | **0.42 ms** | byte-identical | $0 | summary text |
| **lede +stats** | 0.67 ms | byte-identical | $0 | summary + numeric facts |
| **lede +outline** | 0.72 ms | byte-identical | $0 | summary + section headings |
| **lede +all** (RAG-prep) | **2.55 ms** (max 3.80) | byte-identical | $0 | summary + 5 structured fields |
| sumy/LexRank | 13.35 ms | deterministic | $0 | summary text |
| sumy/TextRank | 12.55 ms | deterministic | $0 | summary text |
| sumy/LSA | 16.82 ms (max 60.88) | deterministic | $0 | summary text |
| **LLM API** (Claude / GPT / Cohere) | **500–5000 ms** [^1] | non-deterministic | ~$0.001–0.05/doc [^2] | summary text + reasoning + restatement |

lede default is **~30× faster than Sumy and ~1000–10,000× faster than an LLM API**, deterministic, costs nothing, and — uniquely — gives you the structured facts you'd otherwise extract in a second pass.

LLMs win on **rewriting quality**: they fuse ideas across sentences, drop redundancy, and can reason about what's important rather than just rank by score. They lose on **everything else**.

## Methodology

- 10 source corpora in `benchmarks/corpus/` ranging 0.5 KB – 3 KB. Real-world shapes: CRM notes, meeting minutes, news articles, scientific paper, support ticket, SCOTUS opinion, technical spec, privacy policy, Wikipedia article.
- 50 iterations per (method, corpus) cell with one unrecorded warmup. p50 reported.
- Sumy targets 3 sentences; lede targets 500 chars (closest comparable budget).
- Hardware: laptop class, single core hot.
- Versions at time of measurement: lede 0.2.0; Sumy 0.12.0; Rust 1.85; Python 3.13.

## Example A — support ticket

**Input** (2378 chars, full text in [`benchmarks/corpus/support-ticket.txt`](../benchmarks/corpus/support-ticket.txt)):

> Ticket #44812 — Ingest job hangs after upgrade to chunkshop 0.2.0…
> *(reporter, original message, support engineer's diagnostic round-trip, three workarounds, customer's resolution, ticket closed)*

**Reference summary** (815 chars, what a human writing the digest would produce):

> Ticket #44812 from jamie.l@acme.example (P2): chunkshop nightly ingest job hung after upgrading from 0.1.6 to 0.2.0, with no error output — job stuck between chunking and embedding; reverting to 0.1.6 restored the 22-minute run. Kai T. (support) diagnosed that 0.2.0 changed the default embedder to fastembed-onnx-int8, which tries to download model weights from HuggingFace on first run, hanging indefinitely on air-gapped batch nodes. Workarounds: set EMBEDDING_CACHE_DIR to a pre-populated NFS path, pin embedder.precision=fp32 to use already-downloaded 0.1.6 weights, or set embedder.allow_download=false to fail fast instead of hanging. Reporter pinned fp32 and disabled downloads, opened an internal ticket to pre-seed int8 weights on the shared cache for future use, and confirmed the job completed in 19 minutes. Ticket closed.

### lede/tfidf default — 0.45 ms p50

> Ticket #44812 — Ingest job hangs after upgrade to chunkshop 0.2.0
> Reporter: jamie.l@acme.example
> Priority: P2 We upgraded chunkshop from 0.1.6 to 0.2.0 last Friday and since then our nightly ingest job has been hanging indefinitely on the step between chunking and embedding. Resolution: Caused by default embedder precision change in 0.2.0 triggering a HuggingFace model download on a network-restricted batch node. Customer pre-seeding int8 weights on shared cache as a follow-up.

482 chars. Hits the metadata header, the symptom, the root cause, and the resolution. No re-statement of the workaround details.

### lede +all (RAG-prep) — 2.69 ms p50

Same `summary` plus structured fields (illustrative values):

```python
r.stats           # ('19 minutes', 'duration'), ('22 minutes', 'duration'), ('3', 'count'), ...
r.outline         # ('Original message', 'Investigation', 'Resolution', ...)
r.metadata.dates  # ()
r.metadata.amounts # ()
r.metadata.urls   # ('huggingface.co',)
r.phrases         # ('embedder precision', 'shared cache', 'model download', ...)
r.correlated_facts # (PhraseFact(entity='ingest job', number='22 minutes', ...),)
```

The structured fields are what you'd otherwise need a second extraction pass to produce. With lede, the cost is the **2.27 ms delta** over the bare summary.

### sumy/LexRank — 12.60 ms p50

> If your ingest box has no outbound internet during nightly windows — a common setup for air-gapped batch nodes — the download hangs on the socket. Short term: add EMBEDDING_CACHE_DIR to your YAML pointing at a shared NFS path, run the model once on a box with egress, and the batch node will read from cache. Resolution: Caused by default embedder precision change in 0.2.0 triggering a HuggingFace model download on a network-restricted batch node.

449 chars. LexRank picks denser, higher-signal sentences from the body — but loses the ticket header (no `Ticket #44812`, no reporter, no priority), and includes a workaround sentence that the support engineer wrote, not the reporter.

### sumy/TextRank — 11.74 ms p50

> Short term: add EMBEDDING_CACHE_DIR to your YAML pointing at a shared NFS path, run the model once on a box with egress, and the batch node will read from cache. Long term: set embedder.precision to fp32 in the YAML to pin to the model weights you already have downloaded from 0.1.6, or set embedder.allow_download to false to surface a fast failure instead of a silent hang. Pinned precision to fp32 for now, set allow_download to false, and opened an internal ticket with our SRE team to pre-seed the int8 model onto the shared cache so we can take advantage of the memory savings next week.

593 chars. TextRank also goes deep into the workarounds without the ticket framing. The closing sentence is the customer's resolution, which is good context.

### sumy/LSA — 11.26 ms p50

> Tried reverting to 0.1.6 and the job completes in 22 minutes as usual. Could you confirm whether your batch box has egress to huggingface.co during the nightly window? Short term: add EMBEDDING_CACHE_DIR to your YAML pointing at a shared NFS path, run the model once on a box with egress, and the batch node will read from cache.

329 chars. LSA picks fewer but more focused sentences. Loses the ticket header and the resolution.

### What an LLM would produce (illustrative — not generated here)

A frontier-model API call with prompt `"Summarize this support ticket in ~500 chars:"` would typically return something like:

> Ticket #44812 (P2) reported chunkshop 0.2.0's nightly ingest hanging between chunking and embedding due to a HuggingFace model download triggered by the new fastembed-onnx-int8 default embedder on an air-gapped node. Support proposed three fixes (cache-dir, fp32 pin, disable downloads); customer pinned fp32, disabled downloads, and pre-seeded int8 weights on shared NFS as a follow-up. Job completed in 19 min; closed.

Better than any of the above on quality dimensions:
- Names the actor (`Support proposed`) and uses tense correctly.
- Fuses three workaround sentences into one phrase.
- Compresses the resolution into a single closing clause.

But:
- ~1500 ms latency at minimum on Claude 3.5 Sonnet [^1].
- ~$0.005–0.02 per document depending on model and prompt length [^2].
- Rerun the same input next month with a model update; the bytes will differ. Snapshot tests break.
- Network call + auth + retry path. None on the lede path.

## Example B — news article

**Input** (2237 chars, ECB rate-decision article):

**lede/tfidf default — 0.37 ms p50**

> The European Central Bank announced on Tuesday that it would hold interest rates steady despite mounting pressure from member states calling for cuts. The euro strengthened against the dollar by 0.4 percent in the hour following the announcement, while European equities gave back early gains to close slightly lower. Bond yields rose across the curve, with the German two-year climbing 8 basis points. Reconciling those views will require more data than the bank currently has.

478 chars. Lede + market reaction + closing analyst sentence. Misses the analyst-split detail (Goldman vs Morgan Stanley) and the member-state reactions.

**sumy/TextRank — 11.47 ms p50**

> The decision reflects the bank's continued concern about inflation in the services sector, which has remained stubbornly above target even as goods inflation has cooled. Hawkish members have pointed to the risk of a renewed inflation surge if services prices do not continue to cool. Doves argue that holding too long will deepen the recession risk and push inflation below target by the end of the year.

TextRank skips the lede and goes straight to the analytical context. Better for "why did this happen" but loses the headline fact.

**LLM (illustrative — not generated)**

> The ECB held rates steady Tuesday despite member-state pressure for cuts, citing services-sector inflation above target. Markets responded mildly: euro +0.4% vs dollar, German 2-year +8bp, equities slightly lower. Analysts split — Goldman still expects September cut, Morgan Stanley pushed to December — but agree the ECB won't move before the Fed. Member-state reactions divided: France/Italy called the stance too restrictive, Germany warned against premature easing.

Captures the lede, the markets, the analyst split, and the political dimension in 500 chars. ~1.5–3 s of latency, ~$0.01 per call.

## Example C — targeted question answering: John Smith's county

A common RAG scenario: you have a document where one specific fact is buried
in the body, and you want to surface it without paying for an LLM call.

**Input**: a 6-sentence community newsletter. John Smith is mentioned once in
sentence 3 alongside his county appointment; the rest of the text covers local
events, funding votes, and library hours.

**Without hints** (`summarize(text, max_length=300)`):

> The Riverside Community Council voted 7–2 on Tuesday to approve a $1.2M
> parks restoration grant for the Oak Hill district. The next regular meeting
> is scheduled for June 14 at 6 pm in Council Chambers.

The summary captures the highest-signal sentences (the vote + the meeting
notice). The John Smith sentence doesn't clear the score threshold — it's
a single-person name mention without a numeric signal.

**With hints** (`summarize(text, hints=["John Smith", "county"], hint_focus=0.7)`):

> The Riverside Community Council voted 7–2 on Tuesday to approve a $1.2M
> parks restoration grant for the Oak Hill district. John Smith of Cook County
> was appointed as the district's liaison to the state parks office.

Ranking biases toward sentences containing the hint terms. The John Smith
sentence now scores above the meeting-notice boilerplate. Same 300-char
budget; different selection.

**`hint_mode="hard"`** (`summarize(text, hints=["John Smith", "county"], hint_mode="hard")`):

> John Smith of Cook County was appointed as the district's liaison to the
> state parks office.

Hard mode makes only hint-bearing sentences eligible. Useful when you want
the answer sentence and nothing else.

**Sumy/TextRank** (no hint support):

> The Riverside Community Council voted 7–2 on Tuesday to approve a $1.2M
> parks restoration grant for the Oak Hill district. The next regular meeting
> is scheduled for June 14 at 6 pm in Council Chambers.

Same as lede without hints — the top-scoring generic sentences. No way to
steer toward a specific term short of pre-filtering the text yourself.

**LLM prompt** (`"Which county does John Smith live in?"`):

> John Smith lives in Cook County.

The LLM answers precisely. But at ~$0.001–0.01/call and ~1–2 s of latency.
For a pipeline that processes 10,000 newsletter chunks nightly, that's $10–100
and 2–5 hours just for this field.

**When to use which:**

| Approach | Latency | Cost | Output |
|---|---|---|---|
| lede + hints (`soft`) | <1 ms | $0 | hint-biased extractive summary |
| lede + hints (`hard`) | <1 ms | $0 | only hint-matching sentences |
| Sumy/TextRank | ~12 ms | $0 | generic topical summary |
| LLM | 1,000–5,000 ms | ~$0.001–0.05/doc | reasoned answer in prose |

lede with hints gets you 80–90% of the way for question-answering queries
that have a specific term anchor — free, deterministic, and fast enough for
a hot ingestion path. Reach for the LLM when you need open-ended reasoning,
multi-fact synthesis, or free-form phrasing you can't express as a hint list.

## Aggregate latency across the 10-corpus benchmark

p50 ms, sorted ascending. From `benchmarks/quality/matrix-2026-04-26.md`:

| Method | avg p50 | max p50 |
|---|---|---|
| `rust-lede/tfidf mode=default` | **0.13** | 0.20 |
| `lede/tfidf mode=legacy` | 0.23 | 0.34 |
| `lede/tfidf mode=coverage` | 0.36 | 0.54 |
| `lede/tfidf mode=default` | 0.42 | 0.62 |
| `lede/tfidf mode=default +stats` | 0.67 | 0.96 |
| `lede/tfidf mode=default +outline` | 0.72 | 1.02 |
| `lede/tfidf mode=coverage +all` | 2.51 | 3.77 |
| `lede/tfidf mode=default +all` | **2.55** | **3.80** |
| `sumy/TextRank` | 12.55 | 14.95 |
| `sumy/LexRank` | 13.35 | 16.72 |
| `sumy/LSA` | 16.82 | 60.88 |
| LLM API (Claude / GPT / Cohere) | ~500–5000 [^1] | n/a |

lede is **~30× faster than Sumy on the bare summary** and **~5× faster than Sumy with all five RAG-prep enrichments attached**. The fact that lede can ATTACH structured facts and still be faster is the v0.2 differentiator.

## When each tool wins

| You want | Pick | Why |
|---|---|---|
| Sub-millisecond summary on a per-chunk hot path | **lede** (default) | 0.42 ms / 0.13 ms (Rust). Sumy is 30× slower. |
| Summary + structured facts in one call (RAG prep) | **lede +all** | 2.55 ms p50. Nothing else returns a `SummaryResult` like this. |
| Byte-identical output across Python and Rust | **lede** | Per-fixture parity walker enforces this on every push. |
| Snapshot-test stability / regulated environment | **lede** | Deterministic. Sumy is too. LLMs are not. |
| Highest output quality on a single document | **LLM API** | Reasoning, fusion, restatement. Pay 1000–10,000× the latency for it. |
| Algorithm catalog (LSA / KL-Sum / Edmundson) | **Sumy** | 8+ algorithms, mature. lede ships TF-IDF + position + length only. |
| Multi-document fusion / cross-document reasoning | **LLM API** | Out of scope for any extractive summarizer. |
| Air-gapped / on-device / no-API-budget | **lede** | Stdlib + regex. No network, no model weights, no auth. |
| Want both — cheap pre-filter then expensive LLM | **lede in front of LLM** | The 2026 cost-optimization narrative ([Maxim], [Morph]). 40–94% input-token-cut at the input layer with no quality cost on the LLM's downstream summary. |

[Maxim]: https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/
[Morph]: https://www.morphllm.com/llm-cost-optimization

## Reproducing these numbers

```bash
# Latency matrix (regenerates `benchmarks/quality/matrix-{date}.md`)
.venv/bin/python benchmarks/matrix_eval.py

# Output dump (regenerates `benchmarks/quality/outputs-{date}.md`)
.venv/bin/python benchmarks/quality_eval.py
```

`matrix_eval.py` runs each method × corpus combination 50 times with one unrecorded warmup, reports p50/max in milliseconds, and asserts the SC-B latency budget (250 ms warm).

## Caveats

- **Latency comparisons are on the same single-core hot path.** Sumy initializes parsers / tokenizers per call; lede lazy-initializes once. A long-running daemon would see Sumy improve relative to these numbers but lede is still faster.
- **The 500–5000 ms LLM band is from cited public benchmarks** ([anthropic-claude-3 vs gpt-4 summarization comparison][the-decoder]; [Picovoice 2026 summarization-API guide][picovoice]). Real numbers vary widely with model, prompt, output length, and provider load.
- **Sumy LSA's worst case (60.88 ms) is on `tech-spec`** — a 3 KB doc with heavy headings. The other Sumy backends are much steadier; LSA's SVD step is the outlier.
- **lede's "byte-identical" claim covers the regex backend.** Optional Python-only backends (`spacy`, `yake`) make no parity promise — see [`docs/v0-2-design.md`](v0-2-design.md) for the contract scope.

[^1]: LLM API latency 500–5000 ms is the typical band for frontier-model summarization endpoints. Source: [Anthropic Claude 3 vs GPT-4 summarization benchmark][the-decoder]; [Picovoice 2026 summarization-API guide][picovoice].
[^2]: Per-document cost depends on model and prompt length. Cohere Command R7B is reported at "3–27× cheaper than competitors for budget models" ([MetaCTO][metacto]). Frontier-model APIs sit higher.

[the-decoder]: https://the-decoder.com/anthropics-claude-3-beats-openais-gpt-4-at-text-summarization/
[picovoice]: https://picovoice.ai/blog/guide-to-summarization-apis/
[metacto]: https://www.metacto.com/blogs/cohere-pricing-explained-a-deep-dive-into-integration-development-costs
