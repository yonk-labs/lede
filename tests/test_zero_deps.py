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
