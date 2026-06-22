//! Determinism + "metadata reuses lede core" checks. The bar for lede-enrich
//! is Rust-internal reproducibility (same input -> same bytes), not Python<->Rust
//! byte-parity.

use lede_enrich::{extract_entities, metadata};

#[test]
fn entities_deterministic() {
    let text = "Dr. John Smith of Acme Corp visited Paris and London in 2024.";
    assert_eq!(extract_entities(text), extract_entities(text));
}

#[test]
fn metadata_deterministic_and_reuses_core() {
    let text = "Revenue rose to $5 million on 2024-01-15 per Acme Corp.";
    let a = metadata(text);
    let b = metadata(text);
    assert_eq!(a, b);

    // entities come from our NER:
    assert_eq!(a.entities, extract_entities(text));

    // deterministic fields come straight from lede core (unchanged):
    let core = lede::extract::metadata::metadata(text);
    assert_eq!(a.dates, core.dates);
    assert_eq!(a.amounts, core.amounts);
    assert_eq!(a.urls, core.urls);
}
