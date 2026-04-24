use skimr::extract::stats::stats;

#[test]
fn stats_finds_money() {
    let r = stats("Our Q2 budget was $120K and we spent $45,000 on licenses.");
    let money: Vec<_> = r.iter().filter(|s| s.stat_type == "money").collect();
    assert!(money.iter().any(|s| s.value.contains("120")));
    assert!(money.iter().any(|s| s.value.contains("45")));
    for s in &money {
        assert_eq!(s.unit, "usd");
    }
}

#[test]
fn stats_finds_percent() {
    let r = stats("Revenue grew by 23 percent last quarter and margins improved 8%.");
    let pcts: Vec<_> = r.iter().filter(|s| s.stat_type == "percent").collect();
    assert!(pcts.len() >= 2);
    assert!(pcts.iter().any(|s| s.value.contains("23")));
    assert!(pcts.iter().any(|s| s.value.contains('8')));
}

#[test]
fn stats_finds_dates() {
    let r = stats("Contract signed on 2025-06-14, effective 2026-01-01.");
    let dates: Vec<_> = r.iter().filter(|s| s.stat_type == "date").collect();
    assert!(dates.iter().any(|s| s.value == "2025-06-14"));
    assert!(dates.iter().any(|s| s.value == "2026-01-01"));
}

#[test]
fn stats_finds_durations() {
    let r = stats("Migration will take 3 months. Warranty covers 5 years.");
    let durs: Vec<_> = r.iter().filter(|s| s.stat_type == "duration").collect();
    assert!(durs.iter().any(|s| s.value.contains('3')));
    assert!(durs.iter().any(|s| s.value.contains('5')));
}

#[test]
fn stats_empty_on_no_numbers() {
    assert!(stats("No numbers here.").is_empty());
    assert!(stats("").is_empty());
}

#[test]
fn stats_extracts_bare_year_as_date() {
    // T13a: bare 4-digit years in 1900-2099 emit as stat_type='date'.
    let text = "Proposed by Bentley in 1975. Refined by Malkov in 2016.";
    let facts = stats(text);
    let years: Vec<_> = facts
        .iter()
        .filter(|f| f.stat_type == "date")
        .map(|f| f.value.as_str())
        .collect();
    assert!(years.contains(&"1975"));
    assert!(years.contains(&"2016"));
}

#[test]
fn stats_extracts_hyphenated_duration() {
    // T13a: hyphenated number-unit forms like '90-day' match.
    let text = "We keep a 90-day retention window. The 14-day trial ends soon.";
    let durs: Vec<(String, String)> = stats(text)
        .iter()
        .filter(|f| f.stat_type == "duration")
        .map(|f| (f.value.clone(), f.unit.clone()))
        .collect();
    assert!(durs.contains(&("90 day".to_string(), "day".to_string())));
    assert!(durs.contains(&("14 day".to_string(), "day".to_string())));
}

#[test]
fn stats_extracts_basis_points_and_terabytes() {
    // T13a: added count keywords 'basis points' and 'terabytes'.
    let text = "Yields climbed 8 basis points. Volume reached 2 terabytes per day.";
    let counts: Vec<(String, String)> = stats(text)
        .iter()
        .filter(|f| f.stat_type == "count")
        .map(|f| (f.value.clone(), f.unit.clone()))
        .collect();
    assert!(counts.contains(&("8".to_string(), "basis points".to_string())));
    assert!(counts.contains(&("2".to_string(), "terabytes".to_string())));
}
