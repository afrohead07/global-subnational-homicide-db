#!/usr/bin/env python3
"""
Kenya - the police 'Homicide' category per 100,000 residents, by COUNTY (47), calendar years of the National Police Service Annual Crime Reports on the NPS site (2021 confirmed; 2015-2020 are tried).  TIER C: A PROXY.

POLICE (numerator): National Police Service (NPS), "Annual Crime Report <year>": Appendix "Offences per County for the Year <year>": one row per county (and the Kenya Airports Police Unit and the Railways), one column per
            offence category (17 in 2015, 2017 and 2021; the number differs in some years) and a total. The column "Homicide" is found by its TOTAL: it is the one that equals the national "Homicide" figure of the report's comparative table. THAT CATEGORY IS BROADER THAN MURDER: in the same report's national table it is murder + manslaughter + infanticide + procuring abortion + concealing birth + suicide + causing
            death by dangerous driving (2021: 3,281, of which murder 2,018 = 61.5%, suicide 658, dangerous driving 389). No county table of murder alone is published, so the county figure is a PROXY and every row is tier C; the
            national composition of the year is written into the notes of every row. homicide_cases = the county value of the category (cases recorded by the police).
POPULATION: the report's own appendix "Crime Rate for the Year <year>" lists the population of every county used by the police: the 2009 census for the reports of 2015-2018 (Meru 1,356,301) and the 2019 census for those of
            2019 and later (identified by their totals, 38.6 and 47.6 million); the order of the columns (population then crimes, or crimes then population) is found by the police's own crime index.
CHECKS      (1) in every county row the categories add up to the row's total; (2) the counties and units add up to the TOTAL row; (3) the TOTAL of the first column equals the national "Homicide" figure of the report's
            comparative table; (4) the police's crime index (crimes per 100,000 in the population appendix) equals crimes / population within 1 point for every county; (5) the 47 populations add up to the report's total.

Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/Kenya/ ; the one output is kenya_homicide_rate.csv next to the script.
TLS         nationalpolice.go.ke presents a certificate the default store cannot verify: the operating-system certificate store is used (pip install truststore).
Commands:   python kenya_homicide_rate.py inspect | build          Options: --reuse (use the saved files)     (a report saved by hand as manual_report_<year>.pdf in the raw folder is read too)
Needs:      pip install pandas requests beautifulsoup4 pdfplumber truststore
"""
import argparse
import io
import re
import sys
from pathlib import Path
from urllib.parse import unquote, urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version (revision 14)")

REVISION = 9
P = F.paths(__file__, "Kenya")
RAW, OUT = P.raw, P.out
FETCH = [F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=2), F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=2, os_trust=True)]
REUSE = {"on": False}
REPORTS_PAGE = "https://nationalpolice.go.ke/reports-0"
KNBS_XLSX = "https://www.knbs.or.ke/wp-content/uploads/2025/02/Governance-Peace-and-Security.xlsx"      # Statistical Abstract, table 17.1: crimes reported to the police by year (national)
LOW_COUNT = F.LOW_COUNT
COUNTIES = ["Mombasa", "Kwale", "Kilifi", "Tana River", "Lamu", "Taita Taveta", "Garissa", "Wajir", "Mandera", "Marsabit", "Isiolo", "Meru", "Tharaka Nithi", "Embu", "Kitui", "Machakos", "Makueni", "Nyandarua", "Nyeri",
            "Kirinyaga", "Murang'a", "Kiambu", "Turkana", "West Pokot", "Samburu", "Trans Nzoia", "Uasin Gishu", "Elgeyo Marakwet", "Nandi", "Baringo", "Laikipia", "Nakuru", "Narok", "Kajiado", "Kericho", "Bomet",
            "Kakamega", "Vihiga", "Bungoma", "Busia", "Siaya", "Kisumu", "Homa Bay", "Migori", "Kisii", "Nyamira", "Nairobi"]          # the 47 counties: the names under which every report's spelling is filed
