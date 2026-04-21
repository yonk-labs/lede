//! Shared pipeline state. Full threading lands later tasks if needed for SC-B.

pub struct Pipeline {
    pub text: String,
    pub sentences: Vec<String>,
}

impl Pipeline {
    #[must_use]
    pub fn from_text(text: &str) -> Self {
        Self {
            text: text.to_string(),
            sentences: crate::sentences::split_sentences(text),
        }
    }
}
