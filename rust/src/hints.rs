//! Hint preprocessing, matching, bonus formula, rounding, two-pool selection.
//!
//! Mirror of `src/lede/_hints.py`. Output must be byte-identical for every
//! parity fixture in `fixtures/v0_4_hints/`.

use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::{Mutex, OnceLock};

/// `(preprocessed_hint, weight)` pair.
pub type HintWeight = (String, f64);

/// Additive bonus base weight applied to every hint match.
pub const HINT_BASE_WEIGHT: f64 = 0.5;

/// Maximum per-hint match count before capping in [`hint_bonus`].
pub const HINT_MATCH_CAP: usize = 3;

/// Selection mode for hint-aware pipelines.
///
/// - `Soft` — bonus-augmented ranking: every sentence is a candidate, hints
///   raise scores.
/// - `Hard` — filter to hint-bearing sentences only before ranking.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum HintMode {
    Soft,
    Hard,
}

fn whitespace_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\s+").expect("static regex"))
}

fn regex_cache() -> &'static Mutex<HashMap<String, Regex>> {
    static CACHE: OnceLock<Mutex<HashMap<String, Regex>>> = OnceLock::new();
    CACHE.get_or_init(|| Mutex::new(HashMap::new()))
}

/// Preprocess hint input: strip + collapse whitespace + lowercase + drop empties.
///
/// Mirrors `preprocess_hints` in `src/lede/_hints.py`. The caller passes hints
/// as `(term, weight)` slices; this normalizes the term strings.
#[must_use]
pub fn preprocess_hints(hints: &[HintWeight]) -> Vec<HintWeight> {
    let mut out: Vec<HintWeight> = Vec::with_capacity(hints.len());
    for (raw, weight) in hints {
        let stripped = raw.trim();
        if stripped.is_empty() {
            continue;
        }
        let collapsed = whitespace_re().replace_all(stripped, " ").to_string();
        out.push((collapsed.to_lowercase(), *weight));
    }
    out
}

/// Count non-overlapping word-bounded matches of `hint` in `sentence`
/// (case-insensitive).
///
/// `hint` must already be preprocessed (lowercased, whitespace-collapsed).
/// The sentence is lowercased here before matching. Returns 0 for empty hints.
///
/// Uses `(?-u)\b` to disable Unicode mode and reproduce Python's ASCII `\b`
/// behavior.
#[must_use]
pub fn match_count(hint: &str, sentence: &str) -> usize {
    if hint.is_empty() {
        return 0;
    }
    let lowered = sentence.to_lowercase();
    let mut cache = regex_cache().lock().expect("hint regex cache poisoned");
    let re = cache.entry(hint.to_string()).or_insert_with(|| {
        // (?-u) disables Unicode mode so \b matches Python's ASCII word-boundary.
        Regex::new(&format!(r"(?-u)\b{}\b", regex::escape(hint))).expect("hint regex")
    });
    re.find_iter(&lowered).count()
}

/// Portable integer-math rounding for budget splits.
///
/// Avoids Python `round` (banker's rounding) vs Rust `f64::round`
/// (half-away-from-zero) divergence by encoding `focus` as an integer
/// numerator over 10 000, then performing integer arithmetic throughout.
/// Results are byte-identical to the Python mirror in `src/lede/_hints.py`.
#[must_use]
pub fn round_to_int(value: i64, focus: f64) -> i64 {
    #[allow(clippy::cast_possible_truncation)]
    let num = (focus * 10_000.0) as i64;
    let den: i64 = 10_000;
    (value * num + den / 2) / den
}

/// Sum of per-hint bonuses for one sentence/target.
///
/// For each `(hint, weight)`: `min(count, HINT_MATCH_CAP) × weight × HINT_BASE_WEIGHT`.
#[must_use]
pub fn hint_bonus(sentence: &str, hints: &[HintWeight]) -> f64 {
    let mut total = 0.0;
    for (h, w) in hints {
        let c = match_count(h, sentence);
        if c == 0 {
            continue;
        }
        let capped = c.min(HINT_MATCH_CAP);
        total += (capped as f64) * w * HINT_BASE_WEIGHT;
    }
    total
}

/// Sort indices by (`-score`, original index). Deterministic tiebreak.
fn rank_indices(scores: &[f64]) -> Vec<usize> {
    let mut idx: Vec<usize> = (0..scores.len()).collect();
    idx.sort_by(|&a, &b| {
        scores[b]
            .partial_cmp(&scores[a])
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.cmp(&b))
    });
    idx
}

/// Greedy char-budget selector.
///
/// Picks indices in score-descending order (position tiebreak) until the budget
/// can't fit another sentence. Skips `exclude`. Treats `-inf` scores as
/// ineligible. Mirrors `select_by_chars` in `src/lede/_hints.py`.
#[must_use]
pub fn select_by_chars<S: std::hash::BuildHasher>(
    scores: &[f64],
    lengths: &[usize],
    budget: usize,
    exclude: &HashSet<usize, S>,
    separator_len: usize,
) -> HashSet<usize> {
    let mut chosen: HashSet<usize> = HashSet::new();
    if budget == 0 {
        return chosen;
    }
    let mut used: usize = 0;
    for idx in rank_indices(scores) {
        if exclude.contains(&idx) {
            continue;
        }
        if scores[idx] == f64::NEG_INFINITY {
            continue;
        }
        let sep = if chosen.is_empty() { 0 } else { separator_len };
        let needed = lengths[idx] + sep;
        if used + needed <= budget {
            chosen.insert(idx);
            used += needed;
        }
    }
    chosen
}

/// Top-N count-budget selector.
///
/// Same ranking as [`select_by_chars`]. Stops after `count` selections.
/// Treats `-inf` as ineligible. Mirrors `select_by_count` in
/// `src/lede/_hints.py`.
#[must_use]
pub fn select_by_count<S: std::hash::BuildHasher>(
    scores: &[f64],
    count: usize,
    exclude: &HashSet<usize, S>,
) -> HashSet<usize> {
    let mut chosen: HashSet<usize> = HashSet::new();
    if count == 0 {
        return chosen;
    }
    for idx in rank_indices(scores) {
        if exclude.contains(&idx) {
            continue;
        }
        if scores[idx] == f64::NEG_INFINITY {
            continue;
        }
        chosen.insert(idx);
        if chosen.len() >= count {
            break;
        }
    }
    chosen
}
