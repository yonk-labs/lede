//! Phrase extractor — mirrors src/lede/extract/phrases.py regex backend.

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
            "the", "a", "an", "and", "or", "but", "if", "then", "with", "by", "of", "to", "in",
            "on", "at", "for", "from", "as", "is", "are", "was", "were", "be", "been", "being",
            "has", "have", "had", "do", "does", "did", "will", "would", "could", "should", "may",
            "might", "can", "must", "this", "that", "these", "those", "it", "its", "they", "them",
            "their", "there", "here", "about", "up", "down", "into", "out", "over", "off", "just",
            "also", "not", "no", "our", "we", "you", "your", "he", "she", "his", "her", "him",
            "under", "more", "most", "less", "least", "all", "any", "some", "both", "each",
            "every", "one", "two", "three", "per",
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

/// T13h: identify sub-ngrams absorbed by a longer emitted ngram (same count).
///
/// Drop ngram A if there is a longer emitted ngram B whose tokens contain A
/// contiguously AND counts\[A\] == counts\[B\]. The equal-count signal means
/// A only ever appears inside B's context. Sub-ngrams with counts\[A\] >
/// counts\[B\] (i.e. A has standalone occurrences) are preserved.
fn subsumed(candidates: &[String], counts: &HashMap<String, usize>) -> HashSet<String> {
    let tok_map: HashMap<&String, Vec<&str>> = candidates
        .iter()
        .map(|p| (p, p.split(' ').collect()))
        .collect();
    let mut drop: HashSet<String> = HashSet::new();
    for a in candidates {
        let a_toks = &tok_map[a];
        let a_len = a_toks.len();
        for b in candidates {
            if a == b {
                continue;
            }
            let b_toks = &tok_map[b];
            if b_toks.len() <= a_len {
                continue;
            }
            if counts[b] != counts[a] {
                continue;
            }
            let mut contained = false;
            for i in 0..=(b_toks.len() - a_len) {
                if &b_toks[i..i + a_len] == a_toks.as_slice() {
                    contained = true;
                    break;
                }
            }
            if contained {
                drop.insert(a.clone());
                break;
            }
        }
    }
    drop
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
    let repeated: Vec<String> = order.iter().filter(|p| counts[*p] >= 2).cloned().collect();
    // T13h: subsumption — drop sub-ngrams that only appear inside a longer
    // emitted ngram (same count). Tightens precision by eliminating n-gram
    // explosion noise like "environmental protection" / "protection agency"
    // when "environmental protection agency" is also emitted.
    let drop = subsumed(&repeated, &counts);
    let mut out: Vec<String> = repeated.into_iter().filter(|p| !drop.contains(p)).collect();
    if let Some(kws) = keywords {
        let kw_set: HashSet<String> = word_re()
            .find_iter(&kws.to_lowercase())
            .map(|m| m.as_str().to_string())
            .collect();
        for phrase in &order {
            if counts[phrase] == 1 && phrase.split_whitespace().any(|w| kw_set.contains(w)) {
                out.push(phrase.clone());
            }
        }
    }
    // dedupe, preserve order
    let mut seen: HashSet<String> = HashSet::new();
    out.retain(|p| seen.insert(p.clone()));
    out
}
