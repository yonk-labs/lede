use skimr::Mode;
use skimr::tfidf::{composite_score, length_score, position_score, summarize, tfidf_score};

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

#[test]
fn summarize_short_input_returns_unchanged() {
    let text = "Short text.";
    assert_eq!(summarize(text, 500, Mode::Legacy).summary, text);
}

#[test]
fn summarize_truncate_fallback_under_50_chars() {
    let text = "First sentence. Second sentence. Third sentence. Fourth sentence.";
    let result = summarize(text, 20, Mode::Legacy).summary;
    assert!(result.chars().count() <= 23);
    assert!(result.ends_with("..."));
}

#[test]
fn summarize_fewer_than_three_sentences_truncates() {
    let text = "One only sentence here in this input.";
    let result = summarize(text, 15, Mode::Legacy).summary;
    assert!(result.ends_with("..."));
}

#[test]
fn summarize_respects_char_budget() {
    let text = concat!(
        "Revenue grew 23% in Q4. ",
        "The Enterprise segment led growth. ",
        "Churn remained flat. ",
        "Dr. Smith analyzed the Q4 results. ",
        "Margins improved by 5 points.",
    );
    let result = summarize(text, 100, Mode::Legacy).summary;
    assert!(result.chars().count() <= 100);
}

#[test]
fn summarize_fixture_short_passthrough_byte_identical() {
    let fixture = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("rust crate parent dir")
        .join("fixtures/tfidf/short-passthrough");
    let input = std::fs::read_to_string(fixture.join("input.txt")).expect("read input");
    let expected = std::fs::read_to_string(fixture.join("expected.txt")).expect("read expected");
    assert_eq!(summarize(&input, 500, Mode::Legacy).summary, expected);
}
