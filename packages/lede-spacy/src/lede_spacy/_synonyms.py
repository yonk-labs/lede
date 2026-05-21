"""WordNet synonym expansion for lede_spacy.expand_hints.

Requires the `synonyms` extra:
    pip install lede-spacy[synonyms]

WordNet data is downloaded lazily on first use (quietly). If the
download fails (offline machine), raises with manual-install instructions.
"""
from __future__ import annotations

import sys


def _check_nltk():
    """Return the nltk module or raise ImportError with install instructions."""
    mod = sys.modules.get("nltk")
    if mod is None:
        # Either not imported yet, or monkeypatched to None.
        if "nltk" in sys.modules:
            # monkeypatched to None — treat as absent
            raise ImportError(
                "expand_hints(kinds=('synonyms',)) requires nltk. "
                "Install with: pip install lede-spacy[synonyms]"
            )
        try:
            import nltk  # noqa: F401
            mod = nltk
        except ImportError as e:
            raise ImportError(
                "expand_hints(kinds=('synonyms',)) requires nltk. "
                "Install with: pip install lede-spacy[synonyms]"
            ) from e
    return mod


def _ensure_wordnet(nltk_mod) -> None:
    """Lazy-load WordNet on first synonyms call.

    nltk's `wordnet.synsets()` triggers a LookupError if the corpus
    isn't downloaded. Try once with `nltk.download('wordnet', quiet=True)`;
    if that fails, raise with manual-install instructions.
    """
    from nltk.corpus import wordnet
    try:
        wordnet.synsets("test")  # forces lazy load
    except LookupError:
        try:
            nltk_mod.download("wordnet", quiet=True)
            wordnet.synsets("test")  # verify
        except Exception as e:
            raise RuntimeError(
                "WordNet data is not available and download failed. "
                "Run manually: python -m nltk.downloader wordnet"
            ) from e


def expand_synonyms(term: str, *, top_k: int) -> list[str]:
    """Return up to top_k WordNet synonyms for a single-token term.

    Multi-token terms return [] (caller treats this as passthrough).
    Determinism: synonyms are sorted by (synset POS, lemma name) and
    capped at top_k after casefold-dedup.
    """
    if " " in term.strip():
        return []
    nltk_mod = _check_nltk()
    _ensure_wordnet(nltk_mod)
    from nltk.corpus import wordnet

    # Collect (pos, lemma_name) tuples — pos as string for stable sort.
    candidates: list[tuple[str, str]] = []
    for synset in wordnet.synsets(term):
        pos = synset.pos()
        for lemma in synset.lemmas():
            name = lemma.name().replace("_", " ")
            if name.lower() == term.lower():
                continue
            candidates.append((pos, name))

    # Sort by (pos, lemma_name) for stable deterministic ordering.
    candidates.sort()

    out: list[str] = []
    seen: set[str] = set()
    for _pos, name in candidates:
        low = name.lower()
        if low in seen:
            continue
        seen.add(low)
        out.append(name)
        if len(out) >= top_k:
            break
    return out
