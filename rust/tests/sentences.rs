use skimr::sentences::split_sentences;

#[test]
fn empty_input_returns_empty_vec() {
    assert_eq!(split_sentences(""), Vec::<String>::new());
}

#[test]
fn single_sentence_no_terminator() {
    assert_eq!(
        split_sentences("Hello world"),
        vec!["Hello world".to_string()]
    );
}

#[test]
fn two_sentences_on_period_space_upper() {
    let out = split_sentences("First. Second.");
    assert_eq!(out, vec!["First.".to_string(), "Second.".to_string()]);
}

#[test]
fn protects_decimals() {
    let out = split_sentences("Revenue grew 23.5 percent. Margins held.");
    assert_eq!(
        out,
        vec![
            "Revenue grew 23.5 percent.".to_string(),
            "Margins held.".to_string(),
        ]
    );
}

#[test]
fn protects_abbreviation_dr() {
    let out = split_sentences("Dr. Smith analyzed the results. He was impressed.");
    assert_eq!(
        out,
        vec![
            "Dr. Smith analyzed the results.".to_string(),
            "He was impressed.".to_string(),
        ]
    );
}

#[test]
fn protects_dotted_abbreviation_us() {
    let out = split_sentences("The U.S. market declined. Europe held.");
    assert_eq!(
        out,
        vec![
            "The U.S. market declined.".to_string(),
            "Europe held.".to_string(),
        ]
    );
}

#[test]
fn paragraph_break_splits() {
    let out = split_sentences("First paragraph\n\nSecond paragraph");
    assert_eq!(
        out,
        vec![
            "First paragraph".to_string(),
            "Second paragraph".to_string(),
        ]
    );
}

#[test]
fn no_split_on_lowercase_after_period() {
    let out = split_sentences("See etc. see below.");
    assert_eq!(out, vec!["See etc. see below.".to_string()]);
}

#[test]
fn nul_sentinel_in_input_is_silently_stripped() {
    // Earlier behavior panicked; AAT-019 changed this to silent strip
    // because NUL bytes can show up in PDF-extracted text and an
    // aborting splitter is hostile.
    let out = split_sentences("before\x00after. Second sentence.");
    assert_eq!(
        out,
        vec!["beforeafter.".to_string(), "Second sentence.".to_string()]
    );
}
