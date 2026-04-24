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

// ----- T13e: optional word-form number support via text2num -----

#[cfg(feature = "wordforms")]
mod wordforms {
    use skimr::extract::stats::{stats, stats_with_options, StatsOptions};

    #[test]
    fn extracts_word_form_durations() {
        let text = "He stayed in staging for eight days. The project took two weeks.";
        let facts = stats_with_options(
            text,
            StatsOptions { convert_word_names: true },
        );
        let durs: Vec<(String, String)> = facts
            .iter()
            .filter(|f| f.stat_type == "duration")
            .map(|f| (f.value.clone(), f.unit.clone()))
            .collect();
        assert!(durs.contains(&("eight days".to_string(), "day".to_string())));
        assert!(durs.contains(&("two weeks".to_string(), "week".to_string())));
    }

    #[test]
    fn extracts_word_form_counts() {
        let text = "We saw five thousand users and processed seven hundred requests.";
        let facts = stats_with_options(
            text,
            StatsOptions { convert_word_names: true },
        );
        let values: Vec<String> = facts
            .iter()
            .filter(|f| f.stat_type == "count")
            .map(|f| f.value.clone())
            .collect();
        assert!(values.iter().any(|v| v.contains("five thousand")));
        assert!(values.iter().any(|v| v.contains("seven hundred")));
    }

    #[test]
    fn default_flag_off_unchanged() {
        // The plain stats() helper and explicit flag-off must agree, and
        // neither must surface word-forms.
        let text = "He stayed eight days and two weeks.";
        let a = stats(text);
        let b = stats_with_options(text, StatsOptions::default());
        assert_eq!(a, b);
        assert!(a.iter().all(|f| !f.value.to_lowercase().contains("eight")));
        assert!(a.iter().all(|f| !f.value.to_lowercase().contains("two")));
    }

    #[test]
    fn word_form_preserves_original_spans() {
        // Emitted value must be the ORIGINAL word-form text, not the digit.
        let text = "Retention was seven years after account closure.";
        let facts = stats_with_options(
            text,
            StatsOptions { convert_word_names: true },
        );
        let dur = facts
            .iter()
            .find(|f| f.stat_type == "duration")
            .expect("duration emitted");
        assert_eq!(dur.value, "seven years");
        assert!(dur.phrase.contains("seven years"));
        assert!(dur.context_sentence.contains("seven years"));
        // Crucially the digit form '7' must NOT appear.
        assert!(!dur.value.contains('7'));
    }

    #[test]
    fn word_form_and_digit_mix_in_same_text() {
        // Mixed digit + word-form input: both must surface.
        let text = "We ran for 5 minutes. Then idled for eight days.";
        let facts = stats_with_options(
            text,
            StatsOptions { convert_word_names: true },
        );
        let durs: Vec<String> = facts
            .iter()
            .filter(|f| f.stat_type == "duration")
            .map(|f| f.value.clone())
            .collect();
        assert!(durs.contains(&"5 minutes".to_string()));
        assert!(durs.contains(&"eight days".to_string()));
    }
}
