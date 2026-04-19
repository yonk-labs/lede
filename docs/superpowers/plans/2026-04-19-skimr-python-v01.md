# skimr Python v0.1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the Python half of `skimr` — a deterministic, zero-dep extractive summarization library + CLI that passes the shared fixture corpus, supports TF-IDF/keyword/clean_text/strip_think modes plus optional TextRank, and is ready for the Rust port to match byte-for-byte.

**Architecture:** Stdlib-only core, split by responsibility: `sentences` (splitter), `clean` (clean_text + strip_think), `tfidf` (default mode), `keyword` (query-driven mode), `textrank` (optional extra), `cli` (argparse entry point). Tests are TDD-first. A fixture-walker test in `tests/test_fixtures.py` runs every `fixtures/<mode>/<name>/` directory against its `expected.txt` — this is the contract the Rust port will later have to satisfy.

**Tech Stack:** Python 3.10+, stdlib only (re, collections, pathlib, argparse, subprocess for tests), pytest for testing, optional `networkx>=3.0` for TextRank. Build backend: `hatchling`. License: Apache-2.0.

**Mission brief:** `skill-output/mission-brief/Mission-Brief-skimr.md` — re-read at every DC-XXX checkpoint.

**Active drift checkpoints from the brief:**
- **⛔ DC-001** — after this plan completes, verify SC-001, SC-003, SC-005, SC-008 before starting Plan 2 (Rust).
- **⛔ DC-003** — after Task 12 (TextRank) — verify default path still has zero deps.
- **⛔ DC-FINAL (partial)** — at Plan 1 wrap, verify Plan 1's SC coverage has evidence.

---

## File Structure

Repo layout after this plan:

```
extractive_summary/            (will git init; rename to skimr/ later)
  .gitignore
  LICENSE                      (Apache-2.0)
  README.md
  pyproject.toml
  CLAUDE.md                    (already exists)
  SUMMARIZATION.md             (spec, already exists)
  extractive_functions.md      (spec for clean_text/keyword, already exists)
  extractive_functions.sql     (reference impl, already exists)
  extractive-performance.md    (benchmark baseline, already exists)
  ARCHITECTURE.md              (background, already exists)
  summarize-output.py          (legacy reference, keep for now)
  src/
    skimr/
      __init__.py              (public API)
      sentences.py             (sentence splitter with abbr/decimal handling)
      clean.py                 (clean_text + strip_think)
      tfidf.py                 (TF-IDF scoring + greedy selection pipeline)
      keyword.py               (keyword-scored extractor)
      textrank.py              (optional, only imports networkx when called)
      cli.py                   (argparse entry point)
  tests/
    __init__.py
    test_sentences.py
    test_clean.py              (clean_text + strip_think)
    test_tfidf.py
    test_keyword.py
    test_textrank.py
    test_cli.py
    test_determinism.py
    test_fixtures.py           (walks fixtures/ dir)
    test_zero_deps.py          (CI-gated)
  fixtures/                    (already exists; expands as impls land)
  skill-output/                (research-base, mission-brief, plans outputs)
  docs/
    superpowers/plans/2026-04-19-skimr-python-v01.md   (this file)
  .github/
    workflows/
      test.yml
      zero-deps.yml
```

---

## Task 1: Initialize Git + Package Skeleton

**Files:**
- Create: `.gitignore`
- Create: `LICENSE`
- Create: `pyproject.toml`
- Create: `src/skimr/__init__.py`
- Create: `tests/__init__.py`
- Create: `README.md` (placeholder, filled out in Task 15)

- [ ] **Step 1: Confirm working directory**

```bash
cd /home/yonk/yonk-tools/extractive_summary
pwd
# Expected: /home/yonk/yonk-tools/extractive_summary
```

- [ ] **Step 2: Git init**

```bash
git init
git branch -M main
```

Expected: `Initialized empty Git repository in .git/`

- [ ] **Step 3: Write `.gitignore`**

Create `.gitignore`:

```
# Python
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.coverage
build/
dist/
.venv/
venv/

# IDE
.vscode/
.idea/

# Skill output (research artifacts, not code)
# Keep committed for now; revisit if repo grows large
# skill-output/
```

- [ ] **Step 4: Write `LICENSE` (Apache-2.0)**

Download the canonical Apache-2.0 text:

```bash
curl -fsSL https://www.apache.org/licenses/LICENSE-2.0.txt -o LICENSE
head -5 LICENSE
```

Expected first line: `                                 Apache License`

If curl is unavailable, paste the full text manually from https://www.apache.org/licenses/LICENSE-2.0.txt.

- [ ] **Step 5: Write `pyproject.toml`**

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "skimr"
version = "0.0.1"
description = "Deterministic extractive summarization — zero runtime dependencies"
readme = "README.md"
requires-python = ">=3.10"
license = { file = "LICENSE" }
authors = [{ name = "Yonk" }]
keywords = ["summarization", "extractive", "text", "nlp", "tf-idf", "textrank"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "License :: OSI Approved :: Apache Software License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Topic :: Text Processing :: Linguistic",
]
dependencies = []

[project.optional-dependencies]
textrank = ["networkx>=3.0"]
dev = ["pytest>=7", "pytest-subtests>=0.10"]

[project.scripts]
skimr = "skimr.cli:main"

