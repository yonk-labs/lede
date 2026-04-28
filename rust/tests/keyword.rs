use lede::keyword::extract_keyword;

#[test]
fn picks_sentences_with_matches() {
    let text = concat!(
        "The demo went well. ",
        "Main concern is pricing and budget. ",
        "Will follow up next Tuesday.",
    );
    let out = extract_keyword(text, "pricing budget", 1);
    assert!(out.to_lowercase().contains("pricing"), "got: {out:?}");
}

#[test]
fn respects_num_sentences() {
    let text = concat!(
        "Main concern is pricing. ",
        "Budget is tight. ",
        "Cost is above plan. ",
        "Will follow up next week.",
    );
    let out = extract_keyword(text, "pricing budget cost", 2);
    assert_eq!(out.matches('\n').count(), 1);
}

#[test]
fn causal_bonus_picks_because() {
    let text = concat!(
        "Revenue grew last quarter. ",
        "The deal was lost because of pricing concerns. ",
        "Meeting was scheduled.",
    );
    let out = extract_keyword(text, "pricing", 1);
    assert!(out.to_lowercase().contains("because"), "got: {out:?}");
}

#[test]
fn empty_input_returns_empty() {
    assert_eq!(extract_keyword("", "pricing", 3), "");
}

#[test]
fn empty_or_filtered_keywords_returns_empty() {
    let text = "A short sentence. Another one.";
    // All tokens filtered (<3 chars) → empty (no longer chops to text[..2000]).
    assert_eq!(extract_keyword(text, "x y", 3), "");
    assert_eq!(extract_keyword(text, "", 3), "");
    assert_eq!(extract_keyword(text, "   ", 3), "");
}

#[test]
fn fixture_pricing_notes_byte_identical() {
    let fixture = std::path::Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("rust crate parent dir")
        .join("fixtures/keyword/pricing-notes");
    let input = std::fs::read_to_string(fixture.join("input.txt")).expect("read input");
    let expected = std::fs::read_to_string(fixture.join("expected.txt")).expect("read expected");
    let cfg = std::fs::read_to_string(fixture.join("config.json")).expect("read config");
    let keywords = extract_json_str(&cfg, "keywords");
    let num = extract_json_usize(&cfg, "num_sentences");
    assert_eq!(extract_keyword(&input, &keywords, num), expected);
}

fn extract_json_str(cfg: &str, key: &str) -> String {
    let needle = format!("\"{key}\":");
    let start = cfg.find(&needle).expect("key present") + needle.len();
    let after = &cfg[start..];
    let open = after.find('"').expect("open quote") + 1;
    let remaining = &after[open..];
    let close = remaining.find('"').expect("close quote");
    remaining[..close].to_string()
}
fn extract_json_usize(cfg: &str, key: &str) -> usize {
    let needle = format!("\"{key}\":");
    let start = cfg.find(&needle).expect("key present") + needle.len();
    let after = cfg[start..].trim_start();
    let end = after
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(after.len());
    after[..end].parse().expect("digits")
}
