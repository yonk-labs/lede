//! Offline CRF trainer (feature-gated; not built by default). Reads silver.jsonl
//! ({"text": "<sentence>", "ents": [{start,end,label}]}), tokenizes each sentence
//! with the SAME Rust tokenizer used at inference, projects byte-offset spans -> BIO,
//! featurizes with the shared `sequence_features`, holds out every 10th sentence,
//! trains an L-BFGS CRF, writes models/ner.crfsuite, prints entity-level P/R/F1.
//!
//! crfs 0.4 deviations from the original brief:
//!   - `tagger.tag(...)` returns `io::Result<Vec<&str>>` (not `Vec<String>`), so
//!     `eval` takes `&crfs::Tagger` (not `&mut`) and converts pred to `Vec<String>`.

use std::fs::File;
use std::io::{BufRead, BufReader};
use std::path::Path;

use crfs::{Attribute, Model, Trainer};
use lede_enrich::{project_bio, sequence_features, tokenize};
use serde_json::Value;

fn attrs(feats: &[Vec<String>]) -> Vec<Vec<Attribute>> {
    feats
        .iter()
        .map(|row| row.iter().map(|s| Attribute::new(s.as_str(), 1.0)).collect())
        .collect()
}

/// One silver line -> (tokens, BIO) via the Rust tokenizer + char-span projection.
fn parse_line(v: &Value) -> Option<(Vec<String>, Vec<String>)> {
    let text = v["text"].as_str()?;
    let toks = tokenize(text);
    if toks.is_empty() {
        return None;
    }
    let ents: Vec<(usize, usize, String)> = v["ents"]
        .as_array()?
        .iter()
        .filter_map(|e| {
            Some((
                e["start"].as_u64()? as usize,
                e["end"].as_u64()? as usize,
                e["label"].as_str()?.to_string(),
            ))
        })
        .collect();
    let bio = project_bio(&toks, &ents);
    let tokens = toks.iter().map(|t| t.text.clone()).collect();
    Some((tokens, bio))
}

fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args().nth(1).unwrap_or_else(|| "distill/silver.jsonl".into());
    let model_out = "models/ner.crfsuite";

    let mut trainer = Trainer::lbfgs();
    trainer.params_mut().set_c1(0.1)?;
    trainer.params_mut().set_c2(1.0)?;

    let mut held: Vec<(Vec<String>, Vec<String>)> = Vec::new();
    for (i, line) in BufReader::new(File::open(&path)?).lines().enumerate() {
        let v: Value = serde_json::from_str(&line?)?;
        let Some((tokens, bio)) = parse_line(&v) else { continue };
        if i % 10 == 0 {
            held.push((tokens, bio));
            continue;
        }
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(&tokens, &pos);
        let yseq: Vec<&str> = bio.iter().map(String::as_str).collect();
        trainer.append(&attrs(&feats), &yseq)?;
    }

    std::fs::create_dir_all("models")?;
    trainer.train(Path::new(model_out))?;
    println!("wrote {model_out}");

    // Fidelity eval on the held-out split (gold BIO already projected via Rust).
    let model_bytes = std::fs::read(model_out)?;
    let model = Model::new(&model_bytes)?;
    let tagger = model.tagger()?;
    eval(&tagger, &held);
    Ok(())
}

// crfs 0.4: `tag` is `&self` (not `&mut self`), so tagger is `&crfs::Tagger` here.
fn eval(tagger: &crfs::Tagger, held: &[(Vec<String>, Vec<String>)]) {
    use std::collections::HashMap;
    // per-label (tp, fp, fn) on entity spans
    let mut counts: HashMap<String, [u64; 3]> = HashMap::new();
    for (tokens, gold) in held {
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(tokens, &pos);
        // crfs 0.4: tag returns Vec<&str>; convert to Vec<String> for spans().
        let pred: Vec<String> = tagger
            .tag(&attrs(&feats))
            .unwrap_or_default()
            .into_iter()
            .map(str::to_string)
            .collect();
        let g = spans(gold);
        let p = spans(&pred);
        for (lbl, s, e) in &p {
            let entry = counts.entry(lbl.clone()).or_default();
            if g.contains(&(lbl.clone(), *s, *e)) { entry[0] += 1 } else { entry[1] += 1 }
        }
        for (lbl, s, e) in &g {
            if !p.contains(&(lbl.clone(), *s, *e)) {
                counts.entry(lbl.clone()).or_default()[2] += 1;
            }
        }
    }
    let mut labels: Vec<&String> = counts.keys().collect();
    labels.sort();
    println!("label        P      R      F1");
    for lbl in labels {
        let [tp, fp, fng] = counts[lbl];
        let p = tp as f64 / (tp + fp).max(1) as f64;
        let r = tp as f64 / (tp + fng).max(1) as f64;
        let f1 = if p + r == 0.0 { 0.0 } else { 2.0 * p * r / (p + r) };
        println!("{lbl:<12} {p:.3}  {r:.3}  {f1:.3}");
    }
}

/// BIO label sequence -> set of (label, start_tok, end_tok) spans.
fn spans(labels: &[String]) -> Vec<(String, usize, usize)> {
    let mut out = Vec::new();
    let mut cur: Option<(String, usize)> = None;
    for (i, lbl) in labels.iter().enumerate() {
        if let Some(t) = lbl.strip_prefix("B-") {
            if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
            cur = Some((t.to_string(), i));
        } else if let Some(t) = lbl.strip_prefix("I-") {
            match &cur {
                Some((l, _)) if l == t => {}
                _ => {
                    if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
                    cur = Some((t.to_string(), i));
                }
            }
        } else {
            if let Some((l, s)) = cur.take() { out.push((l, s, i)); }
        }
    }
    if let Some((l, s)) = cur { out.push((l, s, labels.len())); }
    out
}
