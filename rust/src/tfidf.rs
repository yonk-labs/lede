//! TF-IDF + position + length extractive pipeline.
//!
//! Port of src/lede/tfidf.py. Output is byte-identical to Python for every
//! fixture. Insertion-order iteration of per-sentence token counters is
//! preserved exactly so floating-point sums line up.
//!
//! v0.2.0 adds `Mode::Default` with four scorer tweaks (heading filter,
//! cue-phrase boost, digit bonus, section-position weight) on top of the
//! legacy 60/25/15 composite. `Mode::Legacy` preserves v0.0.1 behavior
//! byte-identically.

use crate::headings::{heading_name, is_heading};
use crate::hints::{HintMode, HintWeight};
use crate::types::{AttachOpts, Mode, SummaryResult};
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

const TFIDF_WEIGHT: f64 = 0.60;
const POSITION_WEIGHT: f64 = 0.25;
const LENGTH_WEIGHT: f64 = 0.15;

/// Stopword list. Must stay byte-identical to Python's `_STOPWORDS` frozenset.
/// See src/lede/tfidf.py.
static STOPWORDS_LIST: &[&str] = &[
    "the", "and", "that", "this", "with", "for", "are", "was", "were", "been", "have", "has",
    "had", "not", "but", "what", "all", "when", "who", "will", "can", "from", "they", "each",
    "which", "their", "there", "about", "would", "make", "more", "some", "into", "other", "than",
    "its", "also", "after", "use", "how", "our", "any", "these", "most", "may", "should", "could",
    "does", "did", "just", "because", "over", "such", "through", "very", "your", "a", "an", "is",
    "it", "in", "on", "of", "to", "be", "as", "at", "by",
];

fn stopwords() -> &'static std::collections::HashSet<&'static str> {
    static SW: OnceLock<std::collections::HashSet<&'static str>> = OnceLock::new();
    SW.get_or_init(|| STOPWORDS_LIST.iter().copied().collect())
}

fn token_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    // Python: r"\b[a-z]{3,}\b" — ASCII-only, applied after .lower()
    RE.get_or_init(|| Regex::new(r"(?-u)\b[a-z]{3,}\b").expect("static regex"))
}

// --- v0.2 default-mode scorer tweaks ---

fn cue_phrase_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)^\s*(held|resolution|in summary|conclusion|action item|",
            r"decision|finding|key takeaway|outcome|ruling):?\b",
        ))
        .expect("static regex")
    })
}

fn digit_re_local() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\d+").expect("static regex"))
}

const SECTION_BOOST_HEADINGS: &[&str] = &[
    "discussion",
    "conclusion",
    "held",
    "resolution",
    "key findings",
    "summary",
    "decision",
];

/// Insertion-ordered counter. Mirrors Python's Counter(list) insertion order
/// (first occurrence of each key, with running count).
pub(crate) struct OrderedCounter {
    pub keys: Vec<String>,
    pub counts: HashMap<String, u32>,
}

impl OrderedCounter {
    fn new() -> Self {
        Self {
            keys: Vec::new(),
            counts: HashMap::new(),
        }
    }

    fn push(&mut self, token: String) {
        if let Some(c) = self.counts.get_mut(&token) {
            *c += 1;
        } else {
            self.keys.push(token.clone());
            self.counts.insert(token, 1);
        }
    }

    fn len_tokens(&self) -> u32 {
        self.counts.values().sum()
    }
}

fn tokenize(sentence: &str) -> OrderedCounter {
    let lowered = sentence.to_lowercase();
    let sw = stopwords();
    let mut counter = OrderedCounter::new();
    for m in token_re().find_iter(&lowered) {
        let tok = m.as_str();
        if !sw.contains(tok) {
            counter.push(tok.to_string());
        }
    }
    counter
}

