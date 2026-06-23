//! CRF feature tests (gated). Determinism + back-compat: the additive typed path
//! must not perturb the existing gazetteer outputs.
#![cfg(feature = "crf")]

use lede_enrich::{extract_entities, extract_entities_typed, metadata};

#[test]
fn typed_is_deterministic() {
    let t = "Amazon hired Jeff Bezos in Seattle on 2024-01-15.";
    assert_eq!(extract_entities_typed(t), extract_entities_typed(t));
}

#[test]
fn typed_finds_known_entities_with_labels() {
    let ents = extract_entities_typed("Amazon hired Jeff Bezos in Seattle.");
    assert!(ents.iter().any(|e| e.label == "ORG"));
    assert!(ents.iter().any(|e| e.label == "PERSON"));
    // byte offsets slice back to the surface form:
    let t = "Amazon hired Jeff Bezos in Seattle.";
    for e in &ents {
        assert_eq!(&t[e.start..e.end], e.text);
    }
}

#[test]
fn additive_does_not_change_gazetteer_paths() {
    let t = "Dr. John Smith of Acme Corp visited Paris and London in 2024.";
    // Locked to actual gazetteer output (probed 2026-06-23).
    // The brief guessed ["John Smith", "Acme Corp", "Paris", "London"] but the
    // gazetteer merges the sequence into "John Smith of Acme Corp".
    assert_eq!(
        extract_entities(t),
        vec![
            "John Smith of Acme Corp".to_string(),
            "Paris".to_string(),
            "London".to_string(),
        ]
    );
    assert_eq!(metadata(t).entities, extract_entities(t));
}
