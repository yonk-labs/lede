use lede::extract::correlate::correlate_facts;

#[test]
fn correlates_entity_with_multiple_numbers() {
    let text = concat!(
        "Revenue grew 23 percent year over year. ",
        "Revenue for the quarter was $4.2 billion in total. ",
        "Revenue per customer rose by 8 percent."
    );
    let r = correlate_facts(text);
    assert!(
        r.iter()
            .any(|pf| pf.entity.to_lowercase().contains("revenue"))
    );
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

#[test]
fn correlate_facts_excludes_stopword_entities() {
    // Regression for T13c: `the`, `their` etc. were leaking as entity candidates.
    let text = concat!(
        "The project finished its first phase. The team grew by 5 people. ",
        "The team grew by 10 people. The latency dropped by 20 ms. ",
        "The latency dropped by 30 ms."
    );
    let facts = correlate_facts(text);
    let stopwords = ["the", "its", "by"];
    for pf in &facts {
        assert!(
            !stopwords.contains(&pf.entity.as_str()),
            "stopword entity leaked through: {}",
            pf.entity
        );
    }
}

#[cfg(feature = "wordforms")]
#[test]
fn correlate_facts_with_options_propagates_convert_word_names() {
    // T13e: correlate_facts_with_options forwards the flag to stats().
    use lede::extract::correlate::correlate_facts_with_options;
    use lede::extract::stats::StatsOptions;

    let text = concat!(
        "Retention was seven years after account closure. ",
        "New regime extended it to thirteen months. ",
        "After compliance review it dropped to thirty days. ",
        "Retention was adjusted again to sixty days."
    );
    // Without flag: no word-form stats → no pairings.
    assert!(correlate_facts(text).is_empty());
    // With flag: at least one pairing should surface.
    let pairings = correlate_facts_with_options(
        text,
        StatsOptions {
            convert_word_names: true,
        },
    );
    assert!(
        !pairings.is_empty(),
        "expected at least one pairing with word-form stats"
    );
}
