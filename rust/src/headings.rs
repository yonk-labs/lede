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

// ALL-CAPS short line: 4-80 chars of A-Z/space/colon, no lowercase.
// Upper bound extended from 28 -> 80 in T13b so long document-title
// conventions like "SUPREME COURT OF THE UNITED STATES" (32 chars) match.
fn allcaps_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*[A-Z][A-Z\s]{3,80}:?\s*$").expect("static regex"))
}

// Short label ending in colon (<=30 chars including the colon)
fn short_label_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*.{1,30}:\s*$").expect("static regex"))
}

// Bare title-case single-line heading (T13b Class A). The "no terminal
// punctuation" constraint (enforced by the restricted character class
// `[A-Za-z0-9 ]`) is load-bearing: it excludes short body sentences like
// "Costs declined." that end in a period.
fn bare_title_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\s*[A-Z][A-Za-z0-9][A-Za-z0-9 ]{0,58}$").expect("static regex"))
}

// Numbered-section-prefix heading (T13b Class B). The numeric prefix is
// stripped by `heading_name()` so the emitted name matches gold.
fn numbered_section_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"^\s*\d+\.\s+[A-Z][A-Za-z0-9 ]{0,58}$").expect("static regex")
    })
}

// Title-with-dash heading (T13d): "Title — Metadata" document title line.
// Matches em-dash U+2014, en-dash U+2013, or hyphen-minus (space-bracketed
// so hyphenated single words don't match). Authorized by the labeling
// protocol's Edge-case conventions — the dash-metadata suffix is stripped
// by `heading_name()`.
//
// Trailing `[^.!?]*$` mirrors the `bare_title_re` safety constraint —
// excludes body sentences like "Main concern is pricing — $50K over budget."
// that would otherwise match on the dash clause.
fn title_with_dash_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"^\s*[A-Z][A-Za-z0-9 ]{0,58}\s+[\x{2014}\x{2013}\-]\s+\S[^.!?]*$")
            .expect("static regex")
    })
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

// Numeric-section-prefix stripper (T13b) — leading `\d+. ` run before
// heading-name extraction so "1. Information We Collect" -> "Information
// We Collect".
fn strip_numbered_prefix_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"^\d+\.\s+").expect("static regex"))
}

// Em-dash-metadata-suffix stripper (T13d) — trailing ` — <anything>` removed
// from heading names so "Privacy Policy — Effective Date: ..." yields
// "Privacy Policy".
fn strip_dash_metadata_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"\s+[\x{2014}\x{2013}\-]\s+.*$").expect("static regex")
    })
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
    if bare_title_re().is_match(sentence) {
        return true;
    }
    if numbered_section_re().is_match(sentence) {
        return true;
    }
    if title_with_dash_re().is_match(sentence) {
        return true;
    }
    // Fewer than 4 content-word tokens (rough "title-like" filter).
    let toks = content_word_re().find_iter(sentence).count();
    toks < 4
}

/// Extract the name portion of a heading, or None if not a heading or empty.
///
/// Strips leading markdown `#` markers, leading numeric-section prefix
/// (`\d+\. `), an em-dash/en-dash/hyphen-minus metadata suffix (T13d), and
/// a trailing colon.
#[must_use]
pub fn heading_name(sentence: &str) -> Option<String> {
    let s = sentence.trim();
    if s.is_empty() {
        return None;
    }
    let stripped_md = strip_md_prefix_re().replace(s, "");
    let stripped_num = strip_numbered_prefix_re().replace(&stripped_md, "");
    let stripped_dash = strip_dash_metadata_re().replace(&stripped_num, "");
    let cleaned = stripped_dash.trim_end_matches(':').trim();
    if cleaned.is_empty() {
        None
    } else {
        Some(cleaned.to_string())
    }
}
