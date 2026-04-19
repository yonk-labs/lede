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