/// Tokenize + expose just the ordered list (lowercased, 3+ letter, non-stopword
/// tokens with duplicates, in order). Reused by `extract::top_terms`.
pub(crate) fn tokenize_list(sentence: &str) -> Vec<String> {
    let lowered = sentence.to_lowercase();
    let sw = stopwords();
    let mut out = Vec::new();
    for m in token_re().find_iter(&lowered) {
        let tok = m.as_str();
        if !sw.contains(tok) {
            out.push(tok.to_string());
        }
    }
    out
}

/// Neumaier compensated summation.
///
/// `CPython` 3.12+ applies Neumaier compensation inside the built-in `sum()`
/// fast-path whenever the accumulator is a float. Plain IEEE-754 left-fold
/// (Rust's `Iterator::sum`) diverges by 1-3 ULPs on 6+-term accumulations,
/// which breaks byte-identity with the Python reference on any non-trivial
/// sentence. Mirrors the `CPython` implementation in `bltinmodule.c`.
fn neumaier_sum<I: IntoIterator<Item = f64>>(iter: I) -> f64 {
    let mut it = iter.into_iter();
    let Some(first) = it.next() else {
        return 0.0;
    };
    let mut sum = first;
    let mut c = 0.0;
    for x in it {
        let t = sum + x;
        if sum.abs() >= x.abs() {
            c += (sum - t) + x;
        } else {
            c += (x - t) + sum;
        }
        sum = t;
    }
    sum + c
}

fn normalize(scores: &[f64]) -> Vec<f64> {
    let hi = scores.iter().copied().fold(f64::NEG_INFINITY, f64::max);
    if !hi.is_finite() || hi <= 0.0 {
        return vec![0.0; scores.len()];
    }
    scores.iter().map(|s| s / hi).collect()
}

/// TF-IDF score per sentence, normalized to [0, 1].
#[must_use]
pub fn tfidf_score(sentences: &[String]) -> Vec<f64> {
    let tokenized: Vec<OrderedCounter> = sentences.iter().map(|s| tokenize(s)).collect();
    let n = sentences.len();

    // Document frequency. Only values matter, not iteration order.
    let mut df: HashMap<String, u32> = HashMap::new();
    for tc in &tokenized {
        // set(tokens) in Python → dedupe before incrementing df
        for key in &tc.keys {
            *df.entry(key.clone()).or_insert(0) += 1;
        }
    }

    // IDF: log((n+1)/(freq+1)) + 1
    let n_f = n as f64;
    let idf: HashMap<String, f64> = df
        .into_iter()
        .map(|(term, freq)| (term, ((n_f + 1.0) / (f64::from(freq) + 1.0)).ln() + 1.0))
        .collect();

    let raw: Vec<f64> = tokenized
        .iter()
        .map(|tc| {
            if tc.keys.is_empty() {
                return 0.0;
            }
            // Iterate keys in insertion order — mirrors Python's `for term in tf`.
            // Neumaier compensation is required to match `CPython` 3.12+'s built-in
            // sum() on 6+ float accumulations; plain left-fold drifts by 1-3 ULPs.
            let sum: f64 = neumaier_sum(tc.keys.iter().map(|k| {
                let count = f64::from(*tc.counts.get(k).expect("key must exist"));
                let idf_val = *idf.get(k).unwrap_or(&0.0);
                count * idf_val
            }));
            let total_tokens = f64::from(tc.len_tokens());
            sum / total_tokens
        })
        .collect();

    normalize(&raw)
}

/// Position score: endpoints score 1.0, middle scores lowest. U-shaped.
#[must_use]
pub fn position_score(n: usize) -> Vec<f64> {
    if n == 0 {
        return Vec::new();
    }
    if n == 1 {
        return vec![1.0];
    }
    let denom = (n - 1).max(1) as f64;
    let raw: Vec<f64> = (0..n)
        .map(|i| {
            let d = i.min(n - 1 - i) as f64 / denom;
            (1.0 - 2.0 * d).max(0.0)
        })
        .collect();
    normalize(&raw)
}

