//! Shared CRF feature extraction. Returns `Vec<Vec<String>>` (one feature-string
//! list per token) — deliberately free of `crfs` types so it is unit-testable on
//! its own and reused verbatim by both the trainer and inference.

use crate::gazetteer;

/// Gazetteer lists exposed as binary membership features. Order is fixed so the
/// emitted feature strings are deterministic.
const GAZETTEERS: &[(&str, &[&str])] = &[
    ("ORGS", gazetteer::ORGS),
    ("ORG_SUFFIXES", gazetteer::ORG_SUFFIXES),
    ("COUNTRIES", gazetteer::COUNTRIES),
    ("PLACES", gazetteer::PLACES),
    ("FIRST_NAMES", gazetteer::FIRST_NAMES),
    ("TITLES", gazetteer::TITLES),
    ("CALENDAR", gazetteer::CALENDAR),
    // Expanded type-disambiguation lists (CRF features ONLY; generated
    // src/crf/data.rs). PERSON <- surname/forename, GPE/LOC <- city/state,
    // ORG <- org-word. The rule-based extract_entities does NOT use these, so
    // its golden tests stay byte-identical.
    ("SURNAME", super::data::SURNAMES),
    ("FORENAME", super::data::FORENAMES),
    ("CITY", super::data::CITIES),
    ("STATE", super::data::US_STATES),
    ("ORGWORD", super::data::ORG_WORDS),
];

/// Gazetteer membership as O(1) lookups, built once. The lists (esp. the 2000+
/// surnames) make a per-token linear `contains` scan dominate train + inference
/// time; HashSets keep feature extraction fast (and the sub-ms inference promise).
fn gaz_sets() -> &'static [(&'static str, std::collections::HashSet<String>)] {
    use std::sync::OnceLock;
    static SETS: OnceLock<Vec<(&'static str, std::collections::HashSet<String>)>> = OnceLock::new();
    SETS.get_or_init(|| {
        GAZETTEERS
            .iter()
            .map(|(name, list)| {
                (*name, list.iter().map(|w| w.to_ascii_lowercase()).collect())
            })
            .collect()
    })
}

/// Feature strings for a single token. `pos` is the rule-based tag when the
/// `pos` feature is enabled upstream, else `None` (feature omitted, no hard dep).
fn token_features(word: &str, pos: Option<&str>) -> Vec<String> {
    let mut f = Vec::new();
    f.push(format!("w.lower={}", word.to_lowercase()));
    f.push(format!("shape={}", shape(word)));

    let chars: Vec<char> = word.chars().collect();
    let n = chars.len();
    for k in 1..=3 {
        if n >= k {
            let pre: String = chars[..k].iter().collect();
            f.push(format!("pre{k}={pre}"));
        }
    }
    for k in 1..=4 {
        if n >= k {
            let suf: String = chars[n - k..].iter().collect();
            f.push(format!("suf{k}={suf}"));
        }
    }

    if word.chars().next().is_some_and(char::is_uppercase) {
        f.push("is_title".to_string());
    }
    if n > 0 && word.chars().all(char::is_uppercase) {
        f.push("is_upper".to_string());
    }
    if n > 0 && word.chars().all(|c| c.is_ascii_digit()) {
        f.push("is_digit".to_string());
    }
    if word.contains('-') {
        f.push("has_hyphen".to_string());
    }
    if word.chars().any(|c| c.is_ascii_digit()) {
        f.push("has_digit".to_string());
    }

    let lower = word.to_ascii_lowercase();
    for (name, set) in gaz_sets() {
        if set.contains(&lower) {
            f.push(format!("gaz={name}"));
        }
    }

    if let Some(tag) = pos {
        f.push(format!("pos={tag}"));
    }
    f
}

/// Full per-token feature lists for a tokenized sentence, including a ±2 context
/// window (neighbour features prefixed `±k:`) and BOS/EOS markers. This is the
/// single feature contract shared by the trainer and inference.
pub fn sequence_features(tokens: &[String], pos: &[Option<String>]) -> Vec<Vec<String>> {
    let base: Vec<Vec<String>> = tokens
        .iter()
        .enumerate()
        .map(|(i, w)| token_features(w, pos.get(i).and_then(|o| o.as_deref())))
        .collect();

    let n = tokens.len();
    let mut out: Vec<Vec<String>> = Vec::with_capacity(n);
    for i in 0..n {
        let mut feats = base[i].clone();
        feats.push("bias".to_string());
        for k in 1..=2_isize {
            let j = i as isize - k;
            if j >= 0 {
                for s in &base[j as usize] {
                    feats.push(format!("-{k}:{s}"));
                }
            }
            let j = i as isize + k;
            if (j as usize) < n {
                for s in &base[j as usize] {
                    feats.push(format!("+{k}:{s}"));
                }
            }
        }
        if i == 0 {
            feats.push("BOS".to_string());
        }
        if i == n - 1 {
            feats.push("EOS".to_string());
        }
        out.push(feats);
    }
    out
}

/// Per-character orthographic shape: uppercase→`X`, lowercase→`x`, digit→`d`,
/// anything else kept verbatim. Truncated at 8 chars to bound feature cardinality.
fn shape(word: &str) -> String {
    word.chars()
        .take(8)
        .map(|c| {
            if c.is_uppercase() {
                'X'
            } else if c.is_lowercase() {
                'x'
            } else if c.is_ascii_digit() {
                'd'
            } else {
                c
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shape_maps_classes() {
        assert_eq!(shape("Amazon"), "Xxxxxx");
        assert_eq!(shape("IBM"), "XXX");
        assert_eq!(shape("iPhone15"), "xXxxxxdd");
        assert_eq!(shape("3M"), "dX");
        assert_eq!(shape(""), "");
    }

    #[test]
    fn sequence_features_add_context_and_boundaries() {
        let toks = vec!["Acme".to_string(), "Corp".to_string()];
        let pos = vec![None, None];
        let seq = sequence_features(&toks, &pos);
        assert_eq!(seq.len(), 2);

        // first token sees BOS and the next token's features prefixed +1:
        assert!(seq[0].contains(&"BOS".to_string()));
        assert!(seq[0].iter().any(|s| s.starts_with("+1:w.lower=corp")));

        // last token sees EOS and the previous token's features prefixed -1:
        assert!(seq[1].contains(&"EOS".to_string()));
        assert!(seq[1].iter().any(|s| s.starts_with("-1:w.lower=acme")));
    }

    #[test]
    fn token_features_cover_affix_flags_and_gazetteer() {
        let f = token_features("Amazon", None);
        assert!(f.contains(&"w.lower=amazon".to_string()));
        assert!(f.contains(&"shape=Xxxxxx".to_string()));
        assert!(f.contains(&"suf3=zon".to_string()));
        assert!(f.contains(&"pre2=Am".to_string()));
        assert!(f.contains(&"is_title".to_string()));
        assert!(!f.contains(&"is_upper".to_string()));

        // gazetteer membership becomes a feature, not a hard rule:
        let usa = token_features("France", None);
        assert!(usa.contains(&"gaz=COUNTRIES".to_string()));

        // POS only present when provided:
        assert!(token_features("runs", Some("VERB")).contains(&"pos=VERB".to_string()));
        assert!(!token_features("runs", None).iter().any(|s| s.starts_with("pos=")));
    }
}
