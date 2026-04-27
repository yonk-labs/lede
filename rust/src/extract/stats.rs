//! Numeric-fact extractor. Regex-based; stdlib + regex only.
//!
//! T13e: optional word-form number support behind the `wordforms` cargo
//! feature, backed by the `text2num` crate (MIT). Default build does not
//! link `text2num`.

use crate::sentences::split_sentences;
use regex::Regex;
use std::sync::OnceLock;

#[derive(Debug, Clone, PartialEq)]
pub struct Stat {
    pub value: String,
    pub unit: String,
    pub phrase: String,
    pub context_sentence: String,
    pub stat_type: String,
}

/// Options for [`stats_with_options`]. Kept as a struct so the API can
/// grow without breaking callers — mirrors the Python keyword-only kwargs.
#[derive(Debug, Clone, Copy, Default)]
pub struct StatsOptions {
    /// T13e: when true, spelled-out numbers ("eight days", "five thousand
    /// users") are recognized via text2num and emitted with their
    /// ORIGINAL word-form text preserved in `value` / `phrase` /
    /// `context_sentence`. Requires the `wordforms` cargo feature;
    /// setting this to true without the feature enabled is a no-op
    /// (behaves as if false) because the word-form scanner is compiled
    /// out. The Python companion raises `ImportError` in the same
    /// situation; the Rust build-time gate is the equivalent guardrail.
    pub convert_word_names: bool,
}

// Numeric quantifiers are bounded ({1,15}) for byte-identical parity
// with Python's stats.py. Python's `re` engine is backtracking and
// would otherwise hang on long unbroken digit runs; Rust's `regex`
// crate is RE2-style and unaffected, but mirrors the bounds so the
// same input produces the same matches in both runtimes. Sentences
// containing a 20+ digit unbroken run are also skipped via
// `long_run_re()` below — the second line of defense that keeps
// behavior identical for pathological inputs.
fn money_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(?P<a>\$\d[\d,]{0,18}(?:\.\d{1,4})?[KMB]?)",
            r"|(?P<b>\d[\d,]{0,18}(?:\.\d{1,4})?)\s*(?P<ccy>dollars?|USD|EUR|GBP|JPY|CHF)",
        ))
        .expect("static regex")
    })
}

fn percent_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)(?P<v>\d{1,15}(?:\.\d{1,6})?)\s*(?P<u>%|percent)").expect("static regex")
    })
}

// NOTE: `year` alternative matches bare 4-digit years in 1900-2099. Known
// collision: numerals like "1500 dollars" would also match as a date stat
// because primitives run independently. No current corpus exercises this;
// future work could add a negative lookahead for currency/unit context.
fn date_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?P<iso>\d{4}-\d{2}-\d{2})",
            r"|(?P<us>\d{1,2}/\d{1,2}/\d{2,4})",
            r"|(?P<year>\b(?:19|20)\d{2}\b)",
        ))
        .expect("static regex")
    })
}

fn duration_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(?P<v>\d{1,15})[-\s]*",
            r"(?P<u>seconds?|minutes?|hours?|days?|weeks?|months?|years?)",
        ))
        .expect("static regex")
    })
}

fn count_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(?P<v>\d{1,15}(?:,\d{3}){0,5})\s*",
            r"(?P<u>events?|users?|customers?|requests?|per second|per minute|",
            r"per hour|qps|rps|chunks?",
            r"|terabytes?|basis\s+points?",
            r"|items?|documents?|lines?|entries?|records?|files?|actions?|sections?",
            r"|tons?\s+per\s+(?:year|month|day))",
        ))
        .expect("static regex")
    })
}

// Sentences containing a 20+ digit unbroken run are skipped by stats().
// Mirrors Python's `_LONG_RUN_RE` so both runtimes drop the same
// pathological inputs (encoded blobs, base64 chunks, OCR artifacts).
fn long_run_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| Regex::new(r"\d{20,}").expect("static regex"))
}

