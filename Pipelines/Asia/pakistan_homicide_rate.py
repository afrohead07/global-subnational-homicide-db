#!/usr/bin/env python3
"""
Pakistan - police-registered murder cases per 100,000 residents, by district / city.

NUMERATOR   (official): Pakistan Bureau of Statistics (PBS), "District wise Crime data" (https://www.pbs.gov.pk/social-statistics-2/;
            data of the National Police Bureau): one Excel file per province, column "Murder" (not attempted murder). Only full-year
            blocks are used: blocks titled with a month / quarter are excluded and counted.
DENOMINATOR (official): PBS Population Census 2023, "Table 1" district files (population of 2023 AND 2017), found through
            https://www.pbs.gov.pk/census/ and https://www.pbs.gov.pk/result-excel/. A year uses the census closest in time
            (2020 is equidistant and uses 2023); no growth projection is applied. `population_age_years` is that distance.
UNITS       The crime units are the districts listed under each police range. A district created after the 2023 census has no
            census row: its murders are added to the parent district whose census population still contains it (MERGE_INTO below:
            administrative history typed in the script, not read from a source, so those rows are never tier A). Karachi's seven
            districts are summed into one city. Every other district stands in for its city (`is_city_proxy` = True: it includes
            its rural area). Islamabad is a federal territory with one district.
MATCHING    Crime-sheet names are matched to census names by: an alias (SEED_ALIASES: abbreviations and obvious misspellings seen in the
            sheets), an exact name, the same words in another order or with abbreviations expanded, a unique subset of words
            ("partial") or a close spelling ("fuzzy"). A row that relies on a partial or fuzzy match is tier C. A unit with no match
            is left out and reported with its murders; non-territorial police units (CTD, Crime Branch) are left out and reported.
CHECKS      Crime: each block's unit rows add up to its total rows (a mismatch makes the rows tier C). Census: the district populations
            of a province add up to the province total of the PBS national Table 1 (a difference makes the rows tier B). The text in
            `validation` is built from these results. Tier A: exact / name / alias matches only, no merged unit, every block reconciled,
            the census check passed and a census no more than 3.5 years away. Otherwise B, or C for a weak match or a failed block total.
DEFINITION  Police-registered "Murder" (National Police Bureau via PBS); excludes attempted murder; not identical to UNODC intentional
            homicide; whether the unit counts cases or victims is not stated in the files.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Pakistan/ ; the one output is
            pakistan_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
            If the PBS site does not allow automated downloads, save the listed files by hand in the raw folder under the names shown.
Commands:   python pakistan_homicide_rate.py inspect | build
Options:    --refresh-census   download the census files again (they are otherwise reused)
            --include-periodic keep rows from blocks titled with a month / quarter (default: excluded)
Needs:      pip install pandas openpyxl xlrd requests beautifulsoup4 pdfplumber
"""
from __future__ import annotations

import argparse
import difflib
import io
import logging
import re
import sys
import unicodedata
from datetime import date
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 7:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

log = logging.getLogger("pk_homicide")
P = F.paths(__file__, "Pakistan")        # raw downloads -> Data/Raw/<Region>/Pakistan/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (compatible; homicide-db/1.0)", retries=3)
LOW_COUNT = F.LOW_COUNT

# ------------------------------------------------------------------ config
PAGE_URL = "https://www.pbs.gov.pk/social-statistics-2/"
CENSUS_PAGE = "https://www.pbs.gov.pk/census/"
BASE = "https://www.pbs.gov.pk/wp-content/uploads/2020/07/"
CBASE = "https://www.pbs.gov.pk/wp-content/uploads/census_tables/tables/"
CENSUS_PAGES = ["https://www.pbs.gov.pk/result-excel/", CENSUS_PAGE]

# label on the PBS crime page -> (province name in English, fallback crime-file URL)
PROVINCES = {
    "Islamabad": ("Islamabad", BASE + "Islamabad-1.xlsx"),
    "Balochistan": ("Balochistan", BASE + "Baloch.xlsx"),
    "KP": ("Khyber Pakhtunkhwa", BASE + "KP-1.xlsx"),
    "Punjab": ("Punjab", BASE + "Punjab-1.xlsx"),
    "Sindh": ("Sindh", BASE + "Sindh-1.xlsx"),
}
# Census-2023 "Table 1" district files (2023 AND 2017 population). Candidates are tried in order: Excel, then the older PDF location.
CENSUS_FALLBACK = {
    "Islamabad": [BASE + "table_1_islamabad.xlsx", CBASE + "table_1_islamabad.pdf"],
    "KP": [BASE + "table_1_kp_districts.xlsx", CBASE + "table_1_kp_districts.pdf"],
    "Sindh": [BASE + "table_1_sindh_districts.xlsx", CBASE + "table_1_sindh_districts.pdf"],
    "Balochistan": [BASE + "table_1_balochistan_districts.xlsx", CBASE + "table_1_balochistan_districts.pdf"],
    "Punjab": [BASE + "table_1_punjab_districts.xlsx", CBASE + "table_1_punjab_districts.pdf"],
}
CENSUS_NATIONAL = [BASE + "table_1_national.xlsx", CBASE + "table_1_national.pdf"]  # cross-checks
PROVINCE_ROW = {"Islamabad": "ISLAMABAD", "KP": "KHYBER PAKHTUNKHWA", "Punjab": "PUNJAB", "Sindh": "SINDH", "Balochistan": "BALOCHISTAN"}

