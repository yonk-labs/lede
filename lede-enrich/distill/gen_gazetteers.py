"""Generate src/crf/data.rs — expanded, license-clean gazetteer lists used ONLY
as CRF features (type-disambiguation signal). The rule-based extract_entities
keeps its own original lists, so its golden tests are unaffected.

Sources (public domain, US government):
  - Surnames: US Census 2010 surname file.
  - Forenames: SSA baby-name data (aggregated across years).
Places / org words are curated literals below (trivially public-domain facts).

Run once; commit the generated src/crf/data.rs. Lists are lowercase (contains_ci
lowercases the query), sorted, deduped.
"""
import io
import sys
import urllib.request
import zipfile

CENSUS_URL = "https://www2.census.gov/topics/genealogy/2010surnames/names.zip"
SSA_URL = "https://www.ssa.gov/oact/babynames/names.zip"
N_SURNAMES = 2000
N_FORENAMES = 1500

US_STATES = [
    "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
    "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
    "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana", "maine",
    "maryland", "massachusetts", "michigan", "minnesota", "mississippi",
    "missouri", "montana", "nebraska", "nevada", "ohio", "oklahoma", "oregon",
    "pennsylvania", "tennessee", "texas", "utah", "vermont", "virginia",
    "washington", "wisconsin", "wyoming",
]

# Major world + US cities (curated public-domain facts).
CITIES = [
    "london", "paris", "berlin", "madrid", "rome", "vienna", "amsterdam",
    "brussels", "lisbon", "dublin", "athens", "warsaw", "prague", "budapest",
    "moscow", "kyiv", "istanbul", "cairo", "lagos", "nairobi", "johannesburg",
    "tokyo", "beijing", "shanghai", "seoul", "delhi", "mumbai", "bangkok",
    "jakarta", "manila", "singapore", "sydney", "melbourne", "auckland",
    "toronto", "montreal", "vancouver", "mexico", "bogota", "lima", "santiago",
    "buenos", "aires", "rio", "janeiro", "york", "angeles", "chicago",
    "houston", "phoenix", "philadelphia", "antonio", "diego", "dallas",
    "austin", "francisco", "seattle", "denver", "boston", "atlanta", "miami",
    "detroit", "minneapolis", "portland", "vegas", "baltimore", "milwaukee",
    "albuquerque", "tucson", "fresno", "sacramento", "kansas", "mesa",
    "omaha", "raleigh", "cleveland", "tulsa", "nashville", "huntsville",
    "montgomery", "birmingham", "mobile", "tuscaloosa", "orleans",
]

ORG_WORDS = [
    "university", "college", "institute", "institution", "company",
    "corporation", "incorporated", "association", "foundation", "department",
    "ministry", "bureau", "agency", "commission", "committee", "council",
    "bank", "group", "holdings", "partners", "systems", "technologies",
    "industries", "enterprises", "laboratories", "laboratory", "society",
    "federation", "union", "alliance", "organization", "academy", "school",
    "hospital", "clinic", "airlines", "motors", "pharmaceuticals", "networks",
    "communications", "media", "press", "studios", "records", "club",
    "team", "league", "court", "office", "administration", "authority",
    "parliament", "congress", "senate", "assembly",
]


_UAS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
    "lede-enrich-gazetteer/1",
    "curl/8.0",
]

