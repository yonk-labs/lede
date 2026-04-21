//! Metadata stub — real implementation lands in Task 8.

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Metadata {
    pub dates: Vec<String>,
    pub amounts: Vec<String>,
    pub urls: Vec<String>,
    pub entities: Vec<String>, // always empty in Rust (Python-only via skimr[ner])
}

#[must_use]
pub fn metadata(_text: &str) -> Metadata {
    Metadata::default()
}
