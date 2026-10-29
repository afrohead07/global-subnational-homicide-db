#!/usr/bin/env python3
"""
South Africa - murder per 100,000 residents by PROVINCE, financial years (April to March). The police-district layer follows (it needs Census 2022 populations).

POLICE (numerator): South African Police Service (SAPS), "Police Recorded Crime Statistics": the annual workbooks (sheet `RAW Data`: one row per unit and crime category, ten financial years per workbook,
            levels Station, District, Province and National in the same sheet) and, for the newest financial year, the four quarterly workbooks. Category "Murder" (code 1: murder, farm murder and
            police murder, aggregated as 'all murder'). SAPS counts BODIES: if four people are killed in one incident four murders are recorded, so the unit is the VICTIM of murder.
            Each unit's own name is in the `Station` column, its parent and grandparent in the two columns after it.
POPULATION: Stats SA "Mid-year population estimates" (P0302), the EDITION OF THE YEAR in which the financial year starts (June estimate of that year, age 0.3 years): each edition gives only its own year's
            provincial totals, so the series is made of editions of different vintages and breaks where Stats SA rebased (the first Census 2022 edition); year-to-year provincial jumps above 3% are flagged
            (flag_population_break). A financial year whose edition cannot be found gets no row (a manual_mype_<year>.pdf saved by hand is used). SAPS itself uses the "2021 series" for its ratios: its
            province populations of the newest quarter are printed in the SAPS release and kept as an informative check (population_saps_2021_series).
CHECKS      (1) in every financial year the stations add up to their province and the provinces to the national row of the file; (2) the nine provincial populations add up to the national total of the
            edition within 0.5%; (3) the newest financial year assembled from four quarterly workbooks must have all four quarters; (4) the same financial year in two workbooks must agree (revisions are
            reported, the newest workbook wins). Tier A would need an independent confirmation: the Stats SA mortality report (assault deaths by province) covers only about a third of the police count, so
            it cannot confirm, and every row is tier B with that said in the notes.

TLS         www.saps.gov.za presents an incomplete certificate chain: the downloader tries (1) normal verification, (2) verification against the operating-system certificate store (needs pip install
            truststore) and (3) only with --insecure, verification OFF (a warning is printed; public statistics, no credentials are sent).
BOT PAGES   The Stats SA publication pages answer scripts with a 212-byte bot-protection stub: the publications (PDF) are read at their direct addresses.

Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/South Africa/ ; the one output is south_africa_homicide_rate.csv next to the script.
Commands:   python south_africa_homicide_rate.py inspect | build          Options: --reuse (use the saved files), --insecure (last resort, see TLS)
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine pdfplumber truststore
"""
import argparse
import importlib.util
import io
import re
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version (revision 14)")

REVISION = 6
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "South Africa")
RAW, OUT = P.raw, P.out
REUSE = {"on": False, "insecure": False}


class Ladder:
    """A downloader that climbs the TLS ladder per host: normal verification, then the operating-system certificate store, then (only with --insecure) no verification."""
    def __init__(self, insecure: bool):
        spec = [("verified", {}), ("operating-system certificate store", {"os_trust": True})]
        if insecure:
            spec.append(("verification OFF (--insecure)", {"os_trust": True, "insecure": True}))
        self.names = [n for n, _ in spec]
        self.fetchers = [F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=2, **kw) for _, kw in spec]
        self.ok = {}                                                           # host -> index of the first mode that worked

    @property
    def retrieved(self):
        return {k: v for f in self.fetchers for k, v in f.retrieved.items()}

    def get(self, url, name=None, reuse=False, suffix=None, reject_html=False, headers=None):
        host, last = urlparse(url).netloc, None
        for i in range(self.ok.get(host, 0), len(self.fetchers)):
            try:
                data = self.fetchers[i].get(url, name, reuse=reuse, suffix=suffix, reject_html=reject_html, headers=headers)
                if i and self.ok.get(host) != i:
                    print(f"   [tls] {host}: the default store cannot verify its certificate; downloading with: {self.names[i]}")
                    if self.names[i].startswith("verification OFF"):
                        print(f"   [tls] WARNING: certificate verification is OFF for {host} (public statistics only)")
                self.ok[host] = i
                return data
            except F.RobotsDisallowed:
                raise
            except Exception as e:
                last = e
                if "SSL" not in str(e) and "certificate" not in str(e).lower():
                    raise
        raise RuntimeError(f"{last}  [certificate problem on every mode tried: {', '.join(self.names)}" + ("" if REUSE["insecure"] else "; --insecure is the last resort") + "]")

    def retrieved_on(self, *urls):
        dates = [self.retrieved[u] for u in urls if u in self.retrieved]
        return min(dates) if dates else __import__("datetime").date.today().isoformat()


FETCH = None                                                                   # created in main, once the --insecure option is known
PAGES = {
    "saps": "https://www.saps.gov.za/services/crimestats.php",
    "older": "https://www.saps.gov.za/services/older_crimestats.php",
    "population": "https://www.statssa.gov.za/?page_id=1854&PPN=P0302",
    "deaths": "https://www.statssa.gov.za/?page_id=1854&PPN=P0309.3",
}
FILE_RE = re.compile(r"\.(xlsx?|csv|zip|pdf)(?:[?#]|$)|/download|crimestats|dlf", re.I)
MURDER = re.compile(r"murder", re.I)
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