# Curated fallback forenames (common English given names) used if the SSA
# download is blocked. Public-domain facts; lowercase.
FALLBACK_FORENAMES = [
    "james", "john", "robert", "michael", "william", "david", "richard",
    "joseph", "thomas", "charles", "christopher", "daniel", "matthew", "anthony",
    "donald", "mark", "paul", "steven", "andrew", "kenneth", "joshua", "kevin",
    "brian", "george", "edward", "ronald", "timothy", "jason", "jeffrey", "ryan",
    "jacob", "gary", "nicholas", "eric", "jonathan", "stephen", "larry", "justin",
    "scott", "brandon", "benjamin", "samuel", "gregory", "frank", "alexander",
    "raymond", "patrick", "jack", "dennis", "jerry", "tyler", "aaron", "henry",
    "douglas", "peter", "adam", "nathan", "zachary", "walter", "kyle", "harold",
    "carl", "jeremy", "gerald", "keith", "roger", "arthur", "terry", "lawrence",
    "sean", "christian", "ethan", "austin", "joe", "albert", "jesse", "willie",
    "billy", "bryan", "bruce", "noah", "jordan", "dylan", "ralph", "roy", "eugene",
    "wayne", "alan", "juan", "luis", "elijah", "logan", "victor", "martin",
    "mary", "patricia", "jennifer", "linda", "elizabeth", "barbara", "susan",
    "jessica", "sarah", "karen", "nancy", "lisa", "margaret", "betty", "sandra",
    "ashley", "dorothy", "kimberly", "emily", "donna", "michelle", "carol",
    "amanda", "melissa", "deborah", "stephanie", "rebecca", "laura", "sharon",
    "cynthia", "kathleen", "amy", "angela", "shirley", "anna", "brenda", "pamela",
    "emma", "nicole", "helen", "samantha", "katherine", "christine", "debra",
    "rachel", "carolyn", "janet", "maria", "olivia", "heather", "diane", "julie",
    "joyce", "victoria", "kelly", "christina", "joan", "evelyn", "judith",
    "andrea", "hannah", "megan", "cheryl", "jacqueline", "martha", "madison",
    "teresa", "gloria", "sara", "janice", "julia", "grace", "judy", "abigail",
    "denise", "amber", "marilyn", "danielle", "sophia", "isabella", "ava",
    "mia", "charlotte", "amelia", "harper", "ella", "chloe", "lily", "sofia",
]


def fetch_zip(url):
    last = None
    for ua in _UAS:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": ua})
            with urllib.request.urlopen(req, timeout=60) as r:
                return zipfile.ZipFile(io.BytesIO(r.read()))
        except Exception as e:  # noqa: BLE001 — try next UA
            last = e
    raise last


def census_surnames(n):
    zf = fetch_zip(CENSUS_URL)
    name = next(f for f in zf.namelist() if f.lower().endswith(".csv"))
    out = []
    with zf.open(name) as f:
        header = f.readline()  # name,rank,count,...
        for line in f:
            parts = line.decode("utf-8", "ignore").split(",")
            surname = parts[0].strip().lower()
            if surname and surname != "all other names" and surname.isalpha():
                out.append(surname)
            if len(out) >= n:
                break
    return out


def ssa_forenames(n):
    try:
        zf = fetch_zip(SSA_URL)
    except Exception as e:  # noqa: BLE001
        print(f"  SSA download failed ({e}); using curated fallback forenames", file=sys.stderr)
        return FALLBACK_FORENAMES
    counts = {}
    for fn in zf.namelist():
        if not fn.lower().startswith("yob") or not fn.lower().endswith(".txt"):
            continue
        with zf.open(fn) as f:
            for line in f:
                nm, _sex, cnt = line.decode("utf-8", "ignore").strip().split(",")
                nm = nm.lower()
                if nm.isalpha():
                    counts[nm] = counts.get(nm, 0) + int(cnt)
    top = sorted(counts, key=lambda k: counts[k], reverse=True)[:n]
    return top


def emit_array(name, items):
    uniq = sorted(set(i for i in items if i))
    lines = [f'pub const {name}: &[&str] = &[']
    row = "    "
    for it in uniq:
        chunk = f'"{it}", '
        if len(row) + len(chunk) > 96:
            lines.append(row.rstrip())
            row = "    "
        row += chunk
    if row.strip():
        lines.append(row.rstrip())
    lines.append("];")
    return "\n".join(lines), len(uniq)


def main():
    print("fetching census surnames...", file=sys.stderr)
    surnames = census_surnames(N_SURNAMES)
    print("fetching SSA forenames...", file=sys.stderr)
    forenames = ssa_forenames(N_FORENAMES)

    blocks = []
    total = 0
    for name, items in [
        ("SURNAMES", surnames),
        ("FORENAMES", forenames),
        ("CITIES", CITIES),
        ("US_STATES", US_STATES),
        ("ORG_WORDS", ORG_WORDS),
    ]:
        block, n = emit_array(name, items)
        blocks.append(block)
        total += n
        print(f"  {name}: {n}", file=sys.stderr)

    header = (
        "//! Expanded gazetteer lists used ONLY as CRF features (type signal).\n"
        "//! GENERATED by distill/gen_gazetteers.py from public-domain US Census\n"
        "//! surnames + SSA forenames + curated place/org literals. Do not edit by\n"
        "//! hand; re-run the generator. Lowercase, sorted, deduped.\n"
    )
    out = header + "\n" + "\n\n".join(blocks) + "\n"
    with open("src/crf/data.rs", "w", encoding="utf-8") as f:
        f.write(out)
    print(f"wrote src/crf/data.rs ({total} terms)", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
