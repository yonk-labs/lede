//! v0.4.2 heading/pin retention. Mirror of src/lede/_pins.py. Byte-identical
//! output is enforced by `rust/tests/fixtures.rs::v0_4_2_pins_byte_identical`.

use crate::headings::{is_structural_heading, md_depth};

#[must_use]
pub fn nearest_heading_map(sentences: &[String]) -> Vec<Option<usize>> {
    let mut out = Vec::with_capacity(sentences.len());
    let mut current: Option<usize> = None;
    for (i, s) in sentences.iter().enumerate() {
        if is_structural_heading(s) {
            out.push(None);
            current = Some(i);
        } else {
            out.push(current);
        }
    }
    out
}

#[must_use]
pub fn document_title_index(sentences: &[String]) -> Option<usize> {
    // Look only at the first element: if it's a depth-1 structural heading,
    // return its index; any other case (body sentence or deeper heading) → None.
    if let Some((i, s)) = sentences.iter().enumerate().next() {
        if is_structural_heading(s) {
            return if md_depth(s) == 1 { Some(i) } else { None };
        }
    }
    None
}

#[must_use]
pub fn render_toc_from_list(headings: &[String]) -> String {
    let mut seen = std::collections::HashSet::new();
    let mut out: Vec<String> = Vec::new();
    for h in headings {
        if seen.insert(h.clone()) {
            out.push(h.clone());
        }
    }
    out.join("\n")
}

#[must_use]
pub fn render_toc(text: &str) -> String {
    let sections = crate::extract::outline::outline(text);
    sections
        .iter()
        .map(|sec| {
            let indent = "  ".repeat(sec.depth.saturating_sub(1));
            format!("{indent}{}", sec.name)
        })
        .collect::<Vec<_>>()
        .join("\n")
}

fn render_keep_headings_override(
    sentences: &[String],
    selected: &[usize],
    headings: &[String],
) -> (String, Vec<String>) {
    // Dedup headings preserving order (first occurrence wins).
    let mut seen = std::collections::HashSet::new();
    let mut h_list: Vec<String> = Vec::new();
    for h in headings {
        if seen.insert(h.clone()) {
            h_list.push(h.clone());
        }
    }

    // First-unclaimed stripped-equality match for each heading.
    let mut matched_pos: std::collections::HashMap<String, usize> =
        std::collections::HashMap::new();
    let mut claimed: std::collections::HashSet<usize> = std::collections::HashSet::new();
    for h in &h_list {
        let hs = h.trim();
        for (i, s) in sentences.iter().enumerate() {
            if claimed.contains(&i) {
                continue;
            }
            if s.trim() == hs {
                matched_pos.insert(h.clone(), i);
                claimed.insert(i);
                break;
            }
        }
    }
    let pos_to_heading: std::collections::HashMap<usize, String> = matched_pos
        .iter()
        .map(|(h, &idx)| (idx, h.clone()))
        .collect();
    let mut matched_indices: Vec<usize> = matched_pos.values().copied().collect();
    matched_indices.sort_unstable();

    let mut pinned: Vec<String> = Vec::new();
    let mut out_lines: Vec<String> = Vec::new();
    let mut buf: Vec<String> = Vec::new();
    let mut emitted_idx: std::collections::HashSet<usize> = std::collections::HashSet::new();
    let mut emitted_text: std::collections::HashSet<String> = std::collections::HashSet::new();

    // Title at top (first heading in h_list).
    if let Some(title) = h_list.first() {
        out_lines.push(title.clone());
        pinned.push(title.clone());
        emitted_text.insert(title.clone());
        if let Some(&ti) = matched_pos.get(title) {
            emitted_idx.insert(ti);
        }
    }

    // Unmatched headings (except title already emitted) go before body.
    for h in &h_list {
        if emitted_text.contains(h) {
            continue;
        }
        if !matched_pos.contains_key(h) {
            out_lines.push(h.clone());
            pinned.push(h.clone());
            emitted_text.insert(h.clone());
        }
    }

    // Walk selected sentences; interleave matched headings at nearest match.
    for &s_idx in selected {
        // nearest matched index <= s_idx
        let nearest = matched_indices
            .iter()
            .rev()
            .find(|&&mi| mi <= s_idx)
            .copied();
        if let Some(mi) = nearest {
            if !emitted_idx.contains(&mi) {
                if !buf.is_empty() {
                    out_lines.push(buf.join(" "));
                    buf.clear();
                }
                let h = pos_to_heading[&mi].clone();
                out_lines.push(h.clone());
                pinned.push(h.clone());
                emitted_idx.insert(mi);
                emitted_text.insert(h);
            }
        }
        buf.push(sentences[s_idx].clone());
    }
    if !buf.is_empty() {
        out_lines.push(buf.join(" "));
    }

    // Survival guarantee (§4.3 step 6): any supplied heading not yet emitted —
    // it matched a body line but that section had no selected sentence — is
    // appended so every heading in H is present in the output.
    for h in &h_list {
        if !emitted_text.contains(h) {
            out_lines.push(h.clone());
            pinned.push(h.clone());
            emitted_text.insert(h.clone());
        }
    }

    (out_lines.join("\n"), pinned)
}

