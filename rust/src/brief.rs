//! At-a-glance document brief — composes `summarize` + `key_facts` + `toc`.
//!
//! Mirrors `src/lede/brief.py`. Keep the three output formats
//! (string, markdown, dict) byte-identical with Python for the regex
//! backend on every corpus in `benchmarks/corpus/`.
//!
//! Wordforms note: Python auto-detects `text2num` at import time and
//! flips `convert_word_names` on internally. Rust has no runtime
//! detection — feature gating is a compile-time decision. When built
//! with `--features wordforms`, `brief_with_options` forwards
//! `convert_word_names = true` to its internal `key_facts` call;
//! otherwise it forwards `false`. Consistent with how
//! `stats_with_options` / `key_facts_with_options` gate the same
//! feature.

use crate::extract::key_facts::{KeyFactsOptions, key_facts_with_options};
use crate::extract::outline::toc;
use crate::extract::phrases::phrases;
use crate::tfidf::summarize;
use crate::types::Mode;

/// Output format for [`brief_with_options`].
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum BriefFormat {
    /// Plain text with section labels (`Overview:` / `Key facts:` / ...).
    /// Byte-identical with Python `format="string"`.
    String,
    /// Markdown — `##` headers + bullet lists. Byte-identical with Python
    /// `format="markdown"`.
    Markdown,
    /// Structured dict ([`BriefDict`]). Byte-identical content with Python
    /// `format="dict"`.
    Dict,
}

/// Options for [`brief_with_options`]. Mirrors Python's keyword-only
/// kwargs on `brief()`.
#[derive(Debug, Clone, Copy)]
pub struct BriefOptions {
    /// Overview char budget as a fraction of source length. Clamped to
    /// `[0.05, 0.50]`. Default `0.35`.
    pub overview_max: f64,
    /// Cap on key-facts sentences. Default `10`.
    pub max_facts: usize,
    /// When true, emit a key-phrases section. Default `false`.
    pub include_phrases: bool,
    /// Forward to `key_facts()` so spelled-out numbers ("five thousand
    /// documents") surface. `None` means "follow the build-time
    /// wordforms feature flag" (mirrors Python's auto-detect default
    /// for back-compat); `Some(true)` / `Some(false)` lock the
    /// behavior so output matches a Python caller passing the same
    /// explicit flag, regardless of the build-time feature gate.
    pub convert_word_names: Option<bool>,
    /// Output shape. Default [`BriefFormat::String`].
    pub format: BriefFormat,
}

impl Default for BriefOptions {
    fn default() -> Self {
        Self {
            overview_max: 0.35,
            max_facts: 10,
            include_phrases: false,
            convert_word_names: None,
            format: BriefFormat::String,
        }
    }
}

/// Structured brief payload. Returned inside [`BriefOutput::Dict`] when
/// the caller requests [`BriefFormat::Dict`]. Matches Python's
/// `format="dict"` shape.
#[derive(Debug, Clone, PartialEq)]
pub struct BriefDict {
    pub overview: String,
    pub key_facts: Vec<String>,
    pub toc: Vec<String>,
    /// `Some` only when `include_phrases=true`; `None` otherwise — mirrors
    /// Python's explicit `None` for the absent case.
    pub phrases: Option<Vec<String>>,
}

/// Union return type from [`brief_with_options`]: text for `String` /
/// `Markdown` formats, structured [`BriefDict`] for `Dict` format.
#[derive(Debug, Clone, PartialEq)]
pub enum BriefOutput {
    Text(String),
    Dict(BriefDict),
}

// Overview budget clamps — shared with Python's constants in brief.py.
const OVERVIEW_MIN_FRAC: f64 = 0.05;
const OVERVIEW_MAX_FRAC: f64 = 0.50;
const OVERVIEW_MIN_CHARS: usize = 250;
const OVERVIEW_MAX_CHARS: usize = 1500;

// Compile-time wordforms flag — see module docstring for rationale.
#[cfg(feature = "wordforms")]
const WORDFORMS_ENABLED: bool = true;
#[cfg(not(feature = "wordforms"))]
const WORDFORMS_ENABLED: bool = false;

/// Convenience entry point with default options. Returns a plain
/// `String` (equivalent to `BriefFormat::String`) for ergonomics.
///
/// For other formats or to tune options, use [`brief_with_options`].
#[must_use]
pub fn brief(text: &str) -> String {
    match brief_with_options(text, BriefOptions::default()) {
        BriefOutput::Text(s) => s,
        BriefOutput::Dict(_) => unreachable!("default BriefOptions uses BriefFormat::String"),
    }
}