NON_COUNTY = {"kapu", "railways", "railway"}                     # the Kenya Airports Police Unit and the Railways: in the total, not counties
VARIANTS = {"garrissa": "garissa", "muranga": "muranga", "elgeyomarakwet": "elgeyomarakwet", "tharakanithi": "tharakanithi"}
CAT_ROW = re.compile(r"^\s*([A-Z][A-Z .'\u2019/\-]+?)\s+((?:\d+\s+){11,}\d+)\s*$")           # a name and 12 or more whole numbers: the categories and the total
NUMS_ONLY = re.compile(r"^\s*((?:\d+\s+){11,}\d+)\s*$")                                            # the figures alone (the name is on the line before)
POP_ROW = re.compile(r"^\s*\d{1,2}\s+([A-Z][A-Z .'\u2019/\-]+?)\s+([\d,]+)\s+([\d,]+)\s+(\d+)\s*$")        # number, county, two figures (population and crimes, in either order), index
NAT_HOM = re.compile(r"^\s*Homicide\s+(\d+)\s+(\d+)\s+(-?\d+)\s+(-?[\d.]+)\s+(\d+)\s+(\d+)\b")
SUBS = {"Murder": re.compile(r"a\)\s*Murder\s+\d+\s+\d+\s+-?\d+\s+-?[\d.]+\s+\d+\s+(\d+)", re.I), "Suicide": re.compile(r"f\)\s*Suicide\s+\d+\s+\d+\s+-?\d+\s+-?[\d.]+\s+\d+\s+(\d+)", re.I)}
CENSUS_2019, CENSUS_2009 = 47_564_296, 38_610_097                # the national totals of the two censuses: they identify which census a report's county populations are


def nm(x: str) -> str:
    n = re.sub(r"[^a-z]", "", str(x).lower())
    return VARIANTS.get(n, n)


DISPLAY = {"garissa": "Garissa", "muranga": "Murang'a", "elgeyomarakwet": "Elgeyo Marakwet", "tharakanithi": "Tharaka Nithi", "taitataveta": "Taita Taveta", "transnzoia": "Trans Nzoia", "homabay": "Homa Bay",
           "uasingishu": "Uasin Gishu", "westpokot": "West Pokot", "tanariver": "Tana River"}


def display(name: str) -> str:
    return DISPLAY.get(nm(name)) or " ".join(w.capitalize() for w in name.replace("\u2019", "'").split(" "))


def pdf_pages(data: bytes) -> list:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def get(url: str, name: str, suffix: str):
    last = None
    for f in FETCH:
        try:
            return f.get(url, name, reuse=REUSE["on"], suffix=suffix, reject_html=(suffix == ".pdf"))
        except F.RobotsDisallowed:
            raise
        except Exception as e:
            last = e
            if "SSL" not in str(e) and "certificate" not in str(e).lower():
                raise
    raise last


def find_reports() -> dict:
    from bs4 import BeautifulSoup
    out = {}
    try:
        html = get(REPORTS_PAGE, "ke_reports_page", ".html").decode("utf-8", "replace")
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            name = unquote(a["href"]).rsplit("/", 1)[-1]
            m = re.match(r"Annual Crime Report\s*-\s*(20\d\d)\.pdf$", name, re.I)
            if m:
                out[int(m.group(1))] = urljoin(REPORTS_PAGE, a["href"].strip())
    except Exception as e:
        print(f"[reports] the NPS reports page could not be read: {str(e)[:120]}")
    for p in sorted(RAW.glob("manual_report_*.pdf")):
        y = re.search(r"(20\d\d)", p.name)
        if y:
            out[int(y.group(1))] = str(p)
    return out


def report_pages(url: str, year: int) -> list:
    return pdf_pages(Path(url).read_bytes() if not url.startswith("http") else get(url, f"ke_report_{year}", ".pdf"))


