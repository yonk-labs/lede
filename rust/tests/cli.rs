//! CLI integration tests — spawn the binary and assert output.

use std::io::Write;
use std::process::{Command, Stdio};

fn skimr_bin() -> &'static str {
    env!("CARGO_BIN_EXE_skimr")
}

fn run(args: &[&str], stdin: Option<&str>) -> (i32, String, String) {
    let mut cmd = Command::new(skimr_bin());
    cmd.args(args);
    cmd.stdout(Stdio::piped()).stderr(Stdio::piped());
    if stdin.is_some() {
        cmd.stdin(Stdio::piped());
    }
    let mut child = cmd.spawn().expect("spawn");
    if let Some(data) = stdin {
        child
            .stdin
            .as_mut()
            .unwrap()
            .write_all(data.as_bytes())
            .unwrap();
    }
    let out = child.wait_with_output().expect("wait");
    (
        out.status.code().unwrap_or(-1),
        String::from_utf8(out.stdout).unwrap(),
        String::from_utf8(out.stderr).unwrap(),
    )
}

fn tempdir_for(label: &str) -> std::path::PathBuf {
    let base = std::env::temp_dir()
        .join(format!("skimr-cli-test-{}-{label}", std::process::id()));
    std::fs::create_dir_all(&base).unwrap();
    base
}

#[test]
fn reads_file_tfidf_mode() {
    let f = tempdir_for("tfidf").join("in.txt");
    std::fs::write(&f, "Revenue grew. Costs fell. Margins improved by 5 points.").unwrap();
    let (rc, out, err) = run(
        &[&f.to_string_lossy(), "--mode", "tfidf", "--max-chars", "500"],
        None,
    );
    assert_eq!(rc, 0, "stderr: {err}");
    assert!(out.contains("Revenue") || out.contains("Costs") || out.contains("Margins"));
}

#[test]
fn reads_stdin_when_no_file() {
    let (rc, out, err) = run(&["--mode", "strip_think"], Some("<think>x</think>\nHello."));
    assert_eq!(rc, 0, "stderr: {err}");
    assert_eq!(out.trim(), "Hello.");
}

#[test]
fn clean_text_mode() {
    let f = tempdir_for("clean").join("in.txt");
    std::fs::write(&f, "**Bold** text.").unwrap();
    let (rc, out, _err) = run(&[&f.to_string_lossy(), "--mode", "clean_text"], None);
    assert_eq!(rc, 0);
    assert_eq!(out.trim(), "bold text.");
}

#[test]
fn keyword_mode() {
    let f = tempdir_for("keyword").join("in.txt");
    std::fs::write(
        &f,
        "The demo went well. Main concern is pricing and budget. Will follow up.",
    )
    .unwrap();
    let (rc, out, _err) = run(
        &[
            &f.to_string_lossy(),
            "--mode",
            "keyword",
            "--keywords",
            "pricing budget",
            "--top",
            "1",
        ],
        None,
    );
    assert_eq!(rc, 0);
    assert!(out.to_lowercase().contains("pricing"), "got: {out:?}");
}

#[test]
fn unknown_mode_errors() {
    let (rc, _out, err) = run(&["--mode", "bogus"], Some("text"));
    assert_ne!(rc, 0);
    assert!(err.to_lowercase().contains("mode"));
}
