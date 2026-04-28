//! Canonical text formatters for v0.2 extract primitives.
//!
//! Mirrors `src/lede/_parity.py`. The Python and Rust functions must
//! produce byte-identical strings for the parity walker
//! (`rust/tests/fixtures.rs`) to compare them.
//!
//! Format choices:
//! - One record per line.
//! - Fields within a record separated by ` | ` (space-pipe-space).
//! - Trailing newline at end of output (matches Python's `\n`.join
//!   followed by a final newline).
//! - Empty input → empty string (no trailing newline either).

use crate::extract::correlate::PhraseFact;
use crate::extract::metadata::Metadata;
use crate::extract::outline::Section;
use crate::extract::stats::Stat;

fn join_lines(lines: &[String]) -> String {
    if lines.is_empty() {
        return String::new();
    }
    let mut out = lines.join("\n");
    out.push('\n');
    out
}

#[must_use]
pub fn format_stats(stats: &[Stat]) -> String {
    let lines: Vec<String> = stats
        .iter()
        .map(|s| {
            format!(
                "{} | {} | {} | {} | {}",
                s.stat_type, s.value, s.unit, s.phrase, s.context_sentence
            )
        })
        .collect();
    join_lines(&lines)
}

#[must_use]
pub fn format_outline(outline: &[Section]) -> String {
    let lines: Vec<String> = outline
        .iter()
        .map(|sec| {
            format!(
                "{} | {} | {}",
                sec.depth, sec.name, sec.representative_sentence
            )
        })
        .collect();
    join_lines(&lines)
}

#[must_use]
pub fn format_toc(toc: &[String]) -> String {
    join_lines(toc)
}

#[must_use]
pub fn format_metadata(md: &Metadata) -> String {
    let lines = vec![
        format!("DATES: {}", md.dates.join(", ")),
        format!("AMOUNTS: {}", md.amounts.join(", ")),
        format!("URLS: {}", md.urls.join(", ")),
        format!("ENTITIES: {}", md.entities.join(", ")),
    ];
    join_lines(&lines)
}

#[must_use]
pub fn format_phrases(phrases: &[String]) -> String {
    join_lines(phrases)
}

#[must_use]
pub fn format_key_facts(facts: &[String]) -> String {
    join_lines(facts)
}

#[must_use]
pub fn format_correlate_facts(facts: &[PhraseFact]) -> String {
    let lines: Vec<String> = facts
        .iter()
        .map(|f| {
            format!(
                "{} | {} | {} | {}",
                f.entity, f.number, f.polarity, f.sentence
            )
        })
        .collect();
    join_lines(&lines)
}
