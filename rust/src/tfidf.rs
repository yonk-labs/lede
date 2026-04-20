//! TF-IDF + position + length extractive pipeline.
//!
//! Port of src/skimr/tfidf.py. Output is byte-identical to Python for every
//! fixture. Insertion-order iteration of per-sentence token counters is
//! preserved exactly so floating-point sums line up.

use regex::Regex;
use std::collections::HashMap;
use std::sync::OnceLock;

const TFIDF_WEIGHT: f64 = 0.60;
const POSITION_WEIGHT: f64 = 0.25;
const LENGTH_WEIGHT: f64 = 0.15;

/// Stopword list. Must stay byte-identical to Python's `_STOPWORDS` frozenset.
/// See src/skimr/tfidf.py.
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

/// Tokenize + expose just the ordered list (used by some callers).
#[allow(dead_code)] // used by T6 summarize
fn tokenize_list(sentence: &str) -> Vec<String> {
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

/// Composite: 0.60 * tfidf + 0.25 * position + 0.15 * length.
#[must_use]
pub fn composite_score(sentences: &[String]) -> Vec<f64> {
    if sentences.is_empty() {
        return Vec::new();
    }
    let t = tfidf_score(sentences);
    let p = position_score(sentences.len());
    let l = length_score(sentences);
    (0..sentences.len())
        .map(|i| TFIDF_WEIGHT * t[i] + POSITION_WEIGHT * p[i] + LENGTH_WEIGHT * l[i])
        .collect()
}