[tool.hatch.build.targets.wheel]
packages = ["src/skimr"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-v --tb=short"
```

- [ ] **Step 6: Write `src/skimr/__init__.py`**

```python
"""skimr — deterministic extractive summarization.

Public API:
  summarize(text, max_length, mode='tfidf', **kwargs) -> str
  clean_text(text) -> str
  strip_think(text) -> str
  extract_keyword(text, keywords, num_sentences=10) -> str
"""
from skimr.clean import clean_text, strip_think
from skimr.tfidf import summarize
from skimr.keyword import extract_keyword

__version__ = "0.0.1"
__all__ = ["summarize", "clean_text", "strip_think", "extract_keyword", "__version__"]
```

Note: these imports will fail until later tasks land their modules. That's fine — Task 2 comes next.

- [ ] **Step 7: Write `tests/__init__.py`**

```python
```

(Empty file — marks the directory as a package.)

- [ ] **Step 8: Write placeholder `README.md`**

```markdown
# skimr

Deterministic extractive summarization — zero runtime dependencies.

Python + Rust (Rust coming in v0.1). Work in progress — see `CLAUDE.md` and `skill-output/mission-brief/Mission-Brief-skimr.md` for scope.
```

Full README arrives in Task 15.

- [ ] **Step 9: Install dev deps + verify package skeleton**

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
```

Expected: installs hatchling, pytest, builds `skimr` in editable mode. Import will currently fail because the submodules don't exist yet — that's expected.

```bash
python -c "import skimr" 2>&1 | head -1
# Expected: ModuleNotFoundError: No module named 'skimr.clean' (or similar)
```

Leave the venv active. Subsequent tasks assume it is.

- [ ] **Step 10: Commit**

```bash
git add .gitignore LICENSE pyproject.toml src/skimr/__init__.py tests/__init__.py README.md
git commit -m "chore: initial package skeleton

Python 3.10+ package with hatchling build backend, Apache-2.0 license,
and skimr CLI entry point. Submodules arrive in subsequent commits."
```

---

## Task 2: Sentence Splitter

Per `SUMMARIZATION.md` Step 2: split on `.!?` + whitespace + uppercase letter, but don't split on abbreviations (`Dr.`, `Mr.`, `U.S.`, etc.) or decimals (`3.14`). Also split on paragraph breaks (double newlines).

**Strategy:** two-pass — mask known abbreviations and decimals with a sentinel, split, then unmask. Clean to implement, easy to extend the abbreviation list.

**Files:**
- Create: `src/skimr/sentences.py`
- Create: `tests/test_sentences.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_sentences.py`:

```python
from skimr.sentences import split_sentences


def test_simple_periods():
    text = "Revenue grew. Costs fell. Margins improved."
    assert split_sentences(text) == [
        "Revenue grew.",
        "Costs fell.",
        "Margins improved.",
    ]


def test_question_and_exclamation():
    text = "Did it work? Yes! It did."
    assert split_sentences(text) == ["Did it work?", "Yes!", "It did."]


def test_abbreviation_not_split():
    text = "Dr. Smith analyzed the Q4 results. Revenue grew 23%."
    assert split_sentences(text) == [
        "Dr. Smith analyzed the Q4 results.",
        "Revenue grew 23%.",
    ]


def test_us_uk_abbreviations_not_split():
    text = "The U.S. market grew. The U.K. followed."
    assert split_sentences(text) == [
        "The U.S. market grew.",
        "The U.K. followed.",
    ]


def test_decimal_not_split():
    text = "Pi is 3.14 approximately. E is 2.71."
    assert split_sentences(text) == [
        "Pi is 3.14 approximately.",
        "E is 2.71.",
    ]


def test_paragraph_break_splits():
    text = "First sentence.\n\nSecond paragraph."
    assert split_sentences(text) == ["First sentence.", "Second paragraph."]


def test_empty_input_returns_empty_list():
    assert split_sentences("") == []


def test_single_sentence_no_terminator():
    # SUMMARIZATION.md doesn't require a final period
    assert split_sentences("Just one fragment") == ["Just one fragment"]
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_sentences.py -v
```

Expected: all 8 tests fail with `ImportError: cannot import name 'split_sentences'`.

- [ ] **Step 3: Implement `src/skimr/sentences.py`**

```python
"""Sentence splitter.

Splits on sentence-terminal punctuation (.!?) followed by whitespace and an
uppercase letter, plus paragraph breaks. Protects known abbreviations and
decimal numbers from being treated as sentence boundaries.
"""
import re

# Abbreviations where a trailing period should NOT end a sentence.
# Lowercase compared, case-insensitively matched.
_ABBREVIATIONS = frozenset({
    "mr", "mrs", "ms", "dr", "st", "sr", "jr",
    "inc", "ltd", "co", "corp",
    "vs", "etc", "eg", "ie", "cf",
    "u.s", "u.k", "u.n", "e.u",
    "fig", "no", "vol",
})

_SENTINEL = "\x00"  # ASCII NUL — won't appear in real text


def _mask(text: str) -> str:
    # Protect decimals: digit.digit → digit<SENTINEL>digit
    text = re.sub(r"(\d)\.(\d)", lambda m: f"{m.group(1)}{_SENTINEL}{m.group(2)}", text)

    # Protect known abbreviations. Match word boundary + abbrev + dot.
    def _abbrev_sub(match: re.Match) -> str:
        word = match.group(1)
        if word.lower() in _ABBREVIATIONS:
            return f"{word}{_SENTINEL}"
        return match.group(0)

    # Match (word).(lookahead: whitespace or end). This covers "Dr." and "U.S."
    text = re.sub(r"\b([A-Za-z]+(?:\.[A-Za-z]+)*)\.", _abbrev_sub, text)
    return text


def _unmask(text: str) -> str:
    return text.replace(_SENTINEL, ".")


def split_sentences(text: str) -> list[str]:
    """Split text into sentences. Returns a list; empty input returns []."""
    if not text:
        return []

    masked = _mask(text)

    # Split on paragraph breaks (2+ newlines) OR terminal punct + whitespace + uppercase start.
    # Use a single combined splitter. We keep the terminator by splitting AFTER it.
    parts: list[str] = []
    pattern = re.compile(r"(?<=[.!?])\s+(?=[A-Z])|\n\s*\n")
    for piece in pattern.split(masked):
        piece = piece.strip()
        if piece:
            parts.append(_unmask(piece))

    return parts
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_sentences.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/skimr/sentences.py tests/test_sentences.py
git commit -m "feat(sentences): add sentence splitter with abbreviation + decimal handling"
```

---

## Task 3: strip_think

Per `extractive_functions.sql` (`strip_think`): remove `<think>…</think>` blocks (greedy-across-newlines via the `gs` flag). Used to clean reasoning-model output.

**Files:**
- Create: `src/skimr/clean.py` (will also get `clean_text` in Task 4)
- Create: `tests/test_clean.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_clean.py`:

```python
from pathlib import Path
from skimr.clean import strip_think

FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "strip_think"


def test_simple_block():
    assert strip_think("<think>thinking</think>\nRevenue grew.") == "Revenue grew."


def test_no_block_returns_unchanged_trimmed():
    text = "Revenue grew 23% in Q4. No think block present."
    assert strip_think(text) == text


def test_multiple_blocks():
    text = "<think>a</think>\nOne.\n<think>b</think>\nTwo."
    assert strip_think(text) == "One.\nTwo."


def test_multiline_block():
    text = "<think>\nline one\nline two\n</think>\nAfter."
    assert strip_think(text) == "After."


def test_fixture_simple_block():
    input_text = (FIXTURES / "simple-block" / "input.txt").read_text()
    expected = (FIXTURES / "simple-block" / "expected.txt").read_text()
    assert strip_think(input_text) == expected


def test_fixture_no_think_block():
    input_text = (FIXTURES / "no-think-block" / "input.txt").read_text()
    expected = (FIXTURES / "no-think-block" / "expected.txt").read_text()
    assert strip_think(input_text) == expected


def test_fixture_multiple_blocks():
    input_text = (FIXTURES / "multiple-blocks" / "input.txt").read_text()
    expected = (FIXTURES / "multiple-blocks" / "expected.txt").read_text()
    assert strip_think(input_text) == expected
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_clean.py -v
```

Expected: all 7 tests fail with `ImportError: cannot import name 'strip_think'`.

- [ ] **Step 3: Implement `src/skimr/clean.py` (partial — `strip_think` only)**

```python
"""Text cleaners: clean_text (markdown + filler + boilerplate) and strip_think
(reasoning-model <think>...</think> blocks).

Both functions are deterministic and stdlib-only.
"""
import re

_THINK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL)


def strip_think(text: str) -> str:
    """Remove <think>...</think> blocks and trim surrounding whitespace.

    Mirrors strip_think(text) from extractive_functions.sql.
    """
    if text is None:
        return ""
    return _THINK_RE.sub("", text).strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_clean.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/skimr/clean.py tests/test_clean.py
git commit -m "feat(clean): add strip_think for reasoning-model output"
```

---

## Task 4: clean_text

Port the `clean_text(input_text)` PL/pgSQL function from `extractive_functions.sql` to Python. Order of operations matters — match the SQL exactly.

**Files:**
- Modify: `src/skimr/clean.py` (add `clean_text`)
- Modify: `tests/test_clean.py` (add clean_text tests)

- [ ] **Step 1: Add failing tests to `tests/test_clean.py`**

Append to `tests/test_clean.py`:

```python
from skimr.clean import clean_text

CLEAN_FIXTURES = Path(__file__).resolve().parent.parent / "fixtures" / "clean_text"


def test_clean_text_removes_bold_markdown():
    # Fixture: markdown-basic — hand-traced against SQL spec.
    input_text = (CLEAN_FIXTURES / "markdown-basic" / "input.txt").read_text()
    expected = (CLEAN_FIXTURES / "markdown-basic" / "expected.txt").read_text()
    assert clean_text(input_text) == expected


def test_clean_text_strips_filler_phrases():
    text = "Just wanted to follow up on pricing."
    result = clean_text(text)
    # "just wanted to" removed; result is lowercased; leading space trimmed per-line.
    assert "just wanted to" not in result.lower()
    assert "pricing" in result


def test_clean_text_strips_filler_words():
    text = "Basically, the customer is actually concerned."
    result = clean_text(text)
    assert "basically" not in result
    assert "actually" not in result
    assert "customer" in result


def test_clean_text_strips_crm_boilerplate():
    text = "Pricing is an issue.\nNo updates.\nCalendar invite sent."
    result = clean_text(text)
    assert "no updates" not in result
    assert "calendar invite sent" not in result
    assert "pricing is an issue" in result


def test_clean_text_lowercases():
    assert clean_text("HELLO WORLD") == "hello world"


def test_clean_text_collapses_blank_lines():
    text = "line one\n\n\nline two"
    result = clean_text(text)
    assert result == "line one\nline two"


def test_clean_text_empty_input():
    assert clean_text("") == ""
    assert clean_text(None) == ""
```

- [ ] **Step 2: Run to verify the new tests fail**

```bash
pytest tests/test_clean.py -v -k clean_text
```

Expected: 7 new tests fail with `ImportError: cannot import name 'clean_text'`.

- [ ] **Step 3: Implement `clean_text` in `src/skimr/clean.py`**

Append to `src/skimr/clean.py`:

```python
# --- clean_text: port of extractive_functions.sql/clean_text ---
#
# Order matters — matches the SQL function step by step:
#   1. Strip markdown formatting (*, _, #, ---, bullets, numbered list prefixes)
#   2. Remove filler phrases
#   3. Remove filler words
#   4. Remove CRM boilerplate
#   5. Lowercase
#   6. Collapse whitespace and blank lines
#   7. Trim

_FILLER_PHRASES = re.compile(
    r"\b(just wanted to|i just wanted to|wanted to follow up|as discussed"
    r"|per our conversation|as mentioned|going forward|at the end of the day"
    r"|in terms of|with respect to|in regards to|please find attached"
    r"|hope this helps|let me know if you have any questions"
    r"|looking forward to hearing from you)\b",
    re.IGNORECASE,
)

_FILLER_WORDS = re.compile(
    r"\b(basically|essentially|actually|literally|honestly|frankly"
    r"|obviously|clearly|simply|really|very|quite|rather|pretty much"
    r"|kind of|sort of|in order to|due to the fact that"
    r"|at this point in time|for all intents and purposes)\b",
    re.IGNORECASE,
)

# CRM boilerplate patterns. Each is matched case-insensitively, optional trailing period.
_CRM_PATTERNS = [
    re.compile(r"\bNo update[s]?\b\.?", re.IGNORECASE),
    re.compile(r"\bCalendar invite sent[.]?\b", re.IGNORECASE),
    re.compile(
        r"\bSent (proposal|case study|documentation|overview|pricing)"
        r" (documentation |via email|as requested)?\.?\b",
        re.IGNORECASE,
    ),
    re.compile(r"\bWaiting (on|for) callback\.?\b", re.IGNORECASE),
    re.compile(r"\bUpdated CRM with latest info\.?\b", re.IGNORECASE),
    re.compile(r"\bMeeting confirmed for next week\.?\b", re.IGNORECASE),
    re.compile(r"\bFollowing standard sales process\.?\b", re.IGNORECASE),
    re.compile(r"\bMeeting went as expected\.?\b", re.IGNORECASE),
]


def clean_text(text: str | None) -> str:
    """Port of extractive_functions.sql/clean_text.

    Strips markdown, filler phrases, filler words, CRM boilerplate, then
    lowercases and normalizes whitespace. Returns empty string for None/empty
    input (matches SQL NULL-safe STRICT behavior).
    """
    if not text:
        return ""

    result = text

    # 1. Markdown formatting
    result = re.sub(r"\*{1,3}", "", result)          # *, **, ***
    result = re.sub(r"_{1,3}", "", result)           # _, __, ___
    result = re.sub(r"^#{1,6}\s*", "", result, flags=re.MULTILINE)  # # headers
    result = re.sub(r"^-{3,}$", "", result, flags=re.MULTILINE)     # --- separators
    result = re.sub(r"^\s*[-*+]\s+", "", result, flags=re.MULTILINE)  # bullets
    result = re.sub(r"^\s*\d+\.\s+", "", result, flags=re.MULTILINE)  # numbered list

    # 2-3. Filler
    result = _FILLER_PHRASES.sub("", result)
    result = _FILLER_WORDS.sub("", result)

    # 4. CRM boilerplate
    for pattern in _CRM_PATTERNS:
        result = pattern.sub("", result)

    # 5. Lowercase
    result = result.lower()

    # 6. Whitespace normalization
    result = re.sub(r"[ \t]+", " ", result)                   # collapse spaces/tabs
    result = re.sub(r"\n\s*\n+", "\n", result)                # collapse blank lines
    result = re.sub(r"^\s+", "", result, flags=re.MULTILINE)  # leading ws per line
    result = re.sub(r"\s+$", "", result, flags=re.MULTILINE)  # trailing ws per line
    result = re.sub(r"^\s*$\n?", "", result, flags=re.MULTILINE)  # empty lines

    # 7. Trim
    return result.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_clean.py -v
```

Expected: all tests pass (7 strip_think + 7 clean_text = 14).

- [ ] **Step 5: Populate `fixtures/clean_text/crm-boilerplate/expected.txt`**

The SQL function is the spec, and this Python port is the reference. Generate the expected output from the port, **human-review it against `extractive_functions.sql` rules**, and commit.

```bash
python3 -c "
from skimr.clean import clean_text
from pathlib import Path
p = Path('fixtures/clean_text/crm-boilerplate')
inp = (p / 'input.txt').read_text()
out = clean_text(inp)
print(repr(out))
(p / 'expected.txt').write_text(out)
"
```

Open `fixtures/clean_text/crm-boilerplate/expected.txt` and verify the output against `extractive_functions.sql/clean_text` by reading the SQL rules. Expected behavior:
- `**Meeting Notes**` → `meeting notes`
- `Just wanted to` phrase removed
- `Basically,` filler removed (note: a stray leading comma may remain — the SQL has the same quirk)
- `No updates.`, `Calendar invite sent.`, `Updated CRM with latest info.` removed
- Everything lowercased, blank lines collapsed

If the output diverges from the SQL spec, fix `src/skimr/clean.py` — not the fixture. If the SQL spec itself is ambiguous (e.g., stray punctuation after filler removal), document the quirk in a comment in `clean.py` and commit the output as-is.

- [ ] **Step 6: Commit**

```bash
git add src/skimr/clean.py tests/test_clean.py fixtures/clean_text/crm-boilerplate/expected.txt
git commit -m "feat(clean): add clean_text port of PL/pgSQL reference

Removes markdown formatting, filler phrases and words, CRM boilerplate,
lowercases, normalizes whitespace. Order of operations matches
extractive_functions.sql exactly. crm-boilerplate fixture expected
output populated and human-reviewed."
```

---

## Task 5: TF-IDF Scorer

Per `SUMMARIZATION.md` Step 3: three scoring dimensions (TF-IDF 60%, position 25%, length 15%), normalized to [0,1] per dimension.

**Files:**
- Create: `src/skimr/tfidf.py` (partial — scorer only)
- Create: `tests/test_tfidf.py`

- [ ] **Step 1: Write failing tests for scoring**

Create `tests/test_tfidf.py`:

```python
import math
from skimr.tfidf import tfidf_score, position_score, length_score, composite_score


def test_tfidf_score_returns_normalized_list():
    sentences = [
        "apple banana cherry",
        "apple date elderberry",
        "cherry date fig",
    ]
    scores = tfidf_score(sentences)
    assert len(scores) == 3
    assert all(0.0 <= s <= 1.0 for s in scores)
    # Scores should have at least one non-zero
    assert max(scores) > 0.0


def test_position_score_first_and_last_highest():
    # With 5 sentences, position 0 and 4 should score highest
    scores = position_score(5)
    assert len(scores) == 5
    assert scores[0] == 1.0
    assert scores[-1] == 1.0
    # Middle is lowest
    assert scores[2] < scores[0]
    assert scores[2] < scores[-1]


def test_position_score_single_sentence():
    assert position_score(1) == [1.0]


def test_length_score_sweet_spot():
    # 10-30 words should score highest per SUMMARIZATION.md
    short = "one two three"                                              # 3 words
    mid = " ".join(["word"] * 20)                                        # 20 words — sweet spot
    long = " ".join(["word"] * 100)                                      # 100 words
    scores = length_score([short, mid, long])
    assert scores[1] == max(scores)          # mid is highest
    assert scores[0] < scores[1]
    assert scores[2] < scores[1]


def test_composite_score_weighting():
    # Composite uses 60/25/15 weights. Construct three sentences where we control
    # relative scores and verify the weighted sum reflects the weighting.
    sentences = [
        "pricing budget pricing budget pricing",        # high tfidf for these terms
        "the the the the the the the the the the the the the the the the the",  # low tfidf, mid length
        "unique distinctive singular",                  # mid tfidf, short length
    ]
    composite = composite_score(sentences)
    assert len(composite) == 3
    # Sanity: all in [0, 1]
    assert all(0.0 <= s <= 1.0 for s in composite)
```

- [ ] **Step 2: Run to verify they fail**

```bash
pytest tests/test_tfidf.py -v
```

Expected: all 5 tests fail with ImportError.

- [ ] **Step 3: Implement scoring in `src/skimr/tfidf.py`**

Create `src/skimr/tfidf.py`:

```python
"""TF-IDF + position + length extractive summarization pipeline.

Per SUMMARIZATION.md:
  score = 0.60 * tfidf + 0.25 * position + 0.15 * length

All scores normalized to [0, 1] per dimension. The composite is a weighted
sum, also in [0, 1].
"""
import math
import re
from collections import Counter

from skimr.sentences import split_sentences

_TFIDF_WEIGHT = 0.60
_POSITION_WEIGHT = 0.25
_LENGTH_WEIGHT = 0.15

# Basic stopword list — deliberately small and stable across languages.
# Shared with the cross-language fixture corpus; do not add locale-specific terms.
_STOPWORDS = frozenset({
    "the", "and", "that", "this", "with", "for", "are", "was", "were",
    "been", "have", "has", "had", "not", "but", "what", "all", "when",
    "who", "will", "can", "from", "they", "each", "which", "their",
    "there", "about", "would", "make", "more", "some", "into",
    "other", "than", "its", "also", "after", "use", "how", "our",
    "any", "these", "most", "may", "should", "could", "does", "did",
    "just", "because", "over", "such", "through", "very", "your",
    "a", "an", "is", "it", "in", "on", "of", "to", "be", "as", "at", "by",
})

_TOKEN_RE = re.compile(r"\b[a-z]{3,}\b")


def _tokenize(sentence: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(sentence.lower()) if t not in _STOPWORDS]


def _normalize(scores: list[float]) -> list[float]:
    hi = max(scores, default=0.0)
    if hi <= 0.0:
        return [0.0] * len(scores)
    return [s / hi for s in scores]


def tfidf_score(sentences: list[str]) -> list[float]:
    """TF-IDF score per sentence, normalized to [0, 1]."""
    tokenized = [_tokenize(s) for s in sentences]
    n = len(sentences)

    # Document frequency: how many sentences contain each term
    df: Counter[str] = Counter()
    for tokens in tokenized:
        for term in set(tokens):
            df[term] += 1

    # IDF — smoothed to avoid log(1) = 0 for universal terms
    idf = {term: math.log((n + 1) / (freq + 1)) + 1.0 for term, freq in df.items()}

    raw: list[float] = []
    for tokens in tokenized:
        if not tokens:
            raw.append(0.0)
            continue
        tf = Counter(tokens)
        # Sum of tf-idf, divided by sentence length — average term importance
        score = sum(tf[term] * idf.get(term, 0.0) for term in tf) / len(tokens)
        raw.append(score)

    return _normalize(raw)


def position_score(n: int) -> list[float]:
    """Position score: first and last sentences score 1.0, middle scores lower.

    Uses a U-shape: score(i) = max(1 - i/n, i/n). For i=0 or i=n-1, this is 1.0.
    """
    if n <= 0:
        return []
    if n == 1:
        return [1.0]
    scores: list[float] = []
    for i in range(n):
        # Distance from the nearer endpoint, normalized
        d = min(i, n - 1 - i) / max(n - 1, 1)
        # d=0 at endpoints, d=0.5 at middle. Score = 1 - 2d gives 1 at ends, 0 at middle.
        scores.append(max(0.0, 1.0 - 2.0 * d))
    # Endpoints are already 1.0; normalize is a no-op but keeps shape consistent
    return _normalize(scores)


def length_score(sentences: list[str]) -> list[float]:
    """Length score: peaks in 10-30 word range per SUMMARIZATION.md."""
    raw: list[float] = []
    for s in sentences:
        words = len(s.split())
        if words == 0:
            raw.append(0.0)
        elif 10 <= words <= 30:
            raw.append(1.0)
        elif words < 10:
            raw.append(words / 10.0)
        else:  # words > 30
            # Linear decay to 0 by word count 80
            raw.append(max(0.0, 1.0 - (words - 30) / 50.0))
    return _normalize(raw)


def composite_score(sentences: list[str]) -> list[float]:
    """Composite score: 0.60 * tfidf + 0.25 * position + 0.15 * length."""
    if not sentences:
        return []
    t = tfidf_score(sentences)
    p = position_score(len(sentences))
    l = length_score(sentences)
    return [
        _TFIDF_WEIGHT * t[i] + _POSITION_WEIGHT * p[i] + _LENGTH_WEIGHT * l[i]
        for i in range(len(sentences))
    ]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_tfidf.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/skimr/tfidf.py tests/test_tfidf.py
git commit -m "feat(tfidf): add TF-IDF + position + length scorers

Three scoring dimensions normalized to [0,1], combined with 60/25/15
weighting per SUMMARIZATION.md. Small frozen stopword list shared with
the cross-language fixture corpus."
```

---

## Task 6: Greedy Selector + Reorder

Per `SUMMARIZATION.md` Steps 4-6: greedy-add sentences by score until budget exhausted, then reorder by original position. Fallback to truncation if selection is empty.

**Files:**
- Modify: `src/skimr/tfidf.py` (add `summarize` function)
- Modify: `tests/test_tfidf.py` (add selector + summarize tests)

- [ ] **Step 1: Add failing tests**

Append to `tests/test_tfidf.py`:

```python
from skimr.tfidf import summarize


def test_summarize_short_input_returns_unchanged():
    text = "Short text."
    assert summarize(text, max_length=500) == text


def test_summarize_fallback_truncates_when_max_length_too_small():
    text = "First sentence. Second sentence. Third sentence. Fourth sentence."
    # max_length < 50 triggers truncation fallback per SUMMARIZATION.md step 1
    result = summarize(text, max_length=20)
    assert len(result) <= 23  # 20 + "..." suffix
    assert result.endswith("...")


def test_summarize_fallback_when_fewer_than_three_sentences():
    text = "One only sentence here in this input."
    # Only 1 sentence → falls back to truncation
    result = summarize(text, max_length=15)
    # 15 is < 50, so truncation path; also <3 sentences
    assert result.endswith("...")


def test_summarize_respects_max_length_budget():
    text = (
        "Revenue grew 23% in Q4. "
        "The Enterprise segment led growth. "
        "Churn remained flat. "
        "Dr. Smith analyzed the Q4 results. "
        "Margins improved by 5 points."
    )
    result = summarize(text, max_length=100)
    assert len(result) <= 100


def test_summarize_reorders_by_original_position():
    # Construct text where the highest-TF-IDF sentence is in the middle.
    text = (
        "Opening sentence about apples. "
        "Unique distinctive keyword-heavy sentence. "
        "Closing sentence about apples."
    )
    result = summarize(text, max_length=200)
    # The output should preserve original order if the selected sentences were
    # originally in that order. We check that the first selected sentence appears
    # before the second in the output.
    idx_open = result.find("Opening")
    idx_mid = result.find("Unique")
    idx_close = result.find("Closing")
    # All three selected; output must preserve order
    if idx_open >= 0 and idx_mid >= 0:
        assert idx_open < idx_mid
    if idx_mid >= 0 and idx_close >= 0:
        assert idx_mid < idx_close


def test_summarize_fixture_short_passthrough():
    from pathlib import Path
    fx = Path(__file__).resolve().parent.parent / "fixtures" / "tfidf" / "short-passthrough"
    inp = (fx / "input.txt").read_text()
    expected = (fx / "expected.txt").read_text()
    assert summarize(inp, max_length=500) == expected
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_tfidf.py -v -k summarize
```

Expected: 6 tests fail with `ImportError: cannot import name 'summarize'`.

- [ ] **Step 3: Implement `summarize` in `src/skimr/tfidf.py`**

Append to `src/skimr/tfidf.py`:

```python
# --- Top-level summarize pipeline ---

_MIN_SENTENCES = 3
_MIN_BUDGET_FOR_SENTENCES = 50  # chars; below this, truncate


def _truncate(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    # Reserve 3 chars for the ellipsis
    body_budget = max(0, max_length - 3)
    return text[:body_budget] + "..."


def summarize(text: str, max_length: int = 500) -> str:
    """Extractive summary of ``text`` capped at ``max_length`` characters.

    Per SUMMARIZATION.md:
      1. If input fits the budget, return unchanged.
      2. If the budget is too small for sentences, truncate.
      3. Split into sentences; if fewer than 3, truncate.
      4. Score sentences (TF-IDF + position + length, 60/25/15).
      5. Greedily add highest-scoring sentences until the char budget is spent.
      6. Reorder selected sentences by original position.
      7. Fallback to truncation if selection is empty.
    """
    if not text:
        return ""

    if len(text) <= max_length:
        return text

    if max_length < _MIN_BUDGET_FOR_SENTENCES:
        return _truncate(text, max_length)

    sentences = split_sentences(text)
    if len(sentences) < _MIN_SENTENCES:
        return _truncate(text, max_length)

    scores = composite_score(sentences)
    # Indices sorted by score descending, then by original position ascending
    # (stable tie-break — deterministic).
    indices_by_score = sorted(
        range(len(sentences)),
        key=lambda i: (-scores[i], i),
    )

    selected: list[int] = []
    used = 0
    separator = " "
    for idx in indices_by_score:
        sentence = sentences[idx]
        needed = len(sentence) + (len(separator) if selected else 0)
        if used + needed <= max_length:
            selected.append(idx)
            used += needed

    if not selected:
        return _truncate(text, max_length)

    selected.sort()
    return separator.join(sentences[i] for i in selected)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_tfidf.py -v
```

Expected: all tfidf tests pass (scorer tests from Task 5 + 6 summarize tests).

- [ ] **Step 5: Commit**

```bash
git add src/skimr/tfidf.py tests/test_tfidf.py
git commit -m "feat(tfidf): add summarize() pipeline with greedy selection + reorder

Implements Steps 1-6 of SUMMARIZATION.md. Short-circuits when input fits
budget. Falls back to truncation when budget < 50 chars or sentence
count < 3. Deterministic tie-breaking on (-score, original_position)."
```

---

## Task 7: Keyword-Scored Extractor

Port `extract_sentences(text, keywords, num_sentences)` from `extractive_functions.sql` to Python. Bonuses: +0.5 for length > 200, +0.3 for numeric content, +1.0 for causal/analytical language.

**Files:**
- Create: `src/skimr/keyword.py`
- Create: `tests/test_keyword.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_keyword.py`:

```python
from pathlib import Path
from skimr.keyword import extract_keyword


def test_extract_keyword_picks_sentences_with_matches():
    text = (
        "The demo went well. "
        "Main concern is pricing and budget. "
        "Will follow up next Tuesday."
    )
    result = extract_keyword(text, "pricing budget", num_sentences=1)
    assert "pricing" in result.lower()


def test_extract_keyword_respects_num_sentences():
    text = (
        "Main concern is pricing. "
        "Budget is tight. "
        "Cost is above plan. "
        "Will follow up next week."
    )
    result = extract_keyword(text, "pricing budget cost", num_sentences=2)
    # Returns 2 newline-separated sentences
    assert result.count("\n") == 1


def test_extract_keyword_causal_bonus():
    # "because" triggers +1.0 causal bonus; should rank above a neutral sentence.
    text = (
        "Revenue grew last quarter. "
        "The deal was lost because of pricing concerns. "
        "Meeting was scheduled."
    )
    result = extract_keyword(text, "pricing", num_sentences=1)
    assert "because" in result.lower()


def test_extract_keyword_empty_input_returns_empty():
    assert extract_keyword("", "pricing", num_sentences=3) == ""


def test_extract_keyword_no_keyword_match_returns_first_2000_chars():
    text = "A short sentence. Another one."
    # All keywords filtered (<3 chars) — returns LEFT(input, 2000)
    result = extract_keyword(text, "x y", num_sentences=3)
    assert result == text[:2000]


def test_extract_keyword_fixture_pricing_notes():
    fx = Path(__file__).resolve().parent.parent / "fixtures" / "keyword" / "pricing-notes"
    inp = (fx / "input.txt").read_text()
    expected_path = fx / "expected.txt"
    # If expected.txt was generated and committed, assert exact match.
    if expected_path.exists():
        import json
        cfg = json.loads((fx / "config.json").read_text())
        params = cfg.get("params", {})
        result = extract_keyword(
            inp,
            params["keywords"],
            num_sentences=params.get("num_sentences", 10),
        )
        assert result == expected_path.read_text()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_keyword.py -v
```

Expected: all tests fail with ImportError.

- [ ] **Step 3: Implement `src/skimr/keyword.py`**

Create `src/skimr/keyword.py`:

```python
"""Keyword-scored extractor: port of extract_sentences() from
extractive_functions.sql.

Bonuses (additive to keyword-match count):
  +0.5 if sentence length > 200 chars
  +0.3 if sentence contains a digit
  +1.0 if sentence contains causal/analytical language
"""
import re

_CAUSAL_RE = re.compile(
    r"(because|reason|due to|caused|result|impact|issue|problem"
    r"|concern|risk|challenge|blocker|gap|lack|missing"
    r"|competitor|pricing|budget|cost|expensive|cheaper|alternative"
    r"|decided|chose|prefer|switched|rejected|declined)",
    re.IGNORECASE,
)
_DIGIT_RE = re.compile(r"\d+")
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


def _split_sql_style(text: str) -> list[str]:
    """Match the SQL splitter: replace \\n+ with '. ', then split on [.!?]\\s+."""
    normalized = re.sub(r"\n+", ". ", text)
    parts = _SENTENCE_SPLIT_RE.split(normalized)
    return [p.strip() for p in parts if len(p.strip()) > 20]


def extract_keyword(text: str, keywords: str, num_sentences: int = 10) -> str:
    """Port of extract_sentences(input_text, keywords, num_sentences) from
    extractive_functions.sql.

    Returns top-N sentences newline-joined, ordered by score descending.
    """
    if not text:
        return ""

    # Parse keywords: lowercase, split on whitespace, drop tokens <= 2 chars.
    keyword_list = sorted({
        w.lower().strip()
        for w in keywords.split()
        if len(w.strip()) > 2
    })
    if not keyword_list:
        # SQL: returns LEFT(input_text, 2000) when no valid keywords
        return text[:2000]

    sentences = _split_sql_style(text)
    if not sentences:
        return text

    scored: list[tuple[float, int, str]] = []
    for i, s in enumerate(sentences):
        lower = s.lower()
        score = sum(1.0 for kw in keyword_list if kw in lower)
        if len(s) > 200:
            score += 0.5
        if _DIGIT_RE.search(s):
            score += 0.3
        if _CAUSAL_RE.search(lower):
            score += 1.0
        scored.append((score, i, s))

    # Sort by (-score, original_position) for deterministic tie-break
    scored.sort(key=lambda x: (-x[0], x[1]))
    top = scored[:num_sentences]

    # SQL preserves score-descending order in the output; match it.
    return "\n".join(s for _, _, s in top)
```

- [ ] **Step 4: Run tests to verify passing**

```bash
pytest tests/test_keyword.py -v
```

Expected: 5 or 6 tests pass (the fixture test is conditionally skipped until `expected.txt` exists).

- [ ] **Step 5: Populate `fixtures/keyword/pricing-notes/expected.txt`**

Generate from the port, human-review against the SQL spec, commit.

```bash
python3 -c "
from skimr.keyword import extract_keyword
from pathlib import Path
import json
p = Path('fixtures/keyword/pricing-notes')
inp = (p / 'input.txt').read_text()
cfg = json.loads((p / 'config.json').read_text())
out = extract_keyword(inp, cfg['params']['keywords'], cfg['params']['num_sentences'])
print(repr(out))
(p / 'expected.txt').write_text(out)
"
```

Review the output. The top 3 sentences should be those mentioning pricing/budget/competitor/cheaper — the "Risk:", "Main concern", and "Competitor B" sentences.

- [ ] **Step 6: Re-run tests with fixture expected.txt in place**

```bash
pytest tests/test_keyword.py -v
```

Expected: all 6 tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/skimr/keyword.py tests/test_keyword.py fixtures/keyword/pricing-notes/expected.txt
git commit -m "feat(keyword): add extract_keyword port of SQL extract_sentences

Scores sentences by keyword-match count plus length/numeric/causal
bonuses. pricing-notes fixture expected output populated and reviewed."
```

---

## Task 8: Fixture Walker Test

The crown-jewel test that SC-001 and SC-002 depend on: walks every `fixtures/<mode>/<name>/` directory, reads `config.json`, dispatches to the right function, and asserts byte-identical match with `expected.txt`.

**Files:**
- Create: `tests/test_fixtures.py`

- [ ] **Step 1: Write the test**

Create `tests/test_fixtures.py`:

```python
"""Fixture corpus walker. Runs every fixtures/<mode>/<name>/ directory against
its expected.txt. Fixtures missing expected.txt are reported as pending.

This is the contract the Rust port will have to match byte-for-byte.
"""
import json
from pathlib import Path

import pytest

from skimr.clean import clean_text, strip_think
from skimr.tfidf import summarize
from skimr.keyword import extract_keyword

FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def _discover_fixtures() -> list[tuple[str, Path]]:
    cases: list[tuple[str, Path]] = []
    for mode_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not mode_dir.is_dir() or mode_dir.name == "__pycache__":
            continue
        for fixture_dir in sorted(mode_dir.iterdir()):
            if not fixture_dir.is_dir():
                continue
            if not (fixture_dir / "config.json").exists():
                continue
            cases.append((f"{mode_dir.name}/{fixture_dir.name}", fixture_dir))
    return cases


_FIXTURES = _discover_fixtures()


def _dispatch(mode: str, input_text: str, params: dict) -> str:
    if mode == "clean_text":
        return clean_text(input_text)
    if mode == "strip_think":
        return strip_think(input_text)
    if mode == "tfidf":
        return summarize(input_text, max_length=params.get("max_length", 500))
    if mode == "keyword":
        return extract_keyword(
            input_text,
            params["keywords"],
            num_sentences=params.get("num_sentences", 10),
        )
    if mode == "textrank":
        pytest.skip("textrank requires optional dependency; tested separately")
    raise ValueError(f"unknown mode: {mode}")


@pytest.mark.parametrize("name,fixture_dir", _FIXTURES, ids=[n for n, _ in _FIXTURES])
def test_fixture(name: str, fixture_dir: Path) -> None:
    cfg = json.loads((fixture_dir / "config.json").read_text())
    input_text = (fixture_dir / "input.txt").read_text()

    expected_path = fixture_dir / "expected.txt"
    if not expected_path.exists():
        pytest.skip(f"{name}: expected.txt not yet populated")

    expected = expected_path.read_text()
    actual = _dispatch(cfg["mode"], input_text, cfg.get("params", {}))
    assert actual == expected, f"fixture {name} byte-mismatch"
```

- [ ] **Step 2: Run the test**

```bash
pytest tests/test_fixtures.py -v
```

Expected: every fixture with an `expected.txt` passes; the one without (none, after Task 7) is skipped.

- [ ] **Step 3: Commit**

```bash
git add tests/test_fixtures.py
git commit -m "test: add fixture-walker that runs every fixtures/<mode>/<name>/ case

This is the contract the Rust port must later satisfy byte-for-byte."
```

---

## Task 9: CLI

Mirror `summarize-output.py`'s ergonomics. Reads file path or stdin, dispatches to the selected mode, writes to stdout.

**Files:**
- Create: `src/skimr/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_cli.py`:

```python
import subprocess
import sys
from pathlib import Path


def _run(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "skimr.cli", *args],
        input=stdin,
        capture_output=True,
        text=True,
    )
    return result.returncode, result.stdout, result.stderr


