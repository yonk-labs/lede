use lede::hints::{
    HINT_BASE_WEIGHT, HINT_MATCH_CAP, HintMode, HintWeight, hint_bonus, match_count,
    preprocess_hints, round_to_int, select_by_chars, select_by_count,
};
use std::collections::HashSet;

#[test]
fn preprocess_lowercases_and_strips() {
    let input = vec![
        ("  County  ".to_string(), 1.0),
        ("John SMITH".to_string(), 1.0),
    ];
    assert_eq!(
        preprocess_hints(&input),
        vec![("county".to_string(), 1.0), ("john smith".to_string(), 1.0)]
    );
}

#[test]
fn preprocess_collapses_internal_whitespace() {
    let input = vec![("John   Smith".to_string(), 1.0)];
    assert_eq!(
        preprocess_hints(&input),
        vec![("john smith".to_string(), 1.0)]
    );
}

#[test]
fn preprocess_drops_empty() {
    let input = vec![
        (String::new(), 1.0),
        ("  ".to_string(), 1.0),
        ("county".to_string(), 1.0),
    ];
    assert_eq!(preprocess_hints(&input), vec![("county".to_string(), 1.0)]);
}

#[test]
fn match_count_word_boundary() {
    assert_eq!(match_count("smith", "John Smith lives there"), 1);
    assert_eq!(match_count("smith", "blacksmith works late"), 0);
    assert_eq!(match_count("smith", "the smiths arrived"), 0);
}

#[test]
fn match_count_phrase() {
    assert_eq!(match_count("john smith", "John Smith Sr. is here"), 1);
    assert_eq!(match_count("john smith", "John P. Smith arrived"), 0);
}

#[test]
fn match_count_multiple_non_overlapping() {
    assert_eq!(match_count("smith", "Smith spoke. Then Smith left."), 2);
}

#[test]
fn match_count_apostrophe() {
    assert_eq!(match_count("o'brien", "O'Brien arrived early"), 1);
}

#[test]
fn match_count_hyphenated_phrase() {
    assert_eq!(
        match_count("state-of-the-art", "state-of-the-art design here"),
        1
    );
}

#[test]
fn match_count_empty_hint_zero() {
    assert_eq!(match_count("", "anything"), 0);
}

#[test]
fn round_to_int_matches_python() {
    assert_eq!(round_to_int(500, 0.0), 0);
    assert_eq!(round_to_int(500, 1.0), 500);
    assert_eq!(round_to_int(500, 0.5), 250);
    assert_eq!(round_to_int(501, 0.5), 251); // half-up
    assert_eq!(round_to_int(500, 0.7), 350);
    assert_eq!(round_to_int(10, 0.7), 7);
}

#[test]
fn hint_bonus_no_hints_returns_zero() {
    let hints: Vec<HintWeight> = vec![];
    assert!(hint_bonus("John Smith lives there", &hints).abs() < f64::EPSILON);
}

#[test]
fn hint_bonus_single_match() {
    let hints = vec![("smith".to_string(), 1.0)];
    // 1 * 1.0 * 0.5 = 0.5
    assert!((hint_bonus("John Smith lives", &hints) - 0.5).abs() < f64::EPSILON);
}

#[test]
fn hint_bonus_caps_at_three() {
    let hints = vec![("smith".to_string(), 1.0)];
    // 5 occurrences capped at 3: 3 * 1.0 * 0.5 = 1.5
    assert!((hint_bonus("Smith Smith Smith Smith Smith", &hints) - 1.5).abs() < f64::EPSILON);
}

#[test]
fn hint_bonus_per_hint_weight() {
    let hints = vec![("smith".to_string(), 2.0)];
    // 1 * 2.0 * 0.5 = 1.0
    assert!((hint_bonus("Smith here", &hints) - 1.0).abs() < f64::EPSILON);
}

#[test]
fn hint_bonus_multi_hint_sum() {
    let hints = vec![("smith".to_string(), 1.0), ("county".to_string(), 1.0)];
    // (1*1.0*0.5) + (1*1.0*0.5) = 1.0
    assert!((hint_bonus("Smith lives in Cook County", &hints) - 1.0).abs() < f64::EPSILON);
}

#[test]
fn select_by_chars_simple_budget() {
    let scores = vec![1.0, 2.0];
    let lengths = vec![10, 20];
    let exclude: HashSet<usize> = HashSet::new();
    let chosen = select_by_chars(&scores, &lengths, 25, &exclude, 1);
    let expected: HashSet<usize> = [1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_chars_separator_accounted() {
    let scores = vec![1.0, 0.9, 0.8];
    let lengths = vec![10, 10, 10];
    let exclude: HashSet<usize> = HashSet::new();
    let chosen = select_by_chars(&scores, &lengths, 22, &exclude, 1);
    let expected: HashSet<usize> = [0, 1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_chars_excludes_skipped() {
    let scores = vec![2.0, 1.0];
    let lengths = vec![10, 10];
    let exclude: HashSet<usize> = [0].into_iter().collect();
    let chosen = select_by_chars(&scores, &lengths, 20, &exclude, 1);
    let expected: HashSet<usize> = [1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_chars_zero_budget_empty() {
    let chosen = select_by_chars(&[1.0], &[10], 0, &HashSet::new(), 1);
    assert!(chosen.is_empty());
}

#[test]
fn select_by_chars_neg_infinity_skipped() {
    let scores = vec![f64::NEG_INFINITY, 1.0];
    let lengths = vec![10, 10];
    let chosen = select_by_chars(&scores, &lengths, 50, &HashSet::new(), 1);
    let expected: HashSet<usize> = [1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_count_simple_topn() {
    let scores = vec![0.5, 1.0, 0.3, 0.9];
    let chosen = select_by_count(&scores, 2, &HashSet::new());
    let expected: HashSet<usize> = [1, 3].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_count_position_tiebreak() {
    let scores = vec![1.0, 1.0, 1.0];
    let chosen = select_by_count(&scores, 2, &HashSet::new());
    let expected: HashSet<usize> = [0, 1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_count_excludes_skipped() {
    let scores = vec![2.0, 1.0, 0.5];
    let exclude: HashSet<usize> = [0].into_iter().collect();
    let chosen = select_by_count(&scores, 2, &exclude);
    let expected: HashSet<usize> = [1, 2].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn select_by_count_zero_empty() {
    let chosen = select_by_count(&[1.0, 2.0], 0, &HashSet::new());
    assert!(chosen.is_empty());
}

#[test]
fn select_by_count_neg_infinity_skipped() {
    let scores = vec![f64::NEG_INFINITY, 1.0];
    let chosen = select_by_count(&scores, 2, &HashSet::new());
    let expected: HashSet<usize> = [1].into_iter().collect();
    assert_eq!(chosen, expected);
}

#[test]
fn constants_match_python() {
    assert!((HINT_BASE_WEIGHT - 0.5).abs() < f64::EPSILON);
    assert_eq!(HINT_MATCH_CAP, 3);
}

// Verify HintMode variants are accessible (they're exported for use by T10/T11).
#[test]
fn hint_mode_variants_accessible() {
    assert_eq!(HintMode::Soft, HintMode::Soft);
    assert_eq!(HintMode::Hard, HintMode::Hard);
    assert_ne!(HintMode::Soft, HintMode::Hard);
}
