## TL;DR

The extractive-summarization space is crowded with mature Python options (Sumy is the reference, 3.7k stars, Apache-2.0, actively maintained into 2026) but **thin elsewhere**: Rust has small TF-IDF crates and nothing graph-based, Go has two credible TextRank/LexRank packages (davidbelicza/TextRank inactive since 2021; JesusIslam/tldr still active), and Node has only narrow single-purpose packages (`node-summarizer`, `fast-ai-text-summary`). No single library today ships a deterministic, feature-parity extractive primitive across all four runtimes — that is the gap this project targets. Commercial alternatives (Cohere Summarize, OpenAI, Claude, Mistral, distilled BART/T5) compete on quality, not on cost, speed, or determinism.

---

## Summary Table — direct competitors across all four languages

| Name | Lang | URL | License | Stars | Last activity | Algorithms | Overlap |
|---|---|---|---|---|---|---|---|
| [Sumy](https://github.com/miso-belica/sumy) | Python | github.com/miso-belica/sumy | Apache-2.0 | 3.7k | 2026-02-14 (v0.12.0) | LSA, LexRank, TextRank, Luhn, Edmundson, KL-Sum, SumBasic, Reduction | **Very high** — covers most of the default path |
| [Gensim `summarization`](https://github.com/RaRe-Technologies/gensim) | Python | github.com/RaRe-Technologies/gensim | LGPL-2.1 | 15k+ | Summarization module removed in 4.x | TextRank variant | Historical — no longer available in current Gensim |
| [tfidf-text-summarizer](https://crates.io/crates/tfidf-text-summarizer) | Rust | crates.io/crates/tfidf-text-summarizer | MIT/Apache (typical) | — | Small/niche crate | TF-IDF only, Rayon-parallelized | High — same scoring primitive, default path only |
| [rust-bert](https://github.com/guillaume-be/rust-bert) | Rust | github.com/guillaume-be/rust-bert | Apache-2.0 | ~3k | Active | BART-based abstractive | Low — abstractive, heavyweight (ONNX/torch) |
| [davidbelicza/TextRank](https://github.com/DavidBelicza/TextRank) | Go | github.com/DavidBelicza/TextRank | MIT | 223 | 2021-07 (inactive) | TextRank, phrase extraction, multithreaded | High — but stale |
| [JesusIslam/tldr](https://github.com/JesusIslam/tldr) | Go | github.com/JesusIslam/tldr | MIT | 137 | 2025-10-03 (v0.7.0) | LexRank (Jaccard/Hamming × PageRank/centrality) | High — actively maintained, ~900ns/op |
| [algao1/basically](https://github.com/algao1/basically) | Go | github.com/algao1/basically | — | — | Small/niche | TextRank + Biased TextRank, built on prose | Medium — focused API |
| [arjunmahishi/text-summary](https://pkg.go.dev/github.com/arjunmahishi/text-summary) | Go | pkg.go.dev/.../text-summary | — | — | Small/niche | Simple N-line extractor | Low — thin |
| [node-summarizer](https://www.npmjs.com/package/node-summarizer) | Node | npmjs.com/package/node-summarizer | — | — | — | Frequency + TextRank, plus sentiment | High — but mixes concerns |
| [fast-ai-text-summary](https://github.com/AkshayPanchivala/fast-ai-text-summary) | Node | github.com/AkshayPanchivala/fast-ai-text-summary | — | — | Newer | Frequency-based | Medium — narrow algorithm |
| [node-summary](https://github.com/jbrooksuk/node-summary) | Node | github.com/jbrooksuk/node-summary | — | — | — | Naive per-paragraph extractor | Medium — simplistic |

---

## Commercial alternatives (abstractive, LLM-backed)

These are **not direct competitors** — they are the expensive alternative this library is designed to front. Included so callers can see the tradeoff.

### Cohere Summarize / Command R7B
- **URL:** [cohere.com](https://cohere.com)
- **Purpose:** Dedicated summarization endpoint with extractive and abstractive modes and multiple length presets
- **Target user:** Enterprise teams that already use Cohere's embedding/rerank stack
- **Pricing:** Command R7B reported "3–27× cheaper than competitors for budget models" ([MetaCTO, 2026](https://www.metacto.com/blogs/cohere-pricing-explained-a-deep-dive-into-integration-development-costs))
- **Buzz:** Positioned as the cost-efficient option among frontier providers
- **Overlap:** Low — cloud API, non-deterministic, network-dependent. But competes on the same user need (shrink text for downstream processing).

### OpenAI / Anthropic / Mistral general-purpose models
- **URL:** [platform.openai.com](https://platform.openai.com), [anthropic.com](https://www.anthropic.com), [mistral.ai](https://mistral.ai)
- **Purpose:** General chat models used for summarization via prompt engineering
- **Pricing:** Token-based; wide range
- **Performance note:** Anthropic Claude 3 Opus rated 90% reliable vs. GPT-4 / GPT-4-Turbo at 78% in one summarization benchmark ([the-decoder, 2024](https://the-decoder.com/anthropics-claude-3-beats-openais-gpt-4-at-text-summarization/))
- **Overlap:** Low — highest quality, highest latency (500–5000ms per doc per [SUMMARIZATION.md performance table]), highest cost, non-deterministic.

### Hugging Face transformer models (self-hosted abstractive)
- **facebook/bart-large-cnn** — high-quality abstractive; ~400MB model
- **sshleifer/distilbart-cnn-12-6** — distilled BART, default for HF summarization pipeline
- **google/pegasus-xsum**, **t5-small** — other common choices
- **URL:** [huggingface.co/tasks/summarization](https://huggingface.co/tasks/summarization)
- **License:** Various (model-specific, mostly permissive)
- **Overlap:** Medium — still abstractive, still requires Python + PyTorch/ONNX. Competes for the "I want better quality than extractive" slot but not for the "I want deterministic and sub-ms" slot.

---

## OSS profiles — the libraries this project most directly overlaps

### Sumy (Python) — the benchmark to beat
- **URL:** [github.com/miso-belica/sumy](https://github.com/miso-belica/sumy)
- **Purpose:** Automatic text + HTML summarization library with a rich algorithm catalog
- **License:** Apache-2.0
- **Traction:** 3.7k stars, 543 forks, 16 releases
- **Community health:** **Active** — v0.12.0 released 2026-02-14 adding Thai/Polish/Swedish language support
- **Algorithms:** LSA, LexRank, TextRank, Luhn, Edmundson, KL-Sum, SumBasic, Reduction
- **Overlap:** Very high. Any Python user looking for an extractive primitive starts here. This project needs to either (a) be significantly faster / smaller / more deterministic, (b) offer features Sumy doesn't (e.g., the `clean_text` / `strip_think` utilities, file ingestion), or (c) differentiate on cross-language parity.

### JesusIslam/tldr (Go) — the active Go option
- **URL:** [github.com/JesusIslam/tldr](https://github.com/JesusIslam/tldr)
- **Purpose:** LexRank-based extractive summarizer for Go
- **License:** MIT
- **Traction:** 137 stars, 19 forks
- **Community health:** **Active** — v0.7.0 released 2025-10-03 with performance optimizations; claims ~900ns/op
- **Algorithms:** LexRank with Jaccard / Hamming weighting × PageRank / centrality ranking (four configurable combinations)
- **Overlap:** High. The "go to" Go summarizer. This project would need parity with Python/Rust/Node to justify its existence alongside `tldr`.

### davidbelicza/TextRank (Go) — the stale Go option
- **URL:** [github.com/DavidBelicza/TextRank](https://github.com/DavidBelicza/TextRank)
- **Purpose:** TextRank with phrase + sentence extraction and goroutine multithreading
- **License:** MIT
- **Traction:** 223 stars, 23 forks
- **Community health:** **Stale** — last release v2.1.3 on 2021-07-08, no recent commits visible
- **Overlap:** Medium — the larger-star Go TextRank package, but inactivity is a real adoption risk users will weigh.

### tfidf-text-summarizer (Rust) — closest to our Rust plan
- **URL:** [crates.io/crates/tfidf-text-summarizer](https://crates.io/crates/tfidf-text-summarizer)
- **Purpose:** Cross-platform TF-IDF-based extractive summarizer
- **Scope:** Offers a `summarize` and `par_summarize` (Rayon-parallel) function taking text + reduction factor
- **Overlap:** High for the default path. Does not implement the keyword-scored / causal-language-bonus variant, and no `clean_text` preprocessing.

### rust-bert (Rust) — the abstractive option
- **URL:** [github.com/guillaume-be/rust-bert](https://github.com/guillaume-be/rust-bert)
- **License:** Apache-2.0
- **Overlap:** Low. Targets abstractive BART/T5 workloads with ONNX — heavy dependency footprint, categorically different from a stdlib-only extractive primitive.

### Node ecosystem — fragmented
No Node package has the maturity of Sumy. `node-summarizer` covers TextRank + frequency but bundles sentiment analysis (scope creep). `fast-ai-text-summary` is newer and frequency-only. `node-summary` is a naive paragraph extractor. **None would be considered the "Sumy of Node."** This is the largest gap among the four target languages.

---

## How this project differentiates

Gaps and opportunities this project's positioning can exploit:

1. **Cross-language parity is unclaimed.** No existing library offers byte-identical output across Python, Rust, Go, and Node. Projects with heterogeneous stacks (e.g., a Node frontend + Python data team + Go service layer) today glue together mismatched summarizers and get inconsistent previews.
2. **Deterministic output is undersold.** Sumy and `tldr` are deterministic but don't market it. `SUMMARIZATION.md` makes determinism a headline feature — useful for enterprise callers doing regression testing on agent outputs.
3. **Bundled `clean_text` + `strip_think` utilities.** None of the surveyed libraries ship boilerplate stripping for CRM/markdown filler or reasoning-block removal for Qwen3/DeepSeek-R1 style `<think>` output. Small utilities, real value.
4. **Node is the weak spot of the OSS landscape.** Shipping a competent Node implementation alone could pick up disproportionate adoption.
5. **Query-driven extractive mode is rare.** Sumy does it via KL-Sum / LexRank variants; most other libs don't. The `extract_relevant(text, keywords, N)` API from `extractive_functions.sql` is simple and callable, and worth exposing as a first-class mode.

## Positioning gaps (risks)

1. **Python is saturated.** Sumy's lead is structural — 3.7k stars, active maintenance, 8+ algorithms, Apache-2.0. A new Python extractive lib needs a clear reason to exist (speed? zero-dep? different algorithm? integration surface?).
2. **Go has an active incumbent.** `tldr`'s ~900ns/op and October 2025 release make it a moving target.
3. **"Extractive vs LLM" is a commodity debate.** Shops with API budgets and acceptable latency just call Claude or Cohere and get higher-quality output. This library needs to be positioned for the non-API cases: offline, on-device, regulated, cost-sensitive, or hot-path middleware (per `ARCHITECTURE.md`'s rationale).

---

**Sources:**
- [GitHub — miso-belica/sumy](https://github.com/miso-belica/sumy)
- [GitHub — DavidBelicza/TextRank](https://github.com/DavidBelicza/TextRank)
- [GitHub — JesusIslam/tldr](https://github.com/JesusIslam/tldr)
- [GitHub — algao1/basically](https://github.com/algao1/basically)
- [GitHub — AkshayPanchivala/fast-ai-text-summary](https://github.com/AkshayPanchivala/fast-ai-text-summary)
- [GitHub — jbrooksuk/node-summary](https://github.com/jbrooksuk/node-summary)
- [GitHub — guillaume-be/rust-bert](https://github.com/guillaume-be/rust-bert)
- [crates.io — tfidf-text-summarizer](https://crates.io/crates/tfidf-text-summarizer)
- [npmjs.com — node-summarizer](https://www.npmjs.com/package/node-summarizer)
- [pkg.go.dev — arjunmahishi/text-summary](https://pkg.go.dev/github.com/arjunmahishi/text-summary)
- [HuggingFace — summarization task](https://huggingface.co/tasks/summarization)
- [HuggingFace — BART model doc](https://huggingface.co/docs/transformers/model_doc/bart)
- [Picovoice — Complete Guide to Summarization APIs & SDKs (2026)](https://picovoice.ai/blog/guide-to-summarization-apis/)
- [MetaCTO — Cohere API Pricing 2026](https://www.metacto.com/blogs/cohere-pricing-explained-a-deep-dive-into-integration-development-costs)
- [the-decoder — Claude 3 vs GPT-4 summarization](https://the-decoder.com/anthropics-claude-3-beats-openais-gpt-4-at-text-summarization/)
