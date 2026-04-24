//! Numeric-fact extractor. Regex-based; stdlib + regex only.

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

fn money_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(?P<a>\$\d[\d,]*(?:\.\d+)?[KMB]?)",
            r"|(?P<b>\d[\d,]*(?:\.\d+)?)\s*(?P<ccy>dollars?|USD|EUR|GBP|JPY|CHF)",
        ))
        .expect("static regex")
    })
}

fn percent_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(r"(?i)(?P<v>\d+(?:\.\d+)?)\s*(?P<u>%|percent)").expect("static regex")
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
            r"(?i)(?P<v>\d+)[-\s]*",
            r"(?P<u>seconds?|minutes?|hours?|days?|weeks?|months?|years?)",
        ))
        .expect("static regex")
    })
}

fn count_re() -> &'static Regex {
    static RE: OnceLock<Regex> = OnceLock::new();
    RE.get_or_init(|| {
        Regex::new(concat!(
            r"(?i)(?P<v>\d[\d,]*)\s*",
            r"(?P<u>events?|users?|customers?|requests?|per second|per minute|",
            r"per hour|qps|rps|chunks?",
            r"|terabytes?|basis\s+points?)",
        ))
        .expect("static regex")
    })
}

fn ctx(sent: &str, start: usize, end: usize) -> String {
    let window = 25;
    let l = start.saturating_sub(window);
    let r = (end + window).min(sent.len());
    sent[l..r].trim().to_string()
}

#[must_use]
pub fn stats(text: &str) -> Vec<Stat> {
    let mut out = Vec::new();
    for sent in split_sentences(text) {
        for caps in money_re().captures_iter(&sent) {
            let m = caps.get(0).expect("match");
            let value = caps
                .name("a")
                .or_else(|| caps.name("b"))
                .map(|x| x.as_str().to_string())
                .unwrap_or_default();
            out.push(Stat {
                value,
                unit: "usd".into(),
                phrase: ctx(&sent, m.start(), m.end()),
                context_sentence: sent.clone(),
                stat_type: "money".into(),
            });
        }
        for caps in percent_re().captures_iter(&sent) {
            let m = caps.get(0).expect("match");
            out.push(Stat {
                value: caps["v"].to_string(),
                unit: "percent".into(),
                phrase: ctx(&sent, m.start(), m.end()),
                context_sentence: sent.clone(),
                stat_type: "percent".into(),
            });
        }
        for caps in date_re().captures_iter(&sent) {
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
                phrase: ctx(&sent, m.start(), m.end()),
                context_sentence: sent.clone(),
                stat_type: "date".into(),
            });
        }
        for caps in duration_re().captures_iter(&sent) {
            let m = caps.get(0).expect("match");
            let unit_str = caps["u"].to_lowercase();
            out.push(Stat {
                value: format!("{} {}", &caps["v"], unit_str),
                unit: unit_str.trim_end_matches('s').to_string(),
                phrase: ctx(&sent, m.start(), m.end()),
                context_sentence: sent.clone(),
                stat_type: "duration".into(),
            });
        }
        for caps in count_re().captures_iter(&sent) {
            let m = caps.get(0).expect("match");
            out.push(Stat {
                value: caps["v"].to_string(),
                unit: caps["u"].to_lowercase(),
                phrase: ctx(&sent, m.start(), m.end()),
                context_sentence: sent.clone(),
                stat_type: "count".into(),
            });
        }
    }
    out
}
