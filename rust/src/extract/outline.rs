//! Hierarchical outline extractor. Mirrors src/skimr/extract/outline.py.
//!
//! Detects sections via structural heading patterns (markdown, allcaps,
//! short-colon-label). For each section picks the highest-composite-score
//! non-heading sentence as the representative.
//!
//! Note: `outline()` uses a narrower heading predicate than
//! `crate::headings::is_heading` — it does NOT treat "fewer than 4 content
//! tokens" as a heading signal, because that heuristic misclassifies short
//! body sentences as headings, leaving sections with no
//! representative-sentence candidates.

use crate::headings::heading_name;
use crate::sentences::split_sentences;
use crate::tfidf::{composite_score_parts, separate_heading_lines};
use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, PartialEq)]
pub struct Section {
    pub depth: usize,
    pub name: String,
    pub representative_sentence: String,
}

fn md_heading_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*#+\s+.+$").expect("static regex"))
}

fn allcaps_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*[A-Z][A-Z\s]{3,28}:?\s*$").expect("static regex"))
}

fn short_label_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*.{1,30}:\s*$").expect("static regex"))
}

fn md_depth_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*(#+)\s+").expect("static regex"))
}

/// True when `sentence` matches a structural heading pattern. Narrower than
/// `crate::headings::is_heading` — drops the "< 4 content tokens" fallback.
fn is_structural_heading(sentence: &str) -> bool {
    if sentence.trim().is_empty() {
        return false;
    }
    md_heading_re().is_match(sentence)
        || allcaps_re().is_match(sentence)
        || short_label_re().is_match(sentence)
}

fn md_depth(heading_line: &str) -> usize {
    if let Some(caps) = md_depth_re().captures(heading_line) {
        return caps.get(1).map_or(1, |m| m.as_str().len());
    }
    1
}

struct Sect {
    depth: usize,
    name: String,
    body: Vec<usize>,
}

#[must_use]
pub fn outline(text: &str) -> Vec<Section> {
    if text.is_empty() {
        return Vec::new();
    }

    // Pre-split heading-only lines so they become standalone sentences —
    // mirrors tfidf::summarize's default-mode preprocessing.
    let prepared = separate_heading_lines(text);
    let sentences = split_sentences(&prepared);
    if sentences.is_empty() {
        return Vec::new();
    }

    let parts = composite_score_parts(&sentences);
    let scores: Vec<f64> = parts
        .iter()
        .map(|(t, p, l)| 0.60 * t + 0.25 * p + 0.15 * l)
        .collect();

    let mut sections: Vec<Sect> = Vec::new();
    let mut current: Option<Sect> = None;
    for (i, s) in sentences.iter().enumerate() {
        if is_structural_heading(s) {
            if let Some(cur) = current.take() {
                sections.push(cur);
            }
            let name = heading_name(s).unwrap_or_default();
            current = Some(Sect {
                depth: md_depth(s),
                name,
                body: Vec::new(),
            });
        } else if let Some(cur) = current.as_mut() {
            cur.body.push(i);
        }
    }
    if let Some(cur) = current {
        sections.push(cur);
    }

    let mut out = Vec::with_capacity(sections.len());
    for sect in sections {
        if sect.body.is_empty() || sect.name.is_empty() {
            continue;
        }
        let best_idx = *sect
            .body
            .iter()
            .max_by(|a, b| {
                scores[**a]
                    .partial_cmp(&scores[**b])
                    .expect("no NaN")
                    .then_with(|| b.cmp(a))
            })
            .expect("non-empty");
        out.push(Section {
            depth: sect.depth,
            name: sect.name,
            representative_sentence: sentences[best_idx].clone(),
        });
    }
    out
}
