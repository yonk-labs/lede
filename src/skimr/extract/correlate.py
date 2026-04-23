"""extract.correlate_facts — pair repeated entities with nearby numbers."""
import re
from collections import Counter
from .._types import PhraseFact
from ._backends import register, resolve, get_default_backend
from .stats import stats as _stats
from .phrases import phrases as _phrases, _STOP


_GROWTH_WORDS = frozenset({
    "grew", "grow", "increased", "increase", "rose", "up",
    "higher", "gained", "added",
})
_DECLINE_WORDS = frozenset({
    "fell", "fall", "declined", "decline", "decreased", "decrease",
    "dropped", "down", "lower", "lost",
})


def _polarity(sentence: str) -> str:
    """Infer polarity from cue words in the sentence."""
    lower = sentence.lower()
    toks = set(re.findall(r"[a-z]+", lower))
    if toks & _GROWTH_WORDS:
        return "growth"
    if toks & _DECLINE_WORDS:
        return "decline"
    return "absolute"


def _regex_correlate_facts(text: str) -> tuple[PhraseFact, ...]:
    """Regex-backed entity-number correlator. Registered as ('regex','correlate_facts')."""
    if not text:
        return ()
    stats_list = _stats(text)
    if not stats_list:
        return ()

    # Build single-word frequency map — repeated single-word entity candidates
    single_word_counts: dict[str, int] = {}
    for w in re.findall(r"[a-zA-Z]{3,}", text.lower()):
        single_word_counts[w] = single_word_counts.get(w, 0) + 1
    repeated_words = {
        w for w, c in single_word_counts.items()
        if c >= 2 and w not in _STOP
    }

    # Prefer multi-word phrases from the regex phrases() backend.
    # Pinning backend='regex' keeps this impl internally consistent —
    # a spaCy-backed correlate (T11b) would build its own dep-parsed version.
    repeated_phrases = set(_phrases(text, backend="regex"))

    out: list[PhraseFact] = []
    for st in stats_list:
        sent_lower = st.context_sentence.lower()
        candidates = [
            w for w in re.findall(r"[a-zA-Z]{3,}", sent_lower)
            if w in repeated_words
        ]
        # Prefer a multi-word phrase whose every token appears in the sentence
        phrase_match = next(
            (p for p in repeated_phrases if all(w in sent_lower for w in p.split())),
            None,
        )
        entity = phrase_match if phrase_match else (
            max(candidates, key=lambda w: single_word_counts[w]) if candidates else None
        )
        if not entity:
            continue
        out.append(PhraseFact(
            entity=entity,
            number=st.value,
            polarity=_polarity(st.context_sentence),
            sentence=st.context_sentence,
        ))

    # Filter: require each entity to appear with >= 2 distinct facts
    entity_counts = Counter(pf.entity for pf in out)
    return tuple(pf for pf in out if entity_counts[pf.entity] >= 2)


register("regex", "correlate_facts", _regex_correlate_facts)


def correlate_facts(text: str, *, backend: str | None = None) -> tuple[PhraseFact, ...]:
    """Pair repeated entities with their numeric facts.

    backend='regex' (default): composition over stats() + regex phrases() + cue-word polarity.
    backend='spacy': requires skimr-spacy installed (dep-parser-based impl, future T11b).
    backend='auto': spacy if registered else regex.
    backend=None: uses the global default (see `skimr.set_default_backend`).
    """
    if backend is None:
        backend = get_default_backend()
    impl = resolve(backend, "correlate_facts")
    return impl(text)
