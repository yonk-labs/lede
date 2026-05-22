//! v0.2.0 return types.

use crate::extract::correlate::PhraseFact;
use crate::extract::metadata::Metadata;
use crate::extract::outline::Section;
use crate::extract::stats::Stat;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Mode {
    Default,
    Legacy,
    Coverage,
}

#[derive(Debug, Clone, PartialEq)]
pub struct SummaryResult {
    pub summary: String,
    pub stats: Option<Vec<Stat>>,
    pub outline: Option<Vec<Section>>,
    pub metadata: Option<Metadata>,
    pub phrases: Option<Vec<String>>,
    pub correlated_facts: Option<Vec<PhraseFact>>,
    pub pinned_headings: Vec<String>,
}

impl std::fmt::Display for SummaryResult {
    fn fmt(&self, f: &mut std::fmt::Formatter<'_>) -> std::fmt::Result {
        f.write_str(&self.summary)
    }
}

impl SummaryResult {
    #[must_use]
    pub fn bare(summary: String) -> Self {
        Self {
            summary,
            stats: None,
            outline: None,
            metadata: None,
            phrases: None,
            correlated_facts: None,
            pinned_headings: Vec::new(),
        }
    }
}

/// Enable bits for structured enrichments on the returned `SummaryResult`.
///
/// Five fields, bool-per-field by design (spec: v0.2 Task 4). Clippy's
/// `struct_excessive_bools` fires at >3 bools; it's suppressed because the
/// public API shape is `AttachOpts { stats, outline, metadata, phrases,
/// correlated_facts }` and each bit corresponds to exactly one primitive.
#[allow(clippy::struct_excessive_bools)]
#[derive(Debug, Clone, Default)]
pub struct AttachOpts {
    pub stats: bool,
    pub outline: bool,
    pub metadata: bool,
    pub phrases: bool,
    pub correlated_facts: bool,
}
