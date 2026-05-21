//! Coverage-constrained selector. Mirrors `src/lede/coverage.py`.
//!
//! Picks the highest-scoring sentence from each paragraph (paragraphs are
//! blank-line-delimited; fewer-than-20-char paragraphs are skipped). After a
//! one-per-paragraph pass, the next-best ungrabbed sentences from paragraphs
//! not yet represented fill remaining budget. Reorder by original document
//! position.
//!
//! Coverage mode uses the raw (tfidf, position, length) composite
//! (0.60/0.25/0.15) WITHOUT the default-mode cue/digit/section boosts —
//! coverage is about breadth (how many paragraphs the summary touches), not
//! per-sentence signal density.

use crate::headings::is_heading;
use crate::sentences::split_sentences;
use crate::tfidf::composite_score_parts;
use regex::Regex;
use std::collections::{BTreeMap, HashSet};
use std::sync::OnceLock;

const TFIDF_WEIGHT: f64 = 0.60;
const POSITION_WEIGHT: f64 = 0.25;
const LENGTH_WEIGHT: f64 = 0.15;

fn para_split_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\n\s*\n+").expect("static regex"))
}

/// Return paragraphs of at least 20 chars after strip.
///
/// Mirrors Python's `_split_paragraphs`. Python's `len()` on a `str` counts
/// characters, so we use `chars().count()` rather than `len()` (bytes) to
/// match on non-ASCII inputs.
fn split_paragraphs(text: &str) -> Vec<String> {
    para_split_re()
        .split(text)
        .map(|p| p.trim().to_string())
        .filter(|p| p.chars().count() >= 20)
        .collect()
}

/// Per-sentence coverage-mode scores for the hint two-pool path.
///
/// Returns the raw 60/25/15 composite (tfidf, position, length) per
/// sentence — the same base scores `summarize_coverage` computes
/// internally. Headings get `-inf` so the two-pool selector skips them.
///
/// Note: coverage mode's per-paragraph breadth guarantee is intentionally
/// NOT preserved when hints are used. The caller asked for hint-biased
/// selection; breadth is a secondary concern.
///
/// Mirrors `_composite_score_coverage_for_hints` in `src/lede/coverage.py`.
#[must_use]
pub(crate) fn composite_score_coverage_for_hints(sentences: &[String]) -> Vec<f64> {
    if sentences.is_empty() {
        return Vec::new();
    }
    let parts = composite_score_parts(sentences);
    sentences
        .iter()
        .zip(parts.iter())
        .map(|(s, (t, p, l))| {
            if is_heading(s) {
                f64::NEG_INFINITY
            } else {
                TFIDF_WEIGHT * t + POSITION_WEIGHT * p + LENGTH_WEIGHT * l
            }
        })
        .collect()
}

/// C2 coverage selector — paragraph-aware extractive summary.
#[must_use]
pub fn summarize_coverage(text: &str, max_length: usize) -> String {
    let sentences = split_sentences(text);
    if sentences.is_empty() {
        return text.to_string();
    }
    let parts = composite_score_parts(&sentences);
    let scores: Vec<f64> = parts
        .iter()
        .map(|(t, p, l)| TFIDF_WEIGHT * t + POSITION_WEIGHT * p + LENGTH_WEIGHT * l)
        .collect();

    // Occurrence-counted mapping: the K-th occurrence of a repeated sentence
    // goes to the K-th paragraph that contains it. Earlier "first containing
    // paragraph wins" biased coverage on docs with template/FAQ-style
    // repetitions. Mirrors `src/lede/coverage.py`. Closes AAT-021.
    let paragraphs = split_paragraphs(text);
    let mut occurrence_seen: std::collections::HashMap<&str, usize> =
        std::collections::HashMap::new();
    let sent_to_para: Vec<Option<usize>> = sentences
        .iter()
        .map(|s| {
            let s_ref: &str = s.as_str();
            let target = *occurrence_seen.get(s_ref).unwrap_or(&0);
            let mut seen = 0usize;
            let mut idx: Option<usize> = None;
            for (i, p) in paragraphs.iter().enumerate() {
                if p.contains(s_ref) {
                    if seen == target {
                        idx = Some(i);
                        break;
                    }
                    seen += 1;
                }
            }
            occurrence_seen.insert(s_ref, target + 1);
            idx
        })
        .collect();

    // Best non-heading sentence per paragraph. `BTreeMap` keeps paragraphs in
    // ascending order for the per-paragraph pass.
    let mut best_per_para: BTreeMap<usize, (f64, usize)> = BTreeMap::new();
    for (i, sentence) in sentences.iter().enumerate() {
        if is_heading(sentence) {
            continue;
        }
        let Some(pidx) = sent_to_para[i] else {
            continue;
        };
        let score = scores[i];
        match best_per_para.get(&pidx) {
            Some((best_score, _)) if score <= *best_score => {}
            _ => {
                best_per_para.insert(pidx, (score, i));
            }
        }
    }

    // Per-paragraph pass — iterate paragraphs in document order, add the
    // paragraph's best sentence if budget allows. `sentence.chars().count() + 1`
    // mirrors Python's `len(sentence) + 1` (Python `len` counts chars).
    let mut selected: Vec<usize> = Vec::new();
    let mut covered_paras: HashSet<usize> = HashSet::new();
    let mut budget_used: usize = 0;
    for (para_idx, (_, sent_idx)) in &best_per_para {
        let cost = sentences[*sent_idx].chars().count() + 1;
        if budget_used + cost <= max_length {
            selected.push(*sent_idx);
            covered_paras.insert(*para_idx);
            budget_used += cost;
        }
    }

    // Greedy fill — only add sentences from paragraphs NOT yet represented,
    // preserving the "breadth" guarantee of coverage mode.
    let mut remaining: Vec<(f64, usize)> = Vec::new();
    for (i, sentence) in sentences.iter().enumerate() {
        if selected.contains(&i) {
            continue;
        }
        if is_heading(sentence) {
            continue;
        }
        let Some(pidx) = sent_to_para[i] else {
            continue;
        };
        if covered_paras.contains(&pidx) {
            continue;
        }
        remaining.push((scores[i], i));
    }
    // NaN should not appear in pipeline scores (TF-IDF is rational). Treat any
    // accidental NaN as Equal rather than panicking — it would have to come from
    // a corrupt input upstream and is not worth bringing the worker down over.
    remaining.sort_by(|a, b| b.0.partial_cmp(&a.0).unwrap_or(std::cmp::Ordering::Equal));

    for (_, i) in remaining {
        let cost = sentences[i].chars().count() + 1;
        if budget_used + cost <= max_length {
            selected.push(i);
            if let Some(pidx) = sent_to_para[i] {
                covered_paras.insert(pidx);
            }
            budget_used += cost;
        }
        if budget_used >= max_length {
            break;
        }
    }

    selected.sort_unstable();
    // Match default and legacy modes' separator (" "). Earlier coverage used
    // "\n" which surprised callers diffing across modes — AAT-022.
    selected
        .into_iter()
        .map(|i| sentences[i].clone())
        .collect::<Vec<_>>()
        .join(" ")
}