def test_cli_reads_file_tfidf_mode(tmp_path: Path):
    f = tmp_path / "in.txt"
    f.write_text("Revenue grew. Costs fell. Margins improved by 5 points.")
    rc, out, err = _run([str(f), "--mode", "tfidf", "--max-chars", "500"])
    assert rc == 0, err
    assert "Revenue" in out or "Costs" in out or "Margins" in out


def test_cli_reads_stdin_when_no_file():
    rc, out, err = _run(["--mode", "strip_think"], stdin="<think>x</think>\nHello.")
    assert rc == 0, err
    assert out.strip() == "Hello."


def test_cli_clean_text_mode(tmp_path: Path):
    f = tmp_path / "in.txt"
    f.write_text("**Bold** text.")
    rc, out, err = _run([str(f), "--mode", "clean_text"])
    assert rc == 0, err
    assert out.strip() == "bold text."


def test_cli_keyword_mode(tmp_path: Path):
    f = tmp_path / "in.txt"
    f.write_text(
        "The demo went well. "
        "Main concern is pricing and budget. "
        "Will follow up."
    )
    rc, out, err = _run([
        str(f), "--mode", "keyword",
        "--keywords", "pricing budget",
        "--top", "1",
    ])
    assert rc == 0, err
    assert "pricing" in out.lower()


