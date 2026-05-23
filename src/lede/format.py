"""Output formatting helpers for lede results.

The core primitives stay data-first: ``summarize()`` returns
``SummaryResult`` and extraction primitives return tuples/dataclasses.
This module provides the presentation layer used by both the public API
and the CLI.
"""
from __future__ import annotations

import dataclasses
import json
from typing import Any


def to_data(value: Any) -> Any:
    """Convert lede dataclasses / NamedTuples into JSON-serializable data."""
    if dataclasses.is_dataclass(value):
        return {field.name: to_data(getattr(value, field.name)) for field in dataclasses.fields(value)}
    if isinstance(value, tuple) and hasattr(value, "_fields"):
        return {name: to_data(getattr(value, name)) for name in value._fields}
    if isinstance(value, (list, tuple)):
        return [to_data(v) for v in value]
    if isinstance(value, dict):
        return {str(k): to_data(v) for k, v in value.items()}
    return value


def to_json(value: Any, *, indent: int | None = 2) -> str:
    """Serialize lede data to JSON with UTF-8 characters preserved."""
    return json.dumps(to_data(value), ensure_ascii=False, indent=indent)


def markdown_list(title: str, rows: list[str]) -> str:
    """Render a simple Markdown section with bullet rows."""
    if not rows:
        return f"## {title}\n"
    return "\n".join([f"## {title}", "", *[f"- {row}" for row in rows]])


def stats_text(rows) -> str:
    """Render ``extract.stats`` rows as tab-separated text."""
    return "\n".join(
        f"{s.stat_type}\t{s.value}\t{s.unit}\t{s.context_sentence}"
        for s in rows
    )


def stats_markdown(rows) -> str:
    """Render ``extract.stats`` rows as a Markdown table."""
    if not rows:
        return "## Stats\n"
    lines = ["## Stats", "", "| Type | Value | Unit | Context |", "|---|---|---|---|"]
    for s in rows:
        lines.append(f"| {s.stat_type} | {s.value} | {s.unit} | {s.context_sentence} |")
    return "\n".join(lines)


def metadata_text(m) -> str:
    """Render ``extract.metadata`` as labeled text lists."""
    parts: list[str] = []
    for label, values in (
        ("Dates", m.dates),
        ("Amounts", m.amounts),
        ("URLs", m.urls),
        ("Entities", m.entities),
    ):
        if values:
            parts.append(f"{label}:")
            parts.extend(f"  - {v}" for v in values)
    return "\n".join(parts)


def metadata_markdown(m) -> str:
    """Render ``extract.metadata`` as Markdown sections."""
    lines = ["## Metadata"]
    for label, values in (
        ("Dates", m.dates),
        ("Amounts", m.amounts),
        ("URLs", m.urls),
        ("Entities", m.entities),
    ):
        if values:
            lines.extend(["", f"### {label}", "", *[f"- {v}" for v in values]])
    return "\n".join(lines)


def outline_text(rows) -> str:
    """Render ``extract.outline`` rows as indented text."""
    return "\n".join(
        f"{'  ' * max(s.depth - 1, 0)}- {s.name}: {s.representative_sentence}"
        for s in rows
    )


def outline_markdown(rows) -> str:
    """Render ``extract.outline`` rows as Markdown bullets."""
    return "\n".join(
        [
            "## Outline",
            "",
            *[
                f"{'  ' * max(s.depth - 1, 0)}- **{s.name}**: {s.representative_sentence}"
                for s in rows
            ],
        ]
    )


def correlate_text(rows) -> str:
    """Render ``extract.correlate_facts`` rows as tab-separated text."""
    return "\n".join(f"{r.entity}\t{r.number}\t{r.polarity}\t{r.sentence}" for r in rows)


def correlate_markdown(rows) -> str:
    """Render ``extract.correlate_facts`` rows as Markdown bullets."""
    return markdown_list(
        "Correlated Facts",
        [f"**{r.entity}**: {r.number} ({r.polarity}) - {r.sentence}" for r in rows],
    )


def summary_markdown(result) -> str:
    """Render a ``SummaryResult`` and any attachments as Markdown."""
    lines = ["## Summary", "", result.summary.rstrip()]
    if result.stats:
        lines.extend(["", stats_markdown(result.stats)])
    if result.outline:
        lines.extend(["", outline_markdown(result.outline)])
    if result.metadata:
        lines.extend(["", metadata_markdown(result.metadata)])
    if result.phrases:
        lines.extend(["", markdown_list("Phrases", list(result.phrases))])
    if result.correlated_facts:
        lines.extend(["", correlate_markdown(result.correlated_facts)])
    return "\n".join(lines)


def format_extract(
    kind: str,
    value: Any,
    *,
    output: str = "text",
    scores: bool = False,
) -> str:
    """Render a standalone extraction primitive result.

    Args:
        kind: primitive name, e.g. ``"stats"``, ``"metadata"``,
            ``"key_facts"``, ``"top_terms"``.
        value: result returned by the primitive.
        output: one of ``"text"``, ``"markdown"``, or ``"json"``.
        scores: for ``top_terms`` text/Markdown output, render
            ``TermScore`` records with score and kind.
    """
    if output == "json":
        return to_json(value)
    if output not in ("text", "markdown"):
        raise ValueError(f"output must be 'text', 'markdown', or 'json'; got {output!r}")

    if kind == "stats":
        return stats_markdown(value) if output == "markdown" else stats_text(value)
    if kind in ("facts", "key_facts"):
        rows = list(value)
        return markdown_list("Key Facts", rows) if output == "markdown" else "\n".join(rows)
    if kind == "metadata":
        return metadata_markdown(value) if output == "markdown" else metadata_text(value)
    if kind == "outline":
        return outline_markdown(value) if output == "markdown" else outline_text(value)
    if kind == "toc":
        rows = list(value)
        return markdown_list("Table of Contents", rows) if output == "markdown" else "\n".join(rows)
    if kind == "phrases":
        rows = list(value)
        return markdown_list("Phrases", rows) if output == "markdown" else "\n".join(rows)
    if kind == "correlate_facts":
        return correlate_markdown(value) if output == "markdown" else correlate_text(value)
    if kind == "top_terms":
        if scores:
            rows = [f"{t.term}\t{t.kind}\t{t.score:.6g}" for t in value]
            md_rows = [f"`{t.term}` ({t.kind}, {t.score:.3f})" for t in value]
        else:
            rows = [str(t) for t in value]
            md_rows = rows
        return markdown_list("Top Terms", md_rows) if output == "markdown" else "\n".join(rows)
    raise ValueError(f"unknown extraction kind: {kind!r}")


def format_result(value: Any, *, output: str = "text") -> str:
    """Render any lede value as ``"text"``, ``"markdown"``, or ``"json"``.

    ``SummaryResult`` values use their rich Markdown renderer. Other values
    fall back to ``str(value)`` for text/Markdown unless a specialized CLI
    formatter is used.
    """
    if output == "json":
        return to_json(value)
    if output == "markdown" and hasattr(value, "to_markdown"):
        return value.to_markdown()
    if output == "text":
        return str(value)
    if output == "markdown":
        return str(value)
    raise ValueError(f"output must be 'text', 'markdown', or 'json'; got {output!r}")
