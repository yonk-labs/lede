//! lede — deterministic extractive summarization.
//!
//! Public API mirrors the Python reference in `src/lede/`. Every function here
//! must produce byte-identical output to its Python twin on every fixture in
//! `../fixtures/`. See the mission brief for the full contract.

pub mod brief;
pub mod clean;
pub mod coverage;
pub mod extract;
pub mod headings;
pub mod hints;
pub mod keyword;
pub mod parity;
pub mod pins;
pub mod sentences;
pub mod tfidf;
pub mod types;

pub use brief::{BriefDict, BriefFormat, BriefOptions, BriefOutput, brief, brief_with_options};
pub use clean::{clean_text, strip_think};
pub use keyword::extract_keyword;
pub use tfidf::{
    PinOpts, SummarizeOpts, summarize, summarize_with_attach, summarize_with_hints,
    summarize_with_pins,
};
pub use types::{AttachOpts, Mode, SummaryResult};

pub const VERSION: &str = env!("CARGO_PKG_VERSION");
