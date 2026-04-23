//! Phrase extractor — mirrors src/skimr/extract/phrases.py regex backend.

use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

fn word_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[a-z]{3,}").expect("static regex"))
}

pub(crate) fn stop() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        [
            "the", "a", "an", "and", "or", "but", "if", "then", "with", "by",
            "of", "to", "in", "on", "at", "for", "from", "as", "is", "are",
            "was", "were", "be", "been", "being", "has", "have", "had", "do",
            "does", "did", "will", "would", "could", "should", "may", "might",
            "can", "must", "this", "that", "these", "those", "it", "its",
            "they", "them", "their", "there", "here", "about", "up", "down",
            "into", "out", "over", "off", "just", "also", "not", "no", "our",
            "we", "you", "your", "he", "she", "his", "her", "him", "under",
            "more", "most", "less", "least", "all", "any", "some", "both",
            "each", "every", "one", "two", "three", "per",
        ]
        .into_iter()
        .collect()
    })
}

fn ngrams(buf: &[String], out: &mut Vec<String>) {
    let n = buf.len();
    let upper = std::cmp::min(5, n);
    for size in 2..=upper {
        for i in 0..=(n - size) {
            out.push(buf[i..i + size].join(" "));
        }
    }
}

fn runs(text: &str) -> Vec<String> {
    let lower = text.to_lowercase();
    let mut runs_out: Vec<String> = Vec::new();
    let mut buf: Vec<String> = Vec::new();
    for m in word_re().find_iter(&lower) {
        let w = m.as_str();
        if stop().contains(w) {
            ngrams(&buf, &mut runs_out);
            buf.clear();
        } else {
            buf.push(w.to_string());
        }
    }
    ngrams(&buf, &mut runs_out);
    runs_out
}

#[must_use]
pub fn phrases(text: &str, keywords: Option<&str>) -> Vec<String> {
    if text.is_empty() {
        return Vec::new();
    }
    let r = runs(text);
    let mut counts: HashMap<String, usize> = HashMap::new();
    let mut order: Vec<String> = Vec::new();
    for phrase in &r {
        let e = counts.entry(phrase.clone()).or_insert(0);
        if *e == 0 {
            order.push(phrase.clone());
        }
        *e += 1;
    }
    let mut out: Vec<String> = order
        .iter()
        .filter(|p| counts[*p] >= 2)
        .cloned()
        .collect();
    if let Some(kws) = keywords {
        let kw_set: HashSet<String> = word_re()
            .find_iter(&kws.to_lowercase())
            .map(|m| m.as_str().to_string())
            .collect();
        for phrase in &order {
            if counts[phrase] == 1
                && phrase.split_whitespace().any(|w| kw_set.contains(w))
            {
                out.push(phrase.clone());
            }
        }
    }
    // dedupe, preserve order
    let mut seen: HashSet<String> = HashSet::new();
    out.retain(|p| seen.insert(p.clone()));
    out
}
