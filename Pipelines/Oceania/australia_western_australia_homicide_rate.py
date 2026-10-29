#!/usr/bin/env python3
"""
Australia, Western Australia - homicide per 100,000 residents by Police District, financial years (Districts of 100,000 or more residents).

POLICE (numerator): WA Police Force "Crime time series data" workbook (the `Data` sheet: one row per area, offence and month, January 2007 onwards, 15 Police Districts, two regions and the state): the
            offences recorded by WA Police, always the latest revision. Cases = Murder + Manslaughter of the 12 months of the financial year (July to June); "Attempted / Conspiracy to Murder"
            and "Driving Causing Death" are kept apart as extra columns. The unit is the recorded offence.
POPULATION: the WA Police publish no population, but their monthly crime statistics REPORTS (PDF, one per financial year) print every offence count AND its rate per 100,000 people for the state, the two
            regions and each district. A district's population is derived from the report's own figures: offences / rate x 100,000 on every line whose rate is 25 or more per 100,000 (the reports print rates with one decimal, so such a line is accurate to 0.2%), taking the median
            (the spread of the lines is checked). The rate of the file is OUR count / that population; the published rate of the Murder and Manslaughter lines is kept as a check (they publish one decimal).
            The date of the population is not stated in the reports: it is MEASURED against the ABS June estimates for WA (the closest year within 2%) and population_age_years is its age; if none matches, 0.5.
REPORTS     The current report is linked on the WA Government crime statistics page; the earlier reports are probed at the address pattern seen in WA's own file paths (the monthly upload folders
            2024-07 to 2026-09); a report that cannot be found is left out (no row for that year, no interpolation). A report saved by hand as manual_wa_report_<2023-24>.pdf is used too.
YEAR        `year` is the START year of the financial year (2025 = July 2025 to June 2026) and `financial_year` gives the label, as in the United Kingdom script.
CHECKS      (1) the population implied by the lines of a district agrees (10th to 90th percentile within 1%; the whole range when there are fewer than ten lines); (2) the published Murder + Manslaughter rate agrees with the report's count and our population
            within rounding; (3) the 15 districts add up to the state, and the first eight districts of the contents add up to the Metropolitan Region and the rest to Regional WA (this also assigns each
            district its region, from the data); (4) the state population matches, within 2%, the ABS estimate for Western Australia (the sum of its LGAs at 30 June) of one of the six years around the financial year: that year dates the
            police denominator and gives its age (at most the project limit of 3.5 years); a state population matching no ABS estimate is tier B; (5) the count of
            the workbook (latest) agrees with the count printed in the report within max(10%, 1). Tier A: all five hold; B: any fails. Never tier C.
SERIES      WA Police changed their recording and reporting practices between May and November 2017: the reports used here are later, so the series break does not enter, but it is noted.

Folders:    this script sits in <repo>/Pipelines/Oceania/ ; downloads go to <repo>/Data/Raw/Oceania/Australia Western Australia/ ; the one output is australia_western_australia_homicide_rate.csv next to it.
Commands:   python australia_western_australia_homicide_rate.py inspect | pdf | build          Option: --reuse (use the files saved by an earlier run)
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine pdfplumber
"""
import argparse
import importlib.util
import io
import json
import re
import statistics
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import unquote, urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))             # abs_lga_population.py sits next to this script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 13:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

from abs_lga_population import load_abs_population as _load_abs_population          # shared with the other Australian pipelines
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "Australia Western Australia")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
PAGE = "https://www.wa.gov.au/organisation/western-australia-police-force/crime-statistics"
HOMICIDE = re.compile(r"homicide|murder|manslaughter", re.I)
ENGINE = "calamine" if importlib.util.find_spec("python_calamine") else "openpyxl"


def open_excel(data: bytes, suffix: str = ".xlsx") -> pd.ExcelFile:
    """Open a workbook ONCE: from the bytes with the fast reader, else from a saved copy with its real extension, else with the slower tolerant reader."""
    last = None
    for how in ("bytes", "path", "openpyxl"):
        try:
            if how == "bytes":
                return pd.ExcelFile(io.BytesIO(data), engine=ENGINE)
            if how == "path":
                tmp = RAW / ("_open" + suffix)
                tmp.write_bytes(data)
                return pd.ExcelFile(tmp, engine=ENGINE)
            return pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        except Exception as e:
            last = e
    raise last


