use lede::extract::phrases::phrases;

#[test]
fn finds_repeated_multiword_terms() {
    let text = concat!(
        "The customer support team evaluated the deployment pipeline. ",
        "The deployment pipeline is critical to the customer support team."
    );
    let r = phrases(text, None);
    let joined = r.join(" | ");
    assert!(joined.contains("deployment pipeline"));
    assert!(joined.contains("customer support"));
}

#[test]
fn ignores_singletons() {
    let r = phrases(
        "This unique term shows up only once elsewhere never again.",
        None,
    );
    assert!(r.is_empty());
}

#[test]
fn keywords_include_hits() {
    let r = phrases(
        "Revenue grew. Costs fell. Margins expanded.",
        Some("revenue"),
    );
    assert!(r.iter().any(|p| p.to_lowercase().contains("revenue")));
}

#[test]
fn empty_input() {
    assert!(phrases("", None).is_empty());
}

// -------- T13h: subsumption — drop redundant sub-ngrams --------

#[test]
fn subsumption_drops_redundant_sub_ngrams() {
    // "environmental protection" and "protection agency" are fully absorbed
    // by "environmental protection agency" at equal count.
    let text = concat!(
        "The environmental protection agency is important. ",
        "We believe the environmental protection agency does good work. ",
        "The environmental protection agency announced new rules."
    );
    let out = phrases(text, None);
    assert!(out.iter().any(|p| p == "environmental protection agency"));
    assert!(!out.iter().any(|p| p == "environmental protection"));
    assert!(!out.iter().any(|p| p == "protection agency"));
}

#[test]
fn subsumption_preserves_independently_appearing_sub_ngram() {
    // "united states" appears more often than any containing ngram -> preserved.
    let text = concat!(
        "The United States is a country. ",
        "The United States Environmental Protection Agency is an org. ",
        "The United States requires compliance. ",
        "United States citizens have rights. ",
        "The United States Environmental Protection Agency regulates."
    );
    let out = phrases(text, None);
    assert!(out.iter().any(|p| p == "united states"));
}