/// Length score. Peaks in 10-30 word range.
#[must_use]
pub fn length_score(sentences: &[String]) -> Vec<f64> {
    let raw: Vec<f64> = sentences
        .iter()
        .map(|s| {
            let words = s.split_whitespace().count();
            if words == 0 {
                0.0
            } else if (10..=30).contains(&words) {
                1.0
            } else if words < 10 {
                words as f64 / 10.0
            } else {
                // words > 30
                (1.0 - (words as f64 - 30.0) / 50.0).max(0.0)
            }
        })
        .collect();
    normalize(&raw)
}

/// Per-sentence (tfidf, position, length) triples. Mirrors Python's
/// `_composite_score_parts`.
pub(crate) fn composite_score_parts(sentences: &[String]) -> Vec<(f64, f64, f64)> {
    if sentences.is_empty() {
        return Vec::new();
    }
    let t = tfidf_score(sentences);
    let p = position_score(sentences.len());
    let l = length_score(sentences);
    (0..sentences.len()).map(|i| (t[i], p[i], l[i])).collect()
}

/// Composite: 0.60 * tfidf + 0.25 * position + 0.15 * length. Legacy scorer.
#[must_use]
pub fn composite_score(sentences: &[String]) -> Vec<f64> {
    composite_score_parts(sentences)
        .into_iter()
        .map(|(t, p, l)| TFIDF_WEIGHT * t + POSITION_WEIGHT * p + LENGTH_WEIGHT * l)
        .collect()
}

/// Ensure heading-looking lines are separated from their following line by a
/// blank line, so the sentence splitter treats them as standalone sentences.
///
/// Mirrors `src/lede/tfidf.py::_separate_heading_lines`. Only touches lines
/// the heading detector would classify as headings in isolation. Idempotent.
pub(crate) fn separate_heading_lines(text: &str) -> String {
    if text.is_empty() {
        return String::new();
    }
    // Python `str.split("\n")` keeps trailing empty splits (e.g. "a\n" -> ["a", ""]).
    // Rust's `str::split('\n')` does the same, so `collect::<Vec<_>>()` matches.
    let lines: Vec<&str> = text.split('\n').collect();
    let mut out: Vec<String> = Vec::with_capacity(lines.len());
    let last = lines.len().saturating_sub(1);
    for (i, line) in lines.iter().enumerate() {
        out.push((*line).to_string());
        if i == last {
            continue;
        }
        // If current line is a heading candidate AND the next line is non-empty,
        // insert a blank line so paragraph-break splitting kicks in.
        if !line.trim().is_empty() && is_heading(line) {
            let nxt = lines[i + 1];
            if !nxt.trim().is_empty() {
                out.push(String::new());
            }
        }
    }
    out.join("\n")
}

/// Map each sentence index to the lowercase name of the most recent heading
/// above it (or `""` if none). Mirrors Python's `_build_section_map`.
pub(crate) fn build_section_map(sentences: &[String]) -> Vec<String> {
    let mut current = String::new();
    let mut map = Vec::with_capacity(sentences.len());
    for sentence in sentences {
        if is_heading(sentence) {
            current = heading_name(sentence)
                .map(|s| s.to_lowercase())
                .unwrap_or_default();
        }
        map.push(current.clone());
    }
    map
}

/// v0.2 default scorer: legacy composite + four tweaks.
///
/// - Heading sentences get -inf (dropped from selection).
/// - Sentences under a high-signal section heading get tfidf *= 1.3.
/// - Cue-phrase sentences ("Held:", "Resolution:", ...) get +2.0.
/// - Sentences containing digits get +0.3.
pub(crate) fn composite_score_default(sentences: &[String], section_map: &[String]) -> Vec<f64> {
    let parts = composite_score_parts(sentences);
    let mut scores = Vec::with_capacity(sentences.len());
    for (i, sentence) in sentences.iter().enumerate() {
        if is_heading(sentence) {
            scores.push(f64::NEG_INFINITY);
            continue;
        }
        let (mut t, p, l) = parts[i];
        if SECTION_BOOST_HEADINGS.iter().any(|h| *h == section_map[i]) {
            t *= 1.3;
        }
        let mut score = TFIDF_WEIGHT * t + POSITION_WEIGHT * p + LENGTH_WEIGHT * l;
        if cue_phrase_re().is_match(sentence) {
            score += 2.0;
        }
        if digit_re_local().is_match(sentence) {
            score += 0.3;
        }
        scores.push(score);
    }
    scores
}

