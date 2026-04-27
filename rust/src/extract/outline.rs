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

// Heading patterns + helpers live in `crate::headings` — single source of
// truth so a new pattern requires one edit, not two. T13b Class D cases
// intentionally NOT handled (still tracked as follow-ups):
//   - "Meeting: Platform Migration Planning" (Label:Subject inline pattern)
//   - "Held: Section 412(b) does not authorize..." (inline colon-label
//     with body text on the same line)
//   - "Reply from support (Kai T., day 1)" (parenthetical structured
//     heading; too corpus-specific for a general predicate)
use crate::headings::{heading_name, is_structural_heading, md_depth};
use crate::sentences::split_sentences;
use crate::tfidf::{composite_score_parts, separate_heading_lines};

#[derive(Debug, Clone, PartialEq)]
pub struct Section {
    pub depth: usize,
    pub name: String,
    pub representative_sentence: String,
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
                // NaN-tolerant: degrade to Equal rather than panicking on a
                // corrupt score. The .then_with tiebreak still runs and
                // produces a deterministic order.
                scores[**a]
                    .partial_cmp(&scores[**b])
                    .unwrap_or(std::cmp::Ordering::Equal)
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

/// Lightweight table of contents — section names in document order.
///
/// Equivalent to `outline(text).into_iter().map(|s| s.name).collect()` but
/// exposed as its own primitive for discoverability. Uses the regex heading
/// detector; no backend parameter (regex is the only option, same as
/// `outline()`).
#[must_use]
pub fn toc(text: &str) -> Vec<String> {
    outline(text).into_iter().map(|s| s.name).collect()
}
