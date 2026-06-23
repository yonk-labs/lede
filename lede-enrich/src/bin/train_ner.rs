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
use lede_enrich::{extract_entities, project_bio, sequence_features, tokenize};
use serde_json::Value;

fn attrs(feats: &[Vec<String>]) -> Vec<Vec<Attribute>> {
    feats
        .iter()
        .map(|row| {
            row.iter()
                .map(|s| Attribute::new(s.as_str(), 1.0))
                .collect()
        })
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
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "distill/silver.jsonl".into());
    let model_out = "models/ner.crfsuite";

    // L2SGD, not batch L-BFGS: an L2-regularized CRF trained by stochastic
    // gradient. crfs is single-threaded and batch L-BFGS (full forward-backward
    // gradient + line search over millions of weights per iteration) did not
    // converge in practical time on this feature space. L2SGD keeps the proper
    // CRF objective (probabilistic transition features — more accurate than an
    // averaged perceptron) but updates per-sequence, so it trains fast. The model
    // it writes is loaded unchanged by the same Tagger/Viterbi inference.
    let max_iter: usize = std::env::var("LEDE_NER_MAXITER")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(100);
    let mut trainer = Trainer::l2sgd()
        .with_c2(1.0)?
        .with_max_iterations(max_iter)?;
    // Drop features seen fewer than this many times. The affix + ±2 context
    // features generate a huge singleton tail; pruning it shrinks the bundled
    // model by an order of magnitude and speeds up each L-BFGS iteration.
    // Overridable via LEDE_NER_MINFREQ for the Task 9 tuning sweep.
    let minfreq: f64 = std::env::var("LEDE_NER_MINFREQ")
        .ok()
        .and_then(|v| v.parse().ok())
        .unwrap_or(2.0);
    trainer.set_feature_minfreq(minfreq)?;

    // Eval-only mode: skip (re)training, just load the existing model and eval —
    // so eval-metric iteration costs seconds, not a full retrain.
    let eval_only = std::env::var("LEDE_NER_EVAL_ONLY").is_ok();
    let mut held: Vec<(String, Vec<String>)> = Vec::new();
    for (i, line) in BufReader::new(File::open(&path)?).lines().enumerate() {
        let v: Value = serde_json::from_str(&line?)?;
        let text = v["text"].as_str().unwrap_or("").to_string();
        let Some((tokens, bio)) = parse_line(&v) else {
            continue;
        };
        if i % 10 == 0 {
            held.push((text, bio));
            continue;
        }
        if eval_only {
            continue;
        }
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(&tokens, &pos);
        let yseq: Vec<&str> = bio.iter().map(String::as_str).collect();
        trainer.append(&attrs(&feats), &yseq)?;
    }

    if eval_only {
        println!("eval-only: using existing {model_out}");
    } else {
        std::fs::create_dir_all("models")?;
        trainer.train(Path::new(model_out))?;
        println!("wrote {model_out}");
    }

    // Fidelity eval on the held-out split (gold BIO already projected via Rust).
    let model_bytes = std::fs::read(model_out)?;
    let model = Model::new(&model_bytes)?;
    let tagger = model.tagger()?;
    eval(&tagger, &held);
    Ok(())
}

