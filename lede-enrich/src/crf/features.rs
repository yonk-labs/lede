//! Shared CRF feature extraction. Returns `Vec<Vec<String>>` (one feature-string
//! list per token) — deliberately free of `crfs` types so it is unit-testable on
//! its own and reused verbatim by both the trainer and inference.
