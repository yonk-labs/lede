"""Combined lede + spaCy readable report.

Run:
    python examples/13_readable_report.py

Pass backend="spacy" when you want optional spaCy entities, noun phrases,
and entity-fact links in the report.
"""
from lede import readable_report


DOC = """# City Contract Review

Case Name: City of Acme
Term: 2024
Docket Number: 24-101

Acme Infrastructure won a $13,000 street-services contract in 2024.
Mayor Jane Snyder approved the purchase after two committee meetings.
Acme Infrastructure later sent a $1,000 thank-you payment.
The city council reviewed the contract again in 2025.
"""


def main() -> None:
    report = readable_report(
        DOC,
        max_length=2000,
        max_facts=40,
    )
    print(report.to_markdown())


if __name__ == "__main__":
    main()
