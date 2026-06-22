"""Distillation harness: spaCy en_core_web_sm -> silver entity BYTE-spans.

Reads articles (one JSON per line: {"id": int, "text": str}) from --input,
runs spaCy, keeps only the 11 lexical entity types, emits one JSON per sentence
to --output: {"text": "<sentence>", "ents": [{"start", "end", "label"}]} with
sentence-relative UTF-8 BYTE offsets. Rust owns tokenization (golden-span design)
and works in byte offsets (Rust string slicing is byte-based), so we convert
spaCy's CHARACTER offsets to byte offsets here — otherwise any non-ASCII text
(accents, em-dashes, non-Latin scripts — pervasive in Wikipedia) would misalign
labels against Rust's byte-offset tokens. We deliberately do NOT emit tokens.

We never redistribute the source text — only these spans feed the Rust trainer.
"""
import argparse
import json
import sys

import spacy

LEXICAL = {
    "PERSON", "NORP", "FAC", "ORG", "GPE", "LOC",
    "PRODUCT", "EVENT", "WORK_OF_ART", "LAW", "LANGUAGE",
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="JSONL of {id, text}")
    ap.add_argument("--output", required=True, help="silver.jsonl out")
    ap.add_argument("--model", default="en_core_web_sm")
    args = ap.parse_args()

    nlp = spacy.load(args.model, disable=["lemmatizer"])
    n_sents = 0
    with open(args.input, encoding="utf-8") as fin, open(args.output, "w", encoding="utf-8") as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            text = json.loads(line)["text"]
            doc = nlp(text)
            for sent in doc.sents:
                stext = sent.text
                base = sent.start_char

                def to_byte(char_rel: int) -> int:
                    # char offset (sentence-relative) -> utf-8 byte offset
                    return len(stext[:char_rel].encode("utf-8"))

                ents = [
                    {
                        "start": to_byte(ent.start_char - base),
                        "end": to_byte(ent.end_char - base),
                        "label": ent.label_,
                    }
                    for ent in sent.ents
                    if ent.label_ in LEXICAL
                ]
                fout.write(json.dumps({"text": stext, "ents": ents}) + "\n")
                n_sents += 1
    print(f"wrote {n_sents} sentences to {args.output}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
