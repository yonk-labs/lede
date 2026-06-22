//! Opt-in POS feature tests. Run with `cargo test --features pos`.

#![cfg(feature = "pos")]

use lede_enrich::{correlate_facts_pos, pos_tag};

#[test]
fn pos_tags_basic() {
    let tags = pos_tag("Apple rose sharply in 2024");
    assert!(tags.iter().any(|(t, g)| t == "Apple" && g == "PROPN"));
    assert!(tags.iter().any(|(t, g)| t == "rose" && g == "VERB"));
    assert!(tags.iter().any(|(t, g)| t == "in" && g == "ADP"));
    assert!(tags.iter().any(|(t, g)| t == "2024" && g == "NUM"));
}

#[test]
fn pos_facts_recall_and_verb_polarity() {
    // Single mention ("Apple" once) -> core's repeated-word path yields no fact,
    // but the POS path emits one per stat co-occurring with an NER entity, with
    // verb-scoped polarity.
    let text = "Apple revenue rose to $5 billion in 2024.";
    let facts = correlate_facts_pos(text);
    assert!(
        facts
            .iter()
            .any(|f| f.entity == "Apple" && f.polarity == "growth"),
        "facts: {facts:?}"
    );
}

#[test]
fn deterministic() {
    let text = "Apple revenue rose to $5 billion in 2024.";
    assert_eq!(correlate_facts_pos(text), correlate_facts_pos(text));
}
