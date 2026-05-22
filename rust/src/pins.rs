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

#[must_use]
pub fn render_with_pins(
    sentences: &[String],
    selected: &[usize],
    keep_headings: bool,
    include_toc: bool,
    pin: Option<&[String]>,
    text: &str,
) -> (String, Vec<String>) {
    let mut pinned_headings: Vec<String> = Vec::new();
    let body: String;
    if keep_headings {
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
        let toc_text = render_toc(text);
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
pub fn prepend_blocks(body: &str, include_toc: bool, pin: Option<&[String]>, text: &str) -> String {
    let mut blocks: Vec<String> = Vec::new();
    if let Some(p) = pin {
        if !p.is_empty() {
            blocks.push(p.join("\n"));
        }
    }
    if include_toc {
        let toc_text = render_toc(text);
        if !toc_text.is_empty() {
            blocks.push(toc_text);
        }
    }
    if !body.is_empty() {
        blocks.push(body.to_string());
    }
    blocks.join("\n\n")
}