// crfs 0.4: `tag` is `&self` (not `&mut self`), so tagger is `&crfs::Tagger` here.
fn eval(tagger: &crfs::Tagger, held: &[(String, Vec<String>)]) {
    use std::collections::{HashMap, HashSet};
    // per-label (tp, fp, fn) on typed entity spans
    let mut counts: HashMap<String, [u64; 3]> = HashMap::new();
    let debug = std::env::var("LEDE_NER_DEBUG").is_ok();
    let mut dumped = 0;
    let (mut tok_total, mut tok_match) = (0u64, 0u64);
    let (mut ent_total, mut ent_match) = (0u64, 0u64);
    // untyped entity spans (ignore label): does it find the boundaries at all?
    let (mut u_tp, mut u_fp, mut u_fn) = (0u64, 0u64, 0u64);
    // surface-set agreement vs spaCy gold: CRF vs the current gazetteer baseline.
    let (mut crf_tp, mut crf_fp, mut crf_fn) = (0u64, 0u64, 0u64);
    let (mut gaz_tp, mut gaz_fp, mut gaz_fn) = (0u64, 0u64, 0u64);

    for (text, gold) in held {
        let toks = tokenize(text);
        let tokens: Vec<String> = toks.iter().map(|t| t.text.clone()).collect();
        let pos = vec![None; tokens.len()];
        let feats = sequence_features(&tokens, &pos);
        // crfs 0.4: tag returns Vec<&str>; convert to Vec<String> for spans().
        let pred: Vec<String> = tagger
            .tag(&attrs(&feats))
            .unwrap_or_default()
            .into_iter()
            .map(str::to_string)
            .collect();
        for (g, p) in gold.iter().zip(pred.iter()) {
            tok_total += 1;
            if g == p {
                tok_match += 1;
            }
            if g != "O" {
                ent_total += 1;
                if g == p {
                    ent_match += 1;
                }
            }
        }
        let g = spans(gold);
        let p = spans(&pred);
        if debug && dumped < 15 && g != p {
            println!("DBG toks: {tokens:?}");
            println!("DBG gold: {g:?}");
            println!("DBG pred: {p:?}");
            dumped += 1;
        }
        for (lbl, s, e) in &p {
            let entry = counts.entry(lbl.clone()).or_default();
            if g.contains(&(lbl.clone(), *s, *e)) {
                entry[0] += 1
            } else {
                entry[1] += 1
            }
        }
        for (lbl, s, e) in &g {
            if !p.contains(&(lbl.clone(), *s, *e)) {
                counts.entry(lbl.clone()).or_default()[2] += 1;
            }
        }
        // untyped spans (ignore label)
        let gu: HashSet<(usize, usize)> = g.iter().map(|(_, s, e)| (*s, *e)).collect();
        let pu: HashSet<(usize, usize)> = p.iter().map(|(_, s, e)| (*s, *e)).collect();
        for sp in &pu {
            if gu.contains(sp) {
                u_tp += 1
            } else {
                u_fp += 1
            }
        }
        for sp in &gu {
            if !pu.contains(sp) {
                u_fn += 1
            }
        }
        // surface-set comparison (lowercased), CRF and gazetteer vs gold surfaces
        let surf = |sp: &[(String, usize, usize)]| -> HashSet<String> {
            sp.iter()
                .filter(|(_, s, e)| e > s && *e <= toks.len())
                .map(|(_, s, e)| text[toks[*s].start..toks[*e - 1].end].to_lowercase())
                .collect()
        };
        let gold_surf = surf(&g);
        let crf_surf = surf(&p);
        let gaz_surf: HashSet<String> = extract_entities(text)
            .into_iter()
            .map(|s| s.to_lowercase())
            .collect();
        for s in &crf_surf {
            if gold_surf.contains(s) {
                crf_tp += 1
            } else {
                crf_fp += 1
            }
        }
        for s in &gold_surf {
            if !crf_surf.contains(s) {
                crf_fn += 1
            }
        }
        for s in &gaz_surf {
            if gold_surf.contains(s) {
                gaz_tp += 1
            } else {
                gaz_fp += 1
            }
        }
        for s in &gold_surf {
            if !gaz_surf.contains(s) {
                gaz_fn += 1
            }
        }
    }

    let prf = |tp: u64, fp: u64, fng: u64| {
        let p = tp as f64 / (tp + fp).max(1) as f64;
        let r = tp as f64 / (tp + fng).max(1) as f64;
        let f1 = if p + r == 0.0 {
            0.0
        } else {
            2.0 * p * r / (p + r)
        };
        (p, r, f1)
    };

    println!(
        "token-level acc: {:.3} ({}/{})  |  entity-token acc (gold!=O): {:.3} ({}/{})",
        tok_match as f64 / tok_total.max(1) as f64,
        tok_match,
        tok_total,
        ent_match as f64 / ent_total.max(1) as f64,
        ent_match,
        ent_total,
    );
    let (up, ur, uf) = prf(u_tp, u_fp, u_fn);
    println!(
        "CRF  untyped span      P {up:.3} R {ur:.3} F1 {uf:.3}  (finds boundaries, ignore type)"
    );
    let (cp, cr, cf) = prf(crf_tp, crf_fp, crf_fn);
    println!("CRF  surface (untyped) P {cp:.3} R {cr:.3} F1 {cf:.3}");
    let (gp, gr, gf) = prf(gaz_tp, gaz_fp, gaz_fn);
    println!(
        "GAZ  surface (current) P {gp:.3} R {gr:.3} F1 {gf:.3}  <- current Rust baseline to beat"
    );

    let mut labels: Vec<&String> = counts.keys().collect();
    labels.sort();
    println!("label        P      R      F1   (strict typed entity-span)");
    for lbl in labels {
        let [tp, fp, fng] = counts[lbl];
        let (p, r, f1) = prf(tp, fp, fng);
        println!("{lbl:<12} {p:.3}  {r:.3}  {f1:.3}");
    }
}

/// BIO label sequence -> set of (label, start_tok, end_tok) spans.
fn spans(labels: &[String]) -> Vec<(String, usize, usize)> {
    let mut out = Vec::new();
    let mut cur: Option<(String, usize)> = None;
    for (i, lbl) in labels.iter().enumerate() {
        if let Some(t) = lbl.strip_prefix("B-") {
            if let Some((l, s)) = cur.take() {
                out.push((l, s, i));
            }
            cur = Some((t.to_string(), i));
        } else if let Some(t) = lbl.strip_prefix("I-") {
            match &cur {
                Some((l, _)) if l == t => {}
                _ => {
                    if let Some((l, s)) = cur.take() {
                        out.push((l, s, i));
                    }
                    cur = Some((t.to_string(), i));
                }
            }
        } else if let Some((l, s)) = cur.take() {
            out.push((l, s, i));
        }
    }
    if let Some((l, s)) = cur {
        out.push((l, s, labels.len()));
    }
    out
}
