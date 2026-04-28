"""v0.2.0 return types (frozen dataclasses)."""
from dataclasses import dataclass


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
