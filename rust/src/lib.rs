//! skimr — deterministic extractive summarization.
//!
//! Public API mirrors the Python reference in `src/skimr/`. Every function here
//! must produce byte-identical output to its Python twin on every fixture in
//! `../fixtures/`. See the mission brief for the full contract.

pub mod clean;
pub mod sentences;