fn ctx(sent: &str, start: usize, end: usize) -> String {
    let window = 25;
    let raw_lo = start.saturating_sub(window);
    let raw_hi = (end + window).min(sent.len());
    // Snap to UTF-8 char boundaries — `sent[lo..hi]` panics on a multi-byte
    // boundary, and the regex match indices are byte offsets that may land
    // mid-codepoint when the ±25-char window crosses a non-ASCII glyph.
    // For the lower bound, walk backwards to the previous boundary; for
    // the upper bound, walk forwards to the next one. Both fall back to
    // the natural string edge when no boundary is found in range, which
    // is impossible in practice but keeps the function total.
    let lo = (0..=raw_lo)
        .rev()
        .find(|&i| sent.is_char_boundary(i))
        .unwrap_or(0);
    let hi = (raw_hi..=sent.len())
        .find(|&i| sent.is_char_boundary(i))
        .unwrap_or(sent.len());
    sent[lo..hi].trim().to_string()
}

/// Byte-oriented regex matching over a sentence. Mirrors the Python
/// primitive's emission exactly on the digit-only path.
fn emit_digit_only(sent: &str, out: &mut Vec<Stat>) {
    for caps in money_re().captures_iter(sent) {
        let m = caps.get(0).expect("match");
        let value = caps
            .name("a")
            .or_else(|| caps.name("b"))
            .map(|x| x.as_str().to_string())
            .unwrap_or_default();
        out.push(Stat {
            value,
            unit: "usd".into(),
            phrase: ctx(sent, m.start(), m.end()),
            context_sentence: sent.to_string(),
            stat_type: "money".into(),
        });
    }
    for caps in percent_re().captures_iter(sent) {
        let m = caps.get(0).expect("match");
        out.push(Stat {
            value: caps["v"].to_string(),
            unit: "percent".into(),
            phrase: ctx(sent, m.start(), m.end()),
            context_sentence: sent.to_string(),
            stat_type: "percent".into(),
        });
    }
    for caps in date_re().captures_iter(sent) {
        let m = caps.get(0).expect("match");
        let value = caps
            .name("iso")
            .or_else(|| caps.name("us"))
            .or_else(|| caps.name("year"))
            .map(|x| x.as_str().to_string())
            .unwrap_or_default();
        out.push(Stat {
            value,
            unit: "date".into(),
            phrase: ctx(sent, m.start(), m.end()),
            context_sentence: sent.to_string(),
            stat_type: "date".into(),
        });
    }
    for caps in duration_re().captures_iter(sent) {
        let m = caps.get(0).expect("match");
        let unit_str = caps["u"].to_lowercase();
        out.push(Stat {
            value: format!("{} {}", &caps["v"], unit_str),
            unit: unit_str.trim_end_matches('s').to_string(),
            phrase: ctx(sent, m.start(), m.end()),
            context_sentence: sent.to_string(),
            stat_type: "duration".into(),
        });
    }
    for caps in count_re().captures_iter(sent) {
        let m = caps.get(0).expect("match");
        out.push(Stat {
            value: caps["v"].to_string(),
            unit: caps["u"].to_lowercase(),
            phrase: ctx(sent, m.start(), m.end()),
            context_sentence: sent.to_string(),
            stat_type: "count".into(),
        });
    }
}

#[must_use]
pub fn stats(text: &str) -> Vec<Stat> {
    stats_with_options(text, StatsOptions::default())
}

/// Extract numeric facts with configurable options. See [`StatsOptions`].
#[must_use]
pub fn stats_with_options(text: &str, options: StatsOptions) -> Vec<Stat> {
    let mut out = Vec::new();
    for sent in split_sentences(text) {
        // ReDoS guard mirrored from Python — skip sentences with a 20+
        // digit unbroken run. Real-world numeric tokens never approach
        // 20 digits; pathological inputs (encoded blobs, OCR artifacts)
        // would otherwise hang Python on the bounded `\d{1,15}` retry.
        if long_run_re().is_match(&sent) {
            continue;
        }
        if options.convert_word_names {
            #[cfg(feature = "wordforms")]
            {
                wordforms_impl::emit_word_form(&sent, &mut out);
                continue;
            }
            // If the feature is off, fall through to the digit-only path.
            // Rationale: the Python companion raises ImportError when the
            // dep is missing, because Python dep resolution happens at
            // runtime. In Rust, dep resolution is at build time — a build
            // without the feature cannot satisfy the flag, so the caller
            // sees digit-only output. The zero_dep test guards the
            // feature wiring so this state is only reached intentionally.
        }
        emit_digit_only(&sent, &mut out);
    }
    out
}