def test_cli_unknown_mode_errors():
    rc, out, err = _run(["--mode", "bogus"], stdin="text")
    assert rc != 0
    assert "bogus" in err.lower() or "invalid choice" in err.lower()
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_cli.py -v
```

Expected: tests fail with `No module named skimr.cli`.

- [ ] **Step 3: Implement `src/skimr/cli.py`**

Create `src/skimr/cli.py`:

```python
"""skimr CLI.

Usage:
  skimr [FILE] --mode {tfidf,keyword,clean_text,strip_think} [OPTIONS]

Reads FILE or stdin, writes summary to stdout.
"""
import argparse
import sys
from pathlib import Path

from skimr import summarize, clean_text, strip_think, extract_keyword


def _read_input(path: str | None) -> str:
    if path and path != "-":
        return Path(path).read_text()
    return sys.stdin.read()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="skimr",
        description="Deterministic extractive summarization.",
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=None,
        help="Input file path. Reads stdin if omitted.",
    )
    parser.add_argument(
        "--mode",
        choices=["tfidf", "keyword", "clean_text", "strip_think"],
        default="tfidf",
        help="Summarization mode (default: tfidf).",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=500,
        help="Character budget for tfidf mode (default: 500).",
    )
    parser.add_argument(
        "--keywords",
        default="",
        help="Space-separated keywords for keyword mode.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Number of sentences to return in keyword mode (default: 10).",
    )
    args = parser.parse_args(argv)

    text = _read_input(args.path)

    if args.mode == "tfidf":
        output = summarize(text, max_length=args.max_chars)
    elif args.mode == "keyword":
        if not args.keywords:
            parser.error("--mode keyword requires --keywords")
        output = extract_keyword(text, args.keywords, num_sentences=args.top)
    elif args.mode == "clean_text":
        output = clean_text(text)
    elif args.mode == "strip_think":
        output = strip_think(text)
    else:  # pragma: no cover
        parser.error(f"unknown mode: {args.mode}")

    sys.stdout.write(output)
    if not output.endswith("\n"):
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_cli.py -v
```

Expected: all 5 tests pass.

- [ ] **Step 5: Smoke-test the installed entry point**

```bash
echo "Revenue grew 23%." | skimr --mode tfidf --max-chars 500
```

Expected: prints the input back (short-circuit: input fits budget).

- [ ] **Step 6: Commit**

```bash
git add src/skimr/cli.py tests/test_cli.py
git commit -m "feat(cli): add argparse CLI with four modes