// --- summarize pipeline (port of the 7-step flow from src/lede/tfidf.py) ---

const MIN_SENTENCES: usize = 3;
const MIN_BUDGET_FOR_SENTENCES: usize = 50;

/// Truncate to `max_length` CHARACTERS (not bytes), appending `"..."` if the
/// text didn't already fit. Matches Python's len(str)-as-chars semantics.
fn truncate(text: &str, max_length: usize) -> String {
    let char_count = text.chars().count();
    if char_count <= max_length {
        return text.to_string();
    }
    let body_budget = max_length.saturating_sub(3);
    let byte_end = text
        .char_indices()
        .nth(body_budget)
        .map_or(text.len(), |(i, _)| i);
    let mut out = text[..byte_end].to_string();
    out.push_str("...");
    out
}

/// Legacy summarizer — byte-identical to v0.0.1 behavior.
fn summarize_legacy(text: &str, max_length: usize) -> String {
    if text.is_empty() {
        return String::new();
    }
    if text.chars().count() <= max_length {
        return text.to_string();
    }
    if max_length < MIN_BUDGET_FOR_SENTENCES {
        return truncate(text, max_length);
    }

    let sentences = crate::sentences::split_sentences(text);
    if sentences.len() < MIN_SENTENCES {
        return truncate(text, max_length);
    }

    let scores = composite_score(&sentences);

    // Sort indices by (-score, index). Stable sort preserves original index on ties.
    let mut indices: Vec<usize> = (0..sentences.len()).collect();
    indices.sort_by(|&a, &b| {
        let sa = -scores[a];
        let sb = -scores[b];
        sa.partial_cmp(&sb)
            .expect("no NaN in pipeline scores")
            .then(a.cmp(&b))
    });

    let mut selected: Vec<usize> = Vec::new();
    let mut used = 0usize;
    let separator_chars = 1usize;
    for idx in indices {
        let sentence = &sentences[idx];
        let sent_chars = sentence.chars().count();
        let needed = sent_chars
            + if selected.is_empty() {
                0
            } else {
                separator_chars
            };
        if used + needed <= max_length {
            selected.push(idx);
            used += needed;
        }
    }

    if selected.is_empty() {
        return truncate(text, max_length);
    }

    selected.sort_unstable();
    selected
        .into_iter()
        .map(|i| sentences[i].clone())
        .collect::<Vec<_>>()
        .join(" ")
}

/// Index-returning selector for the v0.2 default mode.
///
/// Returns `Some((sentences, selected_indices))` when the pipeline fires,
/// `None` when there are not enough sentences or budget (caller decides
/// the fallback). Pure refactor of the selection body from `summarize_default`.
fn select_default_indices(text: &str, max_length: usize) -> Option<(Vec<String>, Vec<usize>)> {
    if text.is_empty() {
        return None;
    }
    if max_length < MIN_BUDGET_FOR_SENTENCES {
        return None;
    }
    let prepared = separate_heading_lines(text);
    let sentences = crate::sentences::split_sentences(&prepared);
    if sentences.len() < MIN_SENTENCES {
        return None;
    }
    let section_map = build_section_map(&sentences);
    let scores = composite_score_default(&sentences, &section_map);
    let mut indices: Vec<usize> = (0..sentences.len()).collect();
    indices.sort_by(|&a, &b| {
        let sa = -scores[a];
        let sb = -scores[b];
        sa.partial_cmp(&sb)
            .expect("no NaN in pipeline scores")
            .then(a.cmp(&b))
    });
    let mut selected: Vec<usize> = Vec::new();
    let mut used = 0usize;
    let separator_chars = 1usize;
    for idx in indices {
        if scores[idx] == f64::NEG_INFINITY {
            continue;
        }
        let sent_chars = sentences[idx].chars().count();
        let needed = sent_chars
            + if selected.is_empty() {
                0
            } else {
                separator_chars
            };
        if used + needed <= max_length {
            selected.push(idx);
            used += needed;
        }
    }
    if selected.is_empty() {
        return None;
    }
    selected.sort_unstable();
    Some((sentences, selected))
}