CENSUS_YEARS = (2017, 2023)
FUZZY_CUTOFF = 0.88                      # DECISION: closeness for a fuzzy name match (such rows are tier C)
CLEAN_MATCHES = {"exact", "name", "alias"}
EXCEL_MAGIC = (b"PK\x03\x04", b"\xd0\xcf\x11\xe0")
PDF_MAGIC = (b"%PDF",)
CENSUS_MAGIC = PDF_MAGIC + EXCEL_MAGIC
YEAR_RE = re.compile(r"\b((?:19|20)\d{2})\b")


# ----------------------------------------------------------------- helpers
def norm(s: object) -> str:
    """Lowercase letters only: 'Attempted Murder' -> 'attemptedmurder'."""
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", s.lower())


def norm_district(s: object) -> str:
    """Name key for matching: drops the word 'district' ('KARACHI EAST DISTRICT')."""
    return norm(re.sub(r"(?i)\bdistrict\b", " ", str(s)))


def slug(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def text(v: object) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v).strip()


def to_num(v: object) -> float:
    t = text(v).replace(",", "")
    try:
        return float(t)
    except ValueError:
        return float("nan")


# ------------------------------------------------------------------- fetch
class NeedManual(Exception):
    """The site's robots.txt does not allow an automated download of this file."""
    def __init__(self, name: str, url: str):
        super().__init__(f"{name} <- {url}")
        self.name, self.url = name, url


def get_file(url: str, name: str, magic: tuple[bytes, ...], reuse: bool) -> tuple[bytes, str]:
    """-> (bytes, retrieval date). A file you saved in the raw folder as <name>.xlsx / .xls / .pdf is used first; otherwise the download
    (a failed download falls back to the newest saved copy). A site that disallows robots raises NeedManual."""
    for ext in (".xlsx", ".xls", ".pdf"):
        p = RAW / f"{name}{ext}"
        if p.exists():
            data = p.read_bytes()
            if not data.startswith(magic):
                raise ValueError(f"{p} is not the expected file type")
            print(f"[manual file] {p}")
            return data, date.fromtimestamp(p.stat().st_mtime).isoformat()
    suffix = Path(url.split("?")[0]).suffix or ".xlsx"
    try:
        data = FETCH.get(url, name, reuse=reuse, suffix=suffix, reject_html=True)
    except F.RobotsDisallowed:
        raise NeedManual(name, url)
    except RuntimeError as e:
        log.warning("Download failed for %s (%s); trying a saved copy", url, e)
        data = FETCH.get(url, name, reuse=True, suffix=suffix, reject_html=True)
    if not data.startswith(magic):
        raise ValueError(f"{url} is not the expected file type (HTML/error page?)")
    return data, FETCH.retrieved_on(url)


def soup_of(url: str):
    from bs4 import BeautifulSoup
    return BeautifulSoup(FETCH.get(url).decode("utf-8", "replace"), "html.parser")


def discover_crime_links() -> dict[str, str]:
    links = {k: v[1] for k, v in PROVINCES.items()}
    try:
        found: dict[str, str] = {}
        for a in soup_of(PAGE_URL).find_all("a", href=True):
            label = a.get_text(strip=True)
            if label in PROVINCES and re.search(r"\.xlsx?$", a["href"], re.I):
                found.setdefault(label, a["href"])
        for label, href in found.items():
            if href != links[label]:
                log.warning("Crime link for %s changed: %s", label, href)
            links[label] = href
        missing = set(PROVINCES) - set(found)
        if missing:
            log.warning("Crime links not found on page, using fallback: %s", sorted(missing))
    except (Exception, F.RobotsDisallowed) as exc:
        log.warning("Crime link discovery failed (%s); using fallback URLs", exc)
    return links


def discover_census_links() -> dict[str, list[str]]:
    """Candidate URLs per province: links found on the PBS census pages, then fallbacks."""
    links = {k: list(v) for k, v in CENSUS_FALLBACK.items()}
    keys = {"kp": "KP", "islamabad": "Islamabad", "punjab": "Punjab", "sindh": "Sindh", "balochistan": "Balochistan"}
    try:
        for page in CENSUS_PAGES:
            try:
                soup = soup_of(page)
            except (Exception, F.RobotsDisallowed) as exc:
                log.warning("Could not read %s (%s)", page, exc)
                continue
            for a in soup.find_all("a", href=True):
                href = urljoin(page, a["href"])
                m = re.search(r"/table_1_([a-z_]+)\.(?:xlsx|pdf)$", href, re.I)
                if not m or "province" in m.group(1).lower() or "national" in m.group(1).lower():
                    continue
                for k, label in keys.items():
                    if k in m.group(1).lower() and href not in links[label]:
                        log.info("Census link for %s from %s: %s", label, page, href)
                        links[label].insert(0, href)
    except (Exception, F.RobotsDisallowed) as exc:
        log.warning("Census link discovery failed (%s); using fallback URLs", exc)
    for label in links:  # Excel first (cleaner than PDF text), de-duplicated, order kept
        seen: list[str] = []
        for u in sorted(links[label], key=lambda u: not u.lower().endswith(".xlsx")):
            if u not in seen:
                seen.append(u)
        links[label] = seen
    return links


