//! Numeric facts (entity ↔ number) for the Rust path.
//!
//! M1 default path reuses lede core's deterministic regex `correlate_facts` and
//! re-attributes each fact's `entity` to a gazetteer/NER surface form found in
//! the fact's sentence — core attributes a lowercased repeated word ("apple"),
//! NER gives the proper entity ("Apple"). Return type is the core `PhraseFact`,
//! so there is no schema drift for consumers.
//!
//! Higher-recall anchor-based POS-SVO is the opt-in `pos` feature, not built in
//! the M1 default (see spec §5.3/§5.4).

use crate::ner::extract_entities;
use lede::extract::correlate::{PhraseFact, correlate_facts as core_correlate_facts};

/// Entity-aware numeric facts. Mirrors Python `lede_spacy.spacy_correlate_facts`.
///
/// Facts are structured records for metadata filtering — not text to embed.
#[must_use]
pub fn correlate_facts(text: &str) -> Vec<PhraseFact> {
    core_correlate_facts(text)
        .into_iter()
        .map(|mut fact| {
            if let Some(entity) = extract_entities(&fact.sentence).into_iter().next() {
                fact.entity = entity;
            }
            fact
        })
        .collect()
}

/// Higher-recall facts via the opt-in rule-based POS path (`pos` feature).
///
/// Emits a fact for every numeric stat that co-occurs with an NER entity — not
/// just core's "repeated word" pairings — and scopes polarity to the verb (via
/// [`crate::pos`]) rather than any word in the sentence. Rule-based and
/// license-clean; recall over precision relative to [`correlate_facts`].
#[cfg(feature = "pos")]
#[must_use]
pub fn correlate_facts_pos(text: &str) -> Vec<PhraseFact> {
    use lede::extract::stats::stats;

    let mut out: Vec<PhraseFact> = Vec::new();
    for st in stats(text) {
        let Some(entity) = extract_entities(&st.context_sentence).into_iter().next() else {
            continue;
        };
        let tagged = crate::pos::tag_tokens(&st.context_sentence);
        let polarity = crate::pos::verb_polarity(&tagged).to_string();
        let number = if st.unit.is_empty() {
            st.value.clone()
        } else {
            format!("{} {}", st.value, st.unit)
        };
        let fact = PhraseFact {
            entity,
            number,
            polarity,
            sentence: st.context_sentence.clone(),
        };
        if !out.contains(&fact) {
            out.push(fact);
        }
    }
    out
}
