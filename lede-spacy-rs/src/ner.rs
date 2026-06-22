//! Gazetteer + capitalization/shape-rule NER.
//!
//! Pure rules + static data → deterministic. M1 ships no trained model and no
//! bundled weights (license-clean). Returns unique entity surface forms in
//! first-appearance order, mirroring Python `lede_spacy.extract_entities`.
//!
//! Recall is intentionally below spaCy-`sm` (a bare single capitalized word at a
//! sentence start is only kept if a gazetteer/title rescues it). Expand the
//! gazetteers or enable the opt-in CRF download for more recall.

use crate::gazetteer;

struct Token {
    text: String,
    sentence_start: bool,
}

struct Run {
    parts: Vec<String>,
    sentence_start: bool,
}

/// Unique PERSON/ORG/GPE/LOC/PRODUCT-class surface forms, first-appearance order.
#[must_use]
pub fn extract_entities(text: &str) -> Vec<String> {
    let tokens = tokenize(text);
    let mut out: Vec<String> = Vec::new();
    for run in runs(&tokens) {
        if let Some(surface) = accept(run) {
            if !out.contains(&surface) {
                out.push(surface);
            }
        }
    }
    out
}

/// Word tokens (alphanumeric + apostrophe, plus standalone `&`), each flagged
/// with whether it begins a sentence. Sentence boundaries are `.`/`!`/`?`.
fn tokenize(text: &str) -> Vec<Token> {
    let mut tokens = Vec::new();
    let mut sentence_start = true;
    let mut current = String::new();
    let mut current_start = true;
    let mut last_was_title = false;
    for c in text.chars() {
        if c.is_alphanumeric() || c == '\'' {
            if current.is_empty() {
                current_start = sentence_start;
            }
            current.push(c);
            continue;
        }
        if !current.is_empty() {
            last_was_title = gazetteer::contains_ci(gazetteer::TITLES, &current);
            tokens.push(Token {
                text: std::mem::take(&mut current),
                sentence_start: current_start,
            });
            sentence_start = false;
        }
        match c {
            // A period right after a title ("Dr.") is an abbreviation, not a
            // sentence end — keep the title linked to the following name.
            '.' => {
                if !last_was_title {
                    sentence_start = true;
                }
            }
            '!' | '?' => sentence_start = true,
            '&' => {
                last_was_title = false;
                tokens.push(Token {
                    text: "&".to_string(),
                    sentence_start,
                });
                sentence_start = false;
            }
            _ => {}
        }
    }
    if !current.is_empty() {
        tokens.push(Token {
            text: current,
            sentence_start: current_start,
        });
    }
    tokens
}

fn is_cap(t: &Token) -> bool {
    t.text.chars().next().is_some_and(char::is_uppercase)
}

fn is_connector(t: &Token) -> bool {
    gazetteer::contains_ci(gazetteer::CONNECTORS, &t.text)
}

/// Collect maximal runs of capitalized tokens, allowing a lowercase connector
/// between two capitalized tokens ("Bank of America", "Smith & Co").
fn runs(tokens: &[Token]) -> Vec<Run> {
    let mut result = Vec::new();
    let mut i = 0;
    while i < tokens.len() {
        if !is_cap(&tokens[i]) {
            i += 1;
            continue;
        }
        let sentence_start = tokens[i].sentence_start;
        let mut parts = vec![tokens[i].text.clone()];
        let mut j = i + 1;
        loop {
            // Never extend a run across a sentence boundary (the next token
            // beginning a sentence) — that would merge "Brazil. Brazil".
            if j + 1 < tokens.len()
                && is_connector(&tokens[j])
                && !tokens[j].sentence_start
                && is_cap(&tokens[j + 1])
                && !tokens[j + 1].sentence_start
            {
                parts.push(tokens[j].text.clone());
                parts.push(tokens[j + 1].text.clone());
                j += 2;
            } else if j < tokens.len() && is_cap(&tokens[j]) && !tokens[j].sentence_start {
                parts.push(tokens[j].text.clone());
                j += 1;
            } else {
                break;
            }
        }
        result.push(Run {
            parts,
            sentence_start,
        });
        i = j;
    }
    result
}

/// Decide whether a run is an entity and, if so, return its surface form.
fn accept(mut run: Run) -> Option<String> {
    let mut has_title = false;
    let mut sentence_start = run.sentence_start;

    // Strip a leading title ("Dr Smith" -> "Smith"); PERSON signal.
    if run.parts.len() > 1 && gazetteer::contains_ci(gazetteer::TITLES, &run.parts[0]) {
        run.parts.remove(0);
        has_title = true;
        sentence_start = false;
    } else if sentence_start
        && run.parts.len() > 1
        && gazetteer::contains_ci(gazetteer::SENTENCE_STOPWORDS, &run.parts[0])
    {
        // Strip a leading sentence-initial stopword ("However John" -> "John").
        run.parts.remove(0);
        sentence_start = false;
    }

    // A single bare title/stopword token is never an entity ("He", "It", "Dr").
    if run.parts.len() == 1
        && (gazetteer::contains_ci(gazetteer::SENTENCE_STOPWORDS, &run.parts[0])
            || gazetteer::contains_ci(gazetteer::TITLES, &run.parts[0]))
    {
        return None;
    }

    let has_suffix = run
        .parts
        .iter()
        .any(|p| gazetteer::contains_ci(gazetteer::ORG_SUFFIXES, p));
    let has_gaz = run.parts.iter().any(|p| {
        gazetteer::contains_ci(gazetteer::ORGS, p)
            || gazetteer::contains_ci(gazetteer::COUNTRIES, p)
            || gazetteer::contains_ci(gazetteer::PLACES, p)
            || gazetteer::contains_ci(gazetteer::FIRST_NAMES, p)
    });
    let multi_token = run.parts.len() > 1;

    // Single capitalized token at a sentence start is dropped unless a
    // gazetteer/title/suffix rescues it (avoids the "first word of sentence"
    // false positive without a statistical model).
    if has_title || has_suffix || has_gaz || multi_token || !sentence_start {
        Some(run.parts.join(" "))
    } else {
        None
    }
}