# ------------------------------------------------------------- crime parse
PERIODIC_RE = re.compile(
    r"\b(month|monthly|months|quarter|quarterly|upto|up to|january|february|march|april|may|june|"
    r"july|august|september|october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|"
    r"oct|nov|dec)\b", re.I)


def is_total_name(name: str, province: str) -> bool:
    n = norm(name)
    return n in ("total", "grandtotal") or n.endswith("total") or (n == norm(province) and province != "Islamabad")


def parse_sheet(df: pd.DataFrame, province: str, sheet: str) -> tuple[list[dict], list[dict]]:
    """
    Hierarchy-aware parser. A block looks like:
        title line(s) with a year (anywhere above the header)
        header row   ('Districts Name | All Reported | Murder | ...')
        group row    ('Zhob Range', 'Karachi Range': a name with no numbers)  -> police range
        unit rows    (the actual districts: Zhob, Killa Abdullah, ...)
        total row    (subtotal of the group above, or grand total)
    Group headers and total rows are NOT emitted as districts; each unit keeps its group.
    Islamabad is special: its name cell holds the year.
    Returns (unit records, block diagnostics). Blocks whose title/sheet mention a month/quarter are tagged period_hint='periodic'.
    """
    recs: list[dict] = []
    blocks: list[dict] = []
    m = YEAR_RE.search(sheet)
    sheet_year = int(m.group(1)) if m else None
    cols: dict[str, int] | None = None
    year: int | None = None
    in_data = False
    cur: dict | None = None
    pending: list[str] = []
    group: str | None = None
    since_total = 0.0   # murders since the last total row
    subtotals = 0.0     # sum of group subtotals seen (to validate a grand total)
    orphans = 0.0       # units of groups that have no total row of their own

    for i in range(len(df)):
        row = df.iloc[i].tolist()
        texts = [text(v) for v in row]
        norms = [norm(t) for t in texts]
        nonempty = [t for t in texts if t]
        line = " ".join(nonempty)

        if "murder" in norms and any(n.startswith("district") for n in norms):
            cols = {"murder": norms.index("murder"),
                    "district": next(j for j, n in enumerate(norms) if n.startswith("district"))}
            if "year" in norms:
                cols["year"] = norms.index("year")
            if in_data and not pending and cur is not None:
                continue  # repeated header inside the same block (page break)
            title = " / ".join(pending[-3:])
            if year is None:
                year = sheet_year
            cur = {"province": province, "sheet": sheet, "header_row": i + 1,
                   "block_title": title, "year": year,
                   "period_hint": "periodic" if PERIODIC_RE.search(f"{title} {sheet}") else "unspecified",
                   "n_rows": 0, "n_groups": 0, "n_skipped_no_year": 0, "murders_sum": 0.0,
                   "n_nonnumeric": 0, "total_row_murders": None, "total_mismatches": []}
            blocks.append(cur)
            pending, group, since_total, subtotals, orphans = [], None, 0.0, 0.0, 0.0
            in_data = True
            continue

        # a title-like line inside a block ends it
        if in_data and nonempty and ("crime report" in line.lower()
                                     or (len(nonempty) == 1 and YEAR_RE.search(line))):
            in_data, year = False, None
        if not in_data:
            if line:
                pending.append(line)
                mm = YEAR_RE.search(line)
                if mm:
                    year = int(mm.group(1))
            continue
        if cols is None or cur is None or not nonempty:
            continue  # blank rows do NOT end a block

        raw = texts[cols["district"]]
        if not raw:
            continue  # column-number index rows ('2 3 4 ...') have no name
        row_year = year
        if "year" in cols and YEAR_RE.fullmatch(texts[cols["year"]] or ""):
            row_year = int(texts[cols["year"]])
        if YEAR_RE.fullmatch(raw):  # Islamabad quirk: name cell holds the year
            row_year, raw = int(raw), "Islamabad"
        name = re.sub(r"\s+", " ", raw).strip(" *:.-")
        others = [t for j, t in enumerate(texts) if j != cols["district"] and t]
        if not others:  # name only -> group header (police range / district heading)
            orphans += since_total  # previous group ended without a total row
            since_total = 0.0
            group = name
            cur["n_groups"] += 1
            continue
        murders = to_num(row[cols["murder"]])

        if is_total_name(name, province):
            ok = (murders != murders or abs(murders - since_total) < 1e-9
                  or abs(murders - subtotals) < 1e-9
                  or abs(murders - (subtotals + orphans)) < 1e-9
                  or abs(murders - (subtotals + orphans + since_total)) < 1e-9)
            if not ok:
                cur["total_mismatches"].append((group, murders, since_total))
            if murders == murders and abs(murders - since_total) < 1e-9 and group:
                subtotals += murders
            cur["total_row_murders"] = murders
            since_total = 0.0
            continue
        if row_year is None:
            cur["n_skipped_no_year"] += 1
            continue
        cur["year"] = cur["year"] or row_year
        cur["n_rows"] += 1
        if murders == murders:
            cur["murders_sum"] += murders
            since_total += murders
        else:
            cur["n_nonnumeric"] += 1
        recs.append({"province": province, "district_raw": name, "group": group or "",
                     "year": row_year, "murders": murders, "sheet": sheet,
                     "block_title": cur["block_title"], "period_hint": cur["period_hint"],
                     "block_row": cur["header_row"]})

    for b in blocks:
        if b["n_skipped_no_year"] and b["period_hint"] != "periodic":
            log.warning("[%s/%s] block at row %d: %d rows have no year and were skipped. Title lines above it: %r",
                        province, sheet, b["header_row"], b["n_skipped_no_year"], b["block_title"])
    return recs, blocks