/// v0.2 default summarizer — legacy pipeline with the default scorer and
/// heading-line preprocessing. Headings are filtered from candidates.
///
/// Unlike legacy mode, default mode always runs the sentence pipeline when
/// the budget allows it (>= `MIN_BUDGET_FOR_SENTENCES`) so headings are
/// filtered even when the raw input would otherwise fit.
fn summarize_default(text: &str, max_length: usize) -> String {
    if text.is_empty() {
        return String::new();
    }
    if max_length < MIN_BUDGET_FOR_SENTENCES {
        return truncate(text, max_length);
    }
    if let Some((sentences, selected)) = select_default_indices(text, max_length) {
        selected
            .into_iter()
            .map(|i| sentences[i].clone())
            .collect::<Vec<_>>()
            .join(" ")
    } else {
        let prepared = separate_heading_lines(text);
        let sentences = crate::sentences::split_sentences(&prepared);
        if sentences.len() < MIN_SENTENCES && text.chars().count() <= max_length {
            text.to_string()
        } else {
            truncate(text, max_length)
        }
    }
}

/// Extractive summary of `text` with optional structured enrichments.
///
/// `Mode::Default` applies the v0.2 scorer tweaks (heading filter, cue-phrase
/// boost, digit bonus, section-position weight). `Mode::Legacy` preserves
/// v0.0.1 behavior byte-identically. `Mode::Coverage` is the C2 coverage mode.
///
/// `attach` toggles structured primitives on the result. Stub primitives
/// return empty `Vec`s in v0.2 T4; real implementations land in T6-T11.
#[must_use]
pub fn summarize_with_attach(
    text: &str,
    max_length: usize,
    mode: Mode,
    attach: &AttachOpts,
) -> SummaryResult {
    let summary = match mode {
        Mode::Legacy => summarize_legacy(text, max_length),
        Mode::Default => summarize_default(text, max_length),
        Mode::Coverage => crate::coverage::summarize_coverage(text, max_length),
    };
    SummaryResult {
        summary,
        stats: if attach.stats {
            Some(crate::extract::stats::stats(text))
        } else {
            None
        },
        outline: if attach.outline {
            Some(crate::extract::outline::outline(text))
        } else {
            None
        },
        metadata: if attach.metadata {
            Some(crate::extract::metadata::metadata(text))
        } else {
            None
        },
        phrases: if attach.phrases {
            Some(crate::extract::phrases::phrases(text, None))
        } else {
            None
        },
        correlated_facts: if attach.correlated_facts {
            Some(crate::extract::correlate::correlate_facts(text))
        } else {
            None
        },
        pinned_headings: Vec::new(),
    }
}

/// Extractive summary of `text` capped at `max_length` characters.
///
/// Shortcut for `summarize_with_attach` with the default (empty) attach set.
#[must_use]
pub fn summarize(text: &str, max_length: usize, mode: Mode) -> SummaryResult {
    summarize_with_attach(text, max_length, mode, &AttachOpts::default())
}

// --- v0.4 hint-aware summarization ---

/// Options for hint-biased summarization.
///
/// Default (all fields at their zero/default values) produces output
/// byte-identical to [`summarize`] — the hint path is only activated when
/// `hints` is non-empty after preprocessing.
#[derive(Debug, Clone)]
pub struct SummarizeOpts {
    /// `(term, weight)` hint pairs. Terms are preprocessed (lowercased,
    /// whitespace-collapsed, empties dropped) before use.
    pub hints: Vec<HintWeight>,
    /// Budget fraction allocated to the hint pool. Must be in `[0.0, 1.0]`.
    /// `0.0` gives the hint pool no budget (equivalent to no hints);
    /// `1.0` allocates the entire budget to the hint pool.
    pub hint_focus: f64,
    /// Selection mode for the hint pool.
    pub hint_mode: HintMode,
}

