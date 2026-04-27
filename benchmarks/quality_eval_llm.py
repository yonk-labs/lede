"""A4 — LLM-as-judge pairwise ranking of extractive summaries.

For each corpus:
  - run the 5 summarizers
  - anonymize them as A-E in randomized order (position-bias control)
  - pass source + 5 labeled summaries to an LLM judge
  - ask for a rank 1-5 based on fact coverage, action-item preservation, coherence
  - decode the letter ranking back to summarizer names
  - score 5 pts for 1st, 4 for 2nd, ... 1 for 5th
  - aggregate across all 10 corpora (max 50/summarizer)

Default config targets a local vLLM server exposing an OpenAI-compatible
API at http://localhost:8000/v1. Set the env vars below to point at any
other OpenAI-compatible endpoint (e.g. a remote vLLM, llama.cpp server,
or a hosted provider). Use a non-OpenAI / non-Anthropic model so the
judge sits in a different family from the Claude-authored reference
summaries.

Override with env vars:
    SKIMR_JUDGE_BASE_URL      (default http://localhost:8000/v1)
    SKIMR_JUDGE_MODEL         (default Intel/Qwen3-Coder-Next-int4-AutoRound)
    SKIMR_JUDGE_API_KEY       (default "not-needed" — local servers ignore auth)

Usage:
    .venv/bin/python benchmarks/quality_eval_llm.py
"""
from __future__ import annotations
import json
import os
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from openai import OpenAI  # noqa: E402
from skimr import summarize  # noqa: E402
from skimr.textrank import summarize_textrank  # noqa: E402
from sumy.parsers.plaintext import PlaintextParser  # noqa: E402
from sumy.nlp.tokenizers import Tokenizer  # noqa: E402
from sumy.summarizers.lex_rank import LexRankSummarizer  # noqa: E402
from sumy.summarizers.text_rank import TextRankSummarizer  # noqa: E402
from sumy.summarizers.lsa import LsaSummarizer  # noqa: E402

CORPUS_DIR = ROOT / "benchmarks" / "corpus"
OUT_DIR = ROOT / "benchmarks" / "quality"
OUT_DIR.mkdir(parents=True, exist_ok=True)

BASE_URL = os.environ.get("SKIMR_JUDGE_BASE_URL", "http://localhost:8000/v1")
MODEL = os.environ.get("SKIMR_JUDGE_MODEL", "Intel/Qwen3-Coder-Next-int4-AutoRound")
API_KEY = os.environ.get("SKIMR_JUDGE_API_KEY", "not-needed")
SEED = 42
TARGET_SENTENCES = 3
TARGET_CHARS = 500
SUMMARIZER_NAMES = ["skimr/tfidf-v0.2", "skimr/tfidf-legacy", "skimr/textrank",
                    "sumy/LexRank", "sumy/TextRank", "sumy/LSA"]

random.seed(SEED)
client = OpenAI(base_url=BASE_URL, api_key=API_KEY)


def run_all(text: str) -> dict[str, str]:
    parser = PlaintextParser.from_string(text, Tokenizer("english"))

    def sumy_run(cls):
        return " ".join(str(s) for s in cls()(parser.document, TARGET_SENTENCES))

    return {
        "skimr/tfidf-v0.2": summarize(text, max_length=TARGET_CHARS, mode="default").summary,
        "skimr/tfidf-legacy": summarize(text, max_length=TARGET_CHARS, mode="legacy").summary,
        "skimr/textrank": summarize_textrank(text, num_sentences=TARGET_SENTENCES),
        "sumy/LexRank": sumy_run(LexRankSummarizer),
        "sumy/TextRank": sumy_run(TextRankSummarizer),
        "sumy/LSA": sumy_run(LsaSummarizer),
    }


def build_prompt(source: str, letter_to_summary: dict[str, str]) -> tuple[str, str]:
    system = (
        "You are a careful evaluator of extractive text summaries. "
        "You return only valid JSON in the format specified by the user."
    )
    summary_block = "\n\n".join(
        f"SUMMARY {letter}:\n{summary}"
        for letter, summary in letter_to_summary.items()
    )
    n = len(letter_to_summary)
    last_letter = chr(ord("A") + n - 1)
    user = (
        f"Below is a source document and {n} candidate extractive summaries "
        f"labeled A through {last_letter}, each produced by a different algorithm. Rank "
        "them from best (most useful) to worst based on these criteria, in "
        "priority order:\n"
        "  1. How many important facts from the source are preserved.\n"
        "  2. Whether decisions, action items, holdings, or resolutions are retained.\n"
        "  3. Whether the summary reads coherently.\n\n"
        "Do NOT reward length or surface fluency on their own. Summaries of "
        "different lengths are valid. A summary that omits the key holding, "
        "decision, or action item of the source is worse than one that "
        "includes it, regardless of how well-written it is.\n\n"
        "Return a JSON object with a single field 'ranking' whose value is "
        f"an array of the {n} letters A-{last_letter} in order from best to worst. "
        "Return only JSON; no explanation.\n\n"
        "---\n"
        f"SOURCE DOCUMENT:\n{source}\n"
        "---\n"
        f"{summary_block}\n"
        "---\n"
    )
    return system, user


