#!/usr/bin/env python3
"""Summarize skill output files for compact context injection.

Usage:
    python3 summarize-output.py <path>           # file or directory
    python3 summarize-output.py <path> --top N   # custom sentence count (default 20)

Extracts TL;DR sections + extractive summary (top sentences by relevance).
Prints compact summary to stdout. No external dependencies.
"""

import sys
import os
import re
import string
from collections import Counter
from pathlib import Path

DEFAULT_TOP_N = 20


def extract_tldr(text: str) -> str | None:
    """Extract content under ## TL;DR or ## TLDR heading."""
    pattern = r'##\s+TL;?DR\s*\n(.*?)(?=\n##\s|\Z)'
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else None


def tokenize_sentences(text: str) -> list[str]:
    """Split text into sentences. Simple but effective for markdown."""
    clean = re.sub(r'^---\n.*?\n---\n', '', text, flags=re.DOTALL)
    clean = re.sub(r'```.*?```', '', clean, flags=re.DOTALL)
    clean = re.sub(r'^#+\s+.*$', '', clean, flags=re.MULTILINE)
    clean = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', clean)
    clean = re.sub(r'[*_`]', '', clean)
    sentences = re.split(r'(?<=[.!?])\s+', clean)
    return [s.strip() for s in sentences
            if len(s.strip()) > 30 and not s.strip().startswith('-')]


def score_sentences(sentences: list[str]) -> list[tuple[float, int, str]]:
    """Score sentences by keyword frequency and position."""
    all_words = []
    for s in sentences:
        words = re.findall(r'\b[a-z]{3,}\b', s.lower())
        all_words.extend(words)

    stopwords = {
        'the', 'and', 'that', 'this', 'with', 'for', 'are', 'was', 'were',
        'been', 'have', 'has', 'had', 'not', 'but', 'what', 'all', 'when',
        'who', 'will', 'can', 'from', 'they', 'each', 'which', 'their',
        'there', 'about', 'would', 'make', 'been', 'more', 'some', 'into',
        'other', 'than', 'its', 'also', 'after', 'use', 'how', 'our',
        'any', 'these', 'most', 'may', 'should', 'could', 'does', 'did',
        'just', 'because', 'over', 'such', 'through', 'very', 'your',
    }
    freq = Counter(w for w in all_words if w not in stopwords)

    scored = []
    n = len(sentences)
    for i, sent in enumerate(sentences):
        words = re.findall(r'\b[a-z]{3,}\b', sent.lower())
        if not words:
            continue
        word_score = sum(freq.get(w, 0) for w in words if w not in stopwords)
        keyword_score = word_score / len(words) if words else 0
        pos_ratio = i / max(n, 1)
        position_score = 1.5 if pos_ratio < 0.2 or pos_ratio > 0.8 else 1.0
        length_penalty = 1.0 if len(sent) < 200 else 0.8
        score = keyword_score * position_score * length_penalty
        scored.append((score, i, sent))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored


def summarize_file(filepath: str, top_n: int = DEFAULT_TOP_N) -> str:
    """Summarize a single markdown file."""
    text = Path(filepath).read_text(encoding='utf-8')
    name = Path(filepath).name
    parts = [f"### {name}"]
    tldr = extract_tldr(text)
    if tldr:
        parts.append(f"**TL;DR:** {tldr}")
    sentences = tokenize_sentences(text)
    if sentences:
        scored = score_sentences(sentences)
        top = sorted(scored[:top_n], key=lambda x: x[1])
        facts = [f"- {item[2]}" for item in top]
        parts.append("**Key points:**")
        parts.extend(facts)
    parts.append(f"\n*Full document: `{filepath}`*")
    return '\n'.join(parts)


def summarize_directory(dirpath: str, top_n: int = DEFAULT_TOP_N) -> str:
    """Summarize all markdown files in a directory."""
    p = Path(dirpath)
    md_files = sorted(p.glob('*.md'))
    if not md_files:
        return f"No markdown files found in {dirpath}"
    parts = [f"## Output Summary: {p.name}\n"]
    for f in md_files:
        if f.name.startswith('task-') or f.name == 'TaskIndex.md':
            parts.append(f"*Skipped task file: `{f}`*")
            continue
        parts.append(summarize_file(str(f), top_n=top_n))
        parts.append('')
    parts.append(f"\n*All files in: `{dirpath}`*")
    return '\n'.join(parts)


def main():
    if len(sys.argv) < 2:
        print("Usage: summarize-output.py <file-or-directory> [--top N]",
              file=sys.stderr)
        sys.exit(1)
    target = sys.argv[1]
    top_n = DEFAULT_TOP_N
    if '--top' in sys.argv:
        idx = sys.argv.index('--top')
        if idx + 1 < len(sys.argv):
            top_n = int(sys.argv[idx + 1])
    if os.path.isdir(target):
        print(summarize_directory(target, top_n))
    elif os.path.isfile(target):
        print(summarize_file(target, top_n))
    else:
        print(f"Error: {target} not found", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