WORD = re.compile(r"^[A-Z][A-Z'\u2019/\-]*(?: [A-Z][A-Z'\u2019/\-]*)?$")
POP_FIRST = re.compile(r"^\s*\d{1,2}\s+([A-Z][A-Z .'\u2019/\-]*?)\s*$")                       # "6 TAITA": a number and the first word of a wrapped name
POP_SECOND = re.compile(r"^\s*([A-Z][A-Z .'\u2019/\-]*?)\s+([\d,]+)\s+([\d,]+)\s+(\d+)\s*$")  # "TAVETA 340,671 1,000 293": the second word with the figures


def orient(a: int, b: int, idx: int):
    """(population, crimes) from two figures in either order: the orientation for which the police's index = crimes / population x 100,000 within 1 point; None if neither fits."""
    for pop, cr in ((a, b), (b, a)):
        if pop >= 20_000 and abs(cr / pop * 1e5 - idx) <= 1.0:
            return pop, cr
    return None


def table_lines(pages: list):
    """Both county tables, line by line, with the names that the PDF wraps over two lines put back together: a line that is only a word (offences table) or a number and a word (population table) followed by the line
    that holds the figures; and the figures on a line of their own after a line that is only the county name. Returns ([(name, numbers, page, raw)], [(name, population, crimes, index)], rows that could not be oriented)."""
    cats, pops, bad = [], [], []
    for k, t in enumerate(pages):
        L = [x.strip() for x in t.splitlines()]
        for i, ln in enumerate(L):
            m = CAT_ROW.match(ln)
            if m:
                name = m.group(1).strip()
                if i > 0 and WORD.match(L[i - 1]) and len(L[i - 1]) <= 14 and not CAT_ROW.match(L[i - 1]) and nm(name) not in ("total",):
                    name = L[i - 1] + " " + name
                cats.append((name, [int(x) for x in m.group(2).split()], k + 1, ln))
                continue
            m = NUMS_ONLY.match(ln)
            if m and i > 0 and WORD.match(L[i - 1]):                                   # the name alone on the line before the figures
                cats.append((L[i - 1], [int(x) for x in m.group(1).split()], k + 1, ln))
                continue
            m = POP_ROW.match(ln)
            if m:
                o = orient(int(m.group(2).replace(",", "")), int(m.group(3).replace(",", "")), int(m.group(4)))
                (pops if o else bad).append((m.group(1).strip(), o[0], o[1], int(m.group(4))) if o else (m.group(1).strip(), ln))
                continue
            m = POP_SECOND.match(ln)
            if m and i > 0 and POP_FIRST.match(L[i - 1]):
                o = orient(int(m.group(2).replace(",", "")), int(m.group(3).replace(",", "")), int(m.group(4)))
                if o:
                    pops.append((POP_FIRST.match(L[i - 1]).group(1).strip() + " " + m.group(1).strip(), o[0], o[1], int(m.group(4))))
    return cats, pops, bad


def knbs_national() -> dict:
    """{year: national 'Homicide' cases} from the KNBS Statistical Abstract table 17.1 (an independent official source for the check of every county table), or {} if it cannot be read."""
    try:
        data = get(KNBS_XLSX, "ke_knbs_17_1", ".xlsx")
        xl = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        sh = next((n for n in xl.sheet_names if "17.1" in n), xl.sheet_names[0])
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        hdr = next(i for i in range(min(8, len(raw))) if sum(1 for v in raw.iloc[i] if re.fullmatch(r"20\d\d", str(v).strip().split(".")[0])) >= 5)
        row = next(i for i in range(hdr + 1, len(raw)) if str(raw.iat[i, 0]).strip().lower().startswith("homicide"))
        out = {}
        for j in range(raw.shape[1]):
            y = str(raw.iat[hdr, j]).strip().split(".")[0]
            v = str(raw.iat[row, j]).strip()
            if re.fullmatch(r"20\d\d", y) and re.fullmatch(r"\d+(\.0)?", v):
                out[int(y)] = int(float(v))
        return out
    except Exception as e:
        print(f"[knbs] the national Homicide series of the KNBS abstract could not be read ({str(e)[:90]}); the comparative table of each report is used instead")
        return {}


