//! skimr CLI. Hand-rolled arg parser — no external deps.
//!
//! Modes: `tfidf` (default), `keyword`, `clean_text`, `strip_think`.
//! Reads FILE or stdin, writes the summary to stdout.

use std::io::{Read, Write};
use std::process::ExitCode;

#[derive(Debug)]
struct Args {
    path: Option<String>,
    mode: String,
    max_chars: usize,
    keywords: String,
    top: usize,
}

impl Default for Args {
    fn default() -> Self {
        Self {
            path: None,
            mode: "tfidf".to_string(),
            max_chars: 500,
            keywords: String::new(),
            top: 10,
        }
    }
}

fn print_help(to: &mut impl Write) {
    let _ = writeln!(
        to,
        "Usage: skimr [FILE] --mode {{tfidf,keyword,clean_text,strip_think}} [OPTIONS]\n\
         Reads FILE or stdin, writes summary to stdout.\n\
         \n\
         Options:\n\
         \x20\x20--mode MODE         Summarization mode (default: tfidf)\n\
         \x20\x20--max-chars N       Char budget for tfidf (default: 500)\n\
         \x20\x20--keywords STR      Space-separated keywords for keyword mode\n\
         \x20\x20--top N             Sentences to return in keyword mode (default: 10)\n\
         \x20\x20-h, --help          Show this help"
    );
}

fn parse_args(input: impl Iterator<Item = String>) -> Result<Args, String> {
    let mut out = Args::default();
    let mut iter = input.peekable();
    while let Some(arg) = iter.next() {
        match arg.as_str() {
            "-h" | "--help" => {
                print_help(&mut std::io::stdout());
                std::process::exit(0);
            }
            "--mode" => {
                let v = iter
                    .next()
                    .ok_or_else(|| "--mode requires an argument".to_string())?;
                if !["tfidf", "keyword", "clean_text", "strip_think"].contains(&v.as_str()) {
                    return Err(format!("invalid --mode value: {v}"));
                }
                out.mode = v;
            }
            "--max-chars" => {
                let v = iter
                    .next()
                    .ok_or_else(|| "--max-chars requires an argument".to_string())?;
                out.max_chars = v
                    .parse()
                    .map_err(|_| format!("--max-chars not numeric: {v}"))?;
            }
            "--keywords" => {
                out.keywords = iter
                    .next()
                    .ok_or_else(|| "--keywords requires an argument".to_string())?;
            }
            "--top" => {
                let v = iter
                    .next()
                    .ok_or_else(|| "--top requires an argument".to_string())?;
                out.top = v.parse().map_err(|_| format!("--top not numeric: {v}"))?;
            }
            _ if arg.starts_with("--") => return Err(format!("unknown flag: {arg}")),
            _ => {
                if out.path.is_some() {
                    return Err(format!("unexpected positional argument: {arg}"));
                }
                out.path = Some(arg);
            }
        }
    }
    Ok(out)
}

fn read_input(path: Option<&str>) -> std::io::Result<String> {
    match path {
        Some(p) if p != "-" => std::fs::read_to_string(p),
        _ => {
            let mut s = String::new();
            std::io::stdin().read_to_string(&mut s)?;
            Ok(s)
        }
    }
}

fn main() -> ExitCode {
    let raw: Vec<String> = std::env::args().skip(1).collect();
    let parsed = match parse_args(raw.into_iter()) {
        Ok(a) => a,
        Err(msg) => {
            let _ = writeln!(std::io::stderr(), "error: {msg}");
            return ExitCode::from(2);
        }
    };

    let text = match read_input(parsed.path.as_deref()) {
        Ok(t) => t,
        Err(e) => {
            let _ = writeln!(std::io::stderr(), "error reading input: {e}");
            return ExitCode::from(1);
        }
    };

    let output = match parsed.mode.as_str() {
        "tfidf" => skimr::summarize(&text, parsed.max_chars, skimr::Mode::Default).summary,
        "keyword" => {
            if parsed.keywords.is_empty() {
                let _ = writeln!(
                    std::io::stderr(),
                    "error: --mode keyword requires --keywords"
                );
                return ExitCode::from(2);
            }
            skimr::extract_keyword(&text, &parsed.keywords, parsed.top)
        }
        "clean_text" => skimr::clean_text(&text),
        "strip_think" => skimr::strip_think(&text),
        _ => unreachable!("parse_args validates mode"),
    };

    // Honor write errors. BrokenPipe is the common "user piped into `head`"
    // case — exit 0 there since the user got what they asked for. Any other
    // I/O error (full disk, closed stream, etc.) propagates as exit 1.
    let mut out = std::io::stdout().lock();
    if let Err(e) = out.write_all(output.as_bytes()) {
        if e.kind() == std::io::ErrorKind::BrokenPipe {
            return ExitCode::SUCCESS;
        }
        let _ = writeln!(std::io::stderr(), "error writing output: {e}");
        return ExitCode::from(1);
    }
    if !output.ends_with('\n') {
        if let Err(e) = out.write_all(b"\n") {
            if e.kind() == std::io::ErrorKind::BrokenPipe {
                return ExitCode::SUCCESS;
            }
            let _ = writeln!(std::io::stderr(), "error writing output: {e}");
            return ExitCode::from(1);
        }
    }
    ExitCode::SUCCESS
}