def show(data: bytes, max_sheets: int = 0):
    """The workbook is a long table ('Data': area, offence, month, count). Prints its structure, the full texts of the notes sheets and a scan for population or rate columns."""
    t0 = time.time()
    xl = open_excel(data)
    print(f"   opened in {time.time() - t0:.0f} s; {len(xl.sheet_names)} sheets: {xl.sheet_names}", flush=True)
    for sh in ("Contents", "Explanatory Notes", "Glossary"):                  # every non-empty text, in full: the population behind the police rates may be named here
        if sh not in xl.sheet_names:
            continue
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        print(f"   --- sheet '{sh}' ({raw.shape}), every non-empty text:")
        for i in range(len(raw)):
            txt = " | ".join(str(x).strip().replace("\n", " / ") for x in raw.iloc[i] if not pd.isna(x))
            if txt:
                print(f"      row {i:2d}: {txt[:600]}")
    data_sheet = pd.read_excel(xl, sheet_name="Data", dtype=object) if "Data" in xl.sheet_names else None
    if data_sheet is not None:
        c = list(data_sheet.columns)
        print(f"   --- sheet 'Data': {data_sheet.shape}; columns {[(i, str(x)[:30]) for i, x in enumerate(c)]}")
        hom = data_sheet[data_sheet.iloc[:, 4].astype(str).str.contains("Homicide", case=False, na=False)]
        per = pd.to_datetime(hom.iloc[:, 5], errors="coerce")
        print(f"      homicide rows {len(hom):,}; months {per.min():%Y-%m} to {per.max():%Y-%m} ({per.nunique()} distinct); areas {hom.iloc[:, 0].nunique()}; offences {sorted(map(str, hom.iloc[:, 2].unique()))}")
        cnt = pd.to_numeric(hom.iloc[:, 9], errors="coerce")
        print(f"      counts: {int(cnt.isna().sum())} not numeric; min {cnt.min():g}, max {cnt.max():g}; duplicate (area, offence, month) rows: {int(hom.duplicated([c[0], c[2], c[5]]).sum())}")
        tab = hom.assign(_y=per.dt.year, _c=cnt).query("_y in [2023, 2024, 2025]").groupby([c[0], "_y"])["_c"].sum().unstack().loc[lambda t: t.index.str.contains("WESTERN AUSTRALIA|REGION", case=False)]
        print("      statewide and regional yearly sums of ALL homicide offences incl. attempts and driving (2023-2025):")
        print(tab.to_string())
    print("   --- scan of every sheet for population or rate columns (first 12 rows):")
    for sh in xl.sheet_names:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object, nrows=12)
        cells = [str(x) for x in raw.to_numpy().ravel() if not pd.isna(x)]
        hit = sorted({x[:70] for x in cells if re.search(r"population|per 100|rate|estimated resident|ERP", x, re.I)})
        if hit:
            print(f"      '{sh}': {hit[:6]}")
    for sh in [x for x in xl.sheet_names if x.startswith("Cannington")][:1]:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        print(f"   --- sheet '{sh}' {raw.shape}: the two header rows in full:")
        for i in (6, 7):
            print("      " + " | ".join(str(x)[:26] for x in raw.iloc[i] if not pd.isna(x)))
        print("      last rows:")
        print(raw.iloc[-3:, :8].to_string(max_colwidth=22, header=False))


