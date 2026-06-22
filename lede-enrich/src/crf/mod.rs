//! Distilled CRF NER (opt-in `crf` feature). Typed entities via a pure-Rust
//! CRFsuite model trained offline on spaCy silver labels.

mod features;
pub mod tokenize;
pub use features::sequence_features;
