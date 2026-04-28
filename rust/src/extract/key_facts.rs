//! Key-facts extractor — top-N fact-bearing sentences as complete strings.
//!
//! Mirrors `src/lede/extract/key_facts.py`. Ranked by composite tfidf + stat
//! density, deduped by normalized (`stat_type`, value), returned in document
//! order. Composition primitive: reuses `stats()` and `composite_score_parts`
//! — no new regex patterns.
//!
//! Rust has no `backend=` argument (only 'regex' emits byte-identical output
//! with Python). The `convert_word_names` flag is surfaced via
//! [`KeyFactsOptions`] mirroring the stats API.

use crate::extract::stats::{StatsOptions, stats_with_options};
use crate::sentences::split_sentences;
use crate::tfidf::composite_score_parts;
use regex::Regex;
use std::collections::{HashMap, HashSet};
use std::sync::OnceLock;

// Shared with Python's lede/extract/key_facts.py::_STAT_DENSITY_WEIGHT.
const STAT_DENSITY_WEIGHT: f64 = 0.15;
const TFIDF_WEIGHT: f64 = 0.60;
const POSITION_WEIGHT: f64 = 0.25;
const LENGTH_WEIGHT: f64 = 0.15;

/// Candidate row in the ranking loop: (score, sentence index, dedup keys).
type Candidate = (f64, usize, HashSet<(String, String)>);

fn hyphen_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[-_/]+").expect("static regex"))
}

fn ws_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\s+").expect("static regex"))
}

/// Normalize a value string for dedup. Matches
/// `benchmarks/extraction_eval.py::_norm` and Python
/// `lede/extract/key_facts.py::_norm_value`.
fn norm_value(s: &str) -> String {
    let lowered = s.to_lowercase();
    let dashed = hyphen_re().replace_all(&lowered, " ");
    ws_re().replace_all(dashed.trim(), " ").to_string()
}

/// Options for [`key_facts_with_options`]. Mirrors Python's keyword-only
/// kwargs on `key_facts()`.
#[derive(Debug, Clone, Copy)]
pub struct KeyFactsOptions {
    /// Max number of returned sentences. Default `10`.
    pub max_facts: usize,
    /// Forward to `stats()`; requires the `wordforms` cargo feature when
    /// true. No-op (treated as false) when the feature is off.
    pub convert_word_names: bool,
}

impl Default for KeyFactsOptions {
    fn default() -> Self {
        Self {
            max_facts: 10,
            convert_word_names: false,
        }
    }
}

/// Return top-N sentences containing numeric/named facts.
///
/// See [`key_facts_with_options`] for the full contract.
#[must_use]
pub fn key_facts(text: &str, max_facts: usize) -> Vec<String> {
    key_facts_with_options(
        text,
        KeyFactsOptions {
            max_facts,
            ..Default::default()
        },
    )
}

/// Return top-N sentences containing numeric/named facts.
///
/// Candidates are any sentence that produces at least one `Stat`. Each
/// candidate is scored as:
///
/// ```text
///   0.60*tfidf + 0.25*position + 0.15*length
///   + 0.15 * (num_stats_in_sentence / sentence_len_in_tokens)
/// ```
///
/// Candidates are deduped by normalized (`stat_type`, value): if two
/// sentences share any such key, only the higher-scored one is kept.
/// Ties broken by earlier document position. The top `opts.max_facts`
/// survivors are returned in **document order** (not score order).
#[must_use]
pub fn key_facts_with_options(text: &str, opts: KeyFactsOptions) -> Vec<String> {
    if text.is_empty() {
        return Vec::new();
    }
    let all_stats = stats_with_options(
        text,
        StatsOptions {
            convert_word_names: opts.convert_word_names,
        },
    );
    if all_stats.is_empty() {
        return Vec::new();
    }

    let sentences = split_sentences(text);
    if sentences.is_empty() {
        return Vec::new();
    }

    // Build a sentence-string → first-index lookup for O(1) grouping.
    // First occurrence wins — matches Python dict.setdefault behavior and
    // how stats() emits context_sentence.
    let mut sent_to_idx: HashMap<&str, usize> = HashMap::with_capacity(sentences.len());
    for (i, s) in sentences.iter().enumerate() {
        sent_to_idx.entry(s.as_str()).or_insert(i);
    }

    // Group stats by their context_sentence index. Preserve insertion order
    // so the same stat ordering feeds both the density count and the dedup
    // key set.
    let mut stats_by_sentence: HashMap<usize, Vec<&crate::extract::stats::Stat>> = HashMap::new();
    for stat in &all_stats {
        if let Some(&idx) = sent_to_idx.get(stat.context_sentence.as_str()) {
            stats_by_sentence.entry(idx).or_default().push(stat);
        }
    }
    if stats_by_sentence.is_empty() {
        return Vec::new();
    }

    let parts = composite_score_parts(&sentences);

    let mut candidates: Vec<Candidate> = Vec::with_capacity(stats_by_sentence.len());
    for (idx, stat_list) in &stats_by_sentence {
        let (t, p, l) = parts[*idx];
        let composite = TFIDF_WEIGHT * t + POSITION_WEIGHT * p + LENGTH_WEIGHT * l;
        // Whitespace-token count; matches Python's sentences[idx].split().
        let tok_count = sentences[*idx].split_whitespace().count().max(1);
        let density = stat_list.len() as f64 / tok_count as f64;
        let score = composite + STAT_DENSITY_WEIGHT * density;

        let keys: HashSet<(String, String)> = stat_list
            .iter()
            .map(|s| (s.stat_type.clone(), norm_value(&s.value)))
            .collect();
        candidates.push((score, *idx, keys));
    }

    // Sort score-descending, idx-ascending (deterministic tie-break).
    candidates.sort_by(|a, b| {
        b.0.partial_cmp(&a.0)
            .expect("no NaN in scores")
            .then_with(|| a.1.cmp(&b.1))
    });

    let mut kept_keys: HashSet<(String, String)> = HashSet::new();
    let mut kept: Vec<usize> = Vec::with_capacity(opts.max_facts);
    for (_, idx, keys) in candidates {
        if keys.iter().any(|k| kept_keys.contains(k)) {
            continue;
        }
        kept_keys.extend(keys);
        kept.push(idx);
        if kept.len() >= opts.max_facts {
            break;
        }
    }

    // Return in document order.
    kept.sort_unstable();
    kept.into_iter().map(|i| sentences[i].clone()).collect()
}
