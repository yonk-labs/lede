//! Sentence splitter.
//!
//! Port of `src/lede/sentences.py::split_sentences`. Splits on sentence-terminal
//! punctuation (`.!?`) followed by whitespace and an uppercase letter, plus
//! paragraph breaks. Protects known abbreviations and decimal numbers from being
//! treated as sentence boundaries.
//!
//! Rust's `regex` crate has no lookbehind / lookahead, so the splitter uses
//! `captures_iter` and computes split offsets manually to mirror Python's
//! `re.split((?<=[.!?])\s+(?=[A-Z])|\n\s*\n)` behavior.

use regex::{Captures, Regex};
use std::sync::OnceLock;

/// ASCII NUL — sentinel used to mask protected periods during splitting.
const SENTINEL: char = '\x00';

/// Abbreviations (lowercased) whose trailing period should NOT end a sentence.
/// Matches the Python `_ABBREVIATIONS` frozenset byte-for-byte.
const ABBREVIATIONS: &[&str] = &[
    "mr", "mrs", "ms", "dr", "st", "sr", "jr", "inc", "ltd", "co", "corp", "vs", "etc", "eg", "ie",
    "cf", "u.s", "u.k", "u.n", "e.u", "fig", "vol",
];

fn decimal_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(\d)\.(\d)").expect("decimal regex compiles"))
}

fn abbrev_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"\b([A-Za-z]+(?:\.[A-Za-z]+)*)\.").expect("abbrev regex compiles")
    })
}

// Context-sensitive abbreviation: protect "No." when followed by a number
// ("No. 5", "No. 17"). Bare "no." at end of sentence is NOT protected and
// stays a sentence terminator. Rust's regex crate has no lookahead, so we
// capture the trailing whitespace + digit and emit it back unchanged.
// Mirrors `_NO_NUMBER_RE` in `src/lede/sentences.py`.
fn no_number_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\b(No)\.(\s*)(\d)").expect("no-number regex compiles"))
}

fn splitter_re() -> &'static Regex {
    // Branch A: terminal punct + whitespace + uppercase letter (lookahead simulated
    //   by consuming the uppercase letter; caller restores it via ws.end()).
    // Branch B: paragraph break (two or more newlines, optionally with whitespace).
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"([.!?])(\s+)[A-Z]|\n\s*\n").expect("splitter regex compiles"))
}

fn is_abbreviation(word: &str) -> bool {
    // Lowercase comparison, matching Python's `word.lower() in _ABBREVIATIONS`.
    let lower = word.to_ascii_lowercase();
    ABBREVIATIONS.iter().any(|a| *a == lower)
}

fn mask(text: &str) -> String {
    // Strip the reserved sentinel (NUL) rather than panicking. NUL bytes
    // can show up in PDF-extracted text and other ETL outputs; aborting
    // the splitter on them is hostile. Mirrors src/lede/sentences.py::_mask
    // for parity.
    let cleaned: std::borrow::Cow<str> = if text.contains(SENTINEL) {
        std::borrow::Cow::Owned(text.replace(SENTINEL, ""))
    } else {
        std::borrow::Cow::Borrowed(text)
    };

    // Protect decimals: digit.digit -> digit<SENTINEL>digit
    let after_decimals = decimal_re().replace_all(&cleaned, |caps: &Captures| {
        format!("{}{}{}", &caps[1], SENTINEL, &caps[2])
    });

    // Protect "No." when it precedes a number (issue numbers, citations).
    // Bare "no." stays a terminator.
    let after_no = no_number_re().replace_all(&after_decimals, |caps: &Captures| {
        format!("{}{}{}{}", &caps[1], SENTINEL, &caps[2], &caps[3])
    });

    // Protect known abbreviations. The candidate regex may over-match (e.g.
    // "Basically." captures "Basically"), but `is_abbreviation` filters non-matches
    // and the closure returns the original match text unchanged.
    let after_abbrev = abbrev_re().replace_all(&after_no, |caps: &Captures| {
        let word = &caps[1];
        if is_abbreviation(word) {
            format!("{word}{SENTINEL}")
        } else {
            caps[0].to_string()
        }
    });

    after_abbrev.into_owned()
}

fn unmask(text: &str) -> String {
    text.replace(SENTINEL, ".")
}

/// Split `text` into sentences. Returns an empty vec for empty input.
///
/// NUL bytes (`\x00`) in `text` are silently stripped — they're used
/// internally as a sentinel during decimal/abbreviation masking and
/// can otherwise show up in PDF-extracted text and ETL output. The
/// splitter does not panic on user input.
#[must_use]
pub fn split_sentences(text: &str) -> Vec<String> {
    if text.is_empty() {
        return Vec::new();
    }

    let masked = mask(text);
    let re = splitter_re();

    let mut parts: Vec<String> = Vec::new();
    let mut cursor: usize = 0;

    for caps in re.captures_iter(&masked) {
        // Branch A has capture group 1 (punct) — keep punct on the left, leave
        // the uppercase letter on the right. Branch B is a bare alternation
        // (no capture group 1) — consume the full paragraph-break run.
        let (left_end, next_cursor) = if let Some(punct) = caps.get(1) {
            let ws = caps.get(2).expect("branch A always has ws group");
            (punct.end(), ws.end())
        } else {
            let whole = caps.get(0).expect("match always has group 0");
            (whole.start(), whole.end())
        };

        let piece = masked[cursor..left_end].trim();
        if !piece.is_empty() {
            parts.push(unmask(piece));
        }
        cursor = next_cursor;
    }

    // Tail after the last split boundary.
    let tail = masked[cursor..].trim();
    if !tail.is_empty() {
        parts.push(unmask(tail));
    }

    parts
}