def edits(a: str, b: str) -> int:
    """The number of edits (insertion, deletion, substitution, swap of two neighbouring letters) between two words."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] != b[j - 1]))
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def is_unit(key: str) -> bool:
    """The Kenya Airports Police Unit and the Railways (written RAILWAYS, RAILWAY or, in one report, RAILAYS) are in the total, not counties."""
    return key in NON_COUNTY or edits(key, "railways") <= 2


def expected_census(year: int) -> int:
    """The census whose county populations the police used in the report of this year: the 2009 census up to the report of 2018, the 2019 census from the report of 2019 (checked on the reports of 2015, 2016, 2018,
    2019 and 2021, whose populations add up to the totals of those censuses)."""
    return 2019 if year >= 2019 else 2009


def link_counties(units: dict, pop: dict):
    """-> ({offences key: population key}, [unmatched county names]): exact keys first; then abbreviations written with a slash or a dash (T/NZOIA = Trans Nzoia); then a name that is the start or end of another (the
    first word was lost); then a close spelling (the report writes NYAMARIA for Nyamira); every population row is used at most once and every match must be unique."""
    link, used = {}, set()

    def free(cands):
        return [c for c in cands if c not in used]
    for k in units:
        if k in pop:
            link[k] = k
            used.add(k)
    for k, v in units.items():
        if k in link:
            continue
        parts = [x for x in re.split(r"[/ \-]+", v[0].lower()) if x]
        cand = []
        if len(parts) >= 2:
            for pk in free(pop):
                pw = [x for x in re.split(r"[/ \-]+", pop[pk][0].lower()) if x]
                if len(pw) == len(parts) and all(w.startswith(a) for a, w in zip(parts, pw)):
                    cand.append(pk)
        if len(cand) == 1:
            link[k] = cand[0]
            used.add(cand[0])
    for k in units:
        if k in link:
            continue
        cand = [pk for pk in free(pop) if len(k) >= 4 and len(pk) >= 4 and (pk.endswith(k) or pk.startswith(k) or k.endswith(pk) or k.startswith(pk))]
        if len(cand) == 1:
            link[k] = cand[0]
            used.add(cand[0])
    for k in units:
        if k in link:
            continue

        def subseq(a, b):
            it = iter(b)
            return all(ch in it for ch in a)
        cand = [pk for pk in free(pop) if len(k) >= 5 and pk[0] == k[0] and subseq(k, pk) and pk.endswith(k[-3:])]
        if len(cand) == 1:
            link[k] = cand[0]
            used.add(cand[0])
    for k in units:
        if k in link:
            continue
        cand = [pk for pk in free(pop) if len(k) >= 6 and pk[0] == k[0] and edits(k, pk) <= 2]
        if len(cand) == 1:
            link[k] = cand[0]
            used.add(cand[0])
    return link, [units[k][0] for k in units if k not in link]


def diagnostic(pages: list, year: int, words):
    print(f"   [diagnostic] {year}: raw lines that start with " + ", ".join(words) + " (the first 3 of each), to see how the table is written:")
    for w in words:
        hit = [(k + 1, ln.strip()) for k, t in enumerate(pages) for ln in t.splitlines() if re.match(rf"^\s*(?:\d{{1,2}}\s+)?{w}\b", ln)]
        for k, ln in hit[:3]:
            print(f"      p{k}: {ln[:170]}")


def parse_report(pages: list, year: int, nat_ref=None, borrow=None):
    """-> (rows, notes, others, composition text, population total, census, population table). The county table is the one table (number of columns) and the one column whose county rows add up to the national Homicide
    figure of the year (the KNBS figure, else the report's own comparative table); pop_ext is a population table borrowed from another report when this one has none."""
    catl, popl, badpop = table_lines(pages)
    by_n = {}
    for name, nums, pg, raw in catl:
        by_n.setdefault(len(nums), {}).setdefault(nm(name), (name, nums, pg))
    pop = {}
    for name, p, crime, idx in popl:
        pop.setdefault(nm(name), (name, p, crime, idx))
    notes = []
    own = len(pop)
    filled = []
    if own < 47 and borrow:
        btable, byear, bcensus = borrow
        if own < 30:
            pop = dict(btable)
            filled = ["all"]
            notes.append(f"the report has no population appendix: the county populations of the report of {byear} (same police, same {bcensus} census base as this report) are used")
        else:
            for k, v in btable.items():
                if k not in pop and all(edits(k, q) > 2 for q in pop):
                    pop[k] = v
                    filled.append(v[0])
            if filled:
                notes.append(f"the population appendix of the report lists {own} counties: {', '.join(filled)} taken from the report of {byear} (same police, same {bcensus} census base)")
    if len(pop) < 45:
        diagnostic(pages, year, ["1 MERU", "MERU", "47"])
        sys.exit(f"[stop] {year}: the population appendix 'Crime Rate' (rows of a number, a county, a population and the crimes in either order, the index) was not found ({own} counties; {len(badpop)} rows did not fit crimes / population = index) and no report of the same census base could fill it")
    nat_pdf, comp = None, {}
    for t in pages:
        for ln in t.splitlines():
            m = NAT_HOM.match(ln)
            if m and nat_pdf is None:
                nat_pdf = int(m.group(6))
        for key, rx in SUBS.items():
            m = rx.search(t)
            if m and key not in comp:
                comp[key] = int(m.group(1))
    ref = nat_ref if nat_ref is not None else nat_pdf
    src = "the KNBS Statistical Abstract (table 17.1)" if nat_ref is not None else "the report's comparative table"
    cands, why = [], []
    for n, d in sorted(by_n.items(), key=lambda kv: -len(kv[1])):
        cs = {k: v for k, v in d.items() if k != "total"}
        if len(cs) < 45:
            continue
        bad_rows = [(v[0], sum(v[1][:-1]), v[1][-1]) for v in cs.values() if sum(v[1][:-1]) != v[1][-1]]
        if bad_rows:
            why.append(f"{n} numbers per row: {len(bad_rows)} row(s) whose categories do not add up to the total, e.g. {bad_rows[0]}")
            continue
        for j in range(n - 1):
            sj = sum(v[1][j] for v in cs.values())
            if (ref is not None and sj == ref) or (ref is None and j == 0):
                cands.append((n, j, cs, d.get("total"), sj))
    if len(cands) != 1:
        diagnostic(pages, year, ["MOMBASA", "NAIROBI", "TOTAL"])
        sys.exit(f"[stop] {year}: {len(cands)} county table(s) have a column whose rows add up to the national Homicide figure {ref} ({src}) (a single one is needed); tables with 45 or more rows: {sorted((n, len(d)) for n, d in by_n.items() if len(d) >= 45)}; {why[:2]}")
    n, j, cs, total, sj = cands[0]
    if ref is None:
        notes.append("no national Homicide figure was found: the first column of the county table is assumed to be Homicide")
    else:
        notes.append(f"the Homicide column is column {j + 1} of {n - 1}: its county rows add up to {sj}, the national 'Homicide' figure of {src} ({ref})")
    if total is not None and total[1][j] != sj:
        notes.append(f"the report's own TOTAL row says {total[1][j]}, which is not the sum of its rows ({sj}): the sum is the figure that equals the national one")
    units = {k: v for k, v in cs.items() if not is_unit(k)}
    others = {v[0]: v[1][j] for k, v in cs.items() if is_unit(k)}
    link, miss = link_counties(units, pop)
    if miss or len(set(link.values())) != len(link):
        diagnostic(pages, year, ["\\d{1,2} TAITA", "TAITA", "NAIROBI", "NYAMIRA", "\\d{1,2} NYAMIRA"])
        sys.exit(f"[stop] {year}: counties of the offences table without a (single) population in the 'Crime Rate' appendix: {miss or 'two counties matched the same population row'}; the appendix has {len(pop)} counties; rows that did not fit: {[b[0] for b in badpop][:6]}")
    spelled = [(units[k][0], pop[link[k]][0]) for k in units if k != link[k]]
    if spelled:
        notes.append(f"{len(spelled)} county name(s) are written differently in the two tables and were matched: " + "; ".join(f"{a} = {b}" for a, b in spelled[:8]))
    canon = {nm(c): (c,) for c in COUNTIES}
    clink, cmiss = link_counties(units, canon)
    if cmiss or len(set(clink.values())) != len(clink) or len(clink) != len(COUNTIES):
        sys.exit(f"[stop] {year}: the counties of the offences table do not map one-to-one onto the 47 counties: unmatched {cmiss}, matched {len(clink)} of {len(COUNTIES)}")
    rows, same = {}, 0
    for k, (name, nums, pg) in units.items():
        pname, p, crime, idx = pop[link[k]]
        same += int(crime == nums[-1])
        rows[canon[clink[k]][0]] = (nums[j], nums[-1], p, idx, name)
    ptot = sum(pop[link[k]][1] for k in units)
    census = 2019 if abs(ptot - CENSUS_2019) / CENSUS_2019 <= 0.005 else 2009 if abs(ptot - CENSUS_2009) / CENSUS_2009 <= 0.005 else None
    if census is None and filled:
        census = expected_census(year)
    notes.append("the police crime index equals crimes / population within 1 point in every county of the report's own appendix; the crimes of that appendix equal the row totals of the offences table in " + (f"{same} of {len(units)} counties" if not filled else "the counties it lists"))
    notes.append(f"the county populations add up to {ptot:,}: " + (f"the {census} census total" if census and not filled else (f"the {census} census (taken from the report of the same census base)" if census else "neither the 2009 nor the 2019 census total (the base is not identified)")))
    comp_txt = (f"nationally the category is {sj:,} cases, of which murder {comp['Murder']:,} ({comp['Murder'] / sj:.1%})" + (f" and suicide {comp['Suicide']:,}" if "Suicide" in comp else "")) if "Murder" in comp else "the national composition of the category was not found"
    return rows, notes, others, comp_txt, ptot, census, pop, len(units)


def read_all(reps: dict):
    """-> {year: (rows, notes, others, comp, ptot, census)} for every report that can be read. The population tables of all reports are read first; a report whose own table is missing or lacks counties is completed from
    the table of the NEAREST report of the SAME census base (2009 or 2019), never from another base."""
    nat = knbs_national()
    print(f"[knbs] national Homicide by year (Statistical Abstract table 17.1): {dict(sorted(nat.items())) if nat else 'not available'}")
    pages, pop_tables = {}, {}
    for y in sorted(reps):
        try:
            pages[y] = report_pages(reps[y], y)
        except Exception as e:
            print(f"[{y}] the report could not be read: {str(e)[:100]}")
            continue
        _, popl, _ = table_lines(pages[y])
        pop = {}
        for name, p, crime, idx in popl:
            pop.setdefault(nm(name), (name, p, crime, idx))
        ptot = sum(v[1] for v in pop.values())
        census = 2019 if abs(ptot - CENSUS_2019) / CENSUS_2019 <= 0.005 else 2009 if abs(ptot - CENSUS_2009) / CENSUS_2009 <= 0.005 else None
        if len(pop) >= 45 and census:
            pop_tables[y] = (pop, census)
    ok = {}
    for y in sorted(pages):
        ec = expected_census(y)
        srcs = [z for z, (t, c) in pop_tables.items() if c == ec and z != y]
        borrow = None
        if srcs:
            z = min(srcs, key=lambda q: (abs(q - y), q))
            borrow = (pop_tables[z][0], z, ec)
        try:
            ok[y] = parse_report(pages[y], y, nat.get(y), borrow)[:6]
        except (SystemExit, Exception) as e:
            print(f"[{y}] skipped: {str(e)[:330]}")
    return ok


def cmd_inspect():
    print(f"[kenya_homicide_rate.py revision {REVISION}]")
    reps = find_reports()
    print(f"[reports] Annual Crime Reports found: {sorted(reps)}")
    for y, (rows, notes, others, comp, ptot, census) in sorted(read_all(reps).items()):
        print(f"[{y}] {len(rows)} counties; homicide category {sum(v[0] for v in rows.values()):,}; units {others}; population {ptot:,}; {comp}")
        for n in notes:
            print("   " + n)


def cmd_build():
    print(f"[kenya_homicide_rate.py revision {REVISION}]")
    reps = find_reports()
    if not reps:
        sys.exit("[stop] no Annual Crime Report was found on the NPS reports page (save one by hand as manual_report_<year>.pdf in the raw folder)")
    rows = []
    for y, (data, notes, others, comp, ptot, census) in sorted(read_all(reps).items()):
        age = max(0.0, round(y + 0.5 - {2019: 2019.65, 2009: 2009.65}[census], 1)) if census else None
        print(f"[{y}] {len(data)} counties; homicide category {sum(v[0] for v in data.values()):,}; population {ptot:,}; {comp}")
        for n in notes:
            print("   " + n)
        for county, (h, tot, p, idx, local) in data.items():
            rows.append({"country": "Kenya", "unit": county, "unit_local": local, "population_census": census, "unit_code": "", "admin_level": "admin1", "unit_type": "county", "parent_unit": "", "year": y, "homicide_cases": int(h), "population": int(p),
                         "homicide_rate_per_100k": h / p * 1e5, "flag_low_count": h < LOW_COUNT, "flag_outlier_year": False, "population_age_years": age, "indicator_type": "police_recorded_cases", "reliability_tier": "C",
                         "definition_flags": "includes_manslaughter",
                         "validation": "; ".join(notes + ["TIER C, A PROXY: the police category 'Homicide' includes suicide and causing death by dangerous driving; " + comp]),
                         "indicator": "police-recorded 'Homicide' category (murder, manslaughter, infanticide, procuring abortion, concealing birth, suicide, causing death by dangerous driving), cases, by county",
                         "population_method": "the police's own county population of the report's appendix 'Crime Rate' " + (f"({census} census)" if census else "(census base not identified)"),
                         "data_notes": f"calendar year {y}; {comp}; the Kenya Airports Police Unit and the Railways ({', '.join(f'{a} {b}' for a, b in others.items())}) are in the national total only",
                         "source_homicide": reps[y], "source_population": reps[y] + " (appendix 'Crime Rate for the Year', table of county populations)" if reps[y].startswith("http") else "manual report, appendix table of county populations",
                         "retrieved": "", "category_total_crimes": int(tot)})
    if not rows:
        sys.exit("[stop] no report could be read")
    df = pd.DataFrame(rows)
    got = {u: d for f in FETCH for u, d in getattr(f, "retrieved", {}).items() if u in reps.values() or u == REPORTS_PAGE}
    df["retrieved"] = min(got.values()) if got else __import__("datetime").date.today().isoformat()
    df = df.sort_values(["unit", "year"]).reset_index(drop=True)
    prev_p, prev_y, prev_c = df.groupby("unit")["population"].shift(), df.groupby("unit")["year"].shift(), df.groupby("unit")["population_census"].shift()
    ann = (df["population"] / prev_p) ** (1 / (df["year"] - prev_y)) - 1
    df["population_change_pct"] = (ann * 100).round(2)
    df["flag_population_break"] = ((ann.abs() > 0.03) | (prev_c.notna() & (prev_c != df["population_census"]))).fillna(False).astype(bool)
    df["population_census"] = df["population_census"].astype("Int64").astype(object).where(df["population_census"].notna(), "")
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "kenya")
    print(f"[breaks] rows whose population moves more than 3% a year from the previous report or changes census base: {int(df['flag_population_break'].sum())} (the 2009 to 2019 census change between the reports of 2017 and 2021 accounts for them)")
    last = int(df.year.max())
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()} (all proxies); years {sorted(df.year.unique())}")
    print(f"\nLatest year {last}, the ten highest rates of the 'Homicide' category:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].head(10).round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} counties, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()