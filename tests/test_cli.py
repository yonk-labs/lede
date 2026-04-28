import subprocess
import sys
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
