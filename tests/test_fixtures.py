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
