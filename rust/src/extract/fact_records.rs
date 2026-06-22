//! `extract::fact_records` — structured fact records for downstream ingest
//! (issue #11). Mirrors the **numeric** records of Python
//! `readable_report().fact_records` so a Rust consumer (chunkshop-rs
//! `lede_report`) can assemble fact records at field-level parity.
//!
//! Scope: Rust covers the numeric records derived from [`crate::extract::stats`]
//! (already `pub`). Python's additional `attribute` records (from document
//! key:value parsing) and `entity_number` records (spaCy facts) are Python-only
//! and out of the regex core; a Rust caller layers those itself if needed
//! (e.g. via `lede-enrich` for entity facts).

use crate::extract::stats::stats;

/// A structured fact record. Field-compatible with Python `lede.FactRecord`
/// (`subject` / `predicate` / `object` / `fact_type` / `evidence` /
/// `confidence`).
#[derive(Debug, Clone, PartialEq)]
pub struct FactRecord {
    pub subject: String,
    pub predicate: String,
    pub object: String,
    pub fact_type: String,
    pub evidence: String,
    pub confidence: f64,
}

/// Numeric fact records derived from [`crate::extract::stats`]. Each `Stat`
/// becomes `(document, <stat_type>, <value>, "numeric", <evidence>, 0.8)` —
/// matching the numeric records Python `readable_report` emits.
#[must_use]
pub fn fact_records(text: &str) -> Vec<FactRecord> {
    stats(text)
        .into_iter()
        .map(|s| FactRecord {
            subject: "document".to_string(),
            predicate: s.stat_type,
            object: s.value,
            fact_type: "numeric".to_string(),
            evidence: compact_evidence(&s.context_sentence),
            confidence: 0.8,
        })
        .collect()
}

/// Collapse runs of whitespace to single spaces and truncate to 260 chars,
/// appending `...` when truncated. Mirrors Python `report._compact_evidence`
/// (char-based, matching Python `str` slicing).
fn compact_evidence(text: &str) -> String {
    const MAX_CHARS: usize = 260;
    let value = text.split_whitespace().collect::<Vec<_>>().join(" ");
    if value.chars().count() <= MAX_CHARS {
        return value;
    }
    let head: String = value.chars().take(MAX_CHARS - 1).collect();
    format!("{}...", head.trim_end())
}

#[cfg(test)]
mod tests {
    use super::{compact_evidence, fact_records};

    #[test]
    fn numeric_records_from_stats() {
        let recs = fact_records("Revenue was $5 in 2024.");
        assert!(!recs.is_empty());
        assert!(recs.iter().all(|r| r.subject == "document"
            && r.fact_type == "numeric"
            && (r.confidence - 0.8).abs() < f64::EPSILON));
        assert!(
            recs.iter()
                .any(|r| r.predicate == "money" && r.object == "$5")
        );
        assert!(
            recs.iter()
                .any(|r| r.predicate == "date" && r.object == "2024")
        );
    }

    #[test]
    fn empty_text_no_records() {
        assert!(fact_records("").is_empty());
    }

    #[test]
    fn evidence_collapses_whitespace() {
        assert_eq!(compact_evidence("a   b\n c"), "a b c");
    }

    #[test]
    fn evidence_truncates_long_input() {
        // Mirrors Python _compact_evidence: value[:259].rstrip() + "..." — so
        // the result is up to 262 chars and ends with the ellipsis.
        let out = compact_evidence(&"word ".repeat(100));
        assert!(out.ends_with("..."), "out: {out}");
        assert!(out.chars().count() <= 262);
    }
}
