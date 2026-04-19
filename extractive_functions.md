# Extractive Summarization & Text Cleaning Functions

Pure PL/pgSQL functions for pre-filtering text before sending to an LLM. No extensions required — works on any PostgreSQL 12+ instance.

**Install:** `psql -f extractive_functions.sql`

## Functions

### `clean_text(input_text TEXT) → TEXT`

Strips noise from raw text: markdown formatting, filler words, CRM boilerplate phrases, and excess whitespace. Returns cleaned, lowercase text.

**What it removes:**

| Category | Examples |
|---|---|
| Markdown | `**bold**`, `__underline__`, `# headers`, `---`, bullet prefixes |
| Filler phrases | "just wanted to", "as discussed", "hope this helps", "let me know if you have any questions" |
| Filler words | "basically", "essentially", "actually", "literally", "obviously", "pretty much", "kind of" |
| CRM boilerplate | "No updates", "Calendar invite sent", "Waiting on callback", "Updated CRM with latest info", "Meeting confirmed for next week" |
| Whitespace | Duplicate spaces, blank lines, leading/trailing whitespace |

```sql
-- Basic usage
SELECT clean_text('**Meeting Notes**

Just wanted to follow up on the pricing discussion.
Basically, the customer is concerned about cost — $45K is above their budget.
They''re evaluating Competitor A as a cheaper alternative.

No updates.
Calendar invite sent.
Updated CRM with latest info.');
```

Returns:

```
meeting notes
the pricing discussion.
, the customer is concerned about cost — $45k is above their budget.
they're evaluating competitor a as a cheaper alternative.
```

---

### `extract_sentences(input_text TEXT, keywords TEXT, num_sentences INTEGER DEFAULT 10) → TEXT`

Extracts the N most relevant sentences from a text block. Splits on sentence boundaries (`.` `?` `!` and newlines), scores each sentence, returns the top N ordered by score.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `input_text` | TEXT | — | Text to extract from |
| `keywords` | TEXT | — | Space-separated keywords to match against |
| `num_sentences` | INTEGER | 10 | How many sentences to return |

**Scoring:**

Each sentence gets a score based on:

| Signal | Points | Rationale |
|---|---|---|
| Keyword match | +1 per keyword found | Core relevance |
| Length > 200 chars | +0.5 | Substantive content |
| Contains numbers | +0.3 | Data-rich |
| Causal/analytical language | +1.0 | Actionable insight |

Causal/analytical terms: because, reason, due to, caused, result, impact, issue, problem, concern, risk, challenge, blocker, gap, lack, missing, competitor, pricing, budget, cost, expensive, cheaper, alternative, decided, chose, prefer, switched, rejected, declined.

```sql
-- Extract 3 most relevant sentences about pricing
SELECT extract_sentences(
    'The demo went well with the team. They loved the dashboard.
     Main concern is pricing — $50K is above their Q2 budget.
     Competitor B quoted them $30K for similar functionality.
     Will follow up next Tuesday after their board meeting.
     Risk: they may choose the cheaper option if we can''t negotiate.',
    'pricing budget cost competitor expensive cheaper',
    3
);
```

Returns:

```
Risk: they may choose the cheaper option if we can't negotiate.
Main concern is pricing — $50K is above their Q2 budget.
Competitor B quoted them $30K for similar functionality.
```

---

### `extract_relevant(input_text TEXT, prompt TEXT, num_sentences INTEGER DEFAULT 10) → TEXT`

Convenience wrapper — cleans the text first (`clean_text`), then extracts relevant sentences (`extract_sentences`). Use this directly on raw text columns.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `input_text` | TEXT | — | Raw text (may contain markdown, filler, etc.) |
| `prompt` | TEXT | — | Analysis prompt or keywords to match against |
| `num_sentences` | INTEGER | 10 | How many sentences to return |

```sql
-- Clean and extract from a single note
SELECT extract_relevant(
    '**Call Summary**

     Just wanted to follow up — basically, the customer is very concerned
     about pricing. They mentioned Competitor A is $20K cheaper.
     Updated CRM with latest info.
     Calendar invite sent.
     Budget approval is the main blocker right now.',
    'pricing budget competitor cost',
    2
);
```

