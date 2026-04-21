use skimr::{Mode, summarize};

#[test]
fn coverage_picks_one_per_paragraph() {
    let text = concat!(
        "Para one sentence A is here. Para one sentence B is here.\n\n",
        "Para two sentence A is here. Para two sentence B is here.\n\n",
        "Para three sentence A is here. Para three sentence B is here."
    );
    let r = summarize(text, 500, Mode::Coverage);
    assert_eq!(r.summary.matches("Para one").count(), 1);
    assert_eq!(r.summary.matches("Para two").count(), 1);
    assert_eq!(r.summary.matches("Para three").count(), 1);
}

#[test]
fn coverage_respects_budget() {
    let paras: Vec<String> = (0..6)
        .map(|i| format!("Paragraph number {i} content sentence goes here with stuff."))
        .collect();
    let text = paras.join("\n\n");
    let r = summarize(&text, 200, Mode::Coverage);
    assert!(r.summary.len() <= 220);
}

#[test]
fn coverage_ignores_tiny_paragraphs() {
    let text = concat!(
        "Tiny.\n\n",
        "This second paragraph has enough characters to count here. ",
        "And another sentence. ",
        "And a third to pick from.\n\n",
        "Ok."
    );
    let r = summarize(text, 200, Mode::Coverage);
    assert!(!r.summary.contains("Tiny"));
    assert!(
        r.summary.contains("second paragraph")
            || r.summary.contains("another")
            || r.summary.contains("third")
    );
}

#[test]
fn coverage_splits_ends_support_ticket_style() {
    let text = concat!(
        "Ticket opened about ingest hang after upgrade. ",
        "Job hangs indefinitely with no error output.\n\n",
        "Investigation revealed that the new embedder attempts a model download. ",
        "Air-gapped batch nodes cannot reach HuggingFace.\n\n",
        "Resolution: pin precision to fp32 and disable downloads. ",
        "Ticket closed after overnight job completed in 19 minutes."
    );
    let r = summarize(text, 400, Mode::Coverage);
    assert!(r.summary.contains("Ticket") || r.summary.contains("hang"));
    assert!(r.summary.contains("Resolution") || r.summary.contains("closed"));
}
