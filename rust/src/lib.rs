//! skimr — deterministic extractive summarization.
//!
//! Public API mirrors the Python reference in `src/skimr/`. Every function here
//! must produce byte-identical output to its Python twin on every fixture in
//! `../fixtures/`. See the mission brief for the full contract.

pub mod clean;
pub mod keyword;
pub mod sentences;
pub mod tfidf;

pub use clean::{clean_text, strip_think};
pub use keyword::extract_keyword;
pub use tfidf::summarize;

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