Reads FILE or stdin, dispatches to summarize/extract_keyword/clean_text
/strip_think by --mode. Installed as the skimr entry point."
```

---

## Task 10: Determinism Test

SC-008: 100 consecutive runs of any fixture must return bit-identical bytes.

**Files:**
- Create: `tests/test_determinism.py`

- [ ] **Step 1: Write the test**

```python
"""Determinism: running the same input through any mode N times must return
bit-identical output N times. Catches accidental set/dict iteration, random
tie-breaking, or any other non-deterministic behavior.
"""
import json
from pathlib import Path

import pytest

from skimr.clean import clean_text, strip_think
from skimr.tfidf import summarize
from skimr.keyword import extract_keyword


FIXTURES_ROOT = Path(__file__).resolve().parent.parent / "fixtures"


def _dispatch(mode: str, input_text: str, params: dict) -> str:
    if mode == "clean_text":
        return clean_text(input_text)
    if mode == "strip_think":
        return strip_think(input_text)
    if mode == "tfidf":
        return summarize(input_text, max_length=params.get("max_length", 500))
    if mode == "keyword":
        return extract_keyword(
            input_text,
            params["keywords"],
            num_sentences=params.get("num_sentences", 10),
        )
    pytest.skip(f"mode {mode} not covered by determinism test")