impl Default for SummarizeOpts {
    fn default() -> Self {
        Self {
            hints: Vec::new(),
            hint_focus: 0.7,
            hint_mode: HintMode::Soft,
        }
    }
}

/// Index-returning inner two-pool selection algorithm.
///
/// Returns the sorted selected indices (may be empty — caller handles
/// truncation fallback). Preconditions same as [`two_pool_select`].
fn two_pool_select_indices(
    _text: &str,
    max_length: usize,
    mode: Mode,
    processed: &[HintWeight],
    hint_focus: f64,
    hint_mode: HintMode,
    sentences: &[String],
) -> Vec<usize> {
    // Compute plain scores.
    let plain_scores: Vec<f64> = if mode == Mode::Coverage {
        crate::coverage::composite_score_coverage_for_hints(sentences)
    } else {
        let section_map = build_section_map(sentences);
        composite_score_default(sentences, &section_map)
    };

    // Compute per-sentence hint bonuses, then build hint_scores.
    let bonuses: Vec<f64> = sentences
        .iter()
        .map(|s| crate::hints::hint_bonus(s, processed))
        .collect();

    let hint_scores: Vec<f64> = match hint_mode {
        HintMode::Hard => (0..sentences.len())
            .map(|i| {
                if bonuses[i] > 0.0 {
                    plain_scores[i] + bonuses[i]
                } else {
                    f64::NEG_INFINITY
                }
            })
            .collect(),
        HintMode::Soft => (0..sentences.len())
            .map(|i| plain_scores[i] + bonuses[i])
            .collect(),
    };

    // Character lengths (Python `len(s)` counts chars; Rust mirrors with `chars().count()`).
    let lengths: Vec<usize> = sentences.iter().map(|s| s.chars().count()).collect();

    // Budget split via integer-math rounding (mirrors Python `round_to_int`).
    // `max_length` fits in i64 on any realistic platform; result is in [0, max_length].
    #[allow(clippy::cast_possible_wrap, clippy::cast_sign_loss)]
    let hint_budget = crate::hints::round_to_int(max_length as i64, hint_focus) as usize;
    let normal_budget = max_length - hint_budget;

    let empty: HashSet<usize> = HashSet::new();
    let mut selected_hint =
        crate::hints::select_by_chars(&hint_scores, &lengths, hint_budget, &empty, 1);
    let mut selected_normal =
        crate::hints::select_by_chars(&plain_scores, &lengths, normal_budget, &selected_hint, 1);

    // Rollover: unused hint budget → plain pool.
    // In hard mode, rollover still uses hint_scores so -inf sentences stay
    // ineligible. In soft mode, plain_scores allow any sentence.
    // The extra indices always merge into selected_normal (mirrors Python).
    let used_hint: usize = selected_hint.iter().map(|i| lengths[*i]).sum::<usize>()
        + selected_hint.len().saturating_sub(1);
    let unused_hint = hint_budget.saturating_sub(used_hint);
    if unused_hint > 0 {
        let rollover_scores = if hint_mode == HintMode::Hard {
            &hint_scores
        } else {
            &plain_scores
        };
        let mut excl: HashSet<usize> = selected_hint.iter().copied().collect();
        excl.extend(selected_normal.iter().copied());
        let extra = crate::hints::select_by_chars(rollover_scores, &lengths, unused_hint, &excl, 1);
        selected_normal.extend(extra);
    }

    // Soft-only rollover: unused normal budget → hint pool.
    if hint_mode == HintMode::Soft {
        let used_normal: usize = selected_normal.iter().map(|i| lengths[*i]).sum::<usize>()
            + selected_normal.len().saturating_sub(1);
        let unused_normal = normal_budget.saturating_sub(used_normal);
        if unused_normal > 0 {
            let mut excl: HashSet<usize> = selected_hint.iter().copied().collect();
            excl.extend(selected_normal.iter().copied());
            let extra =
                crate::hints::select_by_chars(&hint_scores, &lengths, unused_normal, &excl, 1);
            selected_hint.extend(extra);
        }
    }

    // Merge, sort, deduplicate.
    let mut selected: Vec<usize> = selected_hint
        .into_iter()
        .chain(selected_normal)
        .collect::<HashSet<usize>>()
        .into_iter()
        .collect();
    selected.sort_unstable();
    selected
}

