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


def test_skimr_default_import_does_not_pull_networkx():
    # Runs in a fresh subprocess so in-process sys.modules taint from other
    # tests (e.g. test_textrank.py importing networkx) can't mask a real
    # regression. Fails if `import skimr` ever starts transitively importing
    # the textrank module.
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import sys, skimr; "
            "from skimr import summarize, clean_text, strip_think, extract_keyword; "
            "print('networkx' in sys.modules)",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "False", (
        f"default skimr import pulled in networkx — breaks zero-dep promise\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
