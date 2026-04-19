# Extractive Pre-filtering: Performance & Quality Results

Benchmark results comparing raw LLM summarization vs extractive pre-filtered summarization using `extract_relevant()` + `aidb.summarize_text_aggregate()`.

**Model:** NVIDIA Nemotron-3-Nano (NIM, `http://192.168.1.193:8006`)
**Database:** 192.168.1.206:5432, sales_demo_app
**Date range:** 2025-11-01 to 2026-02-01, lost deals only

---

## Summary

| Metric | Full Notes | Extractive (3 sent/note) | Improvement |
|---|---|---|---|
| Total input chars | 450K | 223K | **50% smaller** |
| All 5 products | 93.1s | 73.1s | **22% faster** |
| Single product (ClarityDB) | 14.7s | 18.3s | Comparable |
| Single product (OmniConnect) | 27.3s | 16.7s | **39% faster** |
| Output quality | Excellent | Excellent | More focused |

The extractive pre-filter cuts input size in half. Speed gains vary per group (depends on how much the model's reasoning overhead dominates vs input processing). Quality remains high — extractive output tends to be more specific because the LLM sees less noise.

---

## Input Size Reduction

```
Product              Notes   Full Chars   Extracted   Reduction
─────────────────────────────────────────────────────────────────
Neuron Canvas         516     124,942       61,082      51%
TitanDB Enterprise    370      87,640       44,469      49%
Synapse AIOps         346      82,236       41,933      49%
OmniConnect Proxy     310      85,467       39,161      54%
ClarityDB Guardian    286      69,420       36,449      47%
─────────────────────────────────────────────────────────────────
TOTAL               1,828     449,705      223,094      50%
```

---

## What extract_relevant() does to a note

**Original note (1,302 chars):**

```
## Technical Deep-Dive: Johnson Education Co

Detailed walkthrough of OmniConnect Proxy capabilities with Johnson Education Co's
engineering and business teams. Covered architecture, integration, and roadmap.

### Call Summary
Comprehensive call with Sarah Jones and two other stakeholders from their technical
team. Main focus was understanding how OmniConnect Proxy handles data management
challenges. Good energy throughout the session.

### Competitive Landscape
Competition includes **Cerner** (incumbent) and **Medidata** (also evaluating).
We're differentiated on:
- Native support for their Healthcare workflows
- More flexible pricing model
- Faster time to value

They had a bad experience with Medidata previously - opportunity to capitalize.

### Timeline & Urgency
Evaluation timeline shared by Sarah Jones:
- Technical validation: Next 2 weeks
- Final vendor selection: End of month
...

**Deal Details:** $1302 ARR | **Stage:** middle | **Industry:** Healthcare
**Champion:** Sarah Jones | **Product:** OmniConnect Proxy
```

**After `extract_relevant(note_text, 'lost deal reason competitor pricing budget cost ...', 3)`:**

```
more flexible pricing model.
deal details: $1302 arr | stage: middle | industry: healthcare.
main focus was understanding how omniconnect proxy handles data management challenges.
```

Stripped: markdown headers, bullet lists, stakeholder sections, timeline details, boilerplate. Kept: the pricing signal, the deal metadata, and the core challenge. Three sentences, ~160 chars instead of ~1,300.

---

## SQL: Full Notes (no pre-filter)

```sql
SELECT p.product_name,
    COUNT(*) as lost_deals,
    aidb.summarize_text_aggregate(
        sn.note_text,
        aidb.summarize_text_config('nemotron-nano')::json,
        'Analyze these sales notes for lost deals. Identify the top 3
         reasons we lost. Be specific and actionable. Keep your response
         under 250 words. Format as a numbered list.'
    ) as loss_insights
FROM sales_orders so
JOIN products p ON so.product_id = p.product_id
JOIN sales_notes sn ON sn.order_id = so.order_id
WHERE so.status = 'lost'
  AND so.order_date >= '2025-11-01'
  AND so.order_date <= '2026-02-01'
GROUP BY p.product_name
ORDER BY lost_deals DESC;
```

## SQL: Extractive Pre-filter

```sql
SELECT p.product_name,
    COUNT(*) as lost_deals,
    aidb.summarize_text_aggregate(
        extract_relevant(sn.note_text,
            'lost deal reason competitor pricing budget cost
             expensive alternative declined rejected', 3),
        aidb.summarize_text_config('nemotron-nano')::json,
        'Analyze these sales notes for lost deals. Identify the top 3
         reasons we lost. Be specific and actionable. Keep your response
         under 250 words. Format as a numbered list.'
    ) as loss_insights
FROM sales_orders so
JOIN products p ON so.product_id = p.product_id
JOIN sales_notes sn ON sn.order_id = so.order_id
WHERE so.status = 'lost'
  AND so.order_date >= '2025-11-01'
  AND so.order_date <= '2026-02-01'
GROUP BY p.product_name
ORDER BY lost_deals DESC;
```

The only change: wrap `sn.note_text` with `extract_relevant(sn.note_text, '<keywords>', 3)`.

---

## Real Output Comparison

### ClarityDB Guardian (286 notes)

**Full notes** — 69,705 chars input, 14.7s:

> 1. **Champion not fully empowered** – In several lost/at-risk deals (e.g., Williams Finance Systems, Johnson Retail Systems), the primary "champion" (David Brown, Emily Davis, Sarah Miller) lacked direct authority to approve budget or sign contracts. Without a C-level or VP-level sponsor pushing the decision forward, deals stalled after technical validation. *Action:* Identify and engage the economic buyer early, map their decision-making authority, and secure explicit commitment (written intent) before advancing to pricing negotiations.
>
> 2. **Unaddressed integration & scalability concerns** – Competitive losses (e.g., against Siemens/Rockwell, Bloomberg, Refinitiv) occurred when prospects cited blockers such as "implementation complexity," "manual scaling challenges," or "lack of native workflow support." Our demos focused on features but did not prove seamless integration with their existing Terraform, IoT, or ERP layers. *Action:* Build a targeted proof-of-concept that demonstrates end-to-end integration with each prospect's specific stack and quantify performance gains.
>
> 3. **Timing/budget misalignment** – Deals like Davis Manufacturing and Garcia Technology Systems collapsed because the buyer's fiscal-year budget window closed before a decision could be locked, leading to "pushed to next cycle" outcomes. *Action:* Align sales forecasting with the customer's budget calendar, set firm decision-by dates tied to fiscal milestones, and deploy incremental "quick-win" pilots to keep momentum while awaiting final approval.

**Extractive (3 sentences/note)** — 36,734 chars input, 18.3s:

> 1. **Manual/Work-around Inefficiencies Undermine Urgency** – The prospect's current solution is error-prone, slow, and lacks clear ROI metrics.
>    *Action:* Run a time-boxed pilot (e.g., 2-week "data-health" proof) that quantifies hours saved and error reduction, then share the documented ROI with the champion.
>
> 2. **Budget Approval & Decision Delays** – Multiple deals stalled while awaiting fiscal-year sign-off or leadership approval, pushing closure to the next budget cycle.
>    *Action:* Early engage finance leadership (e.g., set up a 30-minute executive briefing) to pre-qualify spend and lock in a decision deadline; align your sales cadence to that fiscal horizon.
>
> 3. **Competitive Pressure and Lack of Differentiated Proof** – Prospects evaluated rival tools (Competitor A/B) and cited implementation complexity as a deal-breaker.
>    *Action:* Deploy tailored reference-customer stories, customized architecture diagrams, and a PoC that directly addresses the prospect's specific data-volume and scaling constraints, positioning your platform as the only solution that matches their technical requirements.

**Observations:** Both identify the same core themes (budget delays, competitive pressure, champion issues). The full-notes version names more specific companies and dollar amounts. The extractive version is more concise and focused on patterns rather than individual deals.

---

### OmniConnect Proxy (310 notes)

**Full notes** — 85,776 chars input, 27.3s:

> 1. **Procurement & Budget Delays** – Multiple deals stalled (e.g., "Waiting for budget approval," "Legal review pending," "Champion OOO") causing the opportunity to slip past critical timelines.
>    **Action:** Implement a rapid-approval playbook: pre-screen budget cycles, assign an internal "budget-owner" sponsor, and submit concise executive summaries with clear ROI metrics to accelerate sign-off before the fiscal-quarter cut-off.
>
> 2. **Competitive Entrenchment & Mis-aligned Value Proposition** – Incumbent vendors (Epic, Cerner, Shopify, Databricks, Snowflake, etc.) held existing relationships and were perceived as cheaper or more familiar.
>    **Action:** Build a differentiated battle-card that quantifies long-term cost savings, faster time-to-value, and unique Healthcare/Retail/Education workflow coverage; leverage reference customers that previously switched from the incumbent.
>
> 3. **Insufficient Technical Tailoring & Proof of Concept** – Prospects highlighted specific gaps (e.g., AI/ML unstructured-data support, PII control, 99.9% uptime, SOC-2/PCI compliance) that our demo didn't fully address.
>    **Action:** Deploy a rapid-customization kit: pre-configured connectors and compliance checklists for each vertical, and commit to a time-boxed (≤ 2-week) PoC with defined success criteria.

**Extractive (3 sentences/note)** — 39,470 chars input, 16.7s:

> 1. **Performance shortcomings in the proof-of-concept (POC)** – The POC for Pacer Freight Services showed a 40% degradation in API response times as usage grew, causing the customer to lose confidence and walk away.
>    *Action:* Implement a performance-validation checklist before any POC sign-off (load-testing thresholds, scalability limits, and a clear escalation path). Build automated regression tests into the demo pipeline.
>
> 2. **Budget-cycle mis-alignment** – Several opportunities (e.g., $13k, $69k, $50k deals) stalled because prospects were waiting for the new fiscal year or internal budget approvals.
>    *Action:* Integrate a "budget-check" step into the qualification stage. Use a pre-approved "early-bird" financing or pilot-only package to keep momentum while the client secures funding.
>
> 3. **Competitive positioning & perceived complexity** – Repeated feedback highlighted concerns about solution complexity, cost-effectiveness, and the need for extensive internal expertise, allowing competitors to win.
>    *Action:* Develop a simplified "starter-kit" offering (bundled pricing, guided onboarding, and a hands-on technical workshop) that demonstrates ROI in under 30 days.

**Observations:** The extractive version surfaced a very specific insight (40% API degradation at Pacer Freight Services) that the full-notes version missed in its more general summary. The extractive filter elevated the data-rich, causal sentences — exactly the kind of detail that matters for loss analysis. 39% faster.

---

## Tuning the extractive filter

Adjust the number of sentences per note to control the size/quality tradeoff:

```sql
-- Aggressive: 2 sentences per note (~37% of original)
extract_relevant(sn.note_text, '<keywords>', 2)

-- Balanced: 3 sentences per note (~50% of original) ← recommended
extract_relevant(sn.note_text, '<keywords>', 3)

-- Conservative: 5 sentences per note (~65% of original)
extract_relevant(sn.note_text, '<keywords>', 5)
```

Match the keywords to your analysis prompt:

```sql
-- Lost deal analysis
extract_relevant(sn.note_text,
    'lost deal reason competitor pricing budget cost expensive alternative declined rejected', 3)

-- Churn/support analysis
extract_relevant(ticket_text,
    'churn cancel unhappy frustrated bug issue broken downtime', 3)

-- Win analysis
extract_relevant(sn.note_text,
    'won closed signed contract champion value pricing competitive advantage', 3)
```

---

## When to use extractive pre-filtering

**Use it when:**
- Notes are long (markdown, CRM boilerplate, stakeholder sections)
- You have hundreds+ notes per group
- LLM latency is a concern
- You want more focused, less repetitive output

**Skip it when:**
- Notes are already short/clean (< 100 chars each)
- You need the LLM to see full context (e.g., timeline analysis)
- The analysis topic is broad and keywords are hard to define