def parse_crime_workbook(data: bytes, province: str) -> tuple[list[dict], list[dict]]:
    sheets = pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object)
    recs, blocks = [], []
    for sheet, df in sheets.items():
        r, b = parse_sheet(df, province, str(sheet))
        recs += r
        blocks += b
    if not recs:
        raise ValueError(f"{province}: no district rows parsed - layout changed?")
    return recs, blocks


# ------------------------------------------------------------ census parse
# One Table-1 row, e.g.
# ISLAMABAD DISTRICT 906 2,363,863 1,247,693 1,115,900 270 111.81 2,609.12 46.91 5.7 2,003,368 2.80
#  name | area | pop2023 | male | female | trans | sex ratio | density | urban% | hh | pop2017 | growth
# Districts created after 2017 may show '-' or 'N/A' for the 2017 columns.
N = r"\d[\d,]*"
V = r"(?:-?[\d,.]+|-|[A-Za-z/*]+)"
ROW_RE = re.compile(
    rf"^(?P<name>[^\d\s][^\d]*?)\s+(?P<area>{V})\s+(?P<pop23>{N})\s+"
    rf"(?P<male>{N}|-)\s+(?P<female>{N}|-)\s+(?P<trans>{N}|-)\s+{V}\s+{V}\s+"
    rf"{V}\s+{V}\s+(?P<pop17>{V})\s+{V}\s*\**$"
)


def pdf_lines(data: bytes) -> list[str]:
    import pdfplumber

    lines: list[str] = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            lines += [ln.strip() for ln in (page.extract_text() or "").splitlines() if ln.strip()]
    return lines


def excel_lines(data: bytes) -> list[str]:
    """Each spreadsheet row -> one text line, so Excel and PDF share one row parser."""
    lines: list[str] = []
    for df in pd.read_excel(io.BytesIO(data), sheet_name=None, header=None, dtype=object).values():
        for row in df.itertuples(index=False):
            parts = []
            for v in row:
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    continue
                if isinstance(v, float):
                    v = int(v) if v.is_integer() else round(v, 4)
                t = str(v).strip()
                if t:
                    parts.append(t)
            if parts:
                lines.append(" ".join(parts))
    return lines


def census_lines(data: bytes) -> list[str]:
    return pdf_lines(data) if data.startswith(b"%PDF") else excel_lines(data)


def load_census_province(label: str, urls: list[str], refresh: bool, expected: int | None = None) -> tuple[list[dict], str, str]:
    """Parse EVERY candidate file (Excel and PDF) and keep the one whose district sum is closest to the province total (or simply the
    largest if no total is known). -> (rows, url, retrieval date)."""
    errors, best = [], None
    for k, url in enumerate(urls):
        try:
            data, got = get_file(url, f"census_table1_{label}_{k}", CENSUS_MAGIC, reuse=not refresh)
            rows = census_districts(census_lines(data), label)
        except NeedManual:
            raise
        except Exception as exc:
            errors.append(f"{url}: {exc}")
            log.info("census %s: candidate skipped (%s)", label, errors[-1])
            continue
        tot = sum(r["pop_2023"] for r in rows)
        log.info("census %-12s candidate %s -> %d districts, %s", label, url.rsplit("/", 1)[-1], len(rows), f"{tot:,}")
        key = abs(tot - expected) if expected else -tot
        if best is None or key < best[0]:
            best = (key, rows, url, got)
        if expected and tot == expected:
            break  # district sum equals the official province total: no need to try others
    if best is None:
        raise RuntimeError(f"census {label}: no usable file. Tried:\n  " + "\n  ".join(errors))
    return best[1], best[2], best[3]


def _int(s: str) -> int:
    return 0 if s == "-" else int(s.replace(",", ""))


def parse_census_rows(lines: list[str], unparsed: list[str] | None = None) -> list[dict]:
    """All Table-1 rows (provinces, districts, tehsils...). Joins wrapped name lines.
    District-looking lines that fail to parse are appended to `unparsed` if given."""
    rows, prev, skip = [], "", False
    for k, ln in enumerate(lines):
        if skip:  # this line was already used as the tail of the previous row's name
            skip = False
            continue
        m = ROW_RE.match(ln) or (ROW_RE.match(prev + " " + ln) if prev else None)
        if m:
            d = m.groupdict()
            p17 = d["pop17"].replace(",", "")
            nm = re.sub(r"\s+", " ", d["name"]).strip()
            nxt = lines[k + 1] if k + 1 < len(lines) else ""
            if (not re.search(r"(DISTRICT|PROTECTED AREA|TEHSIL|TALUKA|TOWN)$", nm, re.I)
                    and re.fullmatch(r"[A-Za-z .'()/&\-]+", nxt)
                    and re.search(r"(DISTRICT|PROTECTED AREA)$", nxt.strip(), re.I)):
                nm, skip = f"{nm} {nxt.strip()}", True  # name wrapped onto the next line
            rows.append({"name": nm, "pop_2023": _int(d["pop23"]),
                         "pop_2017": int(p17) if p17.isdigit() else None,
                         "male": _int(d["male"]), "female": _int(d["female"]), "trans": _int(d["trans"])})
        elif unparsed is not None and re.search(r"\b(DISTRICT|PROTECTED AREA)\b", ln, re.I) and re.search(r"\d", ln):
            unparsed.append(ln)
        prev = ln if re.fullmatch(r"[A-Za-z .'()/&\-]+", ln) else ""
    return rows


