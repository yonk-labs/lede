import subprocess
import sys
import json
from pathlib import Path


def _run(args: list[str], stdin: str | None = None) -> tuple[int, str, str]:
    result = subprocess.run(
        [sys.executable, "-m", "lede.cli", *args],
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


def test_cli_reads_utf8_file_regardless_of_locale(tmp_path: Path, monkeypatch):
    f = tmp_path / "utf8.txt"
    f.write_bytes("Café résumé 1234 tons. Naïve façade.".encode("utf-8"))
    for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
        monkeypatch.delenv(var, raising=False)
    rc, out, err = _run([str(f), "--mode", "clean_text"])
    assert rc == 0, err
    assert "café" in out and "résumé" in out and "naïve" in out and "façade" in out


def test_cli_reads_utf8_stdin_regardless_of_locale(monkeypatch):
    for var in ("LC_ALL", "LANG", "PYTHONIOENCODING"):
        monkeypatch.delenv(var, raising=False)
    rc, out, err = _run(["--mode", "clean_text"], stdin="Café résumé.")
    assert rc == 0, err
    assert "café" in out and "résumé" in out


def test_cli_summary_json_with_attachments():
    rc, out, err = _run(
        ["--mode", "tfidf", "--output", "json", "--attach", "stats,metadata"],
        stdin="Revenue grew 23 percent in 2026. Costs fell. Margins improved.",
    )
    assert rc == 0, err
    data = json.loads(out)
    assert "summary" in data
    assert isinstance(data["stats"], list)
    assert data["metadata"]["dates"] == ["2026"]


def test_cli_summary_markdown():
    rc, out, err = _run(
        ["--mode", "tfidf", "--output", "markdown"],
        stdin="Revenue grew. Costs fell. Margins improved by 5 points.",
    )
    assert rc == 0, err
    assert out.startswith("## Summary")


def test_cli_key_facts_json_with_hints():
    rc, out, err = _run(
        [
            "--mode", "key_facts",
            "--output", "json",
            "--hint", "latency",
            "--max-facts", "2",
        ],
        stdin=(
            "Revenue grew 23 percent. "
            "Latency fell by 40 percent after cache rollout. "
            "Costs were flat."
        ),
    )
    assert rc == 0, err
    data = json.loads(out)
    assert any("Latency" in row for row in data)


def test_cli_metadata_auto_backend_falls_back_to_regex():
    rc, out, err = _run(
        ["--mode", "metadata", "--backend", "auto", "--output", "json"],
        stdin="Launch was on 2026-05-23. Budget was $50K.",
    )
    assert rc == 0, err
    data = json.loads(out)
    assert data["dates"] == ["2026-05-23"]
    assert data["amounts"] == ["$50K"]


def test_cli_top_terms_scores_text():
    rc, out, err = _run(
        ["--mode", "top_terms", "--scores", "--top", "3"],
        stdin="Cache latency dropped. Cache latency matters. Revenue grew.",
    )
    assert rc == 0, err
    assert "\t" in out


def test_cli_report_markdown_regex_backend():
    rc, out, err = _run(
        ["--mode", "report", "--backend", "regex", "--output", "markdown"],
        stdin="Revenue grew 23 percent. Costs fell 5 percent. Acme Corp paid $10.",
    )
    assert rc == 0, err
    assert out.startswith("## Summary")
    assert "## Facts and Important Details" in out
    assert "### Lede Key Facts" in out
    assert "spaCy" not in out


def test_cli_report_defaults_to_lede_only():
    rc, out, err = _run(
        ["--mode", "report", "--output", "markdown"],
        stdin="Revenue grew 23 percent. Costs fell 5 percent. Acme Corp paid $10.",
    )
    assert rc == 0, err
    assert out.startswith("## Summary")
    assert "## Facts and Important Details" in out
    assert "### Lede Key Facts" in out
    assert "spaCy" not in out


def test_cli_report_json_regex_backend():
    rc, out, err = _run(
        ["--mode", "report", "--backend", "regex", "--output", "json"],
        stdin=(
            "**Docket Number:** 23-108\n"
            "**Term:** 2023\n"
            "Revenue grew 23 percent. Costs fell 5 percent. Acme Corp paid $10."
        ),
    )
    assert rc == 0, err
    data = json.loads(out)
    assert "summary" in data
    assert "key_facts" in data
    assert "stats" in data
    assert data["attributes"]["docket_number"]["value"] == "23-108"
    assert data["attributes"]["term"]["value"] == "2023"
    assert data["promotion_candidates"][0]["path"].startswith("lede_report.attributes.")
