//! Distilled CRF NER (opt-in `crf` feature). Typed entities via a pure-Rust
//! CRFsuite model trained offline on spaCy silver labels.

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
            out.push(Entity { text: text[s..e].to_string(), label, start: s, end: e });
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
            "B-ORG".into(), "I-ORG".into(), "O".into(),
            "B-PERSON".into(), "I-PERSON".into(), "O".into(),
        ];
        let ents = merge(text, &toks, &labels);
        assert_eq!(ents, vec![
            Entity { text: "Acme Corp".into(), label: "ORG".into(), start: 0, end: 9 },
            Entity { text: "Jeff Bezos".into(), label: "PERSON".into(), start: 16, end: 26 },
        ]);
    }
}