def census_districts(lines: list[str], label: str) -> list[dict]:
    out, unparsed = [], []
    for r in parse_census_rows(lines, unparsed):
        up = r["name"].upper()
        if not (up.endswith(" DISTRICT") or up.endswith("PROTECTED AREA")):
            continue
        parts = r["male"] + r["female"] + r["trans"]
        if r["pop_2023"] and abs(parts - r["pop_2023"]) > 0.01 * r["pop_2023"]:
            log.warning("[census %s] %s: sex parts %d != total %d; row skipped", label, r["name"], parts, r["pop_2023"])
            continue
        name = re.sub(r"(?i)\s+district$", "", r["name"]).title()
        out.append({**r, "name": name})
    if unparsed:
        log.warning("[census %s] %d district-looking lines could NOT be parsed (population will be missing): %s", label, len(unparsed), unparsed[:6])
    if not out:
        raise ValueError(f"census {label}: no district rows parsed - layout changed?")
    return out


def national_totals() -> dict[str, int]:
    """Province totals from the national table, used to cross-check district sums."""
    for k, url in enumerate(CENSUS_NATIONAL):
        try:
            data, _ = get_file(url, f"census_table1_national_{k}", CENSUS_MAGIC, reuse=True)
            want = set(PROVINCE_ROW.values())
            found = {r["name"].upper(): r["pop_2023"] for r in parse_census_rows(census_lines(data)) if r["name"].upper() in want}
            if found:
                return found
        except NeedManual:
            raise
        except Exception as exc:
            log.info("National cross-check source failed (%s)", exc)
    log.info("National cross-check unavailable")
    return {}


# --------------------------------------------------------------- reference
KARACHI_BARE = {"keamari", "kemari", "korangi", "malir"}  # census names without 'Karachi' (Karachi's seven districts are one city)


def build_reference(census: list[dict]) -> pd.DataFrame:
    rows = []
    for c in census:
        key = f"{c['label']}-{slug(c['name'])}"
        city = "Karachi" if c["label"] == "Sindh" and (norm(c["name"]).startswith("karachi") or norm(c["name"]) in KARACHI_BARE) else ""
        rows.append({"label": c["label"], "district_key": key, "district": c["name"], "city": city,
                     "pop_2017": "" if c["pop_2017"] is None else str(c["pop_2017"]), "pop_2023": str(c["pop_2023"]),
                     "census_source_url": c["url"], "census_retrieved": c["retrieved"]})
    ref = pd.DataFrame(rows)
    dupes = ref[ref.duplicated("district_key", keep=False)]
    if len(dupes):
        sys.exit("[stop] duplicate district keys in the census parse:\n" + dupes[["district_key", "district"]].to_string())
    return ref


ABBR = {"n": "north", "s": "south", "e": "east", "w": "west", "l": "lower", "u": "upper",
        "dg": "dera ghazi", "di": "dera ismail", "cntr": "central", "cntrl": "central"}
# Abbreviated spellings and obvious misspellings seen in the PBS crime sheets -> name expected in the census.
# Applied only for matching; if the target is not in the census the normal matching runs. ("Tando Ahyar" is how the 2023 census spells Tando Allahyar.)
SEED_ALIASES = {
    "mbdin": ["Mandi Bahauddin"], "hyd": ["Hyderabad"], "hernai": ["Harnai"],
    "tayar": ["Tando Allahyar", "Tando Allah Yar", "Tando Ahyar"], "tmk": ["Tando Muhammad Khan"],
    "jshoro": ["Jamshoro"], "ttsingh": ["Toba Tek Singh"], "rykhan": ["Rahim Yar Khan"],
    "kamber": ["Qambar Shahdadkot", "Kambar Shahdadkot", "Qamber Shahdadkot"],
    "sba": ["Shaheed Benazirabad", "Benazirabad", "Nawabshah"],
    "nferoze": ["Naushahro Feroze", "Naushero Feroze", "Nowshero Feroze"],
    "chaghi": ["Chagai"], "noshki": ["Nushki"], "turbatkech": ["Kech", "Turbat"],
    "bunir": ["Buner"],
    "charsada": ["Charsadda"], "orkzai": ["Orakzai"], "battagram": ["Batagram"],
    "lakki": ["Lakki Marwat"], "nankana": ["Nankana Sahib"], "bhakar": ["Bhakkar"],
    "bahawanagar": ["Bahawalnagar"], "tharparkr": ["Tharparkar"],
}
# Districts created AFTER the 2023 census fieldwork: the census has no row for them, so their murders are added to the parent district whose
# census population still contains them. Administrative history typed in here, not read from a source: such rows are never tier A.
# Used only when a unit finds no census match by name.
MERGE_INTO = {
    "Balochistan": {"hub": "Lasbela", "ustamuhammad": "Jaffarabad"},
    "KP": {"swaziristanl": "South Waziristan", "swaziristanu": "South Waziristan"},
    "Punjab": {"wazirabad": "Gujranwala", "muree": "Rawalpindi", "murree": "Rawalpindi", "kotaddu": "Muzaffargarh"},
}
NON_TERRITORIAL_RE = re.compile(r"\b(ctd|crime\s*branch)\b", re.I)    # police units that are not territorial (no population)
GROUP_PREFIX = {"karachi": "Karachi"}                                  # crime-sheet groups whose units are bare names needing a city prefix


