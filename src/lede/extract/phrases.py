"""Heuristic phrase extractor. Repeated 2-5 token n-grams between stopwords."""
import re
from ._backends import register, resolve, get_default_backend


_STOP = frozenset(
    "the a an and or but if then with by of to in on at for from as is are was "
    "were be been being has have had do does did will would could should may "
    "might can must this that these those it its they them their there here "
    "about up down into out over off just also not no our we you your he she "
    "his her him over under more most less least all any some both each every "
    "one two three per".split()
)


def _ngrams(buf: list[str]) -> list[str]:
    """Emit all contiguous 2-5 token n-grams from a non-stopword run."""
    out: list[str] = []
    n = len(buf)
    upper = min(5, n)
    for size in range(2, upper + 1):
        for i in range(0, n - size + 1):
            out.append(" ".join(buf[i:i + size]))
    return out


def _runs(text: str) -> list[str]:
    """Return all 2-5 token n-grams from non-stopword runs (lowercased)."""
    words = re.findall(r"[a-z]{3,}", text.lower())
    runs: list[str] = []
    buf: list[str] = []
    for w in words:
        if w in _STOP:
            runs.extend(_ngrams(buf))
            buf = []
        else:
            buf.append(w)
    runs.extend(_ngrams(buf))
    return runs


def _subsumed(candidates: list[str], counts: dict[str, int]) -> set[str]:
    """Identify sub-ngrams that are fully absorbed by a longer emitted ngram.

    T13h: drop ngram A if there exists a longer emitted ngram B such that A's
    tokens appear contiguously within B's tokens AND counts[A] == counts[B].
    The equal-count signal means A only ever appears inside B's context and
    adds no independent information. Sub-ngrams with counts[A] > counts[B]
    (i.e. A has standalone occurrences) are preserved.
    """
    tok_map = {p: p.split() for p in candidates}
    drop: set[str] = set()
    for a in candidates:
        a_toks = tok_map[a]
        a_len = len(a_toks)
        for b in candidates:
            if a == b:
                continue
            b_toks = tok_map[b]
            if len(b_toks) <= a_len:
                continue
            if counts[b] != counts[a]:
                continue
            # is a contiguous inside b?
            for i in range(len(b_toks) - a_len + 1):
                if b_toks[i:i + a_len] == a_toks:
                    drop.add(a)
                    break
            if a in drop:
                break
    return drop


def _regex_phrases(text: str, keywords: str | None = None) -> tuple[str, ...]:
    """Regex/heuristic phrase extractor. Registered as the 'regex' backend."""
    if not text:
        return ()
    runs = _runs(text)
    counts: dict[str, int] = {}
    order: list[str] = []
    for r in runs:
        counts[r] = counts.get(r, 0) + 1
        if r not in order:
            order.append(r)
    repeated = [r for r in order if counts[r] >= 2]
    # T13h: subsumption — drop sub-ngrams that only appear inside a longer
    # emitted ngram (same count). Tightens precision by eliminating n-gram
    # explosion noise like "environmental protection" / "protection agency"
    # when "environmental protection agency" is also emitted.
    drop = _subsumed(repeated, counts)
    out = [r for r in repeated if r not in drop]
    if keywords:
        kw_set = {k.lower() for k in re.findall(r"[a-z]{3,}", keywords.lower())}
        for r in order:
            if counts.get(r, 0) == 1 and any(k in r.split() for k in kw_set):
                out.append(r)
    # Dedupe keeping first-appearance order
    seen: set[str] = set()
    deduped: list[str] = []
    for r in out:
        if r not in seen:
            seen.add(r)
            deduped.append(r)
    return tuple(deduped)


register("regex", "phrases", _regex_phrases)


def phrases(text: str, keywords: str | None = None, *, backend: str | None = None) -> tuple[str, ...]:
    """Extract repeated multi-word phrases (2-5 token n-grams from non-stopword runs).

    backend='regex' (default): the heuristic stdlib implementation above.
    backend='spacy': requires lede-spacy installed (noun_chunks-based impl, future T10b).
    backend='auto': spacy if registered else regex.
    backend=None: uses the global default (see `lede.set_default_backend`).
    """
    if backend is None:
        backend = get_default_backend()
    impl = resolve(backend, "phrases")
    return impl(text, keywords=keywords)