def find_links():
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(PAGE, "wa_page_crime_statistics", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    except F.RobotsDisallowed:
        print(f"   [robots] {PAGE} does not allow automated reading")
        return []
    except Exception as e:
        print(f"   [skip] {PAGE}: {str(e)[:100]}")
        return []
    return [(a.get_text(" ", strip=True), urljoin(PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)
            if re.search(r"\.(xlsx?|pdf)(?:[?#]|$)|/download", a["href"], re.I)]


def cmd_inspect():
    links = find_links()
    print(f"[files] {len(links)} download links on {PAGE}:")
    for t, u in links:
        print(f"   {t[:60]:60} {unquote(u)[:120]}")
    cand = [(t, u) for t, u in links if re.search(r"time series", t + " " + unquote(u), re.I)]
    if not cand:
        print("   no link mentions 'time series': save the 'crime time series data' workbook by hand as manual_wa_time_series.xlsx in " + str(RAW))
    for t, u in cand[:1]:
        print(f"\n===== {t[:80]} =====", flush=True)
        try:
            t0 = time.time()
            data = FETCH.get(u, "wa_crime_time_series", reuse=REUSE["on"], suffix=".xlsx")
            print(f"   downloaded {len(data) / 1e6:.1f} MB in {time.time() - t0:.0f} s", flush=True)
            show(data)
        except F.RobotsDisallowed:
            print("   [robots] not allowed automatically: save it by hand as manual_wa_time_series.xlsx in " + str(RAW))
        except Exception as e:
            print(f"   [skip] {str(e)[:120]}")
    for p in sorted(RAW.glob("manual_wa*")):
        print(f"\n===== manual file {p.name} =====")
        show(p.read_bytes())
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


ARCHIVE = "https://www.wa.gov.au/system/files/2024-08/crime-statistics-{fy}.pdf"       # the addresses seen in WA's own file paths (the 2020-21 and 2021-22 reports); the other years are probed
FYS = ["2017-18", "2018-19", "2019-20", "2020-21", "2021-22", "2022-23", "2023-24", "2024-25"]
PDF_LINE = re.compile(r"population|per 100,?000|rate|cannington|homicide|murder|manslaughter", re.I)


def pdf_pages(data: bytes) -> list:
    """Text of every page: pdfplumber if installed, else pypdf."""
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        try:
            from pypdf import PdfReader
            return [(pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages]
        except ImportError:
            sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def describe_pdf(data: bytes, label: str, show_pages=(1, 2, 3, 10, 11), lines_per_page=40):
    """The structure of a monthly crime statistics report: which pages hold counts and which hold rates, and the text of the pages that matter for the parser."""
    pages = pdf_pages(data)
    print(f"   {label}: {len(pages)} pages; characters per page (first 12): {[len(t) for t in pages[:12]]}")
    for k in show_pages:
        if k - 1 < len(pages):
            print(f"   --- page {k}, the first {lines_per_page} lines:")
            for ln in pages[k - 1].splitlines()[:lines_per_page]:
                print("      " + ln[:160])
    ttl = [(k + 1, next((ln.strip() for ln in t.splitlines() if re.search(r"district|region|western australia", ln, re.I) and not re.search(r"page \d", ln, re.I)), "")) for k, t in enumerate(pages[:40])]
    print("   area named on each page (the first line that names one): " + "; ".join(f"p{k}: {a[:34]}" for k, a in ttl[1:14]))


def probe_missing(fys=("2023-24", "2024-25")) -> dict:
    """The reports of 2023-24 and 2024-25 are not at the 2024-08 address: the same file name is probed in the monthly upload folders from 2024-07 to 2026-09."""
    found = {}
    folders = [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if "2024-07" <= f"{y}-{m:02d}" <= "2026-09"]
    for fy in fys:
        for fo in folders:
            u = f"https://www.wa.gov.au/system/files/{fo}/crime-statistics-{fy}.pdf"
            try:
                found[fy] = (u, FETCH.get(u, f"wa_annual_report_{fy}", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
                print(f"   {fy}: found in folder {fo} ({len(found[fy][1]) / 1e6:.1f} MB)")
                break
            except F.RobotsDisallowed:
                print(f"   {fy}: robots.txt does not allow {fo}")
                break
            except Exception:
                continue
        else:
            print(f"   {fy}: not found in any folder from {folders[0]} to {folders[-1]}")
    return found


def cmd_pdf():
    links = find_links()
    pdfs = [(t, u) for t, u in links if re.search(r"annual|pdf", t, re.I) and not re.search(r"time series", t, re.I)]
    print(f"[pdf] {len(pdfs)} PDF link(s) on the page")
    for t, u in pdfs[:1]:
        print(f"\n===== {t[:80]} =====", flush=True)
        try:
            data = FETCH.get(u, "wa_annual_report_current", reuse=REUSE["on"], suffix=".pdf", reject_html=True)
            print(f"   downloaded {len(data) / 1e6:.1f} MB")
            describe_pdf(data, "current annual report")
        except Exception as e:
            print(f"   [skip] {str(e)[:140]}")
    print("\n[archive] the annual reports of earlier years, probed at the address pattern seen in WA's own file paths:")
    got = {}
    for fy in FYS:
        u = ARCHIVE.format(fy=fy)
        try:
            got[fy] = FETCH.get(u, f"wa_annual_report_{fy}", reuse=REUSE["on"], suffix=".pdf", reject_html=True)
            print(f"   {fy}: exists ({len(got[fy]) / 1e6:.1f} MB)")
        except F.RobotsDisallowed:
            print(f"   {fy}: robots.txt does not allow it")
        except Exception as e:
            print(f"   {fy}: {str(e)[:70]}")
    print("\n[archive] the two years missing at that address, probed in the monthly upload folders:")
    got.update({fy: b for fy, (u, b) in probe_missing().items()})
    if got:
        fy = sorted(got)[0]
        print(f"\n===== archive report {fy} (the oldest that exists), to see whether the layout changed between years =====")
        describe_pdf(got[fy], f"report {fy}", show_pages=(2, 11), lines_per_page=22)
    print(f"\n[summary] reports found: current + {sorted(got)}")
    print("\n[pdf only] nothing written; paste this output and the denominator parser will be written against it")


LOW_COUNT = F.LOW_COUNT
ABS_POP_PAGE = "https://www.abs.gov.au/statistics/people/population/regional-population/latest-release"
TS_LINK = re.compile(r"time series", re.I)
STATE_AREA, METRO_AREA, REGIONAL_AREA = "WESTERN AUSTRALIA", "METROPOLITAN REGION", "REGIONAL WA REGION"
MIN_LINE_RATE = 25.0            # DECISION: a line whose rate is 25 or more per 100,000 gives a population to within 0.2% (the reports print rates with one decimal), whatever its count
SPREAD_TOL = 0.01               # DECISION: the 10th to 90th percentile of the implied populations of a district within 1% of the median
SUM_TOL = 0.01                  # DECISION: the districts add up to the state / the regions within 1%
ABS_TOL = 0.02                  # DECISION: the state population is within 2% of the ABS estimate
REV_REL, REV_ABS = 0.10, 1      # DECISION: the workbook count (latest) and the report count agree within max(10%, 1)
RATE_ABS, RATE_REL = 0.06, 0.01  # DECISION: the published rate (one decimal) agrees within rounding
AREA_RE = re.compile(r"^(WESTERN AUSTRALIA|METROPOLITAN REGION|REGIONAL WA REGION|[A-Z][A-Z\- ]+ DISTRICT)$")
NUM_RE = re.compile(r"^(?:-|\d[\d,]*(?:\.\d+)?%?)$")


def parse_line(line: str):
    """-> (label, [value tokens]); a text artefact of some reports ('1 ,715') is repaired first."""
    toks = re.sub(r"(\d)\s*,\s*(?=\d{3}\b)", r"\1,", line.strip()).split()
    k = len(toks)
    while k > 0 and NUM_RE.match(toks[k - 1]):
        k -= 1
    return " ".join(toks[:k]), toks[k:]


def num(t: str) -> float:
    return 0.0 if t == "-" else float(t.replace(",", "").rstrip("%"))


def _group_value(g: list):
    """The number made by joining consecutive digit pieces ('3', '06' -> 306); a dash stands alone for 0; None if the group cannot be a number."""
    if g == ["-"]:
        return 0
    if any(x == "-" for x in g):
        return None
    t = "".join(g)
    if not t.isdigit() or (len(t) > 1 and t[0] == "0") or len(t) > 6:
        return None
    return int(t)


def regroup_digits(tokens: list, n: int = 13, max_group: int = 4, max_total_group: int = 6, state_cap: int = 400_000):
    """Some pages of the reports have their numbers split into pieces by the PDF text layer ('3 3 2 4 ... 3 06' for 33, 24, ..., 306). A count line is n-1 monthly values plus a total that equals their
    sum. The total is read first (1 to 4 pieces at the end, so every partial sum is bounded by it); the months are then read by a forward search over (piece, number, running sum). The reading is
    returned if EXACTLY ONE makes the months add up to the total; 'ambiguous' if several do; 'complex' if the search exceeds its cap (the line is skipped, never guessed); None if none does."""
    toks = [t.replace(",", "") for t in tokens]
    N = len(toks)
    found = []
    work = 0
    for Lt in range(1, max_total_group + 1):                # the total may have up to six pieces (a 6-digit total), a month up to four
        if N - Lt < n - 1:
            break
        total = _group_value(toks[N - Lt:])
        if total is None:
            continue
        months, M = toks[:N - Lt], N - Lt
        layers = [{0: {0: 1}}]                                   # layers[k][i][s] = number of ways (capped at 2) to read the first i pieces as k numbers adding up to s
        for k in range(n - 1):
            nxt = {}
            for i, sums in layers[k].items():
                for L in range(1, max_group + 1):
                    j = i + L
                    if j > M - (n - 2 - k):
                        break
                    v = _group_value(months[i:j])
                    if v is None:
                        continue
                    d = nxt.setdefault(j, {})
                    for sm, w in sums.items():
                        s2 = sm + v
                        if s2 <= total:
                            d[s2] = min(2, d.get(s2, 0) + w)
                    work += len(sums)
                    if work > state_cap:
                        return "complex"
            layers.append(nxt)
        w = layers[n - 1].get(M, {}).get(total, 0)
        if w == 0:
            continue
        if w > 1:
            return "ambiguous"
        vals, i, sm = [], M, total                                   # walk back through the layers: the reading is unique, so any predecessor that is reachable belongs to it
        for k in range(n - 1, 0, -1):
            step = None
            for L in range(1, max_group + 1):
                i0 = i - L
                if i0 < 0:
                    break
                v = _group_value(months[i0:i])
                if v is not None and layers[k - 1].get(i0, {}).get(sm - v, 0) > 0:
                    step = (i0, v)
                    break
            vals.append(float(step[1]))
            i, sm = step[0], sm - step[1]
        found.append(vals[::-1] + [float(total)])
    if not found:
        return None
    return found[0] if len(found) == 1 else "ambiguous"


def parse_report(pages: list) -> dict:
    """-> {(area, 'count'|'rate'): {'fy': start year, 'rows': [(label, [12 monthly values], total or rate)]}} for every table page of a monthly crime statistics report."""
    out = {}
    for t in pages:
        lines = [ln for ln in t.splitlines()]
        area = next((ln.strip() for ln in lines if AREA_RE.match(ln.strip())), None)
        hdr = next((ln for ln in lines if ln.strip().startswith("OFFENCE CATEGORY")), None)
        if not area or not hdr:
            continue
        kind = "rate" if re.search(r"Rate per 100,?000", t) and not re.search(r"Sanction", t) else "count"
        months = re.findall(r"([A-Z][a-z]{2}) (\d{2})\b", hdr)
        if len(months) != 12:
            sys.exit(f"[stop] the table of {area} ({kind}) does not name 12 months in its header: {hdr[:100]}")
        fy = 2000 + int(months[0][1]) if months[0][0] == "Jul" else None
        if fy is None:
            sys.exit(f"[stop] the table of {area} does not start in July (first month {months[0]}): not a financial-year report")
        rows, dropped, broken = [], [], []
        for ln in lines[lines.index(hdr) + 1:]:
            label, vals = parse_line(ln)
            if not label or not vals:
                continue
            if kind == "count":
                v13 = vals[:13] if len(vals) == 14 else (vals if len(vals) == 13 and not vals[-1].endswith("%") else None)
                nums = None
                if v13 is not None:
                    nums = [num(v) for v in v13]
                    if abs(sum(nums[:12]) - nums[12]) > 0.5:
                        nums = None
                if nums is None:                                     # not 13 cells that add up: the digit pieces are kept and regrouped later, only if the line is needed
                    broken.append((label, vals[:-1] if vals[-1].endswith("%") else vals))
                else:
                    rows.append((label, nums[:12], nums[12]))
                continue
            if vals and vals[-1].endswith("%"):
                dropped.append((ln.strip(), "a rates line ending in a percentage"))
                continue
            if len(vals) != 13:
                dropped.append((ln.strip(), f"{len(vals)} numeric cells instead of 13"))
                continue
            nums = [num(v) for v in vals]
            rows.append((label, nums[:12], nums[12]))
        if not rows and not broken:
            sys.exit(f"[stop] no offence lines were read from the table of {area} ({kind})")
        out[(area, kind)] = {"fy": fy, "rows": rows, "dropped": dropped, "broken": broken}
    return out


_NOTED: set = set()
MAX_POPS = 14                   # DECISION: 14 good lines per area are enough for the median; the others are not read
MAX_REPAIRS = 24                # DECISION: at most 24 digit-split lines are regrouped per area


def implied_population(rep: dict, area: str):
    """-> (median population, 10th-90th percentile spread, number of lines, published murder rate, published manslaughter rate, report counts of murder and manslaughter).
    Lines that read directly are used first; digit-split lines are regrouped lazily, cheapest first, only as many as are needed."""
    c, r = rep.get((area, "count")), rep.get((area, "rate"))
    if not c or not r:
        sys.exit(f"[stop] {area}: the counts page or the rates page is missing from the report")
    direct, broken, rated = {}, {}, {}
    for x in c["rows"]:
        direct.setdefault(x[0], []).append(x)
    for lab, pcs in c["broken"]:
        broken.setdefault(lab, []).append(pcs)
    for x in r["rows"]:
        rated.setdefault(x[0], []).append(x)
    mine = set(direct) | set(broken)
    only_c, only_r = sorted(mine - set(rated)), sorted(set(rated) - mine)
    if (only_c or only_r) and area not in _NOTED:
        _NOTED.add(area)
        print(f"   [pages] {area}: {len(only_c)} line(s) only on the counts page {only_c[:5]}, {len(only_r)} only on the rates page {only_r[:5]}; the population uses the labels that occur once on both pages")
    cand = []
    for lab in mine & set(rated):
        if len(direct.get(lab, [])) + len(broken.get(lab, [])) != 1 or len(rated[lab]) != 1:
            continue
        tr = rated[lab][0][2]
        if tr < MIN_LINE_RATE:
            continue
        if lab in direct:
            cand.append((0, lab, direct[lab][0][2], tr))
        else:
            cand.append((len(broken[lab][0]), lab, broken[lab][0], tr))
    cand.sort(key=lambda x: (x[0], x[1]))
    pops, repaired, skipped = [], 0, {"ambiguous": 0, "complex": 0, "none": 0}
    for cost, lab, val, tr in cand:
        if len(pops) >= MAX_POPS:
            break
        if cost == 0:
            pops.append(val / tr * 1e5)
            continue
        if repaired >= MAX_REPAIRS:
            continue
        rd = regroup_digits(val)
        if isinstance(rd, list):
            pops.append(rd[12] / tr * 1e5)
            repaired += 1
        else:
            skipped["none" if rd is None else rd] += 1
    if repaired or any(skipped.values()):
        print(f"   [repair] {area}: {repaired} digit-split line(s) regrouped (each with exactly one reading that makes the months add up to the total); skipped: {skipped}")
    if len(pops) < 5:
        for nm, pg in (("counts", c), ("rates", r)):
            print(f"   [diagnostic] {area}, {nm} page: {len(pg['rows'])} lines read directly, {len(pg.get('broken', []))} digit-split, {len(pg['dropped'])} dropped; the first digit-split / dropped lines:")
            for lab, pcs in (pg.get("broken", []))[:4]:
                print(f"      (digit-split) {lab} {' '.join(pcs)[:140]}")
            for ln, why in pg["dropped"][:4]:
                print(f"      ({why}) {ln[:140]}")
        sys.exit(f"[stop] {area}: only {len(pops)} lines with a rate of {MIN_LINE_RATE:g}+ per 100,000 usable on both pages, too few to derive a population")
    if len(pops) >= 10:
        q = statistics.quantiles(pops, n=10)
        lo, hi = q[0], q[8]                                  # the 10th and the 90th percentile
    else:
        lo, hi = min(pops), max(pops)                        # too few lines for percentiles: the whole range
    med = statistics.median(pops)

    def total_of(name):
        if name in direct:
            return direct[name][0][2]
        if name in broken and len(broken[name]) == 1:
            rd = regroup_digits(broken[name][0])
            return rd[12] if isinstance(rd, list) else None
        return 0.0
    cm, cs = total_of("Murder"), total_of("Manslaughter")
    rate_of = lambda name: rated[name][0][2] if name in rated else 0.0
    return med, (hi - lo) / med, len(pops), rate_of("Murder"), rate_of("Manslaughter"), (None if cm is None or cs is None else cm + cs)


def find_reports():
    """-> ({financial-year start: [page texts]}, {financial-year start: address}) from the current report, the archive and manual files."""
    out, found = {}, {}
    mp = RAW / "reports_map.json"
    known = json.loads(mp.read_text()) if (REUSE["on"] and mp.exists()) else {}
    for t, u in find_links():
        if re.search(r"annual|year to date", t, re.I) and not TS_LINK.search(t):
            try:
                pages = pdf_pages(FETCH.get(u, "wa_annual_report_current", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
                fy = parse_report(pages)
                if fy:
                    y = next(iter(fy.values()))["fy"]
                    out[y] = pages
                    found[f"{y}-{str(y + 1)[2:]}"] = u
            except F.RobotsDisallowed:
                print("   [robots] the current report does not allow automated downloads")
    folders = ["2024-08"] + [f"{y}-{m:02d}" for y in (2024, 2025, 2026) for m in range(1, 13) if "2024-07" <= f"{y}-{m:02d}" <= "2026-09" and f"{y}-{m:02d}" != "2024-08"]
    for y in range(2017, 2026):
        fy = f"{y}-{str(y + 1)[2:]}"
        if y in out:
            continue
        man = RAW / f"manual_wa_report_{fy}.pdf"
        if man.exists():
            out[y] = pdf_pages(man.read_bytes())
            found[fy] = str(man)
            continue
        if fy in known and known[fy] is None:
            continue
        cand = [known[fy]] if known.get(fy) else [f"https://www.wa.gov.au/system/files/{fo}/crime-statistics-{fy}.pdf" for fo in folders]
        for u in cand:
            try:
                out[y] = pdf_pages(FETCH.get(u, f"wa_annual_report_{fy}", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
                found[fy] = u
                break
            except F.RobotsDisallowed:
                break
            except Exception:
                time.sleep(0.15)
                continue
        else:
            found[fy] = None
    mp.write_text(json.dumps({**known, **found}, indent=1))
    return out, {int(k[:4]): v for k, v in found.items() if v}


def workbook_counts(data: bytes):
    """-> {(AREA, fy start): {'murder','manslaughter','attempted','driving'}} for the complete financial years of the `Data` sheet (the latest revision of every month)."""
    xl = open_excel(data)
    df = pd.read_excel(xl, sheet_name="Data", dtype=object)
    c = list(df.columns)
    h = df[df.iloc[:, 4].astype(str).str.contains("Homicide", case=False, na=False)].copy()
    per = pd.to_datetime(h.iloc[:, 5], errors="coerce")
    if per.isna().any():
        sys.exit(f"[stop] {int(per.isna().sum())} month(s) of the Data sheet are not dates")
    h["_n"] = pd.to_numeric(h.iloc[:, 9], errors="coerce")
    if h["_n"].isna().any():
        sys.exit("[stop] a count of the Data sheet is not a number")
    h["_fy"] = per.dt.year.where(per.dt.month >= 7, per.dt.year - 1)
    h["_m"] = per.dt.to_period("M")
    lab = h.iloc[:, 2].astype(str).str.strip().str.lower()
    key = lab.map(lambda x: "murder" if x == "murder" else "manslaughter" if x == "manslaughter" else "attempted" if x.startswith("attempted") else "driving" if x.startswith("driving") else None)
    h["_k"] = key
    out, cal = {}, {}
    h["_cy"] = per.dt.year
    h["_area"] = h.iloc[:, 0].astype(str).str.strip().str.upper()
    for (area, fy), g in h.groupby(["_area", "_fy"]):
        if g["_m"].nunique() == 12:
            out[(area, int(fy))] = {k: float(g.loc[g["_k"] == k, "_n"].sum()) for k in ("murder", "manslaughter", "attempted", "driving")}
    for cy, g in h[h["_area"] == STATE_AREA].groupby("_cy"):
        if g["_m"].nunique() == 12:
            cal[int(cy)] = float(g.loc[g["_k"].isin(["murder", "manslaughter"]), "_n"].sum())
    return out, c, cal


def cmd_build():
    from bs4 import BeautifulSoup
    links = find_links()
    ts = next(((t, u) for t, u in links if TS_LINK.search(t + " " + unquote(u))), None)
    man = sorted(RAW.glob("manual_wa_time_series*.xlsx"))
    if man:
        counts, cols, cal = workbook_counts(man[0].read_bytes())
    elif ts:
        counts, cols, cal = workbook_counts(FETCH.get(ts[1], "wa_crime_time_series", reuse=REUSE["on"], suffix=".xlsx"))
    else:
        sys.exit("[stop] no link to the crime time series workbook was found on the WA page (save it by hand as manual_wa_time_series.xlsx)")
    print(f"[workbook] murder, manslaughter, attempts and driving causing death for {len({a for a, _ in counts})} areas, complete financial years {min(y for _, y in counts)}-{max(y for _, y in counts)}")
    reports, report_urls = find_reports()
    print(f"[reports] monthly crime statistics reports available for the financial years {sorted(f'{y}-{str(y + 1)[2:]}' for y in reports)}")
    if not reports:
        sys.exit("[stop] no monthly crime statistics report could be read")
    html = FETCH.get(ABS_POP_PAGE, "abs_page_regional_population", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    alinks = [(a.get_text(" ", strip=True), urljoin(ABS_POP_PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.xlsx?(?:[?#]|$)", a["href"], re.I)]
    erp, lgas, _ = _load_abs_population(alinks, lambda u, n: FETCH.get(u, n, reuse=REUSE["on"], suffix=".xlsx"), open_excel)
    wa_erp = {}
    for (code, y), v in erp.items():
        if lgas.get(code, ("", None))[1] == "Western Australia":
            wa_erp[y] = wa_erp.get(y, 0.0) + v
    abs_state, pth = {}, OUT.parent / "australia_homicide_rate.csv"
    if pth.exists():
        d0 = pd.read_csv(pth, dtype=str, keep_default_na=False)
        abs_state = {int(r.year): float(r.homicide_cases) for r in d0[d0["unit"] == "Western Australia"].itertuples()}
        ratio = {y: cal[y] / abs_state[y] for y in cal if abs_state.get(y)}
        if ratio:
            print(f"[cross-verification] WA Police murder + manslaughter offences (state line, calendar years) / ABS victims for Western Australia: median {statistics.median(ratio.values()):.2f} over {len(ratio)} years "
                  f"(range {min(ratio.values()):.2f}-{max(ratio.values()):.2f}); informative: offences and victims are different units")
    else:
        print(f"[abs state] {pth.name} is not next to this script: the offences-against-victims comparison is skipped")
    rows = []
    for fy in sorted(reports):
        label = f"{fy}-{str(fy + 1)[2:]}"
        rep = parse_report(reports[fy])
        _NOTED.clear()
        areas = sorted({a for a, _ in rep})
        districts = [a for a in dict.fromkeys(a for a, _ in rep) if a.endswith(" DISTRICT")]
        if len(districts) != 15 or STATE_AREA not in areas or METRO_AREA not in areas or REGIONAL_AREA not in areas:
            sys.exit(f"[stop] report {label}: {len(districts)} districts and areas {areas[:4]}...: expected the state, two regions and 15 districts")
        pops = {a: implied_population(rep, a) for a in areas}
        st = pops[STATE_AREA][0]
        dsum = sum(pops[d][0] for d in districts)
        metro = districts[:8]
        msum, rsum = sum(pops[d][0] for d in metro), sum(pops[d][0] for d in districts[8:])
        sum_ok = abs(dsum - st) / st <= SUM_TOL
        group_ok = abs(msum - pops[METRO_AREA][0]) / pops[METRO_AREA][0] <= SUM_TOL and abs(rsum - pops[REGIONAL_AREA][0]) / pops[REGIONAL_AREA][0] <= SUM_TOL
        cand = [(abs(st - wa_erp[y]) / wa_erp[y], y) for y in range(fy - 4, fy + 2) if wa_erp.get(y)]
        err, ymatch = min(cand) if cand else (None, None)
        age = None if ymatch is None else fy - ymatch + 0.5            # the financial year's mid-point is 1 January of fy + 1; an ABS estimate is dated 30 June of its year
        abs_ok = None if err is None else bool(err <= ABS_TOL and age <= F.MAX_DENOMINATOR_AGE)
        pop_age = age if abs_ok else 0.5
        print(f"[{label}] state population implied {st:,.0f}; the 15 districts add up to {dsum:,.0f} ({(dsum - st) / st:+.2%}); first 8 districts {msum:,.0f} vs Metropolitan Region {pops[METRO_AREA][0]:,.0f}, "
              f"the rest {rsum:,.0f} vs Regional WA {pops[REGIONAL_AREA][0]:,.0f}; "
              + ("no ABS estimate for WA to compare with" if err is None else f"closest ABS estimate for WA: June {ymatch} ({wa_erp[ymatch]:,.0f}), {err:.2%} away, so the police population is about {age:.1f} years old"
                 + ("" if abs_ok else " (outside the tolerance)")))
        for d in districts:
            pop, spread, nl, pub_mu, pub_ma, rep_cnt = pops[d]
            wb = counts.get((d, fy))
            if wb is None or pop < F.MIN_POP:
                continue
            cases = int(wb["murder"] + wb["manslaughter"])
            rate_pub = pub_mu + pub_ma
            rate_pdf = None if rep_cnt is None else rep_cnt / pop * 1e5
            pub_ok = None if rate_pdf is None else abs(rate_pdf - rate_pub) <= 2 * RATE_ABS + RATE_REL * rate_pub
            rev_ok = None if rep_cnt is None else abs(cases - rep_cnt) <= max(REV_REL * rep_cnt, REV_ABS)
            spread_ok = spread <= SPREAD_TOL
            parent = "Metropolitan Region" if (group_ok and d in metro) else "Regional WA Region" if group_ok else "Western Australia"
            why = [t for t, bad in ((f"the lines imply populations spread by {spread:.2%}", not spread_ok), ("the published Murder + Manslaughter rate does not agree with the report's count" if pub_ok is False else "the report's Murder / Manslaughter counts could not be read", pub_ok is not True),
                                    (f"the workbook count ({cases}) differs from the report's ({rep_cnt:g})" if rev_ok is False else "the workbook count was not compared with the report's", rev_ok is not True),
                                    ("the districts do not add up to the state or the regions", not (sum_ok and group_ok)),
                                    ("the state population does not match an ABS estimate" if abs_ok is False else "no ABS estimate to compare with", abs_ok is not True)) if bad]
            tier = "A" if not why else "B"
            checks = [f"the population implied by {nl} report lines agrees within {spread:.2%} (10th-90th percentile)" if spread_ok else f"the lines imply populations that spread by {spread:.2%}: beyond 1%",
                      (f"the published Murder + Manslaughter rate ({rate_pub:.1f}) {'agrees' if pub_ok else 'DISAGREES'} with the report's {rep_cnt:g} offences over this population ({rate_pdf:.2f})" if rep_cnt is not None else "the report's Murder and Manslaughter counts could not be read, so the published rate was not checked"),
                      ((f"the workbook count ({cases}) agrees with the report's ({rep_cnt:g})" if rev_ok else f"the workbook count ({cases}) differs from the report's ({rep_cnt:g}): a revision") if rep_cnt is not None else "the workbook count was not compared with the report's"),
                      ("the 15 districts add up to the state and the regions" if (sum_ok and group_ok) else "the districts do NOT add up to the state or the regions within 1%"),
                      (f"the state population matches the ABS estimate of June {ymatch} within {err:.2%}: the police denominator is an ABS estimate about {age:.1f} years old" if abs_ok else f"the state population is {err:.2%} from the closest ABS estimate (June {ymatch}), beyond 2% or older than {F.MAX_DENOMINATOR_AGE} years" if abs_ok is False else "no ABS estimate for WA to compare with")]
            rows.append({"country": "Australia", "unit": d.title().replace("-Esperance", "-Esperance"), "unit_local": d, "unit_code": "", "admin_level": "police_unit", "unit_type": "Police District", "parent_unit": parent,
                         "year": fy, "homicide_cases": cases, "population": int(round(pop)), "homicide_rate_per_100k": cases / int(round(pop)) * 1e5, "flag_low_count": cases < LOW_COUNT,
                         "flag_outlier_year": False, "population_age_years": pop_age, "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "includes_manslaughter",
                         "validation": "; ".join(checks),
                         "indicator": "WA Police recorded offences: Murder + Manslaughter (Attempted / Conspiracy to Murder and Driving Causing Death excluded)",
                         "population_method": f"implied by the WA Police's own published rates (offences / rate x 100,000, median of {nl} lines of the {label} monthly crime statistics report); its date is not stated and is measured against the ABS June estimates for Western Australia",
                         "data_notes": f"financial year {label} (July {fy} to June {fy + 1}), year = start year; the unit is the recorded offence; counts are the latest revision of the time series workbook; WA Police changed recording and "
                                       "reporting practices between May and November 2017 (before this series); offences that cannot be mapped to a district appear only in the state total",
                         "source_homicide": ts[1] if ts else "manual_wa_time_series.xlsx", "source_population": report_urls.get(fy) or str(RAW / f"manual_wa_report_{label}.pdf"), "retrieved": FETCH.retrieved_on(ts[1] if ts else PAGE),
                         "tier_reason": "; ".join(why), "financial_year": label, "murder_offences": int(wb["murder"]), "manslaughter_offences": int(wb["manslaughter"]), "attempted_conspiracy_murder_offences": int(wb["attempted"]),
                         "driving_causing_death_offences": int(wb["driving"]), "report_murder_manslaughter": rep_cnt if rep_cnt is not None else float("nan"), "published_murder_manslaughter_rate": round(rate_pub, 2),
                         "population_spread_pct": round(spread * 100, 3)})
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    print(f"[scope] {df['unit'].nunique()} Police Districts with 100,000+ residents in at least one financial year; financial years {sorted(df['financial_year'].unique())}")
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "australia")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    nb = df[df.reliability_tier != "A"]
    if len(nb):
        print("[tier B] rows that are not tier A, and why:")
        print(nb[["unit", "financial_year", "homicide_cases", "tier_reason"]].to_string(index=False, max_colwidth=110))
    last = int(df.year.max())
    print(f"\nLatest financial year {last}-{str(last + 1)[2:]}:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "parent_unit", "homicide_cases", "population", "homicide_rate_per_100k", "reliability_tier"]].round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} districts, financial years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "pdf", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    {"inspect": cmd_inspect, "pdf": cmd_pdf, "build": cmd_build}[a.cmd]()