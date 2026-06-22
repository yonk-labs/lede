//! Golden snapshots for the rule-based NER. These pin observed behavior; they
//! are NOT a parity promise against Python lede-spacy (which uses spaCy).

use lede_enrich::extract_entities;

#[test]
fn person_with_title_and_place() {
    let got = extract_entities("Dr. John Smith visited Cook County last week.");
    assert_eq!(
        got,
        vec!["John Smith".to_string(), "Cook County".to_string()]
    );
}

#[test]
fn org_gazetteer_rescues_sentence_initial() {
    let got = extract_entities("Apple announced a deal in California.");
    assert_eq!(got, vec!["Apple".to_string(), "California".to_string()]);
}

#[test]
fn rejects_sentence_initial_common_word() {
    let got = extract_entities("However, sales rose sharply.");
    assert!(got.is_empty(), "got: {got:?}");
}

#[test]
fn org_suffix_and_ampersand() {
    let got = extract_entities("The deal with Smith & Co was signed.");
    assert_eq!(got, vec!["Smith & Co".to_string()]);
}

#[test]
fn does_not_merge_separate_entities_across_and() {
    // Regression: "and" must not join two entities into one (found vs spaCy).
    let got = extract_entities("Investors back Volkswagen and BMW today.");
    assert!(got.contains(&"Volkswagen".to_string()), "got: {got:?}");
    assert!(got.contains(&"BMW".to_string()), "got: {got:?}");
    assert!(!got.iter().any(|e| e.contains("and")), "got: {got:?}");
}

#[test]
fn excludes_month_names_from_entities() {
    // Month names are dates (in metadata.dates), not entities — matches spaCy.
    let got = extract_entities("Microsoft acquired GitHub on January 5, 2018.");
    assert!(!got.iter().any(|e| e == "January"), "got: {got:?}");
    assert!(got.contains(&"Microsoft".to_string()), "got: {got:?}");
}

#[test]
fn dedups_first_appearance_order() {
    let got = extract_entities("France beat Brazil. Brazil then beat France.");
    assert_eq!(got, vec!["France".to_string(), "Brazil".to_string()]);
}

#[test]
fn drops_capitalized_common_nouns_and_possessives() {
    // #12: "Company"/"Product"/"Launch"/"Spring" are common nouns; "Our Team"
    // loses its possessive and "Team" is a common noun — none are entities.
    let got = extract_entities(
        "The Company released a new Product. Our Team celebrated the Launch in Spring.",
    );
    assert!(got.is_empty(), "expected no entities, got: {got:?}");
}

#[test]
fn strips_corporate_titles_keeps_people_and_places() {
    // #12: "CEO"/"President" strip like "Dr." → consistent person extraction.
    let got =
        extract_entities("Dr. Jane Doe met CEO Bob Smith and President Lincoln in Washington.");
    assert_eq!(
        got,
        vec![
            "Jane Doe".to_string(),
            "Bob Smith".to_string(),
            "Lincoln".to_string(),
            "Washington".to_string(),
        ]
    );
}

#[test]
fn drops_bare_currency_code() {
    // #12: "EUR" is part of an amount, not a named entity.
    let got = extract_entities("We spent EUR on travel.");
    assert!(!got.iter().any(|e| e == "EUR"), "got: {got:?}");
}
