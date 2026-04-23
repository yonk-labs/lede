# extract.* eval vs gold fixtures — 2026-04-23

Backend under test: **regex** (default, zero-dep). Precision / recall vs. hand-labeled gold at `fixtures/extract/**`. No filtering — the gold set is the contract and the SC-D gate measures the primitive directly against corpus intent (labeling protocol rule #1). `_norm_phrase` is applied symmetrically for hyphen/slash matching fairness on `phrases` and `correlate`.

## Aggregate (target: recall >= 0.85, precision >= 0.80)

| primitive | precision | recall | F1 | TP | FP | FN | status |
|---|---|---|---|---|---|---|---|
| `stats` | 1.000 | 0.367 | 0.537 | 18 | 0 | 31 | **FAIL** |
| `outline` | 1.000 | 0.390 | 0.561 | 16 | 0 | 25 | **FAIL** |
| `metadata` | 1.000 | 1.000 | 1.000 | 5 | 0 | 0 | **pass** |
| `phrases` | 0.622 | 0.443 | 0.518 | 51 | 31 | 64 | **FAIL** |
| `correlate` | 0.333 | 0.071 | 0.118 | 1 | 2 | 13 | **FAIL** |

## Per-corpus breakdown

### `stats`

| corpus | TP | FP | FN |
|---|---|---|---|
| `crm-note-long` | 2 | 0 | 0 |
| `crm-note-short` | 3 | 0 | 0 |
| `meeting-minutes` | 2 | 0 | 7 |
| `news-article` | 1 | 0 | 1 |
| `privacy-policy` | 1 | 0 | 4 |
| `scientific-paper` | 0 | 0 | 5 |
| `scotus-opinion` | 0 | 0 | 5 |
| `support-ticket` | 2 | 0 | 0 |
| `tech-spec` | 6 | 0 | 6 |
| `wikipedia-article` | 1 | 0 | 3 |

### `outline`

| corpus | TP | FP | FN |
|---|---|---|---|
| `crm-note-long` | 6 | 0 | 0 |
| `crm-note-short` | 0 | 0 | 0 |
| `meeting-minutes` | 0 | 0 | 2 |
| `news-article` | 0 | 0 | 0 |
| `privacy-policy` | 0 | 0 | 8 |
| `scientific-paper` | 0 | 0 | 6 |
| `scotus-opinion` | 0 | 0 | 2 |
| `support-ticket` | 3 | 0 | 3 |
| `tech-spec` | 7 | 0 | 0 |
| `wikipedia-article` | 0 | 0 | 4 |

### `metadata`

| corpus | TP | FP | FN |
|---|---|---|---|
| `crm-note-long` | 1 | 0 | 0 |
| `crm-note-short` | 2 | 0 | 0 |
| `meeting-minutes` | 1 | 0 | 0 |
| `news-article` | 0 | 0 | 0 |
| `privacy-policy` | 1 | 0 | 0 |
| `scientific-paper` | 0 | 0 | 0 |
| `scotus-opinion` | 0 | 0 | 0 |
| `support-ticket` | 0 | 0 | 0 |
| `tech-spec` | 0 | 0 | 0 |
| `wikipedia-article` | 0 | 0 | 0 |

### `phrases`

| corpus | TP | FP | FN |
|---|---|---|---|
| `crm-note-long` | 2 | 0 | 7 |
| `crm-note-short` | 0 | 0 | 9 |
| `meeting-minutes` | 3 | 1 | 8 |
| `news-article` | 0 | 0 | 10 |
| `privacy-policy` | 7 | 1 | 3 |
| `scientific-paper` | 9 | 14 | 7 |
| `scotus-opinion` | 12 | 2 | 3 |
| `support-ticket` | 10 | 9 | 3 |
| `tech-spec` | 3 | 0 | 7 |
| `wikipedia-article` | 5 | 4 | 7 |

### `correlate`

| corpus | TP | FP | FN |
|---|---|---|---|
| `crm-note-long` | 0 | 0 | 0 |
| `crm-note-short` | 0 | 1 | 0 |
| `meeting-minutes` | 0 | 0 | 4 |
| `news-article` | 0 | 0 | 0 |
| `privacy-policy` | 0 | 0 | 1 |
| `scientific-paper` | 0 | 0 | 1 |
| `scotus-opinion` | 0 | 0 | 4 |
| `support-ticket` | 0 | 0 | 1 |
| `tech-spec` | 1 | 1 | 1 |
| `wikipedia-article` | 0 | 0 | 1 |

