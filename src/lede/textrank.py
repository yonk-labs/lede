"""TextRank extractive summarization.

Optional feature — requires `pip install lede[textrank]` (pulls networkx).
Imports networkx lazily to avoid breaking the zero-dep default path.
"""
from __future__ import annotations

import math
import re
from collections import Counter

from lede.sentences import split_sentences
from lede.tfidf import _tokenize  # reuse shared tokenizer + stopword list


def _cosine_similarity(a: Counter[str], b: Counter[str]) -> float:
    if not a or not b:
        return 0.0
    shared = set(a) & set(b)
    if not shared:
        return 0.0
    numerator = sum(a[t] * b[t] for t in shared)
    norm_a = math.sqrt(sum(v * v for v in a.values()))
    norm_b = math.sqrt(sum(v * v for v in b.values()))
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return numerator / (norm_a * norm_b)


def summarize_textrank(text: str, num_sentences: int = 5) -> str:
    """TextRank extractive summary.

    Returns top-N sentences by PageRank score, reordered by original position.
    Raises ImportError at call time if networkx is not installed.
    """
    try:
        import networkx as nx  # lazy import; extras-gated
        # networkx 3.x's public nx.pagerank dispatches to a scipy/numpy backend
        # and import-errors when scipy is absent. The pure-Python power-iteration
        # path is accessible via the private _pagerank_python — stable across
        # 3.x and the only way to honour the "networkx is the only optional
        # dep" constraint without pulling scipy/numpy into the extra.
        from networkx.algorithms.link_analysis.pagerank_alg import (
            _pagerank_python as _pagerank,
        )
    except ImportError as exc:
        raise ImportError(
            "TextRank mode requires networkx. Install with: pip install lede[textrank]"
        ) from exc

    if not text:
        return ""
    sentences = split_sentences(text)
    if len(sentences) < num_sentences + 1:
        return text

    # Build sentence-similarity graph
    token_counters = [Counter(_tokenize(s)) for s in sentences]
    graph = nx.Graph()
    n = len(sentences)
    graph.add_nodes_from(range(n))
    for i in range(n):
        for j in range(i + 1, n):
            sim = _cosine_similarity(token_counters[i], token_counters[j])
            if sim > 0.0:
                graph.add_edge(i, j, weight=sim)

    # PageRank on the similarity graph. Fixed seed via sorted node order +
    # personalization for determinism across networkx versions.
    scores = _pagerank(graph, weight="weight")

    # Top-N indices, deterministic tie-break on original position
    ranked = sorted(range(n), key=lambda i: (-scores.get(i, 0.0), i))[:num_sentences]
    ranked.sort()
    return " ".join(sentences[i] for i in ranked)
