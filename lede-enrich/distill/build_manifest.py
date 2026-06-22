"""Build a stratified, tech-weighted corpus manifest from a pinned Wikipedia dump.

Deterministic: fixed dump id, fixed bucket keyword lists, articles taken in dump
order until each quota is filled. Emits corpus_manifest.json (ids only, committed)
and articles.jsonl (texts, gitignored).
"""
import argparse
import json

from datasets import load_dataset

DUMP = "20231101.en"  # pinned snapshot
BUCKETS = {
    "tech": ["software", "computing", "programming", "algorithm", "internet", "computer"],
    "business": ["company", "corporation", "founded", "headquartered", "ceo", "subsidiary"],
    "science": ["physics", "chemistry", "biology", "research", "theorem", "species"],
    "general": [],  # catch-all
}


def bucket_of(text: str) -> str:
    head = text[:600].lower()
    for name, kws in BUCKETS.items():
        if name != "general" and any(kw in head for kw in kws):
            return name
    return "general"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-bucket", type=int, default=1000)
    ap.add_argument("--manifest", default="corpus_manifest.json")
    ap.add_argument("--articles", default="articles.jsonl")
    args = ap.parse_args()

    ds = load_dataset("wikimedia/wikipedia", DUMP, split="train", streaming=True)
    quota = {b: args.per_bucket for b in BUCKETS}
    buckets: dict[str, list[int]] = {b: [] for b in BUCKETS}
    with open(args.articles, "w", encoding="utf-8") as fa:
        for row in ds:
            if all(v == 0 for v in quota.values()):
                break
            text = row["text"]
            if len(text) < 400:
                continue
            b = bucket_of(text)
            if quota[b] <= 0:
                continue
            quota[b] -= 1
            aid = int(row["id"])
            buckets[b].append(aid)
            fa.write(json.dumps({"id": aid, "text": text}) + "\n")

    with open(args.manifest, "w", encoding="utf-8") as fm:
        json.dump({"dump": DUMP, "buckets": buckets}, fm, indent=2)
    print({b: len(ids) for b, ids in buckets.items()})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
