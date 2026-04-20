use skimr::tfidf::{composite_score, length_score, position_score, tfidf_score};

#[test]
fn tfidf_returns_normalized_list() {
    let sentences = vec![
        "apple banana cherry".to_string(),
        "apple date elderberry".to_string(),
        "cherry date fig".to_string(),
    ];
    let scores = tfidf_score(&sentences);
    assert_eq!(scores.len(), 3);
    for s in &scores {
        assert!((0.0..=1.0).contains(s));
    }
    assert!(scores.iter().copied().fold(0.0_f64, f64::max) > 0.0);
}

#[test]
fn position_first_and_last_highest() {
    let scores = position_score(5);
    assert_eq!(scores.len(), 5);
    assert!((scores[0] - 1.0).abs() < 1e-12);
    assert!((scores[4] - 1.0).abs() < 1e-12);
    assert!(scores[2] < scores[0]);
    assert!(scores[2] < scores[4]);
}

#[test]
fn position_single_sentence() {
    assert_eq!(position_score(1), vec![1.0]);
}

#[test]
fn length_score_sweet_spot_peaks_in_middle() {
    let short = "one two three".to_string();
    let mid = "word ".repeat(20).trim().to_string();
    let long = "word ".repeat(100).trim().to_string();
    let sentences = vec![short, mid, long];
    let scores = length_score(&sentences);
    let max = scores.iter().copied().fold(0.0_f64, f64::max);
    assert!((scores[1] - max).abs() < 1e-12);
    assert!(scores[0] < scores[1]);
    assert!(scores[2] < scores[1]);
}

#[test]
fn composite_in_range() {
    let sentences = vec![
        "pricing budget pricing budget pricing".to_string(),
        "the ".repeat(17).trim().to_string(),
        "unique distinctive singular".to_string(),
    ];
    let composite = composite_score(&sentences);
    assert_eq!(composite.len(), 3);
    for s in &composite {
        assert!((0.0..=1.0).contains(s));
    }
}
