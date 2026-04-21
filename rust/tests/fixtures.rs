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
        "clean_text" => Some(skimr::clean_text(input)),
        "strip_think" => Some(skimr::strip_think(input)),
        "tfidf" => {
            let max_length = json_usize(cfg, "max_length").unwrap_or(500);
            Some(skimr::summarize(input, max_length, skimr::Mode::Legacy).summary)
        }
        "keyword" => {
            let keywords = json_str(cfg, "keywords")?;
            let num = json_usize(cfg, "num_sentences").unwrap_or(10);
            Some(skimr::extract_keyword(input, &keywords, num))
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
