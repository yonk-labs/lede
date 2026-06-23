use lede::extract::metadata::metadata;

#[test]
fn collects_iso_dates() {
    let m = metadata("Contract signed 2025-06-14; renewal 2026-01-01.");
    assert!(m.dates.iter().any(|d| d == "2025-06-14"));
    assert!(m.dates.iter().any(|d| d == "2026-01-01"));
}

#[test]
fn collects_money_amounts() {
    let m = metadata("Budget $120K; overage $45,000.");
    assert!(m.amounts.iter().any(|a| a.contains("120")));
    assert!(m.amounts.iter().any(|a| a.contains("45")));
}

#[test]
fn collects_urls() {
    let m = metadata("See https://example.com/docs and http://example.org for details.");
    assert!(m.urls.iter().any(|u| u == "https://example.com/docs"));
    assert!(m.urls.iter().any(|u| u == "http://example.org"));
}

#[test]
fn entities_always_empty_in_rust() {
    let m = metadata("Sarah Jones visited Johnson Education Co in Chicago.");
    assert!(
        m.entities.is_empty(),
        "Rust port does not populate entities"
    );
}

#[test]
fn empty_on_empty_text() {
    let m = metadata("");
    assert!(m.dates.is_empty());
    assert!(m.amounts.is_empty());
    assert!(m.urls.is_empty());
    assert!(m.entities.is_empty());
}

#[test]
fn currency_prefix_amounts() {
    // T13h: currency code before number (e.g. "EUR 2.3 billion") captured as amount.
    let m = metadata("We raised EUR 2.3 billion and spent USD 5 million.");
    assert!(
        m.amounts.iter().any(|a| a.contains("2.3")),
        "EUR prefix not in amounts: {:?}",
        m.amounts,
    );
    assert!(
        m.amounts.iter().any(|a| a.contains('5')),
        "USD prefix not in amounts: {:?}",
        m.amounts,
    );
}