def tokens(s: object) -> list[str]:
    """Word tokens with abbreviations expanded ('N.Waziristan' -> north waziristan)."""
    t = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    t = re.sub(r"\bdistrict\b", " ", t)
    toks, out, i = re.findall(r"[a-z]+", t), [], 0
    while i < len(toks):
        if toks[i] == "d" and i + 1 < len(toks) and toks[i + 1] in ("i", "g"):
            out += ["dera", "ismail" if toks[i + 1] == "i" else "ghazi"]
            i += 2
            continue
        out += ABBR.get(toks[i], toks[i]).split()
        i += 1
    return out


def build_lookup(ref: pd.DataFrame) -> dict:
    lk: dict = {"plain": {}, "sorted": {}, "toks": {}}
    for idx, r in ref.iterrows():
        lab = r["label"]
        tk = tokens(r["district"])
        lk["plain"][(lab, norm_district(r["district"]))] = idx
        lk["sorted"][(lab, "".join(sorted(tk)))] = idx
        lk["toks"].setdefault(lab, []).append((set(tk), idx))
    return lk


def _lookup_name(lab: str, name: str, lk: dict) -> int | None:
    hit = lk["plain"].get((lab, norm_district(name)))
    if hit is None:
        hit = lk["sorted"].get((lab, "".join(sorted(tokens(name)))))
    return hit


def match_district(lab: str, raw: str, lk: dict) -> tuple[int | None, str]:
    """-> (row index in ref, kind). Order: alias -> exact -> word-order/abbreviation -> unique word subset -> fuzzy."""
    for cand in SEED_ALIASES.get(norm(raw), []):
        hit = _lookup_name(lab, cand, lk)
        if hit is not None:
            return hit, "alias"
    plain = norm_district(raw)
    if (lab, plain) in lk["plain"]:
        return lk["plain"][(lab, plain)], "exact"
    tk = tokens(raw)
    hit = lk["sorted"].get((lab, "".join(sorted(tk))))
    if hit is not None:
        return hit, "name"
    ts = set(tk)
    subs = {idx for tset, idx in lk["toks"].get(lab, []) if ts and ts <= tset}
    if len(subs) == 1:
        return next(iter(subs)), "partial"
    cands = [k[1] for k in lk["plain"] if k[0] == lab]
    close = difflib.get_close_matches(plain, cands, n=1, cutoff=FUZZY_CUTOFF)
    if close:
        return lk["plain"][(lab, close[0])], "fuzzy"
    return None, ""


def match_unit(lab: str, mname: str, raw: str, lk: dict) -> tuple[int | None, str]:
    """match_district plus: bare-name retry, then merge into the parent district."""
    idx, kind = match_district(lab, mname, lk)
    if idx is None and mname != raw:
        idx, kind = match_district(lab, raw, lk)
    if idx is None:
        parent = MERGE_INTO.get(lab, {}).get(norm(mname))
        if parent:
            idx, _ = match_district(lab, parent, lk)
            if idx is not None:
                kind = "merged_into_parent"
    return idx, kind


def pick_census(year: int) -> tuple[int, int]:
    """Closest census year (ties -> later census). Returns (census_year, gap)."""
    best = min(CENSUS_YEARS, key=lambda c: (abs(c - year), -c))
    return best, abs(best - year)


# ---------------------------------------------------------------- assembly
def build_units(all_recs, ref, lookup):
    """Crime unit rows matched to census districts. -> (DataFrame of unit rows, unmatched {(label, name): [(year, murders)]})."""
    rows, unmatched = [], {}
    for r in all_recs:
        lab = r["label"]
        gprefix = next((v for k, v in GROUP_PREFIX.items() if norm(r["group"]).startswith(k)), "")
        mname = (f"{gprefix} {r['district_raw']}" if gprefix and not norm(r["district_raw"]).startswith(norm(gprefix)) else r["district_raw"])
        idx, kind = match_unit(lab, mname, r["district_raw"], lookup)
        if idx is None:
            unmatched.setdefault((lab, mname), []).append((r["year"], r["murders"], r["group"]))
            continue
        rows.append({"label": lab, "district_key": ref.loc[idx, "district_key"], "year": r["year"], "murders": r["murders"],
                     "match_type": kind, "source_unit_name": r["district_raw"], "source_sheet": r["sheet"], "source_group": r["group"],
                     "block_key": (lab, r["sheet"], r["block_row"]), "block_title": r["block_title"], "source_url": r["source_url"],
                     "crime_retrieved": r["crime_retrieved"]})
    return pd.DataFrame(rows), unmatched


