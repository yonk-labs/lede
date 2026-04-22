use skimr::extract::phrases::phrases;

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
    let r = phrases("This unique term shows up only once elsewhere never again.", None);
    assert!(r.is_empty());
}

#[test]
fn keywords_include_hits() {
    let r = phrases("Revenue grew. Costs fell. Margins expanded.", Some("revenue"));
    assert!(r.iter().any(|p| p.to_lowercase().contains("revenue")));
}

#[test]
fn empty_input() {
    assert!(phrases("", None).is_empty());
}
