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
        output = summarize(text, max_length=args.max_chars).summary
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