/// Inner two-pool selection algorithm used by [`summarize_with_hints`].
///
/// Preconditions (caller has validated):
/// - `processed` is non-empty
/// - `mode` is not `Mode::Legacy`
/// - `hint_focus` is in `[0.0, 1.0]`
/// - `text` is non-empty and `max_length >= MIN_BUDGET_FOR_SENTENCES`
/// - `sentences.len() >= MIN_SENTENCES`
fn two_pool_select(
    text: &str,
    max_length: usize,
    mode: Mode,
    processed: &[HintWeight],
    hint_focus: f64,
    hint_mode: HintMode,
    sentences: &[String],
) -> String {
    let selected = two_pool_select_indices(
        text, max_length, mode, processed, hint_focus, hint_mode, sentences,
    );
    if selected.is_empty() {
        truncate(text, max_length)
    } else {
        selected
            .into_iter()
            .map(|i| sentences[i].clone())
            .collect::<Vec<_>>()
            .join(" ")
    }
}

/// Index-returning selector for the hint-biased path.
///
/// Returns `Some((sentences, selected_indices))` when the pipeline fires,
/// `None` for empty text, insufficient budget, or too few sentences.
fn select_with_hints_indices(
    text: &str,
    max_length: usize,
    mode: Mode,
    processed: &[HintWeight],
    hint_focus: f64,
    hint_mode: HintMode,
) -> Option<(Vec<String>, Vec<usize>)> {
    if text.is_empty() {
        return None;
    }
    if max_length < MIN_BUDGET_FOR_SENTENCES {
        return None;
    }
    let prepared = separate_heading_lines(text);
    let sentences = crate::sentences::split_sentences(&prepared);
    if sentences.len() < MIN_SENTENCES {
        return None;
    }
    let selected = two_pool_select_indices(
        text, max_length, mode, processed, hint_focus, hint_mode, &sentences,
    );
    if selected.is_empty() {
        return None;
    }
    Some((sentences, selected))
}

/// Mode dispatcher — returns `(sentences, selected_indices)` for the
/// appropriate selection algorithm.
///
/// Routes: non-empty hints → hints path; Coverage (no hints) → coverage
/// path; Default/Legacy (no hints) → default path.
fn select_for_mode(
    text: &str,
    max_length: usize,
    mode: Mode,
    processed: &[HintWeight],
    hint_focus: f64,
    hint_mode: HintMode,
) -> Option<(Vec<String>, Vec<usize>)> {
    if !processed.is_empty() {
        return select_with_hints_indices(text, max_length, mode, processed, hint_focus, hint_mode);
    }
    if mode == Mode::Coverage {
        return crate::coverage::select_coverage_indices(text, max_length);
    }
    select_default_indices(text, max_length)
}

