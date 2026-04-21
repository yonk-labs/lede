//! Outline stub — real implementation lands in Task 6.

#[derive(Debug, Clone, PartialEq)]
pub struct Section {
    pub depth: usize,
    pub name: String,
    pub representative_sentence: String,
}

#[must_use]
pub fn outline(_text: &str) -> Vec<Section> {
    Vec::new()
}
