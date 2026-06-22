//! Metadata extractor — stdlib core only; entities always empty in Rust.

use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, Default, PartialEq)]
pub struct Metadata {
    pub dates: Vec<String>,
    pub amounts: Vec<String>,
    pub urls: Vec<String>,
    pub entities: Vec<String>, // always empty; Python-only via lede[ner]
}

// Date patterns mirror extract::stats: ISO yyyy-mm-dd, US m/d/yyyy, and bare
// years 1900-2099. Same shape, same bounds — keeps Python ↔ Rust output
// byte-identical and matches the doc claim in docs/REFERENCE.md.
fn date_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"\b\d{4}-\d{2}-\d{2}\b|\b\d{1,2}/\d{1,2}/\d{2,4}\b|\b(?:19|20)\d{2}\b")
            .expect("static regex")
    })
}

// Amount quantifiers bounded {0,18} for parity with extract::stats::money_re.
fn amount_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)\$\d[\d,]{0,18}(?:\.\d{1,4})?[KMB]?(?:\s+(?:million|billion|trillion|thousand)\b)?|",
            r"\d[\d,]{0,18}(?:\.\d{1,4})?(?:\s+(?:million|billion|trillion|thousand)\b)?\s*(?:dollars?|USD|EUR|GBP|JPY|CHF)",
        ))
        .expect("static regex")
    })
}

fn url_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r#"(?i)https?://[^\s<>"')]+"#).expect("static regex"))
}

fn collect_unique(re: &Regex, text: &str) -> Vec<String> {
    let mut seen: std::collections::HashSet<String> = std::collections::HashSet::new();
    let mut out: Vec<String> = Vec::new();
    for m in re.find_iter(text) {
        if !seen.contains(m.as_str()) {
            let v = m.as_str().to_string();
            seen.insert(v.clone());
            out.push(v);
        }
    }
    out
}

#[must_use]
pub fn metadata(text: &str) -> Metadata {
    if text.is_empty() {
        return Metadata::default();
    }
    Metadata {
        dates: collect_unique(date_re(), text),
        amounts: collect_unique(amount_re(), text),
        urls: collect_unique(url_re(), text),
        entities: Vec::new(),
    }
}
