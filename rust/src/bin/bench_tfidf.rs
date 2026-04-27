//! Micro-benchmark for `skimr::summarize` (tfidf mode).
//!
//! Reads all of stdin as input, runs `summarize(text, 500, mode)` N times, and
//! emits a single JSON line on stdout: `{"p50_ms": X, "p95_ms": Y, "out_chars": Z}`.
//!
//! Argv:
//!   1: iterations (default 100)
//!   2: mode (default|legacy|coverage; default "default")
//!
//! The inner loop runs in-process so the Python harness doesn't measure
//! process-spawn overhead per iteration.

use std::io::Read;
use std::time::Instant;

fn parse_mode(s: &str) -> skimr::Mode {
    match s {
        "legacy" => skimr::Mode::Legacy,
        "coverage" => skimr::Mode::Coverage,
        "default" => skimr::Mode::Default,
        other => panic!("unknown mode: {other}"),
    }
}

fn main() {
    let mut text = String::new();
    std::io::stdin()
        .read_to_string(&mut text)
        .expect("read stdin");

    let iterations: usize = std::env::args()
        .nth(1)
        .and_then(|s| s.parse().ok())
        .unwrap_or(100);

    let mode = std::env::args()
        .nth(2)
        .as_deref()
        .map_or(skimr::Mode::Default, parse_mode);

    // Warmup run — not measured.
    let _ = skimr::summarize(&text, 500, mode);

    let mut samples: Vec<f64> = Vec::with_capacity(iterations);
    for _ in 0..iterations {
        let t0 = Instant::now();
        let _ = skimr::summarize(&text, 500, mode);
        #[allow(clippy::cast_precision_loss)]
        let ms = t0.elapsed().as_nanos() as f64 / 1e6;
        samples.push(ms);
    }
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap_or(std::cmp::Ordering::Equal));

    let p50 = samples[samples.len() / 2];
    #[allow(
        clippy::cast_precision_loss,
        clippy::cast_possible_truncation,
        clippy::cast_sign_loss
    )]
    let p95_idx = (0.95 * samples.len() as f64) as usize;
    let p95 = samples[p95_idx.min(samples.len() - 1)];

    let out = skimr::summarize(&text, 500, mode).summary;
    println!(
        r#"{{"p50_ms":{p50:.6},"p95_ms":{p95:.6},"out_chars":{oc}}}"#,
        oc = out.chars().count(),
    );
}
