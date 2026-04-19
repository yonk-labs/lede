# Resume: skimr Python v0.1

**Last session:** 2026-04-19. Stopped after T4 at commit `643bfbe`.

## Where we are

Plan: `docs/superpowers/plans/2026-04-19-skimr-python-v01.md` (15 tasks).
Mission brief: `skill-output/mission-brief/Mission-Brief-skimr.md`.

**Done (4/15):**

| # | Task | SHA(s) |
|---|---|---|
| T1 | Package skeleton | `8ad835e` |
| T2 | Sentence splitter | `5d7ef1f` + `0c734bc` (NUL fix) |
| T3 | `strip_think` | `f319f33` |
| T4 | `clean_text` port + crm-boilerplate fixture | `643bfbe` |

**Pending (11/15):**
T5 TF-IDF scorer · T6 Greedy selector · T7 Keyword extractor · T8 Fixture walker test · T9 CLI · T10 Determinism test · T11 Zero-dep check · T12 TextRank (**DC-003 gate**) · T13 CI YAML · T14 README · T15 **DC-001 gate** + tag v0.0.1.

**Test suite:** 23 passing (9 sentences + 14 clean).

## Execution cadence from last session

Option 2 from that session's plan: subagent-driven for the tasks with real algorithmic judgment; inline for mechanical ones.

- **Subagent-driven:** T5, T6, T7, T8, T9, T12
- **Inline:** T10, T11, T13, T14, T15

## Carry-forward concerns

1. **`__init__.py` currently `except ImportError`** (broadened from `ModuleNotFoundError` in T3 to handle not-yet-defined names). **Task 7 must remove the whole try/except** once `clean.py`, `tfidf.py`, `keyword.py` all export their full public surface. Comment in `src/skimr/__init__.py:13-17` flags this.

2. **`fixtures/clean_text/crm-boilerplate/expected.txt` preserves two SQL quirks:**
   - Stray `.` from "Calendar invite sent." and "Updated CRM with latest info." — the regex `\.?\b` can't boundary-match after a period, so the non-period branch wins and the trailing `.` survives.
   - `, the customer...` — leading comma remains after "Basically" was stripped.
   - Both are faithful to `extractive_functions.sql`. Do not "fix" these in the port without simultaneously fixing the SQL.

3. **Deferred from T2 code review** (not blockers, pin when fixtures demand):
   - `Acme Co. Shares soared.` under-splits (Co. treated as abbrev)
   - Digit-after-period doesn't split (`It was 2023. 2024 was better.`) — spec-strict per SUMMARIZATION.md
   - Dotted-abbreviation regex has overreach complexity; decouple eventually

4. **Python 3.13 in use**, but pyproject classifiers only list 3.10–3.12. Sync before CI (T13) or v0.2 publish.

5. **venv uses `uv`, no `pip`** in it. Use `.venv/bin/python -m pytest ...` directly. If installing, use `uv pip install ...` via `/home/yonk/.local/bin/uv`.

## Resume prompt (paste into a fresh session)

> Working directory: `/home/yonk/yonk-tools/extractive_summary`. Resume skimr Plan 1 at Task 5. Read `docs/RESUME.md` first for state. Plan: `docs/superpowers/plans/2026-04-19-skimr-python-v01.md`. Mission brief: `skill-output/mission-brief/Mission-Brief-skimr.md`. Use subagent-driven for T5, T6, T7, T8, T9, T12; inline for T10, T11, T13, T14, T15. DC-003 is a hard gate at end of T12; DC-001 is a hard gate in T15.

## Handy one-liners

```bash
cd /home/yonk/yonk-tools/extractive_summary
.venv/bin/python -m pytest                    # run all tests
git log --oneline                             # see commit progress
```
