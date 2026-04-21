//! Numeric-fact stub — real implementation lands in Task 7.

#[derive(Debug, Clone, PartialEq)]
pub struct Stat {
    pub value: String,
    pub unit: String,
    pub phrase: String,
    pub context_sentence: String,
    pub stat_type: String,
}

#[must_use]
pub fn stats(_text: &str) -> Vec<Stat> {
    Vec::new()
}
