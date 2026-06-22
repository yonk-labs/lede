//! `extract::top_terms` — top-N salient words + phrases (v0.5 Rust mirror of
//! Python `extract/top_terms.py`).
//!
//! Combines per-document TF-IDF on single tokens with multi-word phrase
//! frequency into a unified ranking. Each kind is normalized to `[0, 1]`; the
//! top-N across all candidates is returned in score-descending order, ties
//! broken by term. **Byte-identical to Python on the default path** — it reuses
//! the same tokenizer, stopwords, IDF, and phrase machinery the parity-proven
//! `summarize`/`phrases` paths use, and performs no float summation (only
//! products, max, and division), so no Neumaier compensation is needed.

use std::collections::{HashMap, HashSet};

use crate::extract::phrases::{phrases, runs};
use crate::hints::{HintMode, HintWeight, hint_bonus, preprocess_hints};
use crate::sentences::split_sentences;
use crate::tfidf::tokenize_list;
use crate::types::TermScore;

/// Options for [`top_terms_with_options`] / [`top_terms_scored`].
///
/// `words`/`phrases` replace Python's `kinds` tuple (both default on). Python's
/// `hint_focus` is omitted: it is validated but has no behavioral effect on this
/// primitive, so it carries no information in Rust.
pub struct TopTermsOptions {
    pub n: usize,
    pub words: bool,
    pub phrases: bool,
    pub hints: Vec<HintWeight>,
    pub hint_mode: HintMode,
}

impl Default for TopTermsOptions {
    fn default() -> Self {
        Self {
            n: 10,
            words: true,
            phrases: true,
            hints: Vec::new(),
            hint_mode: HintMode::Soft,
        }
    }
}

struct Candidate {
    term: String,
    score: f64,
    kind: &'static str,
}

/// Per-unique-word TF-IDF, normalized to `[0, 1]`. Mirrors `_word_scores`.
fn word_scores(text: &str) -> Vec<(String, f64)> {
    let sentences = split_sentences(text);
    if sentences.is_empty() {
        return Vec::new();
    }
    let per_sent: Vec<Vec<String>> = sentences.iter().map(|s| tokenize_list(s)).collect();
    let n = sentences.len();

    let mut tf: HashMap<String, u32> = HashMap::new();
    let mut df: HashMap<String, u32> = HashMap::new();
    let mut order: Vec<String> = Vec::new(); // first-occurrence order, avoids hash-order output
    for toks in &per_sent {
        for t in toks {
            let e = tf.entry(t.clone()).or_insert(0);
            if *e == 0 {
                order.push(t.clone());
            }
            *e += 1;
        }
        let mut seen: HashSet<&String> = HashSet::new();
        for t in toks {
            if seen.insert(t) {
                *df.entry(t.clone()).or_insert(0) += 1;
            }
        }
    }
    if order.is_empty() {
        return Vec::new();
    }

    let n_f = n as f64;
    let raw: Vec<(String, f64)> = order
        .into_iter()
        .map(|term| {
            // IDF = log((n+1)/(df+1)) + 1.0 — identical to summarize's IDF.
            let idf = ((n_f + 1.0) / (f64::from(df[&term]) + 1.0)).ln() + 1.0;
            let score = f64::from(tf[&term]) * idf;
            (term, score)
        })
        .collect();
    normalize(raw)
}

/// Per-phrase scores (`count × token_count`), normalized to `[0, 1]`. Mirrors
/// `_phrase_scores`.
fn phrase_scores(text: &str) -> Vec<(String, f64)> {
    let candidates = phrases(text, None);
    if candidates.is_empty() {
        return Vec::new();
    }
    let mut counts: HashMap<String, usize> = HashMap::new();
    for p in runs(text) {
        *counts.entry(p).or_insert(0) += 1;
    }
    let raw: Vec<(String, f64)> = candidates
        .into_iter()
        .map(|phrase| {
            let cnt = counts.get(&phrase).copied().unwrap_or(1);
            let token_count = phrase.matches(' ').count() + 1; // mirrors `phrase.count(" ") + 1`
            let score = (cnt * token_count) as f64;
            (phrase, score)
        })
        .collect();
    normalize(raw)
}

