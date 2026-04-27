"""Optional skimr-spacy companion — adds Metadata.entities.

Requires:
    pip install -e packages/skimr-spacy
    python -m spacy download en_core_web_sm

Importing skimr_spacy registers backends as a side effect. After that,
extract.metadata(text, backend="spacy") populates the entities field.
Rust port does not ship NER by design — entities stays empty there.

Run: python examples/06_with_spacy_entities.py
"""
import sys

# Importing skimr_spacy registers the spaCy backends.
try:
    import skimr_spacy  # noqa: F401  — side-effect import
except ImportError:
    print("This example requires the skimr-spacy companion package.", file=sys.stderr)
    print("    pip install -e packages/skimr-spacy", file=sys.stderr)
    print("    python -m spacy download en_core_web_sm", file=sys.stderr)
    sys.exit(1)

from skimr.extract import metadata

DOC = """
Acme Corp announced today a partnership with skimr Labs to integrate
deterministic summarization into their RAG pipeline. The deal,
brokered by CEO Lin Wu and signed in San Francisco on 2024-11-15,
covers $2.4M in annual licensing through 2027.
"""


def main() -> None:
    # Default backend = regex; entities is empty.
    md_regex = metadata(DOC)
    print("--- backend='regex' (default) ---")
    print(f"  dates:    {md_regex.dates}")
    print(f"  amounts:  {md_regex.amounts}")
    print(f"  urls:     {md_regex.urls}")
    print(f"  entities: {md_regex.entities}  # empty under regex")
    print()

    # Opt into spaCy backend per call.
    md_spacy = metadata(DOC, backend="spacy")
    print("--- backend='spacy' (en_core_web_sm) ---")
    print(f"  dates:    {md_spacy.dates}")
    print(f"  amounts:  {md_spacy.amounts}")
    print(f"  urls:     {md_spacy.urls}")
    print(f"  entities: {md_spacy.entities}  # PERSON / ORG / GPE")


if __name__ == "__main__":
    main()
