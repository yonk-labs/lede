"""Numeric-fact extractor. Regex-based, deterministic, stdlib only."""
import re
from .._types import Stat
from ..sentences import split_sentences


_MONEY_RE = re.compile(
    r"(?P<value>\$\d[\d,]*(?:\.\d+)?[KMB]?)"
    r"|(?P<value2>\d[\d,]*(?:\.\d+)?)\s*(?P<ccy>dollars?|USD|EUR|GBP|JPY|CHF)",
    re.IGNORECASE,
)

_PERCENT_RE = re.compile(
    r"(?P<value>\d+(?:\.\d+)?)\s*(?P<unit>%|percent)",
    re.IGNORECASE,
)

# NOTE: `year` alternative matches bare 4-digit years in 1900-2099. Known
# collision: numerals like "1500 dollars" would also match as a date stat
# because primitives run independently. No current corpus exercises this;
# future work could add a negative lookahead for currency/unit context.
_DATE_RE = re.compile(
    r"(?P<iso>\d{4}-\d{2}-\d{2})"
    r"|(?P<us>\d{1,2}/\d{1,2}/\d{2,4})"
    r"|(?P<year>\b(?:19|20)\d{2}\b)",
)

_DURATION_RE = re.compile(
    r"(?P<value>\d+)[-\s]*(?P<unit>seconds?|minutes?|hours?|days?|weeks?|months?|years?)",
    re.IGNORECASE,
)

_COUNT_RE = re.compile(
    r"(?P<value>\d[\d,]*)\s*(?P<unit>events?|users?|customers?|requests?"
    r"|per second|per minute|per hour|qps|rps|chunks?"
    r"|terabytes?|basis\s+points?)",
    re.IGNORECASE,
)


def _ctx_phrase(sentence: str, start: int, end: int, window: int = 25) -> str:
    """Return `sentence[start-window:end+window]`, clipped to token boundaries."""
    l = max(0, start - window)
    r = min(len(sentence), end + window)
    return sentence[l:r].strip()


def stats(text: str) -> tuple[Stat, ...]:
    """Extract money, percent, date, duration, count facts with context."""
    out: list[Stat] = []
    for sent in split_sentences(text):
        for m in _MONEY_RE.finditer(sent):
            value = m.group("value") or m.group("value2")
            out.append(Stat(
                value=value,
                unit="usd",
                phrase=_ctx_phrase(sent, m.start(), m.end()),
                context_sentence=sent,
                stat_type="money",
            ))
        for m in _PERCENT_RE.finditer(sent):
            out.append(Stat(
                value=m.group("value"),
                unit="percent",
                phrase=_ctx_phrase(sent, m.start(), m.end()),
                context_sentence=sent,
                stat_type="percent",
            ))
        for m in _DATE_RE.finditer(sent):
            value = m.group("iso") or m.group("us") or m.group("year")
            out.append(Stat(
                value=value,
                unit="date",
                phrase=_ctx_phrase(sent, m.start(), m.end()),
                context_sentence=sent,
                stat_type="date",
            ))
        for m in _DURATION_RE.finditer(sent):
            out.append(Stat(
                value=f"{m.group('value')} {m.group('unit').lower()}",
                unit=m.group("unit").lower().rstrip("s"),
                phrase=_ctx_phrase(sent, m.start(), m.end()),
                context_sentence=sent,
                stat_type="duration",
            ))
        for m in _COUNT_RE.finditer(sent):
            out.append(Stat(
                value=m.group("value"),
                unit=m.group("unit").lower(),
                phrase=_ctx_phrase(sent, m.start(), m.end()),
                context_sentence=sent,
                stat_type="count",
            ))
    return tuple(out)
