## TL;DR

LLM cost optimization is the dominant 2026 narrative around text summarization — enterprise API spend more than doubled between late 2024 and mid-2025 ($3.5B → $8.4B), and preprocessing/compression layers are repeatedly cited as a lever to cut spend 40–94% without quality loss. Extractive summarization is positioned in this landscape as the cheap, deterministic, hot-path option; distilled transformer summarizers (DistilBART, T5-small) occupy a middle tier; frontier-model APIs (Cohere, OpenAI, Claude, Mistral) occupy the quality-first tier. No analyst firm has published a dedicated "extractive summarization library" market report — this is a developer-tools subcategory, not a called-out market.

---

## Analyst coverage

No direct Gartner / Forrester / IDC / CB Insights coverage found for "extractive summarization libraries" as a named category. Coverage exists for the adjacent spaces:

- **Enterprise LLM cost management** is a recognized topic — e.g., [Silicon Data — Understanding LLM Cost Per Token: A 2026 Practical Guide](https://www.silicondata.com/blog/llm-cost-per-token)
- **Summarization APIs** as a product category have vendor comparisons: [Eden AI — Best Text Summarization APIs in 2025](https://www.edenai.co/post/best-summarization-apis) and [Picovoice — Complete Guide to Summarization APIs & SDKs (2026)](https://picovoice.ai/blog/guide-to-summarization-apis/)

`status: partial` for analyst coverage specifically.

## Market trends (2026)

Five trends directly relevant to positioning this project:

### 1. LLM API spend is ballooning, driving pressure to compress inputs
> "LLM API spending doubled from $3.5 billion to $8.4 billion between late 2024 and mid-2025."
> — [Maxim — Reduce LLM Cost and Latency, 2026](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/)

### 2. Preprocessing/summarization layers are a headline cost-cut lever
> "A preprocessing layer that summarizes telemetry allows the model to receive important signals without noise. Adding a summarization step before the final prompt in RAG systems can reduce the RAG payload by 80–90%."
> — [Morph — LLM Cost Optimization, 2026](https://www.morphllm.com/llm-cost-optimization)

> "Compressed tools (200 tokens), telemetry summary (300 tokens), state memory (150 tokens), and compressed context (200 tokens) represents roughly a 94% reduction in tokens per request."
> — Same source.

### 3. Hierarchical compression (small model → large model) is emerging
> "Hierarchical compression involves compressing documents in stages, with a smaller model used for preprocessing so the larger model receives only the compressed signal."
> — [Morph, 2026](https://www.morphllm.com/llm-cost-optimization)

The "small preprocessor → big model" pattern is exactly where a deterministic extractive primitive slots in, since it has effectively zero cost and sub-millisecond latency.

### 4. Model routing is commodifying summarization
> "Model Routing LLM: 7 Powerful Strategies to Reduce Token Cost & OpenAI API Spend (2026)"
> — [abhyashsuchi.in](https://abhyashsuchi.in/model-routing-llm-2026-best-practices/)

As routers emerge, pre-summarization becomes a routing input (cheap deterministic summary for simple cases, full LLM for hard cases).

### 5. Multi-language engineering stacks are the norm
Anecdotal but consistent: a typical production AI app has a Python data pipeline, a Go or Rust service tier, and a Node frontend. Each tier today imports a different summarizer — a consistency problem this project targets.

## Architecture context — patterns and anti-patterns

**Pattern: "Small model preprocessing before large model."** Repeatedly recommended across 2026 content ([Morph](https://www.morphllm.com/llm-cost-optimization), [Silent Infotech](https://silentinfotech.com/blog/ai-9/guide-to-llm-token-management-347), [dasroot.net](https://dasroot.net/posts/2026/04/token-optimization-llm-costs-prompt-engineering/)). Extractive-then-LLM fits this pattern directly — and `extractive-performance.md` in this repo shows real numbers: 50% input reduction, 22% faster LLM calls.

**Pattern: "Middleware interception."** From `ARCHITECTURE.md`: tool output gets intercepted before reaching the LLM, with a compact preview substituted. This requires sub-millisecond latency — LLM-based summarization won't fit the hot path, extractive does.

**Anti-pattern: "Full-context RAG."** Per Morph: "Teams routinely pass 4–8 long documents into a prompt when only a snippet or paragraph would do." Extractive pre-filtering fights this directly.

**Anti-pattern: "Summarize-every-tool-call with Claude/GPT."** The latency math alone kills this — 500–5000ms per summarization — and the cost compounds fast across a multi-turn agent session.

## Precedent — similar approaches

- **Sumy (Python)** — proves the extractive-library market exists, sustains 3.7k stars and active development across ~10 years. Validates demand; raises the bar on feature completeness.
- **spaCy ecosystem** — precedent for multi-language (Python + Rust via `tokenizers`) deterministic NLP primitives as commercial-adjacent OSS. Different scope (tokenization/NER) but same cross-runtime-parity philosophy.
- **tree-sitter** — precedent for "one parser, many language bindings" as a successful OSS pattern. Not NLP, but same distribution model.

## Adoption signals

- **Sumy**: 3.7k GitHub stars, maintained for ~10 years, continued 2026 development → sustained demand.
- **Go `tldr`**: 137 stars, active in 2025 → niche but real demand in Go.
- **npm summarizer packages**: Multiple packages with low-to-moderate downloads, none dominant → fragmented Node market.
- **Search volume signal**: 2026 blog content on "LLM cost optimization" is abundant ([Redis](https://redis.io/blog/llm-token-optimization-speed-up-apps/), [Maxim](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/), [Silent Infotech](https://silentinfotech.com/blog/ai-9/guide-to-llm-token-management-347)) — the upstream demand driver for extractive summarization is strong.

## Sources

- [Maxim — Reduce LLM Cost and Latency, 2026](https://www.getmaxim.ai/articles/reduce-llm-cost-and-latency-a-comprehensive-guide-for-2026/)
- [Morph — LLM Cost Optimization: 5 Levers to Cut API Spend 70–85%](https://www.morphllm.com/llm-cost-optimization)
- [Redis — LLM Token Optimization: Cut Costs & Latency in 2026](https://redis.io/blog/llm-token-optimization-speed-up-apps/)
- [Silent Infotech — LLM Token Management in 2026](https://silentinfotech.com/blog/ai-9/guide-to-llm-token-management-347)
- [dasroot.net — Token Optimization Strategies for Cost-Effective LLM Applications](https://dasroot.net/posts/2026/04/token-optimization-llm-costs-prompt-engineering/)
- [Silicon Data — Understanding LLM Cost Per Token: A 2026 Practical Guide](https://www.silicondata.com/blog/llm-cost-per-token)
- [abhyashsuchi.in — Model Routing LLM (2026)](https://abhyashsuchi.in/model-routing-llm-2026-best-practices/)
- [Eden AI — Best Text Summarization APIs in 2025](https://www.edenai.co/post/best-summarization-apis)
- [Picovoice — Complete Guide to Summarization APIs & SDKs (2026)](https://picovoice.ai/blog/guide-to-summarization-apis/)
- [arxiv.org — Towards Optimizing the Costs of LLM Usage](https://arxiv.org/html/2402.01742v1)