Returns:

```
the customer is concerned about pricing.
budget approval is the main blocker right now.
```

---

## Examples

### Single note: find loss-related sentences

```sql
SELECT extract_relevant(note_text, 'lost reason competitor pricing budget', 3)
FROM sales_notes
WHERE note_id = 42;
```

### Per-note extraction across a query

```sql
SELECT sn.note_id,
       LEFT(sn.note_text, 80) AS original,
       extract_relevant(sn.note_text,
           'lost deal competitor pricing budget declined', 2) AS extracted
FROM sales_notes sn
JOIN sales_orders so ON sn.order_id = so.order_id
WHERE so.status = 'lost'
LIMIT 10;
```

### Measure text reduction by product

```sql
SELECT p.product_name,
       COUNT(*) AS notes,
       SUM(LENGTH(sn.note_text)) AS full_chars,
       SUM(LENGTH(extract_relevant(sn.note_text,
           'lost deal competitor pricing budget cost', 2))) AS extracted_chars,
       ROUND(100.0 * SUM(LENGTH(extract_relevant(sn.note_text,
           'lost deal competitor pricing budget cost', 2)))
           / NULLIF(SUM(LENGTH(sn.note_text)), 0), 1) AS pct_remaining
FROM sales_orders so
JOIN products p ON so.product_id = p.product_id
JOIN sales_notes sn ON sn.order_id = so.order_id
WHERE so.status = 'lost'
GROUP BY p.product_name;
```

### Pre-filter before LLM aggregate (AIDB)

The main use case — reduce LLM input size by extracting only relevant sentences before sending to `aidb.summarize_text_aggregate()`:

```sql
SELECT p.product_name,
       COUNT(*) AS lost_deals,
       aidb.summarize_text_aggregate(
           extract_relevant(sn.note_text,
               'lost deal reason competitor pricing budget cost declined rejected', 2),
           aidb.summarize_text_config('granite4-1b')::json,
           'Analyze these sales notes for lost deals. Identify the top 3 reasons
            we lost. Be specific and actionable. Keep your response under 250
            words. Format as a numbered list.'
       ) AS loss_insights
FROM sales_orders so
JOIN products p ON so.product_id = p.product_id
JOIN sales_notes sn ON sn.order_id = so.order_id
WHERE so.status = 'lost'
  AND so.order_date >= '2025-11-01'
  AND so.order_date <= '2026-02-01'
GROUP BY p.product_name
ORDER BY lost_deals DESC;
```

### Clean text only (no extraction)

Useful when you want to reduce noise but keep all content:

```sql
SELECT clean_text(note_text) FROM sales_notes LIMIT 5;
```

### Different keyword sets for different analyses

```sql
-- Churn analysis
SELECT extract_relevant(note_text, 'churn cancel leaving unhappy frustrated', 3)
FROM support_tickets;

-- Competitive intelligence
SELECT extract_relevant(note_text, 'competitor alternative switching evaluated compared', 3)
FROM sales_notes;

-- Technical blockers
SELECT extract_relevant(note_text, 'blocker issue bug error failed broken integration', 3)
FROM engineering_notes;
```

---

## Performance

Tested against 1,828 sales notes (5 product groups, ~451K total chars):

| Sentences per note | Output size | Reduction | Extraction time |
|---|---|---|---|
| 5 | ~65% of original | 35% smaller | — |
| 3 | ~50% of original | 50% smaller | — |
| 2 | ~37% of original | **63% smaller** | — |
| All (no extraction) | 451K chars | baseline | 192ms total |

The extractive filtering adds ~192ms across all 1,828 notes. LLM processing time drops proportionally to input size reduction — a 63% smaller payload means significantly faster LLM responses.

## Edge cases

- **NULL or empty input**: Returns empty string
- **No keywords match (all words ≤ 2 chars)**: Returns first 2000 chars of input
- **No sentences > 20 chars**: Returns full input text unchanged
- **Fewer sentences than requested**: Returns all available sentences