def links_of(url: str, tag: str) -> list[tuple[str, str]]:
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(url, "za_page_" + tag, reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    except F.RobotsDisallowed:
        print(f"   [robots] {url} does not allow automated reading")
        return []
    except Exception as e:
        print(f"   [skip] {url}: {str(e)[:110]}")
        return []
    return [(a.get_text(" ", strip=True), urljoin(url, a["href"].strip())) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if FILE_RE.search(a["href"])]


def show(data: bytes, suffix: str = ".xlsx", max_sheets: int = 6):
    t0 = time.time()
    xl = open_excel(data, suffix)
    print(f"   opened in {time.time() - t0:.0f} s; sheets ({len(xl.sheet_names)}): {xl.sheet_names[:12]}", flush=True)
    for sh in xl.sheet_names[:max_sheets]:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        print(f"   --- sheet '{sh}': {raw.shape}")
        print(raw.iloc[:8, :10].to_string(max_colwidth=24, header=False))
        txt = raw.iloc[:, :14].fillna("").astype(str)
        hit = raw[[bool(MURDER.search(" ".join(r))) for r in txt.itertuples(index=False)]]
        if len(hit):
            print(f"   rows mentioning murder ({len(hit)}), the first 6, first 12 columns:")
            print(hit.iloc[:6, :12].to_string(max_colwidth=24, header=False))
        cols = [c for c in raw.columns[:6] if raw[c].astype(str).str.contains(r"province|district|station", case=False, na=False).any()]
        if cols:
            print(f"   columns that look like station / district / province: {cols}")


SAPS_PDF = "https://www.saps.gov.za/services/downloads/2025/2025-2026_-_4th_Quarter_WEB.pdf"             # the address printed in the SAPS release itself (Q4 2025/26)
MYPE_PDF = "https://www.statssa.gov.za/publications/P0302/P0302{year}.pdf"                                 # mid-year population estimates (direct address pattern; probed)
DEATHS_PDF = "https://www.statssa.gov.za/publications/P03093/P03093{year}.pdf"                              # mortality and causes of death (direct address pattern; probed)
PDF_LINE = re.compile(r"murder|province|eastern cape|gauteng|western cape|kwazulu|population|assault|X85", re.I)


def pdf_pages(data: bytes) -> list:
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


def describe_pdf(data: bytes, label: str, lines_cap: int = 40):
    pages = pdf_pages(data)
    print(f"   {label}: {len(pages)} pages; characters per page (first 10): {[len(t) for t in pages[:10]]}")
    hit = [(k + 1, ln.strip()) for k, t in enumerate(pages) for ln in t.splitlines() if PDF_LINE.search(ln)]
    print(f"   lines that mention murder / province / population ({len(hit)}), the first {lines_cap}:")
    for k, ln in hit[:lines_cap]:
        print(f"      p{k}: {ln[:150]}")


def probe_pdfs(pattern: str, years, what: str):
    got = {}
    print(f"\n[probe] {what}: {pattern}")
    for y in years:
        u = pattern.format(year=y)
        try:
            got[y] = (u, FETCH.get(u, f"za_{what.split()[0].lower()}_{y}", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
            print(f"   {y}: exists ({len(got[y][1]) / 1e6:.1f} MB)")
        except F.RobotsDisallowed:
            print(f"   {y}: robots.txt does not allow it")
        except Exception as e:
            print(f"   {y}: {str(e)[:80]}")
    return got


PROV = re.compile(r"(Eastern Cape|Free State|Gauteng|KwaZulu[- ]Natal|Limpopo|Mpumalanga|North West|Northern Cape|Western Cape)\s+[\d ,.]{7,}", re.I)


def show_pages(pages: list, wanted, n: int = 36, label: str = ""):
    for k in wanted:
        if k - 1 < len(pages):
            print(f"   --- {label} page {k}, the first {n} lines:")
            for ln in pages[k - 1].splitlines()[:n]:
                print("      " + ln[:150])


def province_lines(pages: list, cap: int = 45, label: str = ""):
    hit = [(k + 1, ln.strip()) for k, t in enumerate(pages) for ln in t.splitlines() if PROV.search(ln)]
    print(f"   {label}: {len(hit)} line(s) with a province name followed by a long number, the first {cap}:")
    for k, ln in hit[:cap]:
        print(f"      p{k}: {ln[:150]}")


def assault_lines(pages: list, cap: int = 30, label: str = ""):
    hit = [(k + 1, ln.strip()) for k, t in enumerate(pages) for ln in t.splitlines() if re.search(r"assault|homicide|X85|interpersonal violence", ln, re.I)]
    print(f"   {label}: {len(hit)} line(s) on assault / homicide, the first {cap}:")
    for k, ln in hit[:cap]:
        print(f"      p{k}: {ln[:150]}")


def deep(data: bytes, label: str):
    """The RAW Data sheet of a SAPS workbook: every column header, the levels of the file and a few murder rows at each level."""
    xl = open_excel(data)
    for sh in xl.sheet_names:
        if "raw" not in sh.lower():
            continue
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        hdr_row = next((i for i in range(min(8, len(raw))) if raw.iloc[i].astype(str).str.contains("Station", case=False).any() and raw.iloc[i].astype(str).str.contains("Province", case=False).any()), 2)
        print(f"   --- {label}: sheet '{sh}' {raw.shape}; header row {hdr_row}; EVERY column header:")
        print("      " + " | ".join(f"{j}:{str(v)[:19]}" for j, v in enumerate(raw.iloc[hdr_row])))
        body = raw.iloc[hdr_row + 1:].reset_index(drop=True)
        lv = next((j for j, v in enumerate(raw.iloc[hdr_row]) if "level" in str(v).lower()), None)
        if lv is not None:
            print(f"      levels of the file ({raw.columns[lv] if False else 'Comp level'}): {body.iloc[:, lv].value_counts().head(8).to_dict()}")
        cat = next((j for j, v in enumerate(raw.iloc[hdr_row]) if str(v).strip() == "Crime_Category"), None)
        if cat is not None:
            m = body[body.iloc[:, cat].astype(str).str.strip().str.lower() == "murder"]
            print(f"      rows whose Crime_Category is exactly 'Murder': {len(m)}")
            if lv is not None:
                for lev, g in m.groupby(m.iloc[:, lv].astype(str)):
                    print(f"      level {lev!r}: {len(g)} rows; the first two:")
                    print(g.iloc[:2, 2:min(raw.shape[1], 24)].to_string(max_colwidth=16, header=False))
        return


def pages_with(pages: list, must: list, n: int = 3, lines: int = 26, label: str = ""):
    k = [i + 1 for i, t in enumerate(pages) if all(re.search(m, t, re.I) for m in must)]
    print(f"   {label}: pages matching {must}: {k[:12]}")
    show_pages(pages, k[:n], lines, label)


def cmd_inspect():
    found = {}
    for key, url in PAGES.items():
        links = links_of(url, key)
        found[key] = links
        print(f"\n[{key}] {url}: {len(links)} download-like links")
        for t, u in links[:70]:
            print(f"   {t[:55]:55} {unquote(u)[:120]}")
    cand = [(t, u) for t, u in found["saps"] if re.search(r"\.xlsx?(?:[?#]|$)", u, re.I)]
    print(f"\n[saps] {len(cand)} Excel link(s) on the current crime statistics page (newest first): " + "; ".join(unquote(u).rsplit("/", 1)[-1] for t, u in cand[:8]))
    for t, u in cand[:1]:
        print(f"\n===== {t[:70]} | {unquote(u).rsplit('/', 1)[-1][:80]} =====", flush=True)
        try:
            t0 = time.time()
            data = FETCH.get(u, "saps_workbook", reuse=REUSE["on"], suffix=".xlsx")
            print(f"   downloaded {len(data) / 1e6:.1f} MB in {time.time() - t0:.0f} s", flush=True)
            show(data)
            deep(data, "quarterly workbook")
        except F.RobotsDisallowed:
            print("   [robots] not allowed automatically: save it by hand as manual_saps_workbook.xlsx in " + str(RAW))
        except Exception as e:
            print(f"   [skip] {str(e)[:160]}")
    annual = [u for t, u in found["older"] if re.search(r"annual", unquote(u), re.I) and re.search(r"\.xlsx?$", u, re.I)]
    print(f"\n[older] {len(annual)} annual workbook link(s): " + "; ".join(unquote(u).rsplit("/", 1)[-1] for u in annual[:5]))
    for u in annual[:1]:
        print(f"\n===== {unquote(u).rsplit('/', 1)[-1]} =====", flush=True)
        try:
            data = FETCH.get(u, "saps_annual_workbook", reuse=REUSE["on"], suffix=".xlsx")
            print(f"   downloaded {len(data) / 1e6:.1f} MB", flush=True)
            show(data, max_sheets=4)
            deep(data, "annual workbook")
        except Exception as e:
            print(f"   [skip] {str(e)[:160]}")
    print("\n===== SAPS quarterly release (PDF), the address printed in the release itself =====", flush=True)
    try:
        sp = pdf_pages(FETCH.get(SAPS_PDF, "saps_quarterly_pdf", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
        print(f"   SAPS Q4 2025/26: {len(sp)} pages")
        show_pages(sp, (4, 9, 10, 11), 34, "SAPS")          # the methodology, the population base and the provincial murder table
        mur = [k + 1 for k, t in enumerate(sp) if re.search(r"^\s*(▪\s*)?Murder\b", t, re.M) and re.search(r"Station\s+District\s+Province", t)]
        print(f"   pages with a station table headed 'Murder': {mur[:8]}")
        show_pages(sp, mur[:1], 30, "SAPS murder table")
        pages_with(sp, [r"\bMurder\b", r"ratio|per 100", r"Eastern Cape"], 2, 30, "SAPS province murder ratio")
    except Exception as e:
        print(f"   [skip] {str(e)[:200]}")
    mype = probe_pdfs(MYPE_PDF, range(2019, 2027), "Mid-year population estimates (Stats SA P0302)")
    for y in sorted(mype)[-1:] + [k for k in sorted(mype) if k == 2022][:1]:
        print(f"\n===== mid-year population estimates {y}: the province lines =====")
        mp = pdf_pages(mype[y][1])
        province_lines(mp, 36, f"P0302 {y}")
        if y == max(mype):
            show_pages(mp, (3,), 40, "P0302 contents")
            pages_with(mp, [r"Table 9", r"provincial|province", r"Eastern Cape"], 1, 22, "P0302 Table 9")
    deaths = probe_pdfs(DEATHS_PDF, range(2016, 2025), "Mortality and causes of death (Stats SA P0309.3)")
    if deaths:
        y = max(deaths)
        print(f"\n===== mortality {y}: assault / homicide lines and the province lines =====")
        dp = pdf_pages(deaths[y][1])
        assault_lines(dp, 30, f"P0309.3 {y}")
        province_lines(dp, 12, f"P0309.3 {y}")
        show_pages(dp, (62,), 26, "P0309.3 assault by province")
    for p in sorted(RAW.glob("manual_*.xls*")):
        print(f"\n===== manual file {p.name} =====")
        show(p.read_bytes(), p.suffix)
    if not cand and not list(RAW.glob("manual_*.xls*")):
        print("   no Excel link was found on the SAPS page: open https://www.saps.gov.za/services/crimestats.php in a browser, download the newest 'Detailed' workbook and save it as manual_saps_workbook.xlsx in " + str(RAW))
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


LOW_COUNT = F.LOW_COUNT
PROVINCES = ["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga", "North West", "Northern Cape", "Western Cape"]
FYCOL = re.compile(r"^(\d{4})-(\d{4})$")
QCOL = re.compile(r"^([A-Za-z]+)\s+(\d{4})\s+to\s+([A-Za-z]+)\s+(\d{4})$")
PROV_POP = re.compile(r"^(" + "|".join(PROVINCES) + r")\s+(\d[\d ]{6,})\s+(\d{1,2},\d)\s*$")
PROV_SAPS = re.compile(r"^(" + "|".join(PROVINCES) + r")\s+(\d[\d ]{6,})\s+(\d{1,2}[.,]\d)\s*$")
POP_TOL_NATIONAL = 0.005          # DECISION: the nine provinces add up to the national total of the edition within 0.5%
BREAK_JUMP = 0.03                 # DECISION: a provincial population changing by more than 3% a year (annualised between available editions) is flagged as a break in the series
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}


def raw_sheet(data: bytes):
    xl = open_excel(data)
    name = next((n for n in xl.sheet_names if n.strip().lower() == "raw data"), None)
    if name is None:
        sys.exit(f"[stop] SAPS workbook: no sheet 'RAW Data' (sheets: {xl.sheet_names})")
    raw = pd.read_excel(xl, sheet_name=name, header=None, dtype=object)
    hdr = next((i for i in range(min(8, len(raw))) if str(raw.iat[i, 4]).strip() == "Station" and str(raw.iat[i, 7]).strip() == "Crime_Category"), None)
    if hdr is None or str(raw.iat[hdr, 2]).strip() != "Comp level":
        sys.exit("[stop] SAPS workbook: the header row of 'RAW Data' (Comp level | ... | Station | District | Province | Crime_Category | Code | ...) was not found in its first 8 rows")
    return raw, hdr


def murder_rows(raw, hdr):
    body = raw.iloc[hdr + 1:]
    m = body[body.iloc[:, 7].astype(str).str.strip().str.lower() == "murder"]
    if m.empty:
        sys.exit("[stop] SAPS workbook: no row with Crime_Category 'Murder'")
    return m


def load_annual(data: bytes) -> dict:
    """-> {(level, unit, column 5, column 6): {fy start year: count}} for Murder, from an annual workbook (columns '2015-2016' ...). A station row holds its district and province in columns 5 and 6, a district row
    its province and the country, a province row the country and RSA."""
    raw, hdr = raw_sheet(data)
    cols = {j: int(FYCOL.match(str(raw.iat[hdr, j]).strip()).group(1)) for j in range(raw.shape[1]) if FYCOL.match(str(raw.iat[hdr, j]).strip())}
    if len(cols) < 3:
        sys.exit(f"[stop] SAPS annual workbook: only {len(cols)} financial-year column(s) of the form 2015-2016 in the header row")
    out = {}
    for _, r in murder_rows(raw, hdr).iterrows():
        vals = {y: pd.to_numeric(r.iloc[j], errors="coerce") for j, y in cols.items()}
        if any(v != v for v in vals.values()):
            sys.exit(f"[stop] SAPS annual workbook: a murder count of {str(r.iloc[4])!r} is not a number")
        out[(str(r.iloc[2]).strip(), str(r.iloc[4]).strip(), str(r.iloc[5]).strip(), str(r.iloc[6]).strip())] = {y: int(v) for y, v in vals.items()}
    return out


def load_quarter(data: bytes) -> dict:
    """-> {(level, unit, parent): count} of Murder for the NEWEST three-month period of a quarterly workbook, and the period as ((month, year) of its start)."""
    raw, hdr = raw_sheet(data)
    per = {}
    for j in range(raw.shape[1]):
        m = QCOL.match(re.sub(r"\s+", " ", str(raw.iat[hdr, j]).strip()))
        if m and m.group(1).lower() in MONTHS and m.group(3).lower() in MONTHS:
            per[j] = (int(m.group(2)), MONTHS[m.group(1).lower()], f"{m.group(1)} {m.group(2)} to {m.group(3)} {m.group(4)}")
    if not per:
        sys.exit("[stop] SAPS quarterly workbook: no column named like 'January 2026 to March 2026' in the header row")
    j = max(per, key=lambda k: (per[k][0], per[k][1]))
    out = {}
    for _, r in murder_rows(raw, hdr).iterrows():
        v = pd.to_numeric(r.iloc[j], errors="coerce")
        if v != v:
            sys.exit(f"[stop] SAPS quarterly workbook: a murder count of {str(r.iloc[4])!r} is not a number")
        out[(str(r.iloc[2]).strip(), str(r.iloc[4]).strip(), str(r.iloc[5]).strip(), str(r.iloc[6]).strip())] = int(v)
    return out, per[j][:2], per[j][2]


def _n(x: str) -> str:
    return re.sub(r"\s+", " ", str(x)).strip().casefold()


def reconcile(units: dict, fy: int):
    """-> (province rows, national rows, station sums by province, station sums by district, district rows) for one financial year."""
    prov = {_n(k[1]): v[fy] for k, v in units.items() if k[0] == "Province" and fy in v}
    nat = [v[fy] for k, v in units.items() if k[0] == "National" and fy in v]
    st, sd = {}, {}
    for k, v in units.items():
        if k[0] == "Station" and fy in v:
            st[_n(k[3])] = st.get(_n(k[3]), 0) + v[fy]          # column 6: the province of the station
            sd[_n(k[2])] = sd.get(_n(k[2]), 0) + v[fy]          # column 5: its district (the names are compared without regard to capitalisation)
    dist = {_n(k[1]): v[fy] for k, v in units.items() if k[0] == "District" and fy in v}
    return prov, nat, st, sd, dist


def _numbers(tokens: list) -> list:
    """Numbers written with spaces as thousands separators ('3 380 375 3 681 342'): a number starts at a token of one or two digits and continues with tokens of exactly three digits (a provincial total has 7 or 8 digits)."""
    out, cur = [], ""
    for t in tokens:
        if re.fullmatch(r"\d{1,2}", t):
            if cur:
                out.append(int(cur))
            cur = t
        elif re.fullmatch(r"\d{3}", t) and cur:
            cur += t
        else:
            return []
    if cur:
        out.append(int(cur))
    return out


def _num_from(g: list):
    """A number written with spaces as thousands separators: its first token has 1-3 digits (no leading zero), every other token exactly 3."""
    if not g or not re.fullmatch(r"[1-9]\d{0,2}", g[0]) or any(not re.fullmatch(r"\d{3}", x) for x in g[1:]):
        return None
    return int("".join(g))


def _segment_triples(tokens: list, n: int):
    """The reading of the tokens as n (males, females, total) triples with males + females = total (+-1), numbers of one to three tokens each. Returns the list of totals if EXACTLY ONE reading exists, else None."""
    sols = []

    def rec(i, k, acc):
        if len(sols) > 1:
            return
        if k == n:
            if i == len(tokens):
                sols.append(list(acc))
            return
        for lm in (1, 2, 3):
            m = _num_from(tokens[i:i + lm])
            if m is None:
                continue
            for lf in (1, 2, 3):
                f = _num_from(tokens[i + lm:i + lm + lf])
                if f is None:
                    continue
                for lt in (1, 2, 3):
                    t = _num_from(tokens[i + lm + lf:i + lm + lf + lt])
                    if t is not None and abs(m + f - t) <= 2:
                        rec(i + lm + lf + lt, k + 1, acc + [t])
    rec(0, 0, [])
    return sols[0] if len(sols) == 1 else None


def _total_triples(pages: list):
    """The provincial table by age and sex of an edition: its 'Total' row gives, per province, males, females and total. Five provinces in one row (Eastern Cape, Free State, Gauteng, KwaZulu-Natal, Limpopo) and
    four in the next (Mpumalanga, Northern Cape, North West, Western Cape). Accepted only if every row has exactly one reading with males + females = total, the nine add up to 40-75 million with Gauteng and
    KwaZulu-Natal the largest, and (when the edition prints one) to its national total within 0.5%."""
    rows, nat_row = [], None
    for t in pages:
        for ln in t.splitlines():
            m = re.match(r"^\s*Total\s+(\d[\d ]+)\s*$", ln.replace("\xa0", " ").replace("\u202f", " "))
            if m:
                toks = m.group(1).split()
                for n in (5, 4):
                    r = _segment_triples(toks, n)
                    if r:
                        if n == 5 and r[4] > 40e6:                      # four provinces followed by the national total of the same table (e.g. Mpumalanga, Northern Cape, North West, Western Cape, South Africa)
                            rows.append(r[:4])
                            nat_row = r[4]
                        else:
                            rows.append(r)
                        break
    r5s, r4s = [r for r in rows if len(r) == 5], [r for r in rows if len(r) == 4]
    for r5 in r5s:
        for r4 in r4s:                                                    # the two rows may be on the same page or on neighbouring ones, in either order
            vals = dict(zip(["Eastern Cape", "Free State", "Gauteng", "KwaZulu-Natal", "Limpopo", "Mpumalanga", "Northern Cape", "North West", "Western Cape"], r5 + r4))
            top = sorted(vals.values(), reverse=True)
            if 40e6 <= sum(vals.values()) <= 75e6 and vals["Gauteng"] == top[0] and vals["KwaZulu-Natal"] == top[1]:
                nat = [_numbers(re.sub(r"100,0", " ", ln.replace("Total", "")).split()) for t in pages for ln in t.splitlines() if "100,0" in ln and ln.strip().startswith("Total")]
                nat = [x[2] for x in nat if len(x) == 3] + ([nat_row] if nat_row else [])
                if not nat or all(abs(sum(vals.values()) - x) / x <= 0.005 for x in nat):
                    return vals
    return None


PROV_ANY = re.compile(r"^(" + "|".join(PROVINCES) + r")\b\s*(.*)$", re.I)


def parse_mype(pages: list):
    """-> ({province: population}, rule) from the table of an edition that lists the nine provinces. Rule 1: population and percentage share (shares add up to 100% within 0.6); rule 2 (fallback): population
    only, the nine numbers each of 6 to 9 digits, adding up to 40-75 million with Gauteng the largest province. None if neither is found."""
    for t in pages:
        hits = {}
        for ln in t.splitlines():
            m = PROV_ANY.match(re.sub(r"\s+", " ", ln.strip()))
            if not m:
                continue
            q = re.match(r"^(\d{1,2}(?: \d{3}){2}|\d{1,2}(?:,\d{3}){2}|\d{6,9})\s+(\d{1,2}[,.]\d{1,2})\s*%?(?:\s|$)", m.group(2))
            if q:
                hits[next(p for p in PROVINCES if p.lower() == m.group(1).lower())] = (int(q.group(1).replace(" ", "").replace(",", "")), float(q.group(2).replace(",", ".")))
        if len(hits) == 9 and abs(sum(v[1] for v in hits.values()) - 100) <= 0.6:
            return {k: v[0] for k, v in hits.items()}, "population and share"
    for t in pages:
        hits = {}
        for ln in t.splitlines():
            m = PROV_ANY.match(re.sub(r"\s+", " ", ln.strip()))
            if not m:
                continue
            q = re.match(r"^(\d{1,2}(?: \d{3}){2}|\d{1,2}(?:,\d{3}){2}|\d{6,9})(?:\s|$)", m.group(2))
            if q:
                hits.setdefault(next(p for p in PROVINCES if p.lower() == m.group(1).lower()), int(q.group(1).replace(" ", "").replace(",", "")))
        if len(hits) == 9 and 40e6 <= sum(hits.values()) <= 75e6 and hits["Gauteng"] == max(hits.values()):
            return hits, "population only (no share column)"
    tri = _total_triples(pages)
    if tri:
        return tri, "'Total' rows of the provincial table by sex"
    return None, None


def mype_diagnostic(pages: list, src: str):
    hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if PROV_ANY.match(re.sub(r"\s+", " ", ln.strip())) and re.search(r"\d", ln)]
    print(f"   [diagnostic] {src.rsplit('/', 1)[-1]}: {len(hit)} line(s) that start with a province name and hold a number; the first 14:")
    for k, ln in hit[:14]:
        print(f"      p{k}: {ln[:140]}")
    tot = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if re.match(r"^Total\b", ln.strip()) and len(re.findall(r"\d", ln)) >= 20]
    print(f"   [diagnostic] 'Total' lines with many numbers: {len(tot)}; the first 8, complete:")
    for k, ln in tot[:8]:
        print(f"      p{k}: {ln[:330]}")
    for k in sorted({k for k, _ in tot[:8] if len(pages[k - 1]) > 0})[:3]:
        print(f"   [diagnostic] the first 5 lines of page {k}: " + " | ".join(x.strip()[:70] for x in pages[k - 1].splitlines()[:5]))


def mype_edition(year: int):
    man = RAW / f"manual_mype_{year}.pdf"
    if man.exists():
        return pdf_pages(man.read_bytes()), str(man)
    u = MYPE_PDF.format(year=year)
    try:
        return pdf_pages(FETCH.get(u, f"za_mid-year_{year}", reuse=REUSE["on"], suffix=".pdf", reject_html=True)), u
    except F.RobotsDisallowed:
        return None, u
    except Exception:
        return None, u


def cmd_build():
    print(f"[south_africa_homicide_rate.py revision {REVISION}]")
    links = links_of(PAGES["saps"], "saps")
    older = links_of(PAGES["older"], "older")
    # ---- annual workbooks: the newest one that covers a financial year wins. SAPS's own page has dead links (HTTP 404) and older layouts: the first workbook that reads is required,
    #      the others are optional extras that are skipped, with the reason, when they cannot be read.
    ann_urls, seen = [], set()
    for t, u in older:
        name = unquote(u).rsplit("/", 1)[-1]
        if re.search(r"\.xlsx$", u, re.I) and re.search(r"annual|crime[-_ ]statistics[-_ ]?\d{4}", name, re.I) and not re.search(r"quarter", name, re.I) and name not in seen:
            seen.add(name)
            ann_urls.append(u)
    if not ann_urls:
        sys.exit("[stop] no annual workbook was found on the SAPS older statistics page (save one by hand as manual_saps_annual_<n>.xlsx)")
    units, source_fy, read_ok, taken = {}, {}, 0, {}
    for k, u in enumerate(ann_urls):
        nm = unquote(u).rsplit("/", 1)[-1]
        try:
            d = load_annual(FETCH.get(u, f"saps_annual_{k}", reuse=REUSE["on"], suffix=".xlsx"))
        except (Exception, SystemExit) as e:
            print(f"[annual] {nm}: skipped ({str(e)[:140]})")
            continue
        read_ok += 1
        years = sorted({y for v in d.values() for y in v})
        new_years = [y for y in years if y not in taken]
        over = [y for y in years if y in taken]
        print(f"[annual] {nm}: {len(d)} murder rows, financial years {years[0]}/{str(years[0] + 1)[2:]} to {years[-1]}/{str(years[-1] + 1)[2:]}; used for {len(new_years)} year(s)"
              + (f" ({new_years[0]}/{str(new_years[0] + 1)[2:]} to {new_years[-1]}/{str(new_years[-1] + 1)[2:]})" if new_years else "") + (f"; {len(over)} year(s) already taken from a newer workbook" if over else ""))
        # revisions: only the province and national rows of a year that a newer workbook already supplies are compared (station rows are NOT mixed between workbooks: their names change)
        ref = {(kk[0], _n(kk[1])): vv for kk, vv in units.items() if kk[0] in ("Province", "National")}
        nrev = 0
        for key, vals in d.items():
            if key[0] in ("Province", "National"):
                for y in over:
                    old = ref.get((key[0], _n(key[1])), {}).get(y)
                    if old is not None and old != vals[y]:
                        nrev += 1
                        if nrev <= 3:
                            print(f"   [revision] {key[0]} {key[1]!r} {y}/{y + 1}: {old} in the newer workbook against {vals[y]} in {nm}: the newer workbook is kept")
        if nrev:
            print(f"   [revision] {nrev} province / national count(s) differ between this workbook and a newer one that covers the same financial year")
        for key, vals in d.items():
            for y in new_years:
                units.setdefault(key, {})[y] = vals[y]
                source_fy.setdefault(key, {})[y] = u
        for y in new_years:
            taken[y] = nm
    if not read_ok:
        sys.exit("[stop] none of the annual workbooks of the SAPS older statistics page could be read")
    have = sorted({y for v in units.values() for y in v})
    # ---- the newest financial year from its four quarterly workbooks
    q = {}
    for t, u in links:
        m = re.search(r"(\d{4})-(\d{4})_-_(\d)(?:st|nd|rd|th)_Quarter.*\.xlsx$", unquote(u), re.I)
        if m:
            q.setdefault(int(m.group(1)), {})[int(m.group(3))] = u
    for fy, qs in sorted(q.items()):
        if fy in have:
            continue
        if sorted(qs) != [1, 2, 3, 4]:
            print(f"[quarters] financial year {fy}/{fy + 1}: only quarters {sorted(qs)} are published: no row for it")
            continue
        tot, periods = {}, []
        for n in (1, 2, 3, 4):
            d, start, label = load_quarter(FETCH.get(qs[n], f"saps_q{fy}_{n}", reuse=REUSE["on"], suffix=".xlsx"))
            periods.append(label)
            for key, v in d.items():
                tot[key] = tot.get(key, 0) + v
        print(f"[quarters] financial year {fy}/{fy + 1} = " + " + ".join(periods))
        for key, v in tot.items():
            units.setdefault(key, {})[fy] = v
        have = sorted(set(have) | {fy})
    print(f"[years] financial years with counts: {have[0]}/{str(have[0] + 1)[2:]} to {have[-1]}/{str(have[-1] + 1)[2:]} ({len(have)})")
    # ---- reconciliation of the levels
    prov_names = sorted({k[1] for k in units if k[0] == "Province"})
    if prov_names != sorted(PROVINCES):
        sys.exit(f"[stop] the province rows of the file are {prov_names}, not the nine provinces")
    bad, bad_fy = [], set()
    for fy in have:
        prov, nat, st, sd, dist = reconcile(units, fy)
        if len(nat) != 1:
            sys.exit(f"[stop] {fy}/{fy + 1}: {len(nat)} national rows of Murder, expected one")
        if sum(prov.values()) != nat[0]:
            bad.append(f"{fy}: provinces {sum(prov.values())} against national {nat[0]}")
            bad_fy.add(fy)
        for pn in PROVINCES:
            if st.get(_n(pn), 0) != prov.get(_n(pn)):
                bad.append(f"{fy} {pn}: stations {st.get(_n(pn), 0)} against province {prov.get(_n(pn))}")
                bad_fy.add(fy)
        for dn, dv in dist.items():
            if sd.get(dn, 0) != dv:
                bad.append(f"{fy} {dn}: stations {sd.get(dn, 0)} against district {dv}")
                bad_fy.add(fy)
    print(f"[reconciliation] stations -> districts -> provinces -> national in {len(have)} financial years: " + ("all equal" if not bad else f"{len(bad)} difference(s) in {len(bad_fy)} year(s), the first: {bad[:4]}"))
    # ---- populations: the edition of each financial year's start year; Stats SA published NO edition in 2023 (Census 2022 was built into the 2024 series), so a financial year whose own edition does not
    #      exist takes the next year's edition, marked as substituted (its June estimate is then 0.75 years after the middle of the financial year)
    pops, srcs, subst, rule = {}, {}, set(), {}
    cache = {}

    def edition(y):
        if y not in cache:
            pages, src = mype_edition(y)
            if pages is None:
                cache[y] = (None, None, src, None)
            else:
                pp, rl = parse_mype(pages)
                if pp is None:
                    print(f"[population] edition {y}: no table with the nine provinces and their population was found in {src}")
                    mype_diagnostic(pages, src)
                cache[y] = (pp, rl, src, pages)
        return cache[y]
    for fy in have:
        pp, rl, src, pg = edition(fy)
        if pp is None and pg is None:                                         # the edition itself is not there (not published, or not found): the next year's edition may stand in
            pp2, rl2, src2, _ = edition(fy + 1)
            if pp2 is not None:
                pops[fy], srcs[fy], rule[fy] = pp2, src2, rl2
                subst.add(fy)
                print(f"[population] edition {fy}: not found ({src}); the edition {fy + 1} is used for {fy}/{str(fy + 1)[2:]} and marked as substituted")
                continue
        if pp is None:
            print(f"[population] edition {fy}: not usable: no row for {fy}/{str(fy + 1)[2:]}")
            continue
        pops[fy], srcs[fy], rule[fy] = pp, src, rl
    if not pops:
        sys.exit("[stop] no Stats SA edition could be read")
    print("[population] editions read: " + ", ".join(f"{y}{'*' if y in subst else ''} ({sum(p.values()):,})" for y, p in sorted(pops.items())) + ("   (* substituted by the next edition)" if subst else ""))
    # ---- SAPS's own base (2021 series) of the newest quarter, informative
    saps_pop = {}
    try:
        sp = pdf_pages(FETCH.get(SAPS_PDF, "saps_quarterly_pdf", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
        for t in sp:
            hits = {}
            for ln in t.splitlines():
                m = PROV_SAPS.match(re.sub(r"\s+", " ", ln.strip()))
                if m:
                    hits[m.group(1)] = int(m.group(2).replace(" ", ""))
            if len(hits) == 9:
                saps_pop = hits
                break
        print("[saps base] the 2021-series populations printed in the newest SAPS release: " + (f"read, national {sum(saps_pop.values()):,}" if saps_pop else "not found (informative only)"))
    except Exception as e:
        print(f"[saps base] the SAPS release could not be read ({str(e)[:80]}): informative check skipped")
    rows = []
    last_pop = {}
    for fy in sorted(pops):
        pp = pops[fy]
        nat_pop = sum(pp.values())
        for pn in PROVINCES:
            cases = next(v[fy] for k, v in units.items() if k[0] == "Province" and k[1] == pn and fy in v)
            pop = pp[pn]
            prev = last_pop.get(pn)
            gap = None if prev is None else fy - prev[0]
            jump = None if prev is None else (pop / prev[1]) ** (1 / gap) - 1            # annual rate between this edition and the previous AVAILABLE one (a missing edition widens the gap)
            last_pop[pn] = (fy, pop)
            brk = jump is not None and abs(jump) > BREAK_JUMP
            sub = fy in subst
            checks = [("the stations add up to their districts and provinces, and the provinces to the national row of the file" if fy not in bad_fy else "the stations, districts, provinces and national row of the file do NOT add up in this financial year (see the console)"),
                      (f"population: Stats SA mid-year estimate, edition {fy + 1 if sub else fy} used for the financial year {fy}/{str(fy + 1)[2:]} because Stats SA published no edition in {fy}: SUBSTITUTED, its June estimate is 0.75 years after the middle of the financial year; province {pop:,} of {nat_pop:,}" if sub else f"population: Stats SA mid-year estimate, edition {fy}, province {pop:,} of {nat_pop:,} (table read with the rule: {rule[fy]})"),
                      (f"the provincial population moves {jump:+.1%} a year from the edition of {prev[0]} ({gap} year(s) earlier): a break in the series (rebasing)" if brk else (f"no break: {jump:+.1%} a year from the edition of {prev[0]}" if jump is not None else "no previous edition to compare with")),
                      "Stats SA assault deaths (death notification) cover only about a third of SAPS murders: informative, not a confirmation"]
            rows.append({"country": "South Africa", "unit": pn, "unit_local": pn, "unit_code": "", "admin_level": "admin1", "unit_type": "province", "parent_unit": "", "year": fy, "homicide_cases": int(cases),
                         "population": int(pop), "homicide_rate_per_100k": cases / int(pop) * 1e5, "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": 0.75 if sub else 0.3,
                         "indicator_type": "police_recorded_cases", "reliability_tier": "B", "definition_flags": "counts_victims", "validation": "; ".join(checks),
                         "indicator": "SAPS recorded murder (code 1: murder, farm murder and police murder), victims (bodies counted)",
                         "population_method": (f"Stats SA mid-year population estimates, edition {fy + 1} (June {fy + 1} estimate) SUBSTITUTED for the missing edition {fy}, province total" if sub else f"Stats SA mid-year population estimates, edition {fy} (June {fy} estimate), province total"),
                         "data_notes": f"financial year {fy}/{fy + 1} (April {fy} to March {fy + 1}), year = start year; SAPS counts bodies (four people killed in one incident are four murders); the population editions are of different vintages and break where Stats SA rebased; "
                                       "Stats SA assault deaths cover about a third of the police count",
                         "source_homicide": "https://www.saps.gov.za/services/crimestats.php", "source_population": srcs[fy], "retrieved": FETCH.retrieved_on("https://www.saps.gov.za/services/crimestats.php"),
                         "financial_year": f"{fy}-{str(fy + 1)[2:]}", "flag_population_break": bool(brk), "flag_population_substituted": bool(sub), "population_change_pct": None if jump is None else round(jump * 100, 2),
                         "population_saps_2021_series": saps_pop.get(pn) if fy == max(pops) else None})
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "south_africa")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}; population breaks flagged: {int(df['flag_population_break'].sum())} row(s); substituted populations: {int(df['flag_population_substituted'].sum())} row(s)")
    brk_rows = df[df["flag_population_break"]]
    if len(brk_rows):
        print("[breaks] provinces whose population moves more than 3% a year between editions:")
        print(brk_rows[["unit", "financial_year", "population", "population_change_pct"]].to_string(index=False))
    last = int(df.year.max())
    print(f"\nLatest financial year {last}/{last + 1}:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].round(2).to_string(index=False))
    nat = {y: sum(df[df.year == y].homicide_cases) for y in sorted(df.year.unique())}
    print("national murder (sum of provinces) by financial year: " + ", ".join(f"{y}: {v:,}" for y, v in nat.items()))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} provinces, financial years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--insecure", action="store_true", help="last resort: TLS verification OFF for a host whose certificate cannot be verified (prints a warning)")
    a = ap.parse_args()
    REUSE["on"], REUSE["insecure"] = a.reuse, a.insecure
    FETCH = Ladder(a.insecure)
    cmd_inspect() if a.cmd == "inspect" else cmd_build()