/// Hint-biased extractive summary.
///
/// When `opts.hints` is empty (or all hints are blank after preprocessing),
/// delegates to [`summarize`] for byte-identical backward compatibility.
///
/// # Panics
///
/// - `Mode::Legacy` with non-empty processed hints: legacy mode does not
///   support hint biasing.
/// - `opts.hint_focus` outside `[0.0, 1.0]`.
#[must_use]
pub fn summarize_with_hints(
    text: &str,
    max_length: usize,
    mode: Mode,
    opts: &SummarizeOpts,
) -> SummaryResult {
    let processed = crate::hints::preprocess_hints(&opts.hints);

    // Empty hints → delegate to plain summarize (backward compat, byte-identical).
    if processed.is_empty() {
        return summarize(text, max_length, mode);
    }

    // Validate.
    assert!(mode != Mode::Legacy, "hints not supported in legacy mode");
    assert!(
        (0.0..=1.0).contains(&opts.hint_focus),
        "hint_focus must be in [0.0, 1.0]; got {}",
        opts.hint_focus
    );

    // Early-exit for trivial inputs (mirrors Python `_summarize_with_hints`).
    if text.is_empty() {
        return SummaryResult::bare(String::new());
    }
    if max_length < MIN_BUDGET_FOR_SENTENCES {
        return SummaryResult::bare(truncate(text, max_length));
    }

    let prepared = separate_heading_lines(text);
    let sentences = crate::sentences::split_sentences(&prepared);
    if sentences.len() < MIN_SENTENCES {
        let summary = if text.chars().count() <= max_length {
            text.to_string()
        } else {
            truncate(text, max_length)
        };
        return SummaryResult::bare(summary);
    }

    let summary = two_pool_select(
        text,
        max_length,
        mode,
        &processed,
        opts.hint_focus,
        opts.hint_mode,
        &sentences,
    );

    SummaryResult::bare(summary)
}

/// Options for heading/pin retention. All-default = no pinning.
#[derive(Debug, Clone, Default)]
pub struct PinOpts {
    pub keep_headings: bool,
    pub include_toc: bool,
    pub pin: Vec<String>,
    /// Caller-supplied heading list for `render_with_pins` / `prepend_blocks`.
    /// When non-empty and `keep_headings` is true, overrides heading detection
    /// in the rendered output. When `keep_headings` is false (and `include_toc`
    /// is false and `pin` is empty), this field is a no-op — byte-identical to
    /// an empty list. Mirrors Python `summarize(..., headings=...)`.
    pub headings: Vec<String>,
}

/// Extractive summary with optional heading/pin retention.
///
/// Mirrors Python `summarize(..., keep_headings=, include_toc=, pin=)`.
/// All `PinOpts` defaults = byte-identical to [`summarize_with_hints`].
///
/// # Panics
/// Panics if `PinOpts` is active and `mode == Mode::Legacy`.
#[must_use]
pub fn summarize_with_pins(
    text: &str,
    max_length: usize,
    mode: Mode,
    hint_opts: &SummarizeOpts,
    pin_opts: &PinOpts,
) -> SummaryResult {
    let processed = crate::hints::preprocess_hints(&hint_opts.hints);
    let pins_active = pin_opts.keep_headings
        || pin_opts.include_toc
        || !pin_opts.pin.is_empty()
        || !pin_opts.headings.is_empty();
    if pins_active {
        assert!(
            mode != Mode::Legacy,
            "keep_headings/include_toc/pin/headings not supported in legacy mode"
        );
    }

    // Base summary for the mode (handles empty hints → plain summarize internally).
    let base = summarize_with_hints(text, max_length, mode, hint_opts);
    let mut summary = base.summary;
    let mut pinned_headings: Vec<String> = Vec::new();

    if pins_active {
        let pin_slice: Option<&[String]> = if pin_opts.pin.is_empty() {
            None
        } else {
            Some(&pin_opts.pin)
        };
        let headings_slice: Option<&[String]> = if pin_opts.headings.is_empty() {
            None
        } else {
            Some(pin_opts.headings.as_slice())
        };
        let sel = if pin_opts.keep_headings {
            select_for_mode(
                text,
                max_length,
                mode,
                &processed,
                hint_opts.hint_focus,
                hint_opts.hint_mode,
            )
        } else {
            None
        };
        if let Some((sentences, selected)) = sel {
            let (woven, pinned) = crate::pins::render_with_pins(
                &sentences,
                &selected,
                true,
                pin_opts.include_toc,
                pin_slice,
                text,
                headings_slice,
            );
            summary = woven;
            pinned_headings = pinned;
        } else if pin_opts.include_toc || pin_slice.is_some() {
            summary = crate::pins::prepend_blocks(
                &summary,
                pin_opts.include_toc,
                pin_slice,
                text,
                headings_slice,
            );
        }
    }

    let mut result = SummaryResult::bare(summary);
    result.pinned_headings = pinned_headings;
    result
}
