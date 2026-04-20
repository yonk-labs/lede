//! SC-007 (Rust): the only runtime dep is `regex`.
//!
//! We inspect the Cargo manifest directly (no `serde_json`, no dep) so this
//! test cannot itself contribute to dep bloat.

#[test]
fn manifest_only_depends_on_regex() {
    let manifest = std::fs::read_to_string(
        std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("Cargo.toml"),
    )
    .expect("read Cargo.toml");

    let deps_start = manifest
        .find("[dependencies]")
        .expect("[dependencies] section");
    let after = &manifest[deps_start + "[dependencies]".len()..];
    let end = after.find("\n[").unwrap_or(after.len());
    let deps_block = &after[..end];

    let mut declared: Vec<&str> = Vec::new();
    for line in deps_block.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((name, _)) = line.split_once('=') {
            declared.push(name.trim());
        }
    }

    assert_eq!(
        declared,
        vec!["regex"],
        "unexpected runtime deps in [dependencies]: {declared:?}"
    );
}
