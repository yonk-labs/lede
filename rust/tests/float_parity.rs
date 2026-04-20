//! Float parity regression test for the `CPython` 3.12+ `sum()` Neumaier divergence.
//!
//! `CPython` 3.12 switched built-in `sum()` to Neumaier compensated summation for
//! float accumulators. Rust's `Iterator::sum()` is a plain IEEE-754 left-fold and
//! drifts by 1-3 ULPs on per-sentence TF-IDF sums of 6+ float terms. This test
//! pins Rust's `tfidf_score` output to bit-identity with the Python reference on
//! a known-divergent rich input. If Rust's `neumaier_sum` regresses, this test
//! will trip long before the T9 fixture walker gate.
//!
//! Oracle bits captured 2026-04-20 from `.venv` Python 3.13 running
//! `src/skimr/tfidf.py::tfidf_score` on the same `sentences` vec below.

use skimr::tfidf::tfidf_score;

#[test]
fn tfidf_score_bit_identical_to_python_on_rich_input() {
    let sentences: Vec<String> = vec![
        "Revenue growth slowed considerably during fourth quarter review period across enterprise segments.".to_string(),
        "Margins improved meaningfully while consumer channels remained flat throughout recent quarters everywhere.".to_string(),
        "Churn analysis identified onboarding friction causing retention problems across mid-market customers overall.".to_string(),
        "Expansion revenue recovered after customer success realigned pricing around quarterly outcome reviews consistently.".to_string(),
        "Procurement feedback suggested pricing remained competitive though packaging required further refinement ongoing.".to_string(),
    ];
    // CPython 3.13 tfidf_score(sentences) -> bit-for-bit patterns.
    let expected_bits: [u64; 5] = [
        0x3fef_6fd0_d9f0_faa4,
        0x3fef_f5b3_7d48_11e8,
        0x3ff0_0000_0000_0000,
        0x3fef_6fd0_d9f0_faa4,
        0x3fef_6fd0_d9f0_faa4,
    ];
    let actual = tfidf_score(&sentences);
    assert_eq!(actual.len(), expected_bits.len());
    for (i, (a, want)) in actual.iter().zip(expected_bits.iter()).enumerate() {
        let got = a.to_bits();
        assert_eq!(
            got, *want,
            "sentence {i}: got {a} (bits 0x{got:016x}) want bits 0x{want:016x}",
        );
    }
}
