//! Distilled CRF NER (opt-in `crf` feature). Typed entities via a pure-Rust
//! CRFsuite model trained offline on spaCy silver labels.

mod data;
mod features;
pub mod tokenize;
pub use features::sequence_features;

use crate::crf::tokenize::Tok;

/// Merge a BIO label sequence (aligned to `toks`) into entity spans, slicing the
/// surface text out of `text` by byte offsets.
fn merge(text: &str, toks: &[Tok], labels: &[String]) -> Vec<Entity> {
    let mut out = Vec::new();
    let mut cur: Option<(String, usize, usize)> = None; // (label, start_byte, end_byte)
    let flush = |cur: &mut Option<(String, usize, usize)>, out: &mut Vec<Entity>| {
        if let Some((label, s, e)) = cur.take() {
            out.push(Entity {
                text: text[s..e].to_string(),
                label,
                start: s,
                end: e,
            });
        }
    };
    for (i, tok) in toks.iter().enumerate() {
        let lbl = labels.get(i).map(String::as_str).unwrap_or("O");
        if let Some(t) = lbl.strip_prefix("B-") {
            flush(&mut cur, &mut out);
            cur = Some((t.to_string(), tok.start, tok.end));
        } else if let Some(t) = lbl.strip_prefix("I-") {
            match &mut cur {
                Some((l, _, end)) if l == t => *end = tok.end,
                _ => {
                    flush(&mut cur, &mut out);
                    cur = Some((t.to_string(), tok.start, tok.end));
                }
            }
        } else {
            flush(&mut cur, &mut out);
        }
    }
    flush(&mut cur, &mut out);
    out
}

#[derive(Debug, Clone, PartialEq, Eq)]
pub struct Entity {
    pub text: String,
    pub label: String,
    pub start: usize,
    pub end: usize,
}

use std::sync::OnceLock;

use crfs::{Attribute, Model};

/// Bundled model, gzipped (6.4 MB vs 16.7 MB raw). Decompressed once at first use.
static MODEL_GZ: &[u8] = include_bytes!("../../models/ner.crfsuite.gz");

fn model() -> &'static Model<'static> {
    // The decompressed bytes live in a static OnceLock so the Model (which borrows
    // them) can be `'static` and cached.
    static BYTES: OnceLock<Vec<u8>> = OnceLock::new();
    static M: OnceLock<Model<'static>> = OnceLock::new();
    let bytes = BYTES.get_or_init(|| {
        use std::io::Read;
        let mut out = Vec::new();
        flate2::read::GzDecoder::new(MODEL_GZ)
            .read_to_end(&mut out)
            .expect("bundled CRF model gunzips");
        out
    });
    M.get_or_init(|| Model::new(bytes).expect("bundled CRF model is valid"))
}

/// Typed PERSON/ORG/GPE/… entities via the distilled CRF. Deterministic: fixed
/// bundled weights + fixed feature order + Viterbi decode. Additive — does not
/// affect `extract_entities` or `metadata`.
#[must_use]
pub fn extract_entities_typed(text: &str) -> Vec<Entity> {
    let toks = tokenize::tokenize(text);
    if toks.is_empty() {
        return Vec::new();
    }
    let tokens: Vec<String> = toks.iter().map(|t| t.text.clone()).collect();
    let pos = vec![None; tokens.len()];
    let feats = features::sequence_features(&tokens, &pos);
    let xseq: Vec<Vec<Attribute>> = feats
        .iter()
        .map(|row| {
            row.iter()
                .map(|s| Attribute::new(s.as_str(), 1.0))
                .collect()
        })
        .collect();
    let tagger = model().tagger().expect("tagger");
    // crfs 0.4: tag returns Vec<&str>; merge wants &[String].
    let labels: Vec<String> = tagger
        .tag(&xseq)
        .unwrap_or_default()
        .into_iter()
        .map(str::to_string)
        .collect();
    merge(text, &toks, &labels)
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::crf::tokenize::tokenize;

    #[test]
    fn merge_groups_bio_runs_into_spans() {
        let text = "Acme Corp hired Jeff Bezos.";
        let toks = tokenize(text);
        // tokens: Acme Corp hired Jeff Bezos .
        let labels = vec![
            "B-ORG".into(),
            "I-ORG".into(),
            "O".into(),
            "B-PERSON".into(),
            "I-PERSON".into(),
            "O".into(),
        ];
        let ents = merge(text, &toks, &labels);
        assert_eq!(
            ents,
            vec![
                Entity {
                    text: "Acme Corp".into(),
                    label: "ORG".into(),
                    start: 0,
                    end: 9
                },
                Entity {
                    text: "Jeff Bezos".into(),
                    label: "PERSON".into(),
                    start: 16,
                    end: 26
                },
            ]
        );
    }
}
