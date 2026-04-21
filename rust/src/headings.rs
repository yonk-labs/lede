//! Shared heading detection — mirrors src/skimr/_headings.py.
//!
//! Any sentence matching any of these patterns is considered a heading and is
//! dropped from candidate selection in `Mode::Default`.

use regex::Regex;
use std::sync::OnceLock;

// Markdown ATX-style heading: one or more # followed by space and text
fn md_heading_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*#+\s+.+$").expect("static regex"))
}

// ALL-CAPS short line: 4-30 chars of A-Z/space/colon, no lowercase
fn allcaps_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*[A-Z][A-Z\s]{3,28}:?\s*$").expect("static regex"))
}

// Short label ending in colon (<=30 chars including the colon)
fn short_label_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*.{1,30}:\s*$").expect("static regex"))
}

// Content-word finder — used for the "fewer than 4 content tokens" heuristic.
fn content_word_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[A-Za-z]{3,}").expect("static regex"))
}

// Markdown-prefix stripper — leading `#+ ` run before heading-name extraction.
fn strip_md_prefix_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^#+\s+").expect("static regex"))
}

/// True when `sentence` matches any heading pattern.
#[must_use]
pub fn is_heading(sentence: &str) -> bool {
    let trimmed = sentence.trim();
    if trimmed.is_empty() {
        return false;
    }
    if md_heading_re().is_match(sentence) {
        return true;
    }
    if allcaps_re().is_match(sentence) {
        return true;
    }
    if short_label_re().is_match(sentence) {
        return true;
    }
    // Fewer than 4 content-word tokens (rough "title-like" filter).
    let toks = content_word_re().find_iter(sentence).count();
    toks < 4
}

/// Extract the name portion of a heading, or None if not a heading or empty.
///
/// Strips leading markdown `#` markers and a trailing colon.
#[must_use]
pub fn heading_name(sentence: &str) -> Option<String> {
    let s = sentence.trim();
    if s.is_empty() {
        return None;
    }
    let stripped = strip_md_prefix_re().replace(s, "");
    let cleaned = stripped.trim_end_matches(':').trim();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
    }
}