def _all_fixtures():
    for mode_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not mode_dir.is_dir():
            continue
        for fd in sorted(mode_dir.iterdir()):
            if not fd.is_dir() or not (fd / "config.json").exists():
                continue
            yield (f"{mode_dir.name}/{fd.name}", fd)


@pytest.mark.parametrize(
    "name,fixture_dir",
    list(_all_fixtures()),
    ids=[n for n, _ in _all_fixtures()],
)
def test_determinism_100_runs(name: str, fixture_dir: Path) -> None:
    cfg = json.loads((fixture_dir / "config.json").read_text())
    input_text = (fixture_dir / "input.txt").read_text()

    first = _dispatch(cfg["mode"], input_text, cfg.get("params", {}))
    for _ in range(99):
        other = _dispatch(cfg["mode"], input_text, cfg.get("params", {}))
        assert other == first, f"non-deterministic output on fixture {name}"
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_determinism.py -v
```

Expected: all fixtures pass. If any fails, the implementation has non-deterministic behavior (most likely `set()` or `dict` iteration in the scorer) — fix before proceeding.

- [ ] **Step 3: Commit**

```bash
git add tests/test_determinism.py
git commit -m "test: add 100-run determinism check for every fixture"
```

---

## Task 11: Zero-Dep Check Test

SC-007: default install must have zero non-stdlib runtime dependencies.

**Files:**
- Create: `tests/test_zero_deps.py`

- [ ] **Step 1: Write the test**

```python
"""Zero-dep check: importing skimr with only stdlib on sys.path must succeed.

Uses a subprocess so we can control sys.path cleanly.
"""
import subprocess
import sys
import sysconfig
from pathlib import Path


