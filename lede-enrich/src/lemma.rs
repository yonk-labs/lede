//! Coarse rule-based lemmatizer + small irregulars table. No external/encumbered
//! lookup data; deterministic. spaCy-`sm` is also lookup-based — this trades some
//! accuracy for a zero-data, license-clean build.
//!
//! ponytail: coarse stemmer-ish rules + irregulars, not a full morphological
//! lemmatizer. Upgrade to a bundled lookup table (license permitting) if a
//! consumer needs higher fidelity.

/// Reduce a word to a base form (lowercased).
#[must_use]
pub fn lemma(word: &str) -> String {
    let w = word.to_ascii_lowercase();
    if let Some(base) = irregular(&w) {
        return base.to_string();
    }
    strip_inflection(&w)
}

fn irregular(w: &str) -> Option<&'static str> {
    let base = match w {
        "is" | "are" | "am" | "was" | "were" | "been" | "being" => "be",
        "has" | "had" | "having" => "have",
        "does" | "did" | "done" | "doing" => "do",
        "went" | "gone" | "going" => "go",
        "said" | "saying" => "say",
        "made" | "making" => "make",
        "children" => "child",
        "men" => "man",
        "women" => "woman",
        "people" => "person",
        "feet" => "foot",
        "teeth" => "tooth",
        "mice" => "mouse",
        "geese" => "goose",
        "better" | "best" => "good",
        "worse" | "worst" => "bad",
        _ => return None,
    };
    Some(base)
}

fn strip_inflection(w: &str) -> String {
    // Byte slicing below assumes ASCII; bail out otherwise (no panic, no loss).
    if !w.is_ascii() {
        return w.to_string();
    }
    if w.len() > 4 && (w.ends_with("ies") || w.ends_with("ied")) {
        return format!("{}y", &w[..w.len() - 3]);
    }
    if w.len() > 5 && w.ends_with("ing") {
        return reduce_double(&w[..w.len() - 3]);
    }
    if w.len() > 4 && w.ends_with("ed") {
        return reduce_double(&w[..w.len() - 2]);
    }
    if w.len() > 4 && w.ends_with("es") && ends_sibilant(&w[..w.len() - 2]) {
        return w[..w.len() - 2].to_string();
    }
    if w.len() > 3 && w.ends_with('s') && !w.ends_with("ss") {
        return w[..w.len() - 1].to_string();
    }
    w.to_string()
}

/// Drop a trailing doubled consonant from common CVC-doubling verbs
/// ("runn" -> "run", "stopp" -> "stop"); leave legitimate doubles ("fall").
fn reduce_double(w: &str) -> String {
    let b = w.as_bytes();
    if b.len() >= 2 {
        let last = b[b.len() - 1];
        if last == b[b.len() - 2]
            && matches!(last, b'b' | b'd' | b'g' | b'm' | b'n' | b'p' | b'r' | b't')
        {
            return w[..w.len() - 1].to_string();
        }
    }
    w.to_string()
}

fn ends_sibilant(w: &str) -> bool {
    w.ends_with('s')
        || w.ends_with('x')
        || w.ends_with('z')
        || w.ends_with("ch")
        || w.ends_with("sh")
}

#[cfg(test)]
mod tests {
    use super::lemma;

    #[test]
    fn lemmatizes() {
        assert_eq!(lemma("Studies"), "study");
        assert_eq!(lemma("running"), "run");
        assert_eq!(lemma("walked"), "walk");
        assert_eq!(lemma("stopped"), "stop");
        assert_eq!(lemma("boxes"), "box");
        assert_eq!(lemma("cats"), "cat");
        assert_eq!(lemma("falling"), "fall");
        assert_eq!(lemma("was"), "be");
        assert_eq!(lemma("children"), "child");
        assert_eq!(lemma("dog"), "dog");
    }
}
