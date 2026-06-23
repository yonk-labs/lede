//! Inference-side tokenizer. Word runs (alphanumeric + apostrophe) and standalone
//! punctuation become tokens, each carrying byte offsets so entity spans can be
//! sliced back out of the source. Roughly mirrors spaCy whitespace+punct splitting;
//! tokenizer divergence vs spaCy is the main fidelity risk (spec R-1).

pub struct Tok {
    pub text: String,
    pub start: usize,
    pub end: usize,
}

/// Split into word tokens (alphanumeric + apostrophe) and single-char punctuation
/// tokens, each with byte offsets. Whitespace is a separator only.
pub fn tokenize(text: &str) -> Vec<Tok> {
    let mut toks = Vec::new();
    let mut start: Option<usize> = None;
    for (i, c) in text.char_indices() {
        if c.is_alphanumeric() || c == '\'' {
            if start.is_none() {
                start = Some(i);
            }
        } else {
            if let Some(s) = start.take() {
                toks.push(Tok {
                    text: text[s..i].to_string(),
                    start: s,
                    end: i,
                });
            }
            if !c.is_whitespace() {
                let end = i + c.len_utf8();
                toks.push(Tok {
                    text: text[i..end].to_string(),
                    start: i,
                    end,
                });
            }
        }
    }
    if let Some(s) = start.take() {
        toks.push(Tok {
            text: text[s..].to_string(),
            start: s,
            end: text.len(),
        });
    }
    toks
}

/// Project entity char-spans `(start, end, label)` onto `toks`, yielding one BIO
/// tag per token. A token belongs to an entity when it is fully contained in the
/// span (`tok.start >= start && tok.end <= end`); the first contained token is
/// `B-`, the rest `I-`. Tokens only partially overlapping a span fall to `O`
/// (rare in clean text). Spans are assumed non-overlapping (spaCy ents are).
pub fn project_bio(toks: &[Tok], ents: &[(usize, usize, String)]) -> Vec<String> {
    let mut bio = vec!["O".to_string(); toks.len()];
    for (start, end, label) in ents {
        let mut first = true;
        for (i, t) in toks.iter().enumerate() {
            if t.start >= *start && t.end <= *end {
                bio[i] = format!("{}-{}", if first { "B" } else { "I" }, label);
                first = false;
            }
        }
    }
    bio
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn tokenize_words_and_punct_with_offsets() {
        let text = "Acme Corp, Paris.";
        let toks = tokenize(text);
        let pairs: Vec<(&str, usize, usize)> = toks
            .iter()
            .map(|t| (t.text.as_str(), t.start, t.end))
            .collect();
        assert_eq!(
            pairs,
            vec![
                ("Acme", 0, 4),
                ("Corp", 5, 9),
                (",", 9, 10),
                ("Paris", 11, 16),
                (".", 16, 17),
            ]
        );
        // offsets slice the original text back out:
        assert_eq!(&text[toks[3].start..toks[3].end], "Paris");
    }

    #[test]
    fn project_bio_labels_tokens_from_char_spans() {
        let text = "Acme Corp hired Jeff Bezos.";
        let toks = tokenize(text);
        // entity byte-spans (sentence-relative); the harness converts spaCy's
        // char offsets to UTF-8 byte offsets so they align with our byte tokens.
        // (ASCII here, so byte==char.)
        let ents = vec![
            (0usize, 9usize, "ORG".to_string()),      // "Acme Corp"
            (16usize, 26usize, "PERSON".to_string()), // "Jeff Bezos"
        ];
        let bio = project_bio(&toks, &ents);
        assert_eq!(
            bio,
            vec!["B-ORG", "I-ORG", "O", "B-PERSON", "I-PERSON", "O"]
        );
    }
}
