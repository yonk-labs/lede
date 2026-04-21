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