def final_rows(units: pd.DataFrame, ref: pd.DataFrame, block_ok: dict, census_ok: dict) -> list[dict]:
    ref = ref.copy()
    ref["city_name"] = ref["city"].where(ref["city"] != "", ref["district"])
    units = units.merge(ref[["district_key", "district", "city_name"]], on="district_key", how="left")
    out = []
    for (lab, cname, year), g in units.groupby(["label", "city_name", "year"], sort=True):
        members = ref[(ref["label"] == lab) & (ref["city_name"] == cname)]
        census_year, gap = pick_census(int(year))
        pops = members[f"pop_{census_year}"].map(to_num)
        if not pops.notna().all() or not len(pops):
            continue                                                            # a member district has no population for that census
        pop = int(round(pops.sum()))
        murders = g["murders"].sum(min_count=1)
        if murders != murders or pop < F.MIN_POP:
            continue
        murders = int(murders)
        province = PROVINCES[lab][0]
        multi = len(members) > 1
        kinds = set(g["match_type"])
        bks = [block_ok.get(k) for k in g["block_key"]]
        cok = census_ok.get(lab)
        weak = bool(kinds - CLEAN_MATCHES - {"merged_into_parent"})
        merged = "merged_into_parent" in kinds
        if any(b is False for b in bks) or weak:
            tier = "C"
        elif merged or any(b is None for b in bks) or cok is not True or gap > F.MAX_DENOMINATOR_AGE:
            tier = "B"
        else:
            tier = "A"
        checks = []
        checks.append("the unit rows of every crime block add up to the block's total rows" if all(b is True for b in bks)
                      else ("a crime block's total row DIFFERS from its unit rows" if any(b is False for b in bks) else "no total row in a crime block to reconcile against"))
        checks.append("the district populations of the province add up to the PBS national Table 1 province total" if cok is True
                      else ("the district populations of the province DIFFER from the PBS national Table 1 province total" if cok is False
                            else "the national Table 1 province total was not available for the census check"))
        checks.append("crime names matched to census names by " + ", ".join(sorted(kinds)))
        notes = []
        if multi:
            notes.append(f"sum of {len(members)} census districts ({' + '.join(members['district'])})")
        elif lab != "Islamabad":
            notes.append("the district stands in for its city (includes rural area)")
        if merged:
            notes.append("includes units created after the 2023 census, added to the parent district (MERGE_INTO: typed administrative history, not from a source)")
        if weak:
            notes.append("relies on a partial or fuzzy name match: unconfirmed")
        titles = sorted({str(t)[:110] for t in g["block_title"]})
        notes.append(f"treated as a full year because the block title names no month or quarter ({'; '.join(repr(t) for t in titles)}); the files do not state the period")
        notes.append("the files do not state whether the count is of cases or of victims; attempted murder is a separate column and is not included")
        isl = lab == "Islamabad"
        out.append({
            "country": "Pakistan", "unit": cname, "unit_local": "", "unit_code": "",
            "admin_level": "admin1" if isl else ("city" if multi else "admin2"),
            "unit_type": "federal_capital_territory" if isl else ("city" if multi else "district"),
            "parent_unit": "" if isl else province, "year": int(year), "homicide_cases": murders, "population": pop,
            "homicide_rate_per_100k": murders / pop * 1e5, "flag_low_count": murders < LOW_COUNT, "flag_outlier_year": False,
            "population_age_years": float(gap), "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "",
            "validation": "; ".join(checks),
            "indicator": "PBS / National Police Bureau 'Murder' column of the district-wise crime files (attempted murder excluded)",
            "population_method": f"PBS Population Census {census_year} district population (closest census to {int(year)}, {gap} years away), no growth projection",
            "data_notes": "; ".join(notes),
            "source_homicide": " ; ".join(sorted(set(g["source_url"]))),
            "source_population": " ; ".join(sorted(set(members["census_source_url"]))), "retrieved": min(min(g["crime_retrieved"]), min(members["census_retrieved"])),
            "is_city_proxy": bool(not multi and not isl), "population_census_year": census_year,
            "n_crime_units": int(g["source_unit_name"].nunique()), "crime_units": " | ".join(sorted(set(g["source_unit_name"])))})
    return out


