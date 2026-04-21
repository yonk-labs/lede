//! Correlate-facts stub — real implementation lands in Task 11.

#[derive(Debug, Clone, PartialEq)]
pub struct PhraseFact {
    pub entity: String,
    pub number: String,
    pub polarity: String,
    pub sentence: String,
}

#[must_use]
pub fn correlate_facts(_text: &str) -> Vec<PhraseFact> {
    Vec::new()
}
