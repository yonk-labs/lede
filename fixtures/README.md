# Fixture Corpus

Language-agnostic test fixtures for `skimr`. Every implementation (Python, Rust, and later Node + Go) must produce **byte-identical output** for every fixture here.

## Layout

```
fixtures/
  <mode>/
    <fixture-name>/
      input.txt       # raw input
      config.json     # mode + params
      expected.txt    # expected byte-identical output (when known)
```

Modes:

| Directory | Mode |
|---|---|
| `clean_text/` | `clean_text` — markdown + filler + CRM-boilerplate stripper |
| `strip_think/` | `strip_think` — removes `<think>…</think>` blocks |
| `tfidf/` | TF-IDF + position + length (default summarizer, 60/25/15 weighting) |
| `keyword/` | Keyword-scored extractive (query-driven sentence selection) |

## `config.json` schema

```json
{
  "mode": "clean_text | strip_think | tfidf | keyword | textrank",
  "params": {
    "max_length": 500,              // tfidf, textrank
    "keywords": "pricing budget",   // keyword
    "num_sentences": 3              // keyword, textrank
  }
}
```

Unused params for a given mode are omitted.

## Missing `expected.txt`

Some fixtures intentionally ship without an `expected.txt`. That means: **inputs are frozen, but ground-truth output waits for the first spec-compliant implementation to populate it.** This applies to TF-IDF and keyword-scored modes where the scoring math is non-trivial to hand-verify.

Workflow:
1. First impl (Python reference) lands with the scoring pipeline.
2. Run it over every fixture missing an `expected.txt`.
3. Human reviews each generated output against the live spec (`docs/v0-2-design.md` for v0.2, plus the Python reference implementation).
4. Approved outputs commit as `expected.txt`. Those bytes are now the contract.
5. Rust impl must match those bytes exactly. Any Rust mismatch is Rust's bug (or a spec bug — never "let's regenerate expected from Rust").

Per DC-002 in the mission brief: when implementations disagree, the fix is in whichever language diverges from the spec, never in the fixtures.

## Fixture naming

Short, descriptive, lowercase-with-hyphens:
- `simple-markdown`
- `crm-boilerplate`
- `decimal-numbers`
- `abbreviation-boundaries`
- `reasoning-block-nested`

Names become part of test identifiers. Keep them stable.

## Adding a fixture

1. `mkdir fixtures/<mode>/<name>`
2. Write `input.txt`, `config.json`, and (if derivable) `expected.txt`.
3. If `expected.txt` is spec-derivable (e.g., `clean_text` rules are mechanical), hand-craft it and review.
4. If not (TF-IDF scoring, TextRank), leave `expected.txt` out — first impl will populate.