# -------------------------------------------------------------------- main
def run(args) -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    manual: list[NeedManual] = []

    # ---- 1. crime files
    crime_links = discover_crime_links()
    all_recs, all_blocks = [], []
    for label, url in crime_links.items():
        try:
            data, got = get_file(url, f"crime_{label}", EXCEL_MAGIC, reuse=False)
        except NeedManual as e:
            manual.append(e)
            continue
        recs, blocks = parse_crime_workbook(data, label)
        for r in recs:
            r.update(label=label, source_url=url, crime_retrieved=got)
        log.info("crime  %-12s %4d rows in %d blocks / %d sheets, years %s-%s", label, len(recs), len(blocks),
                 len({b["sheet"] for b in blocks}), min(r["year"] for r in recs), max(r["year"] for r in recs))
        all_recs += recs
        all_blocks += blocks

    # ---- 2. census
    try:
        census_links = discover_census_links()
        nat = national_totals()
    except NeedManual as e:
        manual.append(e)
        census_links, nat = {k: list(v) for k, v in CENSUS_FALLBACK.items()}, {}
    census: list[dict] = []
    census_ok: dict[str, bool | None] = {}
    for label, urls in census_links.items():
        try:
            rows, url, got = load_census_province(label, urls, args.refresh_census, nat.get(PROVINCE_ROW[label]))
        except NeedManual:
            manual.append(NeedManual(f"census_table1_{label}_0", urls[0]))
            continue
        tot = sum(r["pop_2023"] for r in rows)
        exp = nat.get(PROVINCE_ROW[label])
        census_ok[label] = (tot == exp) if exp else None
        log.info("census %-12s %3d districts, 2023 pop %s%s", label, len(rows), f"{tot:,}", f" (province total {exp:,}; diff {tot - exp:+,})" if exp else "")
        for r in rows:
            r.update(label=label, url=url, retrieved=got)
        census += rows
    if manual:
        print(f"\n[manual download needed] the PBS site's robots.txt does not allow automated downloads of these files. A person may save them in a browser;"
              f"\nsave each under the name shown (.xlsx or .pdf) in {RAW}, then run the script again:")
        for e in manual:
            print(f"   {e.name}   <-   {e.url}")
        sys.exit("[stop] some PBS files could not be downloaded automatically")
    if not all_recs or not census:
        sys.exit("[stop] no crime or census data could be read")
    ref = build_reference(census)

    # ---- 3. exclusions, accounting, matching
    periodic = [r for r in all_recs if r["period_hint"] == "periodic"]
    if periodic and not args.include_periodic:
        log.warning("%d rows (%g murders) from month/quarter-labelled blocks were EXCLUDED; use --include-periodic to keep them",
                    len(periodic), sum(r["murders"] for r in periodic if r["murders"] == r["murders"]))
        all_recs = [r for r in all_recs if r["period_hint"] != "periodic"]
    block_ok: dict = {}
    for b in all_blocks:                                  # each total row must equal the units above it (or the subtotals)
        if b["period_hint"] == "periodic" and not args.include_periodic:
            continue
        block_ok[(b["province"], b["sheet"], b["header_row"])] = (None if b["total_row_murders"] is None else not b["total_mismatches"])
        for grp, tot, got in b["total_mismatches"]:
            log.warning("[%s/%s] block row %d (year %s), group %r: total row says %g, units above sum to %g",
                        b["province"], b["sheet"], b["header_row"], b["year"], grp, tot, got)
    print("\n[blocks] the crime blocks used for the rates (province / sheet, year, units, title as printed in the file):")
    for b in all_blocks:
        if b["period_hint"] != "periodic" or args.include_periodic:
            print(f"   {b['province']} / {b['sheet']}: {b['year']}, {b['n_rows']} units, total row "
                  f"{'none' if b['total_row_murders'] is None else format(b['total_row_murders'], 'g')}: {b['block_title'][:100]!r}")
    nonterr = [r for r in all_recs if NON_TERRITORIAL_RE.search(r["district_raw"])]
    if nonterr:
        log.warning("%d rows are non-territorial police units (e.g. %s): no population, left out (%g murders)", len(nonterr),
                    nonterr[0]["district_raw"], sum(r["murders"] for r in nonterr if r["murders"] == r["murders"]))
        all_recs = [r for r in all_recs if not NON_TERRITORIAL_RE.search(r["district_raw"])]
    lookup = build_lookup(ref)
    units, unmatched = build_units(all_recs, ref, lookup)
    if units.empty:
        sys.exit("[stop] no crime unit could be matched to a census district")
    dup = units.duplicated(["district_key", "year", "source_unit_name", "source_group", "source_sheet"], keep=False)
    if dup.any():
        sys.exit("[stop] the same unit is listed twice for a year (two annual blocks?):\n"
                 + units.loc[dup, ["source_unit_name", "year", "source_sheet", "murders"]].to_string())
    weak = units[~units["match_type"].isin(CLEAN_MATCHES | {"merged_into_parent"})]
    for _, r in weak.drop_duplicates("source_unit_name").iterrows():
        log.warning("%s match for '%s' -> %s: unconfirmed (tier C)", r["match_type"], r["source_unit_name"], r["district_key"])
    if unmatched:
        print("\n[unmatched] crime units with no census match are left out (label, name [police group]: years, murders -> closest census names):")
        for (lab, name), ys in sorted(unmatched.items()):
            names = {norm_district(x): x for x in ref[ref["label"] == lab]["district"]}
            close = [names[c] for c in difflib.get_close_matches(norm_district(name), list(names), n=3, cutoff=0.4)]
            print(f"   {lab}: {name} [{ys[0][2]}]: {sorted({y for y, _, _ in ys})}, {sum(m for _, m, _ in ys if m == m):g} murders -> {close or 'none close'}")
    total_in = sum(r["murders"] for r in all_recs if r["murders"] == r["murders"])

    rows = final_rows(units, ref, block_ok, census_ok)
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    kept = df["homicide_cases"].sum()
    print(f"\n[coverage] the output holds {int(kept):,} of the {int(total_in):,} murders in the territorial full-year units of the crime files "
          f"({kept / total_in:.1%}); the rest are the unmatched units above or units under {F.MIN_POP:,} residents")
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[pakistan] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "pakistan")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    last = df[df.year == df.year.max()].sort_values("homicide_rate_per_100k", ascending=False)
    print(f"\nHighest rates in {int(df.year.max())}:")
    print(last[["unit", "parent_unit", "homicide_cases", "population", "homicide_rate_per_100k", "reliability_tier"]].head(10).round(2).to_string(index=False))
    if args.cmd == "build":
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df.groupby(['parent_unit', 'unit']).ngroups} units, years {int(df.year.min())}-{int(df.year.max())})")
    else:
        print("\n[inspect only] no CSV written")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--refresh-census", action="store_true", help="download the census files again")
    ap.add_argument("--include-periodic", action="store_true", help="keep rows from blocks titled with a month/quarter (default: excluded)")
    sys.exit(run(ap.parse_args()))