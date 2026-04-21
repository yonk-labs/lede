"""v0.2.0 return types (frozen dataclasses)."""
from dataclasses import dataclass


@dataclass(frozen=True)
class SummaryResult:
    summary: str
    # Attachments populated by later tasks; None here.
    stats: tuple | None = None
    outline: tuple | None = None
    metadata: object | None = None
    phrases: tuple[str, ...] | None = None
    correlated_facts: tuple | None = None

    def __str__(self) -> str:
        return self.summary
