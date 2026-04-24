# extract.* eval vs gold fixtures — 2026-04-24

Backend under test: **regex** (default, zero-dep). For stats, `convert_word_names=True` (text2num installed).

Match rule: format-tolerant. Bidirectional substring on value after hyphen/underscore/whitespace normalization for stats; sub/super-ngram overlap for phrases; strict equality for metadata/outline/correlate. Same full gold set on both precision and recall sides — see harness docstring for rationale vs. the rejected T13-initial gold-filtered approach.

## Aggregate (target: recall >= 0.85, precision >= 0.80)

| primitive | precision | recall | F1 | TP_p | FP | TP_r | FN | status |
|---|---|---|---|---|---|---|---|---|
| `stats` | 0.913 | 0.857 | 0.884 | 42 | 4 | 42 | 7 | **pass** |
| `outline` | 0.972 | 0.854 | 0.909 | 35 | 1 | 35 | 6 | **pass** |
| `metadata` | 1.000 | 1.000 | 1.000 | 5 | 0 | 5 | 0 | **pass** |
| `phrases` | 0.809 | 0.478 | 0.601 | 55 | 13 | 55 | 60 | **FAIL** |
| `correlate` | 0.250 | 0.071 | 0.111 | 1 | 3 | 1 | 13 | **FAIL** |

## Per-corpus breakdown

### `stats`

| corpus | TP_p | FP | TP_r | FN |
|---|---|---|---|---|
| `crm-note-long` | 2 | 0 | 2 | 0 |
| `crm-note-short` | 3 | 0 | 3 | 0 |
| `meeting-minutes` | 7 | 0 | 7 | 2 |
| `news-article` | 2 | 1 | 2 | 0 |
| `privacy-policy` | 5 | 0 | 5 | 0 |
| `scientific-paper` | 2 | 1 | 2 | 3 |
| `scotus-opinion` | 5 | 1 | 5 | 0 |
| `support-ticket` | 2 | 0 | 2 | 0 |
| `tech-spec` | 10 | 1 | 10 | 2 |
| `wikipedia-article` | 4 | 0 | 4 | 0 |

### `outline`

| corpus | TP_p | FP | TP_r | FN |
|---|---|---|---|---|
| `crm-note-long` | 6 | 0 | 6 | 0 |
| `crm-note-short` | 0 | 0 | 0 | 0 |
| `meeting-minutes` | 0 | 0 | 0 | 2 |
| `news-article` | 0 | 0 | 0 | 0 |
| `privacy-policy` | 8 | 0 | 8 | 0 |
| `scientific-paper` | 6 | 0 | 6 | 0 |
| `scotus-opinion` | 1 | 1 | 1 | 1 |
| `support-ticket` | 3 | 0 | 3 | 3 |
| `tech-spec` | 7 | 0 | 7 | 0 |
| `wikipedia-article` | 4 | 0 | 4 | 0 |

### `metadata`

| corpus | TP_p | FP | TP_r | FN |
|---|---|---|---|---|
| `crm-note-long` | 1 | 0 | 1 | 0 |
| `crm-note-short` | 2 | 0 | 2 | 0 |
| `meeting-minutes` | 1 | 0 | 1 | 0 |
| `news-article` | 0 | 0 | 0 | 0 |
| `privacy-policy` | 1 | 0 | 1 | 0 |
| `scientific-paper` | 0 | 0 | 0 | 0 |
| `scotus-opinion` | 0 | 0 | 0 | 0 |
| `support-ticket` | 0 | 0 | 0 | 0 |
| `tech-spec` | 0 | 0 | 0 | 0 |
| `wikipedia-article` | 0 | 0 | 0 | 0 |

### `phrases`

| corpus | TP_p | FP | TP_r | FN |
|---|---|---|---|---|
| `crm-note-long` | 2 | 0 | 2 | 7 |
| `crm-note-short` | 0 | 0 | 0 | 9 |
| `meeting-minutes` | 3 | 1 | 3 | 8 |
| `news-article` | 0 | 0 | 0 | 10 |
| `privacy-policy` | 7 | 1 | 7 | 3 |
| `scientific-paper` | 15 | 2 | 12 | 4 |
| `scotus-opinion` | 10 | 0 | 12 | 3 |
| `support-ticket` | 10 | 5 | 11 | 2 |
| `tech-spec` | 3 | 0 | 3 | 7 |
| `wikipedia-article` | 5 | 4 | 5 | 7 |

### `correlate`

| corpus | TP_p | FP | TP_r | FN |
|---|---|---|---|---|
| `crm-note-long` | 0 | 0 | 0 | 0 |
| `crm-note-short` | 0 | 0 | 0 | 0 |
| `meeting-minutes` | 0 | 0 | 0 | 4 |
| `news-article` | 0 | 0 | 0 | 0 |
| `privacy-policy` | 0 | 0 | 0 | 1 |
| `scientific-paper` | 0 | 0 | 0 | 1 |
| `scotus-opinion` | 0 | 1 | 0 | 4 |
| `support-ticket` | 0 | 1 | 0 | 1 |
| `tech-spec` | 1 | 1 | 1 | 1 |
| `wikipedia-article` | 0 | 0 | 0 | 1 |

