//! Facts: NER entity re-attribution over lede core's regex correlate_facts.
//! Not a parity promise against Python lede-spacy.

use lede_enrich::correlate_facts;

#[test]
fn reattributes_entity_with_ner_surface_form() {
    let text = "Apple grew fast. Apple reported revenue of $5 billion in 2024.";
    let facts = correlate_facts(text);
    assert!(!facts.is_empty(), "expected at least one fact");

    // Our facts carry the NER surface form ("Apple"), not core's lowercased word.
    assert!(
        facts.iter().any(|f| f.entity == "Apple"),
        "facts: {facts:?}"
    );

    // Contrast: lede core attributes the lowercased repeated word.
    let core = lede::extract::correlate::correlate_facts(text);
    assert!(core.iter().any(|f| f.entity == "apple"), "core: {core:?}");
}

#[test]
fn deterministic() {
    let text = "Apple grew fast. Apple reported revenue of $5 billion in 2024.";
    assert_eq!(correlate_facts(text), correlate_facts(text));
}
