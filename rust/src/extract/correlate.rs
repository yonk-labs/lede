//! Pair repeated entities with numeric facts. Mirrors correlate.py.

use crate::extract::phrases::{phrases, stop};
use crate::extract::stats::{Stat, StatsOptions, stats, stats_with_options};
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

#[derive(Debug, Clone, PartialEq)]
pub struct PhraseFact {
    pub entity: String,
    pub number: String,
    pub polarity: String,
    pub sentence: String,
}

fn word_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[a-zA-Z]{3,}").expect("static regex"))
}

fn growth_words() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        [
            "grew",
            "grow",
            "increased",
            "increase",
            "rose",
            "up",
            "higher",
            "gained",
            "added",
        ]
        .into_iter()
        .collect()
    })
}

fn decline_words() -> &'static HashSet<&'static str> {
    static S: OnceLock<HashSet<&'static str>> = OnceLock::new();
    S.get_or_init(|| {
        [
            "fell",
            "fall",
            "declined",
            "decline",
            "decreased",
            "decrease",
            "dropped",
            "down",
            "lower",
            "lost",
        ]
        .into_iter()
        .collect()
    })
}

fn polarity(sentence: &str) -> &'static str {
    let lower = sentence.to_lowercase();
    let toks: HashSet<String> = word_re()
        .find_iter(&lower)
        .map(|m| m.as_str().to_string())
        .collect();
    if toks.iter().any(|t| growth_words().contains(t.as_str())) {
        return "growth";
    }
    if toks.iter().any(|t| decline_words().contains(t.as_str())) {
        return "decline";
    }
    "absolute"
}

#[must_use]
pub fn correlate_facts(text: &str) -> Vec<PhraseFact> {
    correlate_facts_with_options(text, StatsOptions::default())
}

/// Same as [`correlate_facts`] but forwards [`StatsOptions`] to the
/// internal `stats_with_options` call (T13e). Mirrors Python's
/// `correlate_facts(text, convert_word_names=...)`.
#[must_use]
pub fn correlate_facts_with_options(text: &str, options: StatsOptions) -> Vec<PhraseFact> {
    if text.is_empty() {
        return Vec::new();
    }
    let stats_list: Vec<Stat> = if options.convert_word_names {
        stats_with_options(text, options)
    } else {
        stats(text)
    };
    if stats_list.is_empty() {
        return Vec::new();
    }

    // Count single-word occurrences
    let lower = text.to_lowercase();
    let mut word_counts: HashMap<String, usize> = HashMap::new();
    for m in word_re().find_iter(&lower) {
        *word_counts.entry(m.as_str().to_string()).or_insert(0) += 1;
    }
    let repeated_words: HashSet<String> = word_counts
        .iter()
        .filter(|(w, c)| **c >= 2 && !stop().contains(w.as_str()))
        .map(|(w, _)| w.clone())
        .collect();

    let repeated_phrases: Vec<String> = phrases(text, None);

    let mut pairings: Vec<PhraseFact> = Vec::new();
    for st in &stats_list {
        let sent_lower = st.context_sentence.to_lowercase();
        let candidates: Vec<String> = word_re()
            .find_iter(&sent_lower)
            .map(|m| m.as_str().to_string())
            .filter(|w| repeated_words.contains(w))
            .collect();

        let phrase_match = repeated_phrases
            .iter()
            .find(|p| p.split_whitespace().all(|w| sent_lower.contains(w)))
            .cloned();

        let entity = if let Some(p) = phrase_match {
            Some(p)
        } else {
            // Tie-break: Python's max(key=...) returns the FIRST tied element;
            // Rust's Iterator::max_by_key returns the LAST. Use manual tie-break
            // with `bi.cmp(ai)` so lower index wins on equal count — matches
            // Python's first-in-wins semantics. Same pattern as T6 outline fix.
            candidates
                .iter()
                .enumerate()
                .max_by(|(ai, a), (bi, b)| {
                    word_counts
                        .get(*a)
                        .copied()
                        .unwrap_or(0)
                        .cmp(&word_counts.get(*b).copied().unwrap_or(0))
                        .then_with(|| bi.cmp(ai))
                })
                .map(|(_, w)| w.clone())
        };

        if let Some(e) = entity {
            pairings.push(PhraseFact {
                entity: e,
                number: st.value.clone(),
                polarity: polarity(&st.context_sentence).to_string(),
                sentence: st.context_sentence.clone(),
            });
        }
    }

    // Keep entities with >= 2 facts
    let mut entity_counts: HashMap<String, usize> = HashMap::new();
    for pf in &pairings {
        *entity_counts.entry(pf.entity.clone()).or_insert(0) += 1;
    }
    pairings
        .into_iter()
        .filter(|pf| entity_counts[&pf.entity] >= 2)
        .collect()
}
