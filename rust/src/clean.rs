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
