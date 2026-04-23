# extract.* eval vs gold fixtures — 2026-04-23

Backend under test: **regex** (default, zero-dep). Gold is filtered to the regex-backend-capable subset per primitive for recall; precision is measured against the full gold set so sub/super-phrase overlap counts as a hit (see harness docstring). Dropped-gold counts are shown below so the spaCy-backend eval (future) can reason about the unfiltered set.

## Aggregate (target: recall >= 0.85, precision >= 0.80)

| primitive | precision | recall | F1 | TP_p | FP | TP_r | FN | gold dropped | status |
|---|---|---|---|---|---|---|---|---|---|
| `stats` | 1.000 | 1.000 | 1.000 | 18 | 0 | 18 | 0 | 31 | **pass** |
| `outline` | 1.000 | 1.000 | 1.000 | 16 | 0 | 16 | 0 | 25 | **pass** |
| `metadata` | 1.000 | 1.000 | 1.000 | 5 | 0 | 5 | 0 | 0 | **pass** |
| `phrases` | 0.829 | 1.000 | 0.907 | 68 | 14 | 55 | 0 | 64 | **pass** |
| `correlate` | 1.000 | 1.000 | 1.000 | 1 | 0 | 1 | 0 | 13 | **pass** |

## Per-corpus breakdown

### `stats`

| corpus | TP_p | FP | TP_r | FN | gold dropped |
|---|---|---|---|---|---|
| `crm-note-long` | 2 | 0 | 2 | 0 | 0 |
| `crm-note-short` | 3 | 0 | 3 | 0 | 0 |
| `meeting-minutes` | 2 | 0 | 2 | 0 | 7 |
| `news-article` | 1 | 0 | 1 | 0 | 1 |
| `privacy-policy` | 1 | 0 | 1 | 0 | 4 |
| `scientific-paper` | 0 | 0 | 0 | 0 | 5 |
| `scotus-opinion` | 0 | 0 | 0 | 0 | 5 |
| `support-ticket` | 2 | 0 | 2 | 0 | 0 |
| `tech-spec` | 6 | 0 | 6 | 0 | 6 |
| `wikipedia-article` | 1 | 0 | 1 | 0 | 3 |

### `outline`

| corpus | TP_p | FP | TP_r | FN | gold dropped |
|---|---|---|---|---|---|
| `crm-note-long` | 6 | 0 | 6 | 0 | 0 |
| `crm-note-short` | 0 | 0 | 0 | 0 | 0 |
| `meeting-minutes` | 0 | 0 | 0 | 0 | 2 |
| `news-article` | 0 | 0 | 0 | 0 | 0 |
| `privacy-policy` | 0 | 0 | 0 | 0 | 8 |
| `scientific-paper` | 0 | 0 | 0 | 0 | 6 |
| `scotus-opinion` | 0 | 0 | 0 | 0 | 2 |
| `support-ticket` | 3 | 0 | 3 | 0 | 3 |
| `tech-spec` | 7 | 0 | 7 | 0 | 0 |
| `wikipedia-article` | 0 | 0 | 0 | 0 | 4 |

### `metadata`

| corpus | TP_p | FP | TP_r | FN | gold dropped |
|---|---|---|---|---|---|
| `crm-note-long` | 1 | 0 | 1 | 0 | 0 |
| `crm-note-short` | 2 | 0 | 2 | 0 | 0 |
| `meeting-minutes` | 1 | 0 | 1 | 0 | 0 |
| `news-article` | 0 | 0 | 0 | 0 | 0 |
| `privacy-policy` | 1 | 0 | 1 | 0 | 0 |
| `scientific-paper` | 0 | 0 | 0 | 0 | 0 |
| `scotus-opinion` | 0 | 0 | 0 | 0 | 0 |
| `support-ticket` | 0 | 0 | 0 | 0 | 0 |
| `tech-spec` | 0 | 0 | 0 | 0 | 0 |
| `wikipedia-article` | 0 | 0 | 0 | 0 | 0 |

### `phrases`

| corpus | TP_p | FP | TP_r | FN | gold dropped |
|---|---|---|---|---|---|
| `crm-note-long` | 2 | 0 | 2 | 0 | 7 |
| `crm-note-short` | 0 | 0 | 0 | 0 | 9 |
| `meeting-minutes` | 3 | 1 | 3 | 0 | 8 |
| `news-article` | 0 | 0 | 0 | 0 | 10 |
| `privacy-policy` | 8 | 0 | 8 | 0 | 3 |
| `scientific-paper` | 19 | 4 | 9 | 0 | 7 |
| `scotus-opinion` | 14 | 0 | 12 | 0 | 3 |
| `support-ticket` | 11 | 8 | 10 | 0 | 3 |
| `tech-spec` | 3 | 0 | 3 | 0 | 7 |
| `wikipedia-article` | 8 | 1 | 8 | 0 | 7 |

### `correlate`

| corpus | TP_p | FP | TP_r | FN | gold dropped |
|---|---|---|---|---|---|
| `crm-note-long` | 0 | 0 | 0 | 0 | 0 |
| `crm-note-short` | 0 | 0 | 0 | 0 | 0 |
| `meeting-minutes` | 0 | 0 | 0 | 0 | 4 |
| `news-article` | 0 | 0 | 0 | 0 | 0 |
| `privacy-policy` | 0 | 0 | 0 | 0 | 1 |
| `scientific-paper` | 0 | 0 | 0 | 0 | 1 |
| `scotus-opinion` | 0 | 0 | 0 | 0 | 4 |
| `support-ticket` | 0 | 0 | 0 | 0 | 1 |
| `tech-spec` | 1 | 0 | 1 | 0 | 1 |
| `wikipedia-article` | 0 | 0 | 0 | 0 | 1 |

