//! `extract::textrank` — term-level `TextRank` keyphrase ranking (issue #7).
//!
//! Builds an undirected co-occurrence graph over non-stopword tokens (sliding
//! window) and runs weighted `PageRank` (Mihalcea–Tarau). Pure Rust, zero deps.
//!
//! **Capability-parity only:** deterministic within Rust, but NOT byte-identical
//! to any Python reference (the Python `textrank.py` is a different, sentence-
//! level variant). It is therefore **off the fixture walker**, consistent with
//! lede's "optional backends make no parity promise" policy.
//!
//! Determinism: a sorted vocabulary fixes node order, and every float sum is
//! taken over neighbors in sorted-index order — no hash-iteration-order
//! dependence (lede's determinism rule).

use std::cmp::Ordering;
use std::collections::HashMap;

use crate::tfidf::tokenize_list;

const WINDOW: usize = 4;
const DAMPING: f64 = 0.85;
const MAX_ITER: usize = 50;
const TOL: f64 = 1e-6;

/// Top-N keyphrase tokens ranked by weighted `PageRank` over a co-occurrence
/// graph, score-descending with ties broken by term. Deterministic.
#[must_use]
pub fn textrank_terms(text: &str, n: usize) -> Vec<String> {
    let tokens = tokenize_list(text);
    if tokens.is_empty() {
        return Vec::new();
    }

    // Sorted, unique vocabulary → deterministic node indexing.
    let mut vocab: Vec<String> = tokens.clone();
    vocab.sort();
    vocab.dedup();
    let count = vocab.len();
    if count == 1 {
        return vocab.into_iter().take(n).collect();
    }
    let index: HashMap<&str, usize> = vocab
        .iter()
        .enumerate()
        .map(|(i, t)| (t.as_str(), i))
        .collect();

    // Undirected weighted co-occurrence within a sliding window.
    let mut weight: Vec<HashMap<usize, f64>> = vec![HashMap::new(); count];
    for (i, tok) in tokens.iter().enumerate() {
        let a = index[tok.as_str()];
        let end = (i + WINDOW).min(tokens.len());
        for other in &tokens[i + 1..end] {
            let b = index[other.as_str()];
            if a != b {
                *weight[a].entry(b).or_insert(0.0) += 1.0;
                *weight[b].entry(a).or_insert(0.0) += 1.0;
            }
        }
    }

    // Neighbor lists sorted by index — deterministic summation order.
    let neighbors: Vec<Vec<(usize, f64)>> = weight
        .iter()
        .map(|m| {
            let mut v: Vec<(usize, f64)> = m.iter().map(|(&u, &w)| (u, w)).collect();
            v.sort_by_key(|&(u, _)| u);
            v
        })
        .collect();
    let degree: Vec<f64> = neighbors
        .iter()
        .map(|ns| ns.iter().map(|&(_, w)| w).sum())
        .collect();

    // Weighted PageRank power iteration.
    let count_f = count as f64;
    let mut score = vec![1.0 / count_f; count];
    for _ in 0..MAX_ITER {
        let mut next = vec![(1.0 - DAMPING) / count_f; count];
        for v in 0..count {
            let mut acc = 0.0;
            for &(u, w) in &neighbors[v] {
                if degree[u] > 0.0 {
                    acc += (w / degree[u]) * score[u];
                }
            }
            next[v] += DAMPING * acc;
        }
        let diff: f64 = (0..count).map(|i| (next[i] - score[i]).abs()).sum();
        score = next;
        if diff < TOL {
            break;
        }
    }

    let mut ranked: Vec<usize> = (0..count).collect();
    ranked.sort_by(|&a, &b| {
        score[b]
            .partial_cmp(&score[a])
            .unwrap_or(Ordering::Equal)
            .then_with(|| vocab[a].cmp(&vocab[b]))
    });
    ranked
        .into_iter()
        .take(n)
        .map(|i| vocab[i].clone())
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn empty_input() {
        assert!(textrank_terms("", 10).is_empty());
    }

    #[test]
    fn deterministic() {
        let doc = "alpha beta gamma. alpha beta delta. alpha gamma epsilon. beta gamma zeta.";
        assert_eq!(textrank_terms(doc, 10), textrank_terms(doc, 10));
    }

    #[test]
    fn central_term_outranks_peripheral() {
        // "network" recurs and co-occurs widely → outranks a once-seen term.
        let doc = "network speed matters. network latency matters. network packet loss matters. \
                   network bandwidth matters.";
        let ranked = textrank_terms(doc, 10);
        let pos = |t: &str| ranked.iter().position(|x| x == t);
        assert!(
            pos("network") < pos("bandwidth"),
            "network should outrank bandwidth; ranked: {ranked:?}"
        );
    }

    #[test]
    fn respects_n() {
        let doc = "alpha beta gamma. alpha beta delta. alpha gamma epsilon.";
        assert!(textrank_terms(doc, 2).len() <= 2);
    }
}