#[allow(clippy::too_many_arguments)]
#[must_use]
pub fn render_with_pins(
    sentences: &[String],
    selected: &[usize],
    keep_headings: bool,
    include_toc: bool,
    pin: Option<&[String]>,
    text: &str,
    headings: Option<&[String]>,
) -> (String, Vec<String>) {
    let mut pinned_headings: Vec<String> = Vec::new();
    let body: String;
    if keep_headings {
        // Dispatch to override renderer when caller-supplied headings are present.
        let use_override = matches!(headings, Some(h) if !h.is_empty());
        if use_override {
            let h_list = headings.unwrap();
            let (b, pinned) = render_keep_headings_override(sentences, selected, h_list);
            body = b;
            pinned_headings = pinned;
        } else {
            // Auto-detection path — unchanged.
            let heading_of = nearest_heading_map(sentences);
            let title_idx = document_title_index(sentences);
            let mut emitted = std::collections::HashSet::new();
            let mut out_lines: Vec<String> = Vec::new();
            let mut buf: Vec<String> = Vec::new();
            if let Some(t) = title_idx {
                out_lines.push(sentences[t].clone());
                emitted.insert(t);
                pinned_headings.push(sentences[t].clone());
            }
            for &s_idx in selected {
                if let Some(h) = heading_of[s_idx] {
                    if !emitted.contains(&h) {
                        if !buf.is_empty() {
                            out_lines.push(buf.join(" "));
                            buf.clear();
                        }
                        out_lines.push(sentences[h].clone());
                        emitted.insert(h);
                        pinned_headings.push(sentences[h].clone());
                    }
                }
                buf.push(sentences[s_idx].clone());
            }
            if !buf.is_empty() {
                out_lines.push(buf.join(" "));
            }
            if pinned_headings.is_empty() {
                body = selected
                    .iter()
                    .map(|&i| sentences[i].clone())
                    .collect::<Vec<_>>()
                    .join(" ");
            } else {
                body = out_lines.join("\n");
            }
        }
    } else {
        body = selected
            .iter()
            .map(|&i| sentences[i].clone())
            .collect::<Vec<_>>()
            .join(" ");
    }

    let mut blocks: Vec<String> = Vec::new();
    if let Some(p) = pin {
        if !p.is_empty() {
            blocks.push(p.join("\n"));
        }
    }
    if include_toc {
        let toc_text = match headings {
            Some(h) if !h.is_empty() => render_toc_from_list(h),
            _ => render_toc(text),
        };
        if !toc_text.is_empty() {
            blocks.push(toc_text);
        }
    }
    if !body.is_empty() {
        blocks.push(body);
    }
    (blocks.join("\n\n"), pinned_headings)
}

#[must_use]
pub fn prepend_blocks(
    body: &str,
    include_toc: bool,
    pin: Option<&[String]>,
    text: &str,
    headings: Option<&[String]>,
) -> String {
    let mut blocks: Vec<String> = Vec::new();
    if let Some(p) = pin {
        if !p.is_empty() {
            blocks.push(p.join("\n"));
        }
    }
    if include_toc {
        let toc_text = match headings {
            Some(h) if !h.is_empty() => render_toc_from_list(h),
            _ => render_toc(text),
        };
        if !toc_text.is_empty() {
            blocks.push(toc_text);
        }
    }
    if !body.is_empty() {
        blocks.push(body.to_string());
    }
    blocks.join("\n\n")
}