#[cfg(feature = "wordforms")]
#[allow(clippy::cast_possible_wrap, clippy::cast_sign_loss)]
// Char offsets come from a single sentence; they fit in isize on every
// target skimr supports. The arithmetic below never approaches the
// wrapping boundary in practice, so the pedantic lints just add noise.
mod wordforms_impl {
    //! text2num-backed span-preserving scan. Mirrors the Python
    //! `_word_form_spans` + `_substitute` + `_map_back_impl` +
    //! `_stats_regex_on` pipeline.

    use super::{Stat, count_re, ctx, date_re, duration_re, money_re, percent_re};
    use regex::Regex;
    use std::sync::OnceLock;
    use text2num::lang::English;
    use text2num::word_to_digit::{Token, find_numbers};

    fn token_re() -> &'static Regex {
        static RE: OnceLock<Regex> = OnceLock::new();
        RE.get_or_init(|| Regex::new(r"\w+|[^\w\s]+").expect("static regex"))
    }

    /// Token wrapper carrying the original char span so we can map an
    /// `Occurence`'s token-index range back to byte offsets.
    struct CharToken {
        text: String,
        lower: String,
        char_start: usize,
        char_end: usize,
    }

    impl Token for &CharToken {
        fn text(&self) -> &str {
            &self.text
        }
        fn text_lowercase(&self) -> &str {
            &self.lower
        }
    }

    fn tokenize_with_spans(sentence: &str) -> Vec<CharToken> {
        token_re()
            .find_iter(sentence)
            .map(|m| {
                let s = m.as_str();
                CharToken {
                    text: s.to_string(),
                    lower: s.to_lowercase(),
                    char_start: m.start(),
                    char_end: m.end(),
                }
            })
            .collect()
    }

    /// Returns `(orig_char_start, orig_char_end, digit_text)` tuples.
    fn word_form_spans(sentence: &str) -> Vec<(usize, usize, String)> {
        let tokens = tokenize_with_spans(sentence);
        if tokens.is_empty() {
            return Vec::new();
        }
        // threshold=0.0 matches the Python impl so small isolated numbers
        // like "two weeks" are included.
        let occurrences = find_numbers(tokens.iter(), &English {}, 0.0);
        occurrences
            .into_iter()
            .map(|occ| {
                let start_tok = &tokens[occ.start];
                let end_tok = &tokens[occ.end - 1];
                (start_tok.char_start, end_tok.char_end, occ.text)
            })
            .collect()
    }

    /// Tuples of `(orig_start, orig_end, sub_start, sub_end)` for each
    /// substituted word-form span.
    type SpanMap = Vec<(usize, usize, usize, usize)>;

    fn substitute(sentence: &str, spans: &[(usize, usize, String)]) -> (String, SpanMap) {
        if spans.is_empty() {
            return (sentence.to_string(), Vec::new());
        }
        let mut out = String::with_capacity(sentence.len());
        let mut span_map: SpanMap = Vec::with_capacity(spans.len());
        let mut cursor = 0usize;
        let mut sub_offset: isize = 0;
        for (orig_start, orig_end, digit_text) in spans {
            out.push_str(&sentence[cursor..*orig_start]);
            let sub_start = (*orig_start as isize + sub_offset) as usize;
            out.push_str(digit_text);
            let sub_end = sub_start + digit_text.len();
            span_map.push((*orig_start, *orig_end, sub_start, sub_end));
            sub_offset += digit_text.len() as isize - (*orig_end as isize - *orig_start as isize);
            cursor = *orig_end;
        }
        out.push_str(&sentence[cursor..]);
        (out, span_map)
    }

    fn map_back(sub_start: usize, sub_end: usize, span_map: &SpanMap) -> (usize, usize) {
        let map_pos = |sub_pos: usize, is_end: bool| -> usize {
            let mut delta: isize = 0;
            for (orig_s, orig_e, sub_s, sub_e) in span_map {
                if *sub_e <= sub_pos {
                    delta +=
                        (*sub_e as isize - *sub_s as isize) - (*orig_e as isize - *orig_s as isize);
                    continue;
                }
                if *sub_s >= sub_pos {
                    break;
                }
                // sub_s < sub_pos < sub_e
                return if is_end { *orig_e } else { *orig_s };
            }
            (sub_pos as isize - delta) as usize
        };

        let mut orig_start = map_pos(sub_start, false);
        let mut orig_end = map_pos(sub_end, true);
        for (orig_s, orig_e, sub_s, sub_e) in span_map {
            if *sub_s >= sub_start && *sub_e <= sub_end {
                orig_start = orig_start.min(*orig_s);
                orig_end = orig_end.max(*orig_e);
            }
        }
        (orig_start, orig_end)
    }

    #[allow(clippy::too_many_lines)]
    pub(super) fn emit_word_form(sent_orig: &str, out: &mut Vec<Stat>) {
        let spans = word_form_spans(sent_orig);
        let (sent_sub, span_map) = substitute(sent_orig, &spans);
        let has_subs = !span_map.is_empty();

        for caps in money_re().captures_iter(&sent_sub) {
            let m = caps.get(0).expect("match");
            let (orig_s, orig_e) = map_back(m.start(), m.end(), &span_map);
            let value = if has_subs {
                sent_orig[orig_s..orig_e].trim().to_string()
            } else {
                caps.name("a")
                    .or_else(|| caps.name("b"))
                    .map(|x| x.as_str().to_string())
                    .unwrap_or_default()
            };
            out.push(Stat {
                value,
                unit: "usd".into(),
                phrase: ctx(sent_orig, orig_s, orig_e),
                context_sentence: sent_orig.to_string(),
                stat_type: "money".into(),
            });
        }

        for caps in percent_re().captures_iter(&sent_sub) {
            let m = caps.get(0).expect("match");
            let (orig_s, orig_e) = map_back(m.start(), m.end(), &span_map);
            let v = caps.name("v").expect("value group");
            let (v_orig_s, v_orig_e) = map_back(v.start(), v.end(), &span_map);
            let value = if has_subs {
                sent_orig[v_orig_s..v_orig_e].trim().to_string()
            } else {
                caps["v"].to_string()
            };
            out.push(Stat {
                value,
                unit: "percent".into(),
                phrase: ctx(sent_orig, orig_s, orig_e),
                context_sentence: sent_orig.to_string(),
                stat_type: "percent".into(),
            });
        }

        for caps in date_re().captures_iter(&sent_sub) {
            let m = caps.get(0).expect("match");
            let (orig_s, orig_e) = map_back(m.start(), m.end(), &span_map);
            let value = if has_subs {
                sent_orig[orig_s..orig_e].trim().to_string()
            } else {
                caps.name("iso")
                    .or_else(|| caps.name("us"))
                    .or_else(|| caps.name("year"))
                    .map(|x| x.as_str().to_string())
                    .unwrap_or_default()
            };
            out.push(Stat {
                value,
                unit: "date".into(),
                phrase: ctx(sent_orig, orig_s, orig_e),
                context_sentence: sent_orig.to_string(),
                stat_type: "date".into(),
            });
        }

        for caps in duration_re().captures_iter(&sent_sub) {
            let m = caps.get(0).expect("match");
            let unit_str = caps["u"].to_lowercase();
            let (orig_s, orig_e) = map_back(m.start(), m.end(), &span_map);
            let v = caps.name("v").expect("value group");
            let u = caps.name("u").expect("unit group");
            let (v_orig_s, v_orig_e) = map_back(v.start(), v.end(), &span_map);
            let (u_orig_s, u_orig_e) = map_back(u.start(), u.end(), &span_map);
            let value = if has_subs {
                let orig_value = sent_orig[v_orig_s..v_orig_e].trim().to_string();
                let orig_unit = sent_orig[u_orig_s..u_orig_e].trim().to_lowercase();
                format!("{orig_value} {orig_unit}")
            } else {
                format!("{} {}", &caps["v"], unit_str)
            };
            out.push(Stat {
                value,
                unit: unit_str.trim_end_matches('s').to_string(),
                phrase: ctx(sent_orig, orig_s, orig_e),
                context_sentence: sent_orig.to_string(),
                stat_type: "duration".into(),
            });
        }

        for caps in count_re().captures_iter(&sent_sub) {
            let m = caps.get(0).expect("match");
            let (orig_s, orig_e) = map_back(m.start(), m.end(), &span_map);
            let v = caps.name("v").expect("value group");
            let (v_orig_s, v_orig_e) = map_back(v.start(), v.end(), &span_map);
            let value = if has_subs {
                sent_orig[v_orig_s..v_orig_e].trim().to_string()
            } else {
                caps["v"].to_string()
            };
            out.push(Stat {
                value,
                unit: caps["u"].to_lowercase(),
                phrase: ctx(sent_orig, orig_s, orig_e),
                context_sentence: sent_orig.to_string(),
                stat_type: "count".into(),
            });
        }
    }
}