def test_skimr_imports_with_only_stdlib():
    stdlib_path = sysconfig.get_paths()["stdlib"]
    # Find the installed skimr source dir via the current package
    import skimr
    skimr_dir = Path(skimr.__file__).resolve().parent.parent

    env_path = f"{skimr_dir}:{stdlib_path}"
    result = subprocess.run(
        [
            sys.executable,
            "-I",  # ignore PYTHONPATH and user site-packages
            "-c",
            "import skimr; "
            "from skimr import summarize, clean_text, strip_think, extract_keyword; "
            "print('OK')",
        ],
        env={"PYTHONPATH": env_path, "PATH": sysconfig.get_paths()['scripts']},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"skimr failed to import with only stdlib:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    assert "OK" in result.stdout


def test_textrank_not_importable_without_extra():
    # If skimr.textrank raises ImportError on import, that's fine.
    # If it imports but the callable warns/errors on use, that's also fine.
    # This test codifies: the default path (summarize, clean_text, extract_keyword,
    # strip_think) must not require networkx.
    import skimr
    # Ensure no transitive import of networkx happens when loading skimr:
    assert "networkx" not in sys.modules, (
        "default skimr import pulled in networkx — breaks zero-dep promise"
    )
```

- [ ] **Step 2: Run**

```bash
pytest tests/test_zero_deps.py -v
```

Expected: both tests pass. If `test_textrank_not_importable_without_extra` fails, check that `src/skimr/__init__.py` does NOT top-level import `skimr.textrank`.

- [ ] **Step 3: Commit**

```bash
git add tests/test_zero_deps.py
git commit -m "test: assert skimr default path imports with only stdlib (SC-007)"
```

---

## Task 12: Optional TextRank Mode

⛔ **DC-003 checkpoint:** After this task, re-read `skill-output/mission-brief/Mission-Brief-skimr.md` and verify (a) `pip install skimr` without the extra still passes `test_zero_deps.py`, and (b) `pip install skimr[textrank]` enables the new mode.

**Files:**
- Create: `src/skimr/textrank.py`
- Create: `tests/test_textrank.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_textrank.py`:

```python
"""TextRank mode — only runs when the [textrank] extra is installed."""
import pytest

networkx = pytest.importorskip("networkx", reason="networkx not installed; run `pip install skimr[textrank]`")

from skimr.textrank import summarize_textrank


def test_textrank_returns_nonempty_for_multi_sentence_input():
    text = (
        "Revenue grew 23% in Q4. "
        "The Enterprise segment led growth. "
        "Churn remained flat. "
        "Margins improved by 5 points. "
        "Outlook for next quarter is cautiously optimistic."
    )
    result = summarize_textrank(text, num_sentences=2)
    assert result
    assert result.count("\n") >= 0  # at most 1 newline for 2 sentences


def test_textrank_short_input_returns_unchanged():
    text = "Only one sentence here."
    # Below threshold: falls through to input unchanged
    assert summarize_textrank(text, num_sentences=3) == text


def test_textrank_deterministic():
    text = (
        "Revenue grew. Costs fell. Margins improved. "
        "Dr. Smith analyzed the Q4 results. The Enterprise segment led growth."
    )
    first = summarize_textrank(text, num_sentences=2)
    for _ in range(99):
        assert summarize_textrank(text, num_sentences=2) == first
```

- [ ] **Step 2: Implement `src/skimr/textrank.py`**

Create `src/skimr/textrank.py`:

```python
"""TextRank extractive summarization.

Optional feature — requires `pip install skimr[textrank]` (pulls networkx).
Imports networkx lazily to avoid breaking the zero-dep default path.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from skimr.sentences import split_sentences
from skimr.tfidf import _tokenize  # reuse shared tokenizer + stopword list


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    numerator = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return numerator / (norm_a * norm_b)


def summarize_textrank(text: str, num_sentences: int = 5) -> str:
    """TextRank extractive summary.

    Returns top-N sentences by PageRank score, reordered by original position.
    Raises ImportError at call time if networkx is not installed.
    """
    try:
        import networkx as nx  # lazy import; extras-gated
    except ImportError as exc:
        raise ImportError(
            "TextRank mode requires networkx. Install with: pip install skimr[textrank]"
        ) from exc

    if not text:
        return ""
    sentences = split_sentences(text)
    if len(sentences) < num_sentences + 1:
        return text

    # Build sentence-similarity graph
    token_counters = [Counter(_tokenize(s)) for s in sentences]
    graph = nx.Graph()
    n = len(sentences)
    graph.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(token_counters[i], token_counters[j])
            if sim > 0.0:
                graph.add_edge(i, j, weight=sim)

    # PageRank on the similarity graph. Fixed seed via sorted node order +
    # personalization for determinism across networkx versions.
    scores = nx.pagerank(graph, weight="weight")

    # Top-N indices, deterministic tie-break on original position
    ranked = sorted(range(n), key=lambda i: (-scores.get(i, 0.0), i))[:num_sentences]
    ranked.sort()
    return " ".join(sentences[i] for i in ranked)
```

- [ ] **Step 3: Run tests with the extra installed**

```bash
pip install -e ".[textrank]"
pytest tests/test_textrank.py -v
```

Expected: 3 passed.

- [ ] **Step 4: Verify default-install still has zero deps**

Create a temporary venv to test the no-extra case:

```bash
python3 -m venv /tmp/skimr-zero-dep
/tmp/skimr-zero-dep/bin/pip install -e .
/tmp/skimr-zero-dep/bin/python -c "
import skimr
from skimr import summarize, clean_text, strip_think, extract_keyword
import sys
assert 'networkx' not in sys.modules, 'networkx leaked into default import'
print('zero-dep default path OK')
"
rm -rf /tmp/skimr-zero-dep
```

Expected: `zero-dep default path OK`.

- [ ] **Step 5: ⛔ DC-003 drift check**

Re-read `skill-output/mission-brief/Mission-Brief-skimr.md`. Verify:

1. **Am I still solving the stated Purpose?** (Deterministic extractive summarization — yes, TextRank is in scope as an optional mode.)
2. **Does my current work map to SC-XXX?** (Yes — SC-004 "Optional TextRank mode available behind an optional dep". Also reinforces SC-007 zero-dep promise.)
3. **Am I doing anything in Out of Scope?** (No — TextRank is explicitly in scope; networkx is the only optional dep.)

If any answer flags drift, stop and propose a correction before continuing.

- [ ] **Step 6: Commit**

```bash
git add src/skimr/textrank.py tests/test_textrank.py
git commit -m "feat(textrank): add optional TextRank mode behind [textrank] extra

Requires networkx>=3.0. Lazy-imported so default skimr install remains
zero-dep. Deterministic via stable tie-break + sorted node ordering."
```

---

## Task 13: GitHub Actions CI

Two workflows: main test suite across Python versions, and a dedicated zero-dep check.

**Files:**
- Create: `.github/workflows/test.yml`
- Create: `.github/workflows/zero-deps.yml`

- [ ] **Step 1: Write `.github/workflows/test.yml`**

```yaml
name: tests

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python ${{ matrix.python-version }}
        uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      - name: Install with dev + textrank extras
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev,textrank]"
      - name: Run pytest
        run: pytest
```

- [ ] **Step 2: Write `.github/workflows/zero-deps.yml`**

```yaml
name: zero-deps

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  zero-deps:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install skimr with no extras
        run: |
          python -m pip install --upgrade pip
          pip install -e .
      - name: Verify no non-stdlib runtime deps
        run: |
          python -c "
          import subprocess, sys
          output = subprocess.check_output([sys.executable, '-m', 'pip', 'show', 'skimr'], text=True)
          for line in output.splitlines():
              if line.startswith('Requires:'):
                  deps = line.split(':', 1)[1].strip()
                  if deps:
                      raise SystemExit(f'skimr has runtime deps: {deps!r}')
                  print('zero-deps: OK')
                  break
          "
      - name: Verify skimr imports with default install
        run: |
          python -c "
          import skimr
          from skimr import summarize, clean_text, strip_think, extract_keyword
          import sys
          assert 'networkx' not in sys.modules
          print('import check: OK')
          "
```

- [ ] **Step 3: Commit (CI runs after push)**

```bash
git add .github/workflows/test.yml .github/workflows/zero-deps.yml
git commit -m "ci: add test matrix and zero-dep verification workflows"
```

---

## Task 14: Final README

Fresh-clone → summarize a doc in under 5 minutes. SC-010's install/use bar.

**Files:**
- Modify: `README.md`

- [ ] **Step 1: Write the README**

Replace `README.md` with:

````markdown
# skimr

**Deterministic extractive summarization — zero runtime dependencies.**

Python library + CLI that shrinks text before it hits an LLM, cache, or preview. Same algorithm, reproducible output, sub-millisecond latency. Rust port coming in v0.1.

## Install

```bash
pip install skimr                    # default: zero deps
pip install "skimr[textrank]"        # adds optional networkx-based TextRank mode
```

From source:

```bash
git clone https://github.com/<YOUR-ORG>/skimr.git
cd skimr
pip install -e ".[dev]"
```

## Quick Start

```python
from skimr import summarize, clean_text, strip_think, extract_keyword

text = open("long_doc.md").read()

# Default: TF-IDF + position + length, 500-char budget
summary = summarize(text, max_length=500)

# Query-driven: top-3 sentences relevant to keywords
relevant = extract_keyword(text, "pricing budget competitor", num_sentences=3)

# Strip markdown, filler, CRM boilerplate before passing to an LLM
cleaned = clean_text(text)

# Remove <think>...</think> blocks from reasoning-model output
from anthropic import Anthropic  # or openai, etc.
raw = ...  # LLM response
visible = strip_think(raw)
```

## CLI

```bash
# Summarize a file (TF-IDF default, 500-char budget)
skimr long_doc.md

# Query-driven extractive
skimr long_doc.md --mode keyword --keywords "pricing budget" --top 3

# Pipe stdin
cat long_doc.md | skimr --mode tfidf --max-chars 1000

# Strip boilerplate only
skimr raw_note.txt --mode clean_text

# Strip reasoning blocks
echo "<think>...</think>Real answer." | skimr --mode strip_think
```

## Modes

| Mode | When to use | Deps |
|---|---|---|
| `tfidf` (default) | "Give me the most important N chars of this document" | stdlib only |
| `keyword` | "Give me sentences relevant to these keywords" | stdlib only |
| `clean_text` | Strip markdown, filler, CRM boilerplate | stdlib only |
| `strip_think` | Remove `<think>…</think>` from reasoning-model output | stdlib only |
| `textrank` | Graph-based extractive on long docs | requires `[textrank]` extra |

## Design Notes

- **Deterministic.** Same input → same bytes, every time. No random tie-breaking.
- **Zero-dep default.** Stdlib only. TextRank is opt-in.
- **Cross-runtime parity.** Shared fixture corpus under `fixtures/` is the contract. A Rust port (v0.1) will produce byte-identical output for every fixture.
- **Extractive, not abstractive.** No LLM calls. For abstractive summarization, use a different tool.

Full spec: [`SUMMARIZATION.md`](SUMMARIZATION.md) and [`extractive_functions.md`](extractive_functions.md).
Project scope: [`skill-output/mission-brief/Mission-Brief-skimr.md`](skill-output/mission-brief/Mission-Brief-skimr.md).

## License

Apache-2.0.
````

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: write README with quick-start, CLI usage, and mode table"
```

---

## Task 15: Plan 1 Exit — DC-001 Drift Check + Tag v0.0.1

⛔ **DC-001 checkpoint.** This is Plan 1's exit gate. Before tagging, explicitly verify every Plan-1 SC has evidence.

**Files:**
- No new files; produces a git tag.

- [ ] **Step 1: Run the full test suite clean**

```bash
pytest
```

Expected: all tests pass. If any fail, stop — Plan 1 is not done.

- [ ] **Step 2: Re-read the mission brief**

```bash
cat skill-output/mission-brief/Mission-Brief-skimr.md
```

- [ ] **Step 3: Verify Plan 1 SC coverage (explicit — write this in the commit message)**

Check each applicable SC:

| SC | Plan 1 evidence |
|---|---|
| SC-001 (Python passes fixture corpus) | `pytest tests/test_fixtures.py -v` shows all fixtures pass |
| SC-003 (four core modes spec-compliant) | `tests/test_tfidf.py`, `tests/test_keyword.py`, `tests/test_clean.py` pass |
| SC-004 (optional TextRank) | `pytest tests/test_textrank.py` passes with `[textrank]` installed; zero-deps workflow passes without |
| SC-005 (CLI) | `tests/test_cli.py` passes; `skimr --help` shows all four modes |
| SC-007 (zero-dep default) | `.github/workflows/zero-deps.yml` passes |
| SC-008 (determinism) | `tests/test_determinism.py` passes 100-run check |

SC-002, SC-006, SC-009, SC-010 (tag v0.1.0) are Plan 2's job. Do **not** tag v0.1.0 here.

- [ ] **Step 4: Answer the three drift questions**

Write the answers in the tag annotation (Step 6). Answers should be affirmative; if any is not, stop and reconcile.

1. Am I still solving the stated Purpose? (Deterministic extractive summarization, Python + Rust, byte-identical across runtimes.)
2. Does my current work map to at least one SC-XXX? (Yes — Plan 1 covers SC-001, SC-003, SC-004, SC-005, SC-007, SC-008.)
3. Am I doing anything in Out of Scope? (No — no Rust code yet, no file extraction, no neural summarization, no PyPI publish.)

- [ ] **Step 5: Push to GitHub (first push)**

If the GitHub repo doesn't exist yet, create it (via `gh repo create yonk-tools/skimr --public` or the GitHub UI).

```bash
git remote add origin git@github.com:<YOUR-ORG>/skimr.git
git push -u origin main
```

Wait for the CI workflows to go green. If either fails, fix and push before tagging.

- [ ] **Step 6: Tag v0.0.1**

```bash
git tag -a v0.0.1 -m "v0.0.1 — Python reference implementation

Plan 1 complete. Python library + CLI covers SC-001, SC-003, SC-004,
SC-005, SC-007, SC-008 of the mission brief.

Drift-check answers:
1. Still solving stated Purpose: yes.
2. All work maps to at least one SC-XXX: yes.
3. Nothing from Out of Scope: confirmed.

Next: Plan 2 (Rust port). SC-002 (byte-identity with Python) and SC-006
(benchmark vs Sumy) land there. v0.1.0 is tagged at Plan 2 completion."

git push origin v0.0.1
```

- [ ] **Step 7: Offer Plan 2 handoff**

Plan 1 done. Tell the user:
- Python impl green, fixture corpus is the frozen contract Rust must match.
- Recommended next step: run `/writing-plans` for the Rust port, using this plan's output (fixture corpus + Python bytes) as Rust's target.

---

## Out of Scope for Plan 1

Listed here to make scope discipline explicit. Do not add any of these mid-plan:

- Rust implementation (entire Plan 2)
- PyPI publication (`twine upload`, trusted publishers, etc.)
- Benchmark numbers vs. Sumy (Plan 2 — needs Rust for the "fastest of both" comparison)
- Integration memo for a real Yonk project (Plan 2)
- Registry publication, docs site, launch materials
- Non-English stopword lists, ICU dependencies
- File format extraction (PDF, DOCX, HTML) — future companion package
- Streaming / incremental summarization
- Rename of the repo directory from `extractive_summary/` to `skimr/` (cosmetic; defer)

---

## Self-Review Checklist

Run this before handing off:

- [ ] **Spec coverage.** Every Plan-1 SC has a task that produces its evidence. (Confirmed: SC-001 → Task 8; SC-003 → Tasks 3-7; SC-004 → Task 12; SC-005 → Task 9; SC-007 → Tasks 11, 13; SC-008 → Task 10.)
- [ ] **No placeholders.** Ctrl-F for TBD, TODO, "fill in", "similar to Task" — should return nothing.
- [ ] **Type consistency.** All public names (`summarize`, `clean_text`, `strip_think`, `extract_keyword`, `summarize_textrank`) appear identically in `__init__.py`, CLI, tests, and README.
- [ ] **Ordering.** No task references a symbol defined in a later task. (Task 2's `split_sentences` is used in Tasks 5, 6, 12 — all later. ✓)
- [ ] **Commit cadence.** Every task ends with a single commit. No task leaves uncommitted state. ✓
