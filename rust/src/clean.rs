//! Text cleaners ported from src/skimr/clean.py.

use regex::Regex;
use std::sync::OnceLock;

fn think_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    // Python: re.compile(r"<think>.*?</think>\s*", re.DOTALL)
    RE.get_or_init(|| Regex::new(r"(?s)<think>.*?</think>\s*").expect("static regex"))
}

/// Remove `<think>...</think>` blocks and trim surrounding whitespace.
#[must_use]
pub fn strip_think(text: &str) -> String {
    think_re().replace_all(text, "").trim().to_string()
}

// --- clean_text: port of src/skimr/clean.py::clean_text ---
//
// Order matches the Python reference step by step:
//   1. Strip markdown (*, _, #, ---, bullets, numbered list prefixes)
//   2. Remove filler phrases
//   3. Remove filler words
//   4. Remove CRM boilerplate (8 patterns, in order)
//   5. Lowercase
//   6. Collapse whitespace and blank lines
//   7. Trim

fn md_asterisks_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\*{1,3}").expect("static regex"))
}

fn md_underscores_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"_{1,3}").expect("static regex"))
}

fn md_headers_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^#{1,6}\s*").expect("static regex"))
}

fn md_hrule_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^-{3,}$").expect("static regex"))
}

fn md_bullets_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^\s*[-*+]\s+").expect("static regex"))
}

fn md_numbered_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^\s*\d+\.\s+").expect("static regex"))
}

fn filler_phrases_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)\b(just wanted to|i just wanted to|wanted to follow up|as discussed|per our conversation|as mentioned|going forward|at the end of the day|in terms of|with respect to|in regards to|please find attached|hope this helps|let me know if you have any questions|looking forward to hearing from you)\b",
        )
        .expect("static regex")
    })
}

fn filler_words_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)\b(basically|essentially|actually|literally|honestly|frankly|obviously|clearly|simply|really|very|quite|rather|pretty much|kind of|sort of|in order to|due to the fact that|at this point in time|for all intents and purposes)\b",
        )
        .expect("static regex")
    })
}

fn crm_no_updates_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bNo update[s]?\b\.?").expect("static regex"))
}

fn crm_calendar_invite_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bCalendar invite sent[.]?\b").expect("static regex"))
}

fn crm_sent_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(
            r"(?i)\bSent (proposal|case study|documentation|overview|pricing) (documentation |via email|as requested)?\.?\b",
        )
        .expect("static regex")
    })
}

fn crm_waiting_callback_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bWaiting (on|for) callback\.?\b").expect("static regex"))
}

fn crm_updated_crm_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bUpdated CRM with latest info\.?\b").expect("static regex"))
}

fn crm_meeting_confirmed_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)\bMeeting confirmed for next week\.?\b").expect("static regex")
    })
}

fn crm_sales_process_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)\bFollowing standard sales process\.?\b").expect("static regex")
    })
}

fn crm_meeting_expected_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?i)\bMeeting went as expected\.?\b").expect("static regex"))
}

fn ws_spaces_tabs_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"[ \t]+").expect("static regex"))
}

fn ws_blank_lines_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\n\s*\n+").expect("static regex"))
}

fn ws_leading_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^\s+").expect("static regex"))
}

fn ws_trailing_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)\s+$").expect("static regex"))
}

fn ws_empty_lines_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"(?m)^\s*$\n?").expect("static regex"))
}

/// Port of `src/skimr/clean.py::clean_text`.
///
/// Strips markdown, filler phrases, filler words, and CRM boilerplate, then
/// lowercases and normalizes whitespace. Returns an empty string for empty
/// input (mirrors the Python STRICT/NULL-safe behavior).
#[must_use]
pub fn clean_text(text: &str) -> String {
    if text.is_empty() {
        return String::new();
    }

    let mut s = text.to_string();

    // 1. Markdown formatting
    s = md_asterisks_re().replace_all(&s, "").into_owned();
    s = md_underscores_re().replace_all(&s, "").into_owned();
    s = md_headers_re().replace_all(&s, "").into_owned();
    s = md_hrule_re().replace_all(&s, "").into_owned();
    s = md_bullets_re().replace_all(&s, "").into_owned();
    s = md_numbered_re().replace_all(&s, "").into_owned();

    // 2-3. Filler
    s = filler_phrases_re().replace_all(&s, "").into_owned();
    s = filler_words_re().replace_all(&s, "").into_owned();

    // 4. CRM boilerplate (order matters)
    s = crm_no_updates_re().replace_all(&s, "").into_owned();
    s = crm_calendar_invite_re().replace_all(&s, "").into_owned();
    s = crm_sent_re().replace_all(&s, "").into_owned();
    s = crm_waiting_callback_re().replace_all(&s, "").into_owned();
    s = crm_updated_crm_re().replace_all(&s, "").into_owned();
    s = crm_meeting_confirmed_re().replace_all(&s, "").into_owned();
    s = crm_sales_process_re().replace_all(&s, "").into_owned();
    s = crm_meeting_expected_re().replace_all(&s, "").into_owned();

    // 5. Lowercase
    s = s.to_lowercase();

    // 6. Whitespace normalization
    s = ws_spaces_tabs_re().replace_all(&s, " ").into_owned();
    s = ws_blank_lines_re().replace_all(&s, "\n").into_owned();
    s = ws_leading_re().replace_all(&s, "").into_owned();
    s = ws_trailing_re().replace_all(&s, "").into_owned();
    s = ws_empty_lines_re().replace_all(&s, "").into_owned();

    // 7. Trim
    s.trim().to_string()
}
