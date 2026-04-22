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
    out = [r for r in order if counts[r] >= 2]
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
    backend='spacy': requires skimr-spacy installed (noun_chunks-based impl, future T10b).
    backend='auto': spacy if registered else regex.
    backend=None: uses the global default (see `skimr.set_default_backend`).
    """
    if backend is None:
        backend = get_default_backend()
    impl = resolve(backend, "phrases")
    return impl(text, keywords=keywords)