def judge_one(corpus_name: str, source: str, outs: dict[str, str]) -> dict:
    # Randomize letter assignment per corpus to control for position bias.
    letters = [chr(ord("A") + i) for i in range(len(outs))]
    shuffled_summarizers = list(outs.keys())
    random.shuffle(shuffled_summarizers)
    letter_to_summarizer = dict(zip(letters, shuffled_summarizers))
    letter_to_summary = {l: outs[letter_to_summarizer[l]] for l in letters}

    system, user = build_prompt(source, letter_to_summary)

    # Source: https://platform.openai.com/docs/guides/structured-outputs
    resp = client.chat.completions.create(
        model=MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    content = resp.choices[0].message.content or ""
    data = json.loads(content)
    ranking_letters: list[str] = data["ranking"]

    # Validate
    if sorted(ranking_letters) != letters:
        raise ValueError(f"Bad ranking {ranking_letters!r} for {corpus_name}")

    ranked_summarizers = [letter_to_summarizer[l] for l in ranking_letters]
    # N points for 1st, N-1 for 2nd, ... 1 for last
    n = len(ranked_summarizers)
    scores = {s: n - i for i, s in enumerate(ranked_summarizers)}

    return {
        "corpus": corpus_name,
        "letter_to_summarizer": letter_to_summarizer,
        "ranking_letters": ranking_letters,
        "ranked_summarizers": ranked_summarizers,
        "scores": scores,
        "usage": {
            "prompt_tokens": resp.usage.prompt_tokens,
            "completion_tokens": resp.usage.completion_tokens,
            "total_tokens": resp.usage.total_tokens,
        } if resp.usage else None,
    }


def main() -> int:
    corpora = sorted(CORPUS_DIR.glob("*.txt"))
    date = time.strftime("%Y-%m-%d")
    results: list[dict] = []

    total_prompt_tokens = 0
    total_completion_tokens = 0

    for path in corpora:
        name = path.stem
        print(f"  judging {name}...", file=sys.stderr)
        text = path.read_text()
        outs = run_all(text)
        result = judge_one(name, text, outs)
        results.append(result)
        if result["usage"]:
            total_prompt_tokens += result["usage"]["prompt_tokens"]
            total_completion_tokens += result["usage"]["completion_tokens"]
        print(
            f"    -> {' > '.join(result['ranked_summarizers'])}",
            file=sys.stderr,
        )

    # Aggregate
    aggregate: dict[str, int] = {s: 0 for s in SUMMARIZER_NAMES}
    for r in results:
        for s, pts in r["scores"].items():
            aggregate[s] += pts

    # Write outputs
    json_path = OUT_DIR / f"llm-judge-{date}.json"
    json_path.write_text(json.dumps({
        "model": MODEL,
        "seed": SEED,
        "date": date,
        "total_prompt_tokens": total_prompt_tokens,
        "total_completion_tokens": total_completion_tokens,
        "results": results,
        "aggregate": aggregate,
    }, indent=2))

    # Markdown table
    md: list[str] = [f"# A4 — LLM-as-judge ranking ({MODEL}) — {date}\n\n"]
    md.append(f"Model: `{MODEL}`, seed: `{SEED}`, temperature: 0. "
              f"Each corpus is judged once: 5 summaries anonymized as A-E in "
              f"randomized order, ranked best-to-worst by fact coverage, "
              f"action-item preservation, coherence (length explicitly excluded "
              f"as a reward signal).\n\n")
    md.append(f"**Total tokens used:** {total_prompt_tokens + total_completion_tokens:,} "
              f"({total_prompt_tokens:,} prompt + {total_completion_tokens:,} completion)\n\n")

    max_score = len(SUMMARIZER_NAMES) * len(results)
    md.append(f"## Aggregate (higher = better; max {max_score})\n\n")
    md.append("| summarizer | total points |\n|---|---|\n")
    for s in sorted(aggregate, key=lambda k: -aggregate[k]):
        md.append(f"| `{s}` | {aggregate[s]} |\n")
    md.append("\n")

    md.append("## Per-corpus rankings\n\n")
    md.append("| corpus | 1st | 2nd | 3rd | 4th | 5th |\n|---|---|---|---|---|---|\n")
    for r in results:
        row = [f"`{r['corpus']}`"] + [f"`{s}`" for s in r["ranked_summarizers"]]
        md.append("| " + " | ".join(row) + " |\n")
    md.append("\n")

    md_path = OUT_DIR / f"llm-judge-{date}.md"
    md_path.write_text("".join(md))

    print(f"Wrote {md_path}")
    print(f"Wrote {json_path}")
    print(f"Total tokens: {total_prompt_tokens + total_completion_tokens:,}")
    print("Aggregate:")
    for s in sorted(aggregate, key=lambda k: -aggregate[k]):
        print(f"  {s:20s} {aggregate[s]:3d} / 50")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
