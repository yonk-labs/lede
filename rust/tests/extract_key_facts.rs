use lede::extract::key_facts::{KeyFactsOptions, key_facts, key_facts_with_options};

#[test]
fn key_facts_returns_sentences_containing_stats() {
    let text = concat!(
        "Unit tests pass at 94 percent coverage. ",
        "The team saw 20 users onboard last quarter. ",
        "Some unrelated prose without numbers. ",
        "Deploy takes 5 minutes on average.",
    );
    let out = key_facts(text, 10);
    assert!(out.iter().any(|s| s.contains("94 percent")));
    assert!(out.iter().any(|s| s.contains("20 users")));
    assert!(out.iter().any(|s| s.contains("5 minutes")));
    assert!(!out.iter().any(|s| s.contains("unrelated prose")));
}

#[test]
fn key_facts_respects_max_facts() {
    let text = "We saw 1 event. Then 2 events. Then 3 events. Then 4 events. Then 5 events.";
    let out = key_facts(text, 2);
    assert_eq!(out.len(), 2);
}

#[test]
fn key_facts_returns_document_order() {
    let text = concat!(
        "Revenue rose 40 percent in Q1. ",
        "Middle sentence with no stat. ",
        "Costs fell 12 percent over the year.",
    );
    let out = key_facts(text, 10);
    let q1_idx = out.iter().position(|s| s.contains("40 percent"));
    let q4_idx = out.iter().position(|s| s.contains("12 percent"));
    assert!(q1_idx.is_some());
    assert!(q4_idx.is_some());
    assert!(q1_idx.unwrap() < q4_idx.unwrap());
}

#[test]
fn key_facts_dedups_same_fact_across_sentences() {
    let text = concat!(
        "We processed 50,000 events in the pilot. ",
        "Later analysis confirmed 50,000 events were processed. ",
        "Totally separate: 3 percent error rate was observed.",
    );
    let out = key_facts(text, 10);
    let count = out.iter().filter(|s| s.contains("50,000 events")).count();
    assert_eq!(count, 1);
    assert!(out.iter().any(|s| s.contains("3 percent")));
}

#[test]
fn key_facts_empty_for_no_stats() {
    let text = "Just prose here. No numbers anywhere. Nothing to extract.";
    assert!(key_facts(text, 10).is_empty());
}

#[test]
fn key_facts_with_options_max_facts_override() {
    let text = "We saw 1 event. Then 2 events. Then 3 events.";
    let out = key_facts_with_options(
        text,
        KeyFactsOptions {
            max_facts: 1,
            convert_word_names: false,
            ..Default::default()
        },
    );
    assert_eq!(out.len(), 1);
}

#[cfg(feature = "wordforms")]
#[test]
fn key_facts_word_forms_when_enabled() {
    let text = "The project took eight days. Coverage improved to 94 percent.";
    let out = key_facts_with_options(
        text,
        KeyFactsOptions {
            max_facts: 10,
            convert_word_names: true,
        },
    );
    assert!(out.iter().any(|s| s.contains("eight days")));
    assert!(out.iter().any(|s| s.contains("94 percent")));
}
