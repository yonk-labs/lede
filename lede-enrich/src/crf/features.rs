//! Shared CRF feature extraction. Returns `Vec<Vec<String>>` (one feature-string
//! list per token) — deliberately free of `crfs` types so it is unit-testable on
//! its own and reused verbatim by both the trainer and inference.

/// Per-character orthographic shape: uppercase→`X`, lowercase→`x`, digit→`d`,
/// anything else kept verbatim. Truncated at 8 chars to bound feature cardinality.
fn shape(word: &str) -> String {
    word.chars()
        .take(8)
        .map(|c| {
            if c.is_uppercase() {
                'X'
            } else if c.is_lowercase() {
                'x'
            } else if c.is_ascii_digit() {
                'd'
            } else {
                c
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn shape_maps_classes() {
        assert_eq!(shape("Amazon"), "Xxxxxx");
        assert_eq!(shape("IBM"), "XXX");
        assert_eq!(shape("iPhone15"), "xXxxxxdd");
        assert_eq!(shape("3M"), "dX");
        assert_eq!(shape(""), "");
    }
}
