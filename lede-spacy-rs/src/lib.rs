//! lede-spacy-rs — deterministic, license-clean spaCy-`sm`-class NER + numeric
//! facts for the lede Rust path. Companion to the Python `lede-spacy` package.
//!
//! M1 default path bundles **no trained weights**: gazetteer + capitalization/
//! shape-rule NER, the core's regex date/money/url metadata, and (slice 2) regex
//! facts re-attributed with NER entities. Higher-recall POS/CRF models are an
//! opt-in, download-on-build feature — never bundled (PTB/LDC licensing).
//!
//! No cross-language byte-parity with Python `lede-spacy` is promised — this is
//! spaCy-`sm`-*class*, not byte-identical. Output is deterministic within Rust.
//!
//! Spec: `docs/superpowers/specs/2026-06-22-lede-spacy-rs-m1-design.md`.

mod facts;
mod gazetteer;
mod lemma;
mod ner;
#[cfg(feature = "pos")]
mod pos;

pub use facts::correlate_facts;
pub use lemma::lemma;
pub use ner::extract_entities;

#[cfg(feature = "pos")]
pub use facts::correlate_facts_pos;
#[cfg(feature = "pos")]
pub use pos::pos_tag;

use lede::extract::metadata::{Metadata, metadata as core_metadata};

/// lede core regex metadata (dates / amounts / urls) plus NER `entities`.
///
/// The deterministic fields come straight from `lede`'s regex path (byte-identical
/// to `backend="regex"`); `entities` is filled by [`extract_entities`]. Mirrors
/// Python `lede_spacy.spacy_metadata`.
#[must_use]
pub fn metadata(text: &str) -> Metadata {
    let mut m = core_metadata(text);
    m.entities = extract_entities(text);
    m
}
