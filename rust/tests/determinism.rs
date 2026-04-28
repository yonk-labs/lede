//! Determinism: 100 runs per fixture must produce bit-identical output.

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
        "tfidf" => Some(
            lede::summarize(
                input,
                json_usize(cfg, "max_length").unwrap_or(500),
                lede::Mode::Legacy,
            )
            .summary,
        ),
        "keyword" => {
            let kw = json_str(cfg, "keywords")?;
            let n = json_usize(cfg, "num_sentences").unwrap_or(10);
            Some(lede::extract_keyword(input, &kw, n))
        }
        "textrank" => None,
        _ => panic!("unknown mode: {mode}"),
    }
}

#[test]
fn hundred_runs_bit_identical() {
    let root = fixtures_root();
    for mode_dir in std::fs::read_dir(&root).expect("read fixtures/") {
        let mode_dir = mode_dir.expect("entry").path();
        if !mode_dir.is_dir() {
            continue;
        }
        for fx in std::fs::read_dir(&mode_dir).expect("read mode") {
            let fx = fx.expect("entry").path();
            if !fx.is_dir() {
                continue;
            }
            if !fx.join("config.json").exists() {
                continue;
            }
            let input = std::fs::read_to_string(fx.join("input.txt")).unwrap();
            let cfg = std::fs::read_to_string(fx.join("config.json")).unwrap();
            let mode = json_str(&cfg, "mode").expect("mode");

            let Some(first) = dispatch(&mode, &input, &cfg) else {
                continue;
            };
            for _ in 0..99 {
                let other = dispatch(&mode, &input, &cfg).unwrap();
                assert_eq!(other, first, "non-deterministic on {fx:?}");
            }
        }
    }
}
