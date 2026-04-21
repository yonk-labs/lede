//! v0.2.0 return types.
//!
//! Attachment fields (stats, outline, metadata, phrases, `correlated_facts`)
//! land in Task 4. For now `SummaryResult` is a thin wrapper around the
//! summary string with a `Display` impl so `print!`/`format!` work
//! ergonomically.

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Default,
    Legacy,
    Coverage,
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct SummaryResult {
    pub summary: String,
}

impl std::fmt::Display for SummaryResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.summary)
    }
}

impl SummaryResult {
    #[must_use]
    pub fn bare(summary: String) -> Self {
        Self { summary }
    }
}
