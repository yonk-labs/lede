//! Coarse rule-based POS tagger — closed-class word lists + suffix heuristics.
//! No model, no bundled weights, no network: license-clean and deterministic.
//! Opt-in (`pos` feature).
//!
//! The higher-accuracy averaged-perceptron path (NLTK weights) is intentionally
//! NOT built here: depending on the `postagger` crate would transitively
//! redistribute PTB/LDC-trained weights (spec §6). That path is a deferred
//! `pos-perceptron` feature loading user-supplied weights.
//!
//! ponytail: rule-based tagger, sm-class accuracy not promised. Upgrade path is
//! the user-supplied-weights perceptron feature above.

use crate::gazetteer::contains_ci;

const DET: &[&str] = &[
    "the", "a", "an", "this", "that", "these", "those", "some", "any", "no", "each", "every", "all",
];
const PRON: &[&str] = &[
    "he", "she", "it", "they", "we", "you", "i", "him", "her", "them", "us", "his", "its", "their",
    "our", "my", "your", "who", "which",
];
const ADP: &[&str] = &[
    "of", "in", "on", "at", "by", "for", "with", "to", "from", "into", "over", "under", "about",
    "as", "than", "per", "during", "despite",
];
const CONJ: &[&str] = &[
    "and", "or", "but", "nor", "so", "yet", "because", "although", "while", "if", "when",
];
const AUX: &[&str] = &[
    "is", "are", "was", "were", "be", "been", "being", "am", "has", "have", "had", "do", "does",
    "did", "will", "would", "can", "could", "should", "may", "might", "must", "shall",
];
const GROWTH: &[&str] = &[
    "grew",
    "grow",
    "increased",
    "increase",
    "rose",
    "rise",
    "gained",
    "gain",
    "added",
    "climbed",
    "jumped",
    "surged",
    "up",
    "higher",
];
const DECLINE: &[&str] = &[
    "fell",
    "fall",
    "declined",
    "decline",
    "decreased",
    "decrease",
    "dropped",
    "drop",
    "lost",
    "lose",
    "down",
    "lower",
    "slipped",
];
const COMMON_VERBS: &[&str] = &[
    "reported",
    "report",
    "said",
    "say",
    "announced",
    "announce",
    "posted",
    "post",
    "reached",
    "reach",
    "totaled",
    "total",
    "earned",
    "earn",
    "saw",
];

/// Coarse Universal-style POS tag.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub(crate) enum Tag {
    Noun,
    Propn,
    Verb,
    Adj,
    Adv,
    Adp,
    Det,
    Pron,
    Conj,
    Num,
    Aux,
}

impl Tag {
    pub(crate) fn as_str(self) -> &'static str {
        match self {
            Tag::Noun => "NOUN",
            Tag::Propn => "PROPN",
            Tag::Verb => "VERB",
            Tag::Adj => "ADJ",
            Tag::Adv => "ADV",
            Tag::Adp => "ADP",
            Tag::Det => "DET",
            Tag::Pron => "PRON",
            Tag::Conj => "CONJ",
            Tag::Num => "NUM",
            Tag::Aux => "AUX",
        }
    }
}

fn tokenize(text: &str) -> Vec<String> {
    text.split_whitespace()
        .map(|w| {
            w.trim_matches(|c: char| !c.is_alphanumeric() && c != '$' && c != '%' && c != '\'')
        })
        .filter(|w| !w.is_empty())
        .map(str::to_string)
        .collect()
}

pub(crate) fn tag_one(token: &str) -> Tag {
    let lw = token.to_ascii_lowercase();
    let first = token.chars().next();
    if token.starts_with('$') || token.ends_with('%') || first.is_some_and(|c| c.is_ascii_digit()) {
        return Tag::Num;
    }
    if contains_ci(DET, &lw) {
        return Tag::Det;
    }
    if contains_ci(PRON, &lw) {
        return Tag::Pron;
    }
    if contains_ci(ADP, &lw) {
        return Tag::Adp;
    }
    if contains_ci(CONJ, &lw) {
        return Tag::Conj;
    }
    if contains_ci(AUX, &lw) {
        return Tag::Aux;
    }
    if contains_ci(GROWTH, &lw) || contains_ci(DECLINE, &lw) || contains_ci(COMMON_VERBS, &lw) {
        return Tag::Verb;
    }
    if lw.ends_with("ing") || lw.ends_with("ed") {
        return Tag::Verb;
    }
    if lw.ends_with("ly") {
        return Tag::Adv;
    }
    if lw.ends_with("tion") || lw.ends_with("ment") || lw.ends_with("ness") || lw.ends_with("ity") {
        return Tag::Noun;
    }
    if lw.ends_with("ous") || lw.ends_with("ful") || lw.ends_with("ive") || lw.ends_with("able") {
        return Tag::Adj;
    }
    if first.is_some_and(char::is_uppercase) {
        return Tag::Propn;
    }
    Tag::Noun
}

pub(crate) fn tag_tokens(text: &str) -> Vec<(String, Tag)> {
    tokenize(text)
        .into_iter()
        .map(|t| {
            let g = tag_one(&t);
            (t, g)
        })
        .collect()
}

/// Polarity from the first growth/decline verb-tagged token; else "absolute".
/// Uses POS to scope polarity to verbs rather than any word in the sentence.
pub(crate) fn verb_polarity(tagged: &[(String, Tag)]) -> &'static str {
    for (tok, tag) in tagged {
        if *tag != Tag::Verb {
            continue;
        }
        let lw = tok.to_ascii_lowercase();
        if contains_ci(GROWTH, &lw) {
            return "growth";
        }
        if contains_ci(DECLINE, &lw) {
            return "decline";
        }
    }
    "absolute"
}

/// (token, POS-tag) pairs. Coarse rule-based tags; deterministic. Mirrors the
/// shape of Python `pos_tag`.
#[must_use]
pub fn pos_tag(text: &str) -> Vec<(String, String)> {
    tag_tokens(text)
        .into_iter()
        .map(|(t, g)| (t, g.as_str().to_string()))
        .collect()
}