/// Divide every score by the max (Python: `score / max(values)`); all-zero when
/// the max is non-positive.
fn normalize(raw: Vec<(String, f64)>) -> Vec<(String, f64)> {
    let hi = raw
        .iter()
        .map(|(_, s)| *s)
        .fold(f64::NEG_INFINITY, f64::max);
    if hi <= 0.0 {
        return raw.into_iter().map(|(t, _)| (t, 0.0)).collect();
    }
    raw.into_iter().map(|(t, s)| (t, s / hi)).collect()
}

fn ranked(text: &str, opts: &TopTermsOptions) -> Vec<Candidate> {
    if text.is_empty() {
        return Vec::new();
    }
    let mut candidates: Vec<Candidate> = Vec::new();
    if opts.words {
        for (term, score) in word_scores(text) {
            candidates.push(Candidate {
                term,
                score,
                kind: "word",
            });
        }
    }
    if opts.phrases {
        for (term, score) in phrase_scores(text) {
            candidates.push(Candidate {
                term,
                score,
                kind: "phrase",
            });
        }
    }
    if candidates.is_empty() {
        return Vec::new();
    }

    let hints = preprocess_hints(&opts.hints);
    if !hints.is_empty() {
        match opts.hint_mode {
            HintMode::Hard => {
                candidates.retain(|c| hint_bonus(&c.term, &hints) > 0.0);
                if candidates.is_empty() {
                    return Vec::new();
                }
            }
            HintMode::Soft => {
                for c in &mut candidates {
                    c.score += hint_bonus(&c.term, &hints);
                }
            }
        }
    }

    // Sort by (-score, term): score descending, ties broken by term ascending.
    candidates.sort_by(|a, b| {
        b.score
            .partial_cmp(&a.score)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then_with(|| a.term.cmp(&b.term))
    });
    candidates.truncate(opts.n);
    candidates
}

/// Top-N salient terms (words + phrases), score-descending. Mirrors Python
/// `top_terms(text, n=n)` with defaults.
#[must_use]
pub fn top_terms(text: &str, n: usize) -> Vec<String> {
    let opts = TopTermsOptions {
        n,
        ..TopTermsOptions::default()
    };
    top_terms_with_options(text, &opts)
}

/// Top-N salient terms with full options.
#[must_use]
pub fn top_terms_with_options(text: &str, opts: &TopTermsOptions) -> Vec<String> {
    ranked(text, opts).into_iter().map(|c| c.term).collect()
}

/// Top-N salient terms with scores + kind (Python `with_scores=True`).
#[must_use]
pub fn top_terms_scored(text: &str, opts: &TopTermsOptions) -> Vec<TermScore> {
    ranked(text, opts)
        .into_iter()
        .map(|c| TermScore {
            term: c.term,
            score: c.score,
            kind: c.kind.to_string(),
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    const DOC: &str = "Cook County raised property taxes. Cook County council met about taxes. \
         The council debated property taxes again.";

    #[test]
    fn ranks_repeated_terms() {
        let terms = top_terms(DOC, 5);
        assert!(!terms.is_empty());
        // "taxes"/"county"/"council"/"property" repeat → should surface.
        assert!(terms.iter().any(|t| t == "taxes"));
    }

    #[test]
    fn empty_input() {
        assert!(top_terms("", 10).is_empty());
    }

    #[test]
    fn with_scores_descending_and_normalized() {
        let scored = top_terms_scored(DOC, &TopTermsOptions::default());
        assert!(!scored.is_empty());
        // descending
        for w in scored.windows(2) {
            assert!(w[0].score >= w[1].score);
        }
        // top score normalized to <= 1.0 + (no hints) so exactly the max kind == 1.0
        assert!(scored[0].score <= 1.0 + f64::EPSILON);
        assert!(
            scored
                .iter()
                .all(|t| t.kind == "word" || t.kind == "phrase")
        );
    }

    #[test]
    fn hard_hint_filters_to_matches() {
        let opts = TopTermsOptions {
            hints: vec![("taxes".to_string(), 1.0)],
            hint_mode: HintMode::Hard,
            ..TopTermsOptions::default()
        };
        let terms = top_terms_with_options(DOC, &opts);
        assert!(terms.iter().all(|t| t.contains("taxes")));
        assert!(terms.iter().any(|t| t == "taxes"));
    }

    #[test]
    fn words_only_have_no_space() {
        let opts = TopTermsOptions {
            phrases: false,
            ..TopTermsOptions::default()
        };
        assert!(
            top_terms_with_options(DOC, &opts)
                .iter()
                .all(|t| !t.contains(' '))
        );
    }
}
