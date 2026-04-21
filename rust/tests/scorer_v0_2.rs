//! v0.2 scorer tests — `Mode::Default` tweaks.
//!
//! Mirrors the Python tests in `tests/skimr/test_scorer_v0_2.py`. Exercises
//! heading filter, cue-phrase boost, digit bonus, and section-position weight.

use skimr::{Mode, summarize};

#[test]
fn heading_filter_drops_markdown() {
    let text = concat!(
        "# Title\n",
        "Sarah led the walkthrough. Jon covered integration questions. ",
        "Main concern is pricing at $50K.\n\n",
        "## Next Steps\n",
        "Follow up Monday. Decision Tuesday."
    );
    let r = summarize(text, 200, Mode::Default);
    assert!(!r.summary.contains("# Title"));
    assert!(!r.summary.contains("## Next Steps"));
}

#[test]
fn heading_filter_drops_allcaps() {
    let text = concat!(
        "INTRODUCTION\n",
        "The company grew revenue by 23 percent last quarter. ",
        "Costs declined by 8 percent. ",
        "HELD: revenue growth is the primary driver."
    );
    let r = summarize(text, 150, Mode::Default);
    assert!(!r.summary.contains("INTRODUCTION"));
}

#[test]
fn cue_phrase_boost_picks_held() {
    let text = concat!(
        "Revenue grew last quarter by ten percent. ",
        "Costs were flat year over year. ",
        "Held: the deal terms are binding through 2027. ",
        "Meetings continue next week."
    );
    let r = summarize(text, 150, Mode::Default);
    assert!(r.summary.contains("Held"), "got: {:?}", r.summary);
}

#[test]
fn legacy_mode_does_not_filter_headings() {
    let text = "# Title\nSentence one. Sentence two. Sentence three.";
    let r = summarize(text, 120, Mode::Legacy);
    assert!(r.summary.contains("Sentence"));
}

#[test]
fn section_position_weight_boosts_discussion() {
    let text = concat!(
        "Introduction\n",
        "This paper examines compensated summation. We build on prior work. ",
        "Methods are described briefly.\n\n",
        "Discussion\n",
        "Our key finding is that Neumaier summation eliminates divergence. ",
        "Twelve lines of safe Rust suffice. ",
        "The fix has no performance cost."
    );
    let r = summarize(text, 200, Mode::Default);
    assert!(
        r.summary.contains("Neumaier")
            || r.summary.contains("Twelve")
            || r.summary.contains("performance cost"),
        "expected Discussion content; got: {:?}",
        r.summary
    );
}
