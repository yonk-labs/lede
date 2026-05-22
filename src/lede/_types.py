"""v0.2.0 return types (frozen dataclasses)."""
from dataclasses import dataclass
from typing import NamedTuple


class TermScore(NamedTuple):
    """One scored term from ``extract.top_terms(with_scores=True)`` (v0.4.1).

    A ``NamedTuple`` (not a frozen dataclass like the other types here) so
    downstream consumers can both unpack positionally
    (``for term, score, kind in result``) and access by name
    (``ts.term`` / ``ts.score`` / ``ts.kind``).

    Fields:
        term: the word or phrase.
        score: per-kind-normalized salience in ``[0.0, 1.0]`` (plain mode);
            in soft-hint mode the ``hint_bonus`` is added on top so a
            matching term may exceed 1.0. Scores are normalized within each
            kind independently — a word at 1.0 and a phrase at 1.0 are each
            top-of-their-kind, not equal on a shared cross-kind scale.
        kind: ``"word"`` (single token, TF-IDF scored) or ``"phrase"``
            (multi-word n-gram, repetition×length scored).
    """

    term: str
    score: float
    kind: str


@dataclass(frozen=True)
class Stat:
    value: str
    unit: str
    phrase: str
    context_sentence: str
    stat_type: str  # "money" | "percent" | "count" | "date" | "duration"


@dataclass(frozen=True)
class Section:
    depth: int
    name: str
    representative_sentence: str


@dataclass(frozen=True)
class Metadata:
    dates: tuple[str, ...] = ()
    amounts: tuple[str, ...] = ()
    urls: tuple[str, ...] = ()
    entities: tuple[str, ...] = ()  # populated only when lede[ner] installed (Task 9)


@dataclass(frozen=True)
class PhraseFact:
    entity: str
    number: str
    polarity: str  # "absolute" | "growth" | "decline" | "unknown"
    sentence: str


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    stats: tuple[Stat, ...] | None = None
    outline: tuple[Section, ...] | None = None
    metadata: Metadata | None = None
    phrases: tuple[str, ...] | None = None
    correlated_facts: tuple[PhraseFact, ...] | None = None

    def __str__(self) -> str:
        return self.summary
