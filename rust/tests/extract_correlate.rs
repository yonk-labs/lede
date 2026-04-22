use skimr::extract::correlate::correlate_facts;

#[test]
fn correlates_entity_with_multiple_numbers() {
    let text = concat!(
        "Revenue grew 23 percent year over year. ",
        "Revenue for the quarter was $4.2 billion in total. ",
        "Revenue per customer rose by 8 percent."
    );
    let r = correlate_facts(text);
    assert!(r.iter().any(|pf| pf.entity.to_lowercase().contains("revenue")));
    assert!(r.iter().any(|pf| pf.polarity == "growth"));
}

#[test]
fn ignores_entities_appearing_once() {
    let text = "The server returned a 500 error. The team had lunch at noon.";
    let r = correlate_facts(text);
    assert!(r.is_empty());
}

#[test]
fn decline_polarity_detected() {
    let text = concat!(
        "Costs fell by 12 percent this quarter. ",
        "Costs declined by $5 million overall. ",
        "Costs decreased as staff reductions took effect."
    );
    let r = correlate_facts(text);
    assert!(r.iter().any(|pf| pf.entity.to_lowercase().contains("cost")));
    assert!(r.iter().any(|pf| pf.polarity == "decline"));
}

#[test]
fn empty_input() {
    assert!(correlate_facts("").is_empty());
}
