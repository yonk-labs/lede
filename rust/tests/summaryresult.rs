use lede::{AttachOpts, Mode, SummaryResult, summarize, summarize_with_attach};

#[test]
fn display_returns_summary() {
    let r = summarize("Hello world. This is a test sentence.", 100, Mode::Default);
    assert_eq!(format!("{r}"), r.summary);
}

#[test]
fn default_has_no_attachments() {
    let r = summarize("Sentence one. Sentence two.", 80, Mode::Default);
    assert!(r.stats.is_none());
    assert!(r.outline.is_none());
    assert!(r.metadata.is_none());
    assert!(r.phrases.is_none());
    assert!(r.correlated_facts.is_none());
}

#[test]
fn attach_all_populates_every_field() {
    let opts = AttachOpts {
        stats: true,
        outline: true,
        metadata: true,
        phrases: true,
        correlated_facts: true,
    };
    let r = summarize_with_attach("Sentence A. Sentence B.", 100, Mode::Default, &opts);
    assert!(r.stats.is_some());
    assert!(r.outline.is_some());
    assert!(r.metadata.is_some());
    assert!(r.phrases.is_some());
    assert!(r.correlated_facts.is_some());
}

#[test]
fn attach_nothing_gives_bare_result() {
    let opts = AttachOpts::default();
    let r = summarize_with_attach("Sentence A. Sentence B.", 100, Mode::Default, &opts);
    assert!(r.stats.is_none());
    assert!(r.outline.is_none());
    assert!(r.metadata.is_none());
    assert!(r.phrases.is_none());
    assert!(r.correlated_facts.is_none());
}

#[test]
fn bare_constructor_produces_empty_attachments() {
    let r = SummaryResult::bare("hi".into());
    assert_eq!(r.summary, "hi");
    assert!(r.stats.is_none());
}