/// Produce an at-a-glance brief of `text`.
///
/// Composes [`summarize`] (overview) + [`key_facts_with_options`] +
/// [`toc`] into a single caller-friendly artifact. Optional [`phrases`]
/// via `opts.include_phrases = true`.
///
/// See [`BriefFormat`] for output shape details.
///
/// **Wordforms:** when built with `--features wordforms`, this function
/// forwards `convert_word_names = true` to its internal `key_facts`
/// call so spelled-out numbers ("five thousand documents") surface
/// in the key-facts section. Without the feature the flag is `false`.
#[must_use]
#[allow(
    clippy::cast_precision_loss,
    clippy::cast_possible_truncation,
    clippy::cast_sign_loss
)]
pub fn brief_with_options(text: &str, opts: BriefOptions) -> BriefOutput {
    // Clamp overview_max to sane fraction bounds, then char-clamp.
    // chars().count() is non-negative; frac is clamped to a positive range,
    // so the product fits in usize after rounding (and is then clamped again).
    let frac = opts
        .overview_max
        .clamp(OVERVIEW_MIN_FRAC, OVERVIEW_MAX_FRAC);
    let raw_budget = (text.chars().count() as f64 * frac) as usize;
    let budget = raw_budget.clamp(OVERVIEW_MIN_CHARS, OVERVIEW_MAX_CHARS);

    let overview_result = summarize(text, budget, Mode::Default);
    let overview_text = overview_result.summary.trim_end().to_string();

    // Resolve wordforms: opts.convert_word_names overrides the build-time
    // gate; None falls back to the feature flag. Mirrors Python's
    // `convert_word_names is None ? _HAS_WORDFORMS : convert_word_names`.
    let use_wordforms = opts.convert_word_names.unwrap_or(WORDFORMS_ENABLED);
    let facts = key_facts_with_options(
        text,
        KeyFactsOptions {
            max_facts: opts.max_facts,
            convert_word_names: use_wordforms,
        },
    );

    let sections = toc(text);

    let phrases_list: Vec<String> = if opts.include_phrases {
        phrases(text, None)
    } else {
        Vec::new()
    };

    match opts.format {
        BriefFormat::Dict => BriefOutput::Dict(BriefDict {
            overview: overview_text,
            key_facts: facts,
            toc: sections,
            phrases: if opts.include_phrases {
                Some(phrases_list)
            } else {
                None
            },
        }),
        BriefFormat::Markdown => {
            let mut parts: Vec<String> =
                vec!["## Overview\n".to_string(), overview_text, String::new()];
            if !facts.is_empty() {
                parts.push("\n## Key facts\n".to_string());
                for f in &facts {
                    parts.push(format!("- {f}"));
                }
                parts.push(String::new());
            }
            if !sections.is_empty() {
                parts.push("\n## Also in this doc\n".to_string());
                for s in &sections {
                    parts.push(format!("- {s}"));
                }
                parts.push(String::new());
            }
            if opts.include_phrases && !phrases_list.is_empty() {
                parts.push("\n## Key phrases\n".to_string());
                parts.push(phrases_list.join("  \u{00b7}  "));
                parts.push(String::new());
            }
            BriefOutput::Text(parts.join("\n"))
        }
        BriefFormat::String => {
            let mut parts: Vec<String> =
                vec!["Overview:".to_string(), overview_text, String::new()];
            if !facts.is_empty() {
                parts.push("Key facts:".to_string());
                for f in &facts {
                    parts.push(format!("  - {f}"));
                }
                parts.push(String::new());
            }
            if !sections.is_empty() {
                parts.push("Also in this doc:".to_string());
                for s in &sections {
                    parts.push(format!("  - {s}"));
                }
                parts.push(String::new());
            }
            if opts.include_phrases && !phrases_list.is_empty() {
                parts.push("Key phrases:".to_string());
                parts.push(format!("  {}", phrases_list.join(", ")));
                parts.push(String::new());
            }
            let joined = parts.join("\n");
            // Match Python's `"\n".join(parts).rstrip() + "\n"`.
            let trimmed = joined.trim_end().to_string();
            BriefOutput::Text(format!("{trimmed}\n"))
        }
    }
}
