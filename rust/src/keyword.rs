//! Keyword-scored extractor. Port of `src/skimr/keyword.py`.
//!
//! Matches the SQL reference `extract_sentences(input_text, keywords, num_sentences)`:
//! normalize `\n+` to `". "`, split after terminal punctuation, keep segments
//! with more than 20 characters, score by keyword-match count plus bonuses
//! (length, digit presence, causal vocabulary), and return the top-N
//! sentences joined by newlines in score-descending order.

use regex::Regex;
use std::collections::BTreeSet;
use std::sync::OnceLock;

fn causal_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(because|reason|due to|caused|result|impact|issue|problem",
            r"|concern|risk|challenge|blocker|gap|lack|missing",
            r"|competitor|pricing|budget|cost|expensive|cheaper|alternative",
            r"|decided|chose|prefer|switched|rejected|declined)",
        ))
        .expect("static regex")
    })
}

fn digit_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\d+").expect("static regex"))
}

fn newline_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\n+").expect("static regex"))
}

fn sentence_split_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[.!?]\s+").expect("static regex"))
}

/// SQL-style splitter: replace `\n+` with `". "`, then split after any
/// terminal punctuation (`.`, `!`, `?`) followed by whitespace. Keep only
/// segments whose trimmed length (in code points) is greater than 20.
fn split_sql_style(text: &str) -> Vec<String> {
    let normalized = newline_re().replace_all(text, ". ");
    let split = sentence_split_re();

    let mut parts: Vec<&str> = Vec::new();
    let mut cursor = 0usize;
    for m in split.find_iter(&normalized) {
        // `.!?` are 1-byte ASCII, so `m.start() + 1` is a safe char boundary.
        let after_punct = m.start() + 1;
        parts.push(&normalized[cursor..after_punct]);
        cursor = m.end();
    }
    parts.push(&normalized[cursor..]);

    parts
        .into_iter()
        .map(str::trim)
        .filter(|p| p.chars().count() > 20)
        .map(str::to_string)
        .collect()
}

/// Extract the top `num_sentences` sentences relevant to `keywords`.
///
/// Returns the empty string for empty `text`. When `keywords` contains no
/// token longer than 2 characters, returns the first 2000 code points of
/// `text` (matching the SQL `LEFT(input_text, 2000)` fallback). Otherwise
/// scores each SQL-style-split sentence by keyword-match count plus bonuses
/// (+0.5 if length > 200 chars, +0.3 if it contains a digit, +1.0 if it
/// contains causal/analytical vocabulary), sorts by `(-score, position)`,
/// takes the top N, and joins them with `\n`.
#[must_use]
pub fn extract_keyword(text: &str, keywords: &str, num_sentences: usize) -> String {
    if text.is_empty() {
        return String::new();
    }

    // Python: sorted({w.lower().strip() for w in keywords.split() if len(w.strip()) > 2})
    // `str::split_whitespace` mirrors Python's `str.split()` with no arg.
    let kw_set: BTreeSet<String> = keywords
        .split_whitespace()
        .map(str::to_lowercase)
        .filter(|s| s.chars().count() > 2)
        .collect();
    if kw_set.is_empty() {
        // Mirrors Python: empty/all-filtered keywords return "" rather than the
        // SQL reference's silent LEFT(text, 2000) chop, which was a footgun.
        return String::new();
    }
    let keyword_list: Vec<String> = kw_set.into_iter().collect();

    let sentences = split_sql_style(text);
    if sentences.is_empty() {
        return text.to_string();
    }

    let mut scored: Vec<(f64, usize, String)> = sentences
        .iter()
        .enumerate()
        .map(|(i, s)| {
            let lower = s.to_lowercase();
            let mut score = keyword_list
                .iter()
                .filter(|kw| lower.contains(kw.as_str()))
                .count() as f64;
            if s.chars().count() > 200 {
                score += 0.5;
            }
            // Python runs _DIGIT_RE.search on the original sentence `s`.
            if digit_re().is_match(s) {
                score += 0.3;
            }
            if causal_re().is_match(&lower) {
                score += 1.0;
            }
            (score, i, s.clone())
        })
        .collect();

    // Sort by (-score, original position); stable tiebreak matches Python.
    // NaN-tolerant: degrade to Equal so a corrupt score never panics; the
    // position tiebreak still produces deterministic order.
    scored.sort_by(|a, b| {
        let sa = -a.0;
        let sb = -b.0;
        sa.partial_cmp(&sb)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.1.cmp(&b.1))
    });

    scored
        .into_iter()
        .take(num_sentences)
        .map(|(_, _, s)| s)
        .collect::<Vec<_>>()
        .join("\n")
}
