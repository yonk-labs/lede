//! SC-007 (Rust): the only *required* runtime dep is `regex`.
//!
//! Optional deps gated behind a cargo `[features]` flag (e.g. `text2num`
//! behind the `wordforms` feature, T13e) do not count — default builds
//! still compile with only `regex`. We verify by (1) enumerating
//! `[dependencies]` and rejecting anything not marked `optional = true`
//! except `regex`, and (2) scanning `[features]` to confirm every
//! optional dep is reachable only via an explicit feature flag.
//!
//! We inspect the Cargo manifest directly (no `serde_json`, no dep) so this
//! test cannot itself contribute to dep bloat.

#[test]
fn manifest_only_requires_regex_at_runtime() {
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

    let mut required: Vec<&str> = Vec::new();
    let mut optional: Vec<&str> = Vec::new();
    for line in deps_block.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with('#') {
            continue;
        }
        if let Some((name, rest)) = line.split_once('=') {
            let name = name.trim();
            if rest.contains("optional = true") {
                optional.push(name);
            } else {
                required.push(name);
            }
        }
    }

    assert_eq!(
        required,
        vec!["regex"],
        "unexpected *required* runtime deps in [dependencies]: {required:?} \
         (optional deps are fine if gated behind a feature)"
    );

    // Guardrail: if an optional dep exists, it must be routed through a
    // named feature in [features] (not default-enabled via `default = [...]`).
    if !optional.is_empty() {
        let features_start = manifest
            .find("[features]")
            .expect("[features] section required when optional deps are declared");
        let features_block = &manifest[features_start..];
        // The `default` feature (if present) must not pull in an optional dep.
        // A simple line-oriented check is enough here because we control the
        // manifest layout.
        for opt in &optional {
            let target = format!("dep:{opt}");
            // Must appear in some feature value — otherwise it's unreachable.
            assert!(
                features_block.contains(&target),
                "optional dep {opt:?} is not gated behind any feature in [features]"
            );
            // Must NOT appear in a `default = [ ... ]` line (case-insensitive
            // substring check is sufficient).
            let default_line = features_block
                .lines()
                .find(|l| l.trim_start().starts_with("default"));
            if let Some(line) = default_line {
                assert!(
                    !line.contains(&target) && !line.contains(opt),
                    "optional dep {opt:?} leaks into the default feature: {line:?}"
                );
            }
        }
    }
}
