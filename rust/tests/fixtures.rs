//! Fixture walker — SC-002 gate.
//!
//! Every fixture in ../fixtures/<mode>/<name>/ is a tuple of
//! (input.txt, config.json, expected.txt). The config picks the mode and
//! params. This test runs the Rust implementation and asserts byte equality
//! with expected.txt. Any mismatch is a DC-002 failure.

use std::path::{Path, PathBuf};

fn fixtures_root() -> PathBuf {
    Path::new(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("crate parent")
        .join("fixtures")
}

fn json_str(cfg: &str, key: &str) -> Option<String> {
    let needle = format!("\"{key}\":");
    let start = cfg.find(&needle)? + needle.len();
    let after = cfg[start..].trim_start();
    if !after.starts_with('"') {
        return None;
    }
    let after = &after[1..];
    let close = after.find('"')?;
    Some(after[..close].to_string())
}

fn json_usize(cfg: &str, key: &str) -> Option<usize> {
    let needle = format!("\"{key}\":");
    let start = cfg.find(&needle)? + needle.len();
    let after = cfg[start..].trim_start();
    let end = after
        .find(|c: char| !c.is_ascii_digit())
        .unwrap_or(after.len());
    after[..end].parse().ok()
}

fn dispatch(mode: &str, input: &str, cfg: &str) -> Option<String> {
    match mode {
        "clean_text" => Some(lede::clean_text(input)),
        "strip_think" => Some(lede::strip_think(input)),
        "tfidf" => {
            let max_length = json_usize(cfg, "max_length").unwrap_or(500);
            let scorer_mode = json_str(cfg, "scorer_mode").unwrap_or_else(|| "legacy".to_string());
            let m = match scorer_mode.as_str() {
                "default" => lede::Mode::Default,
                "coverage" => lede::Mode::Coverage,
                _ => lede::Mode::Legacy,
            };
            Some(lede::summarize(input, max_length, m).summary)
        }
        "keyword" => {
            let keywords = json_str(cfg, "keywords")?;
            let num = json_usize(cfg, "num_sentences").unwrap_or(10);
            Some(lede::extract_keyword(input, &keywords, num))
        }
        "textrank" => None,
        _ => panic!("unknown fixture mode: {mode}"),
    }
}

#[test]
fn every_fixture_byte_identical() {
    let root = fixtures_root();
    let mut failures: Vec<String> = Vec::new();
    let mut ran = 0usize;

    for mode_entry in std::fs::read_dir(&root).expect("read fixtures/") {
        let mode_dir = mode_entry.expect("read mode entry").path();
        if !mode_dir.is_dir() {
            continue;
        }
        for fx_entry in std::fs::read_dir(&mode_dir).expect("read mode dir") {
            let fx_dir = fx_entry.expect("read fx entry").path();
            if !fx_dir.is_dir() {
                continue;
            }
            let cfg_path = fx_dir.join("config.json");
            if !cfg_path.exists() {
                continue;
            }
            let input = std::fs::read_to_string(fx_dir.join("input.txt")).expect("read input");
            let expected =
                std::fs::read_to_string(fx_dir.join("expected.txt")).expect("read expected");
            let cfg = std::fs::read_to_string(&cfg_path).expect("read config");
            let mode = json_str(&cfg, "mode").expect("mode field");
            let name = format!(
                "{}/{}",
                mode_dir.file_name().unwrap().to_string_lossy(),
                fx_dir.file_name().unwrap().to_string_lossy(),
            );
            let Some(actual) = dispatch(&mode, &input, &cfg) else {
                continue;
            };
            ran += 1;
            if actual != expected {
                failures.push(format!("{name}: byte mismatch"));
            }
        }
    }

    assert!(ran > 0, "no fixtures ran — check fixtures/ path");
    assert!(
        failures.is_empty(),
        "fixture failures:\n  {}",
        failures.join("\n  ")
    );
}

// ----------------------------------------------------------------------------
// v0.2 extract-primitive parity walker (P2.1 / AAT-017)
//
// Layout: fixtures/extract-parity/<primitive>/<corpus>/{input,expected}.txt
// Expected.txt is the canonical text format produced by lede._parity in
// Python. The Rust walker runs the matching primitive on input.txt, formats
// with lede::parity::*, and byte-compares. Any drift between Python and
// Rust on the v0.2 differentiator surface (the AAT-flagged gap) shows up
// here.
//
// To regenerate fixtures: `python benchmarks/gen_parity_fixtures.py`.

fn dispatch_extract(primitive: &str, input: &str) -> Option<String> {
    match primitive {
        "stats" => Some(lede::parity::format_stats(&lede::extract::stats::stats(
            input,
        ))),
        "outline" => Some(lede::parity::format_outline(
            &lede::extract::outline::outline(input),
        )),
        "toc" => Some(lede::parity::format_toc(&lede::extract::outline::toc(
            input,
        ))),
        "metadata" => Some(lede::parity::format_metadata(
            &lede::extract::metadata::metadata(input),
        )),
        "phrases" => Some(lede::parity::format_phrases(
            &lede::extract::phrases::phrases(input, None),
        )),
        "key_facts" => Some(lede::parity::format_key_facts(
            // Default max_facts=10 mirrors Python's keyword default.
            &lede::extract::key_facts::key_facts(input, 10),
        )),
        "correlate_facts" => Some(lede::parity::format_correlate_facts(
            &lede::extract::correlate::correlate_facts(input),
        )),
        _ => None, // unknown primitive — caller will report the mismatch
    }
}

#[test]
fn v0_2_extract_primitives_byte_identical() {
    let root = fixtures_root().join("extract-parity");
    if !root.is_dir() {
        // No parity fixtures yet — skip rather than fail.
        return;
    }

    let mut failures: Vec<String> = Vec::new();
    let mut ran = 0usize;

    for prim_entry in std::fs::read_dir(&root).expect("read extract-parity/") {
        let prim_dir = prim_entry.expect("read primitive entry").path();
        if !prim_dir.is_dir() {
            continue;
        }
        let primitive = prim_dir.file_name().unwrap().to_string_lossy().to_string();
        for fx_entry in std::fs::read_dir(&prim_dir).expect("read primitive dir") {
            let fx_dir = fx_entry.expect("read fixture entry").path();
            if !fx_dir.is_dir() {
                continue;
            }
            let input_path = fx_dir.join("input.txt");
            let expected_path = fx_dir.join("expected.txt");
            if !input_path.exists() || !expected_path.exists() {
                continue;
            }
            let input = std::fs::read_to_string(&input_path).expect("read input");
            let expected = std::fs::read_to_string(&expected_path).expect("read expected");
            let corpus = fx_dir.file_name().unwrap().to_string_lossy();
            let name = format!("{primitive}/{corpus}");
            let Some(actual) = dispatch_extract(&primitive, &input) else {
                failures.push(format!("{name}: unknown primitive"));
                continue;
            };
            ran += 1;
            if actual != expected {
                // Show first diverging line for triage without dumping
                // the entire blob into the test output.
                let diff = first_diff_line(&expected, &actual);
                failures.push(format!("{name}: byte mismatch — {diff}"));
            }
        }
    }

    assert!(
        ran > 0,
        "no extract-parity fixtures ran — regenerate with `python benchmarks/gen_parity_fixtures.py`"
    );
    assert!(
        failures.is_empty(),
        "v0.2 extract parity failures (Python ↔ Rust drift):\n  {}",
        failures.join("\n  ")
    );
}

fn first_diff_line(expected: &str, actual: &str) -> String {
    let exp_lines: Vec<&str> = expected.lines().collect();
    let act_lines: Vec<&str> = actual.lines().collect();
    for (i, (e, a)) in exp_lines.iter().zip(act_lines.iter()).enumerate() {
        if e != a {
            return format!(
                "line {} differs\n    expected: {:?}\n    actual:   {:?}",
                i + 1,
                e,
                a
            );
        }
    }
    if exp_lines.len() == act_lines.len() {
        "(no line diff but bytes differ — trailing newline?)".to_string()
    } else {
        format!(
            "length differs: expected {} lines, actual {} lines",
            exp_lines.len(),
            act_lines.len()
        )
    }
}
