#!/usr/bin/env python3
"""
Australia, Queensland - homicide per 100,000 residents by local government area (LGA), calendar years (LGAs of 100,000 or more residents).

POLICE (numerator): Queensland Police Service (QPS) open data (CC BY, updated monthly), kept in the QPS public storage bucket named by the open data portal's metadata (the portal pages answer
            with a bot challenge): "LGA Reported Offences Number" (offences reported by LGA, month and offence type, January 2001 onwards). The unit is the reported OFFENCE (the bucket has no
            victims file). Cases = "Homicide (Murder)" + "Manslaughter (excl. by driving)" + "Manslaughter Unlawful Striking Causing Death"; "Other Homicide", "Attempted Murder", "Conspiracy to
            Murder" and "Driving Causing Death" are kept apart as extra columns. Only complete calendar years are used.
FILE LAYOUT  Every data row has ONE FIELD MORE than the header names (94 labels, 95 fields): the last value column has no label. The file is read with index_col=False (otherwise pandas shifts every
            label by one and the LGA names become the row index) and that last column is dropped; it is not a homicide column. Before use the script classifies the extra field and tests that the labels
            sit over the right values (the Assault total equals the sum of its components). Month labels are codes such as JAN01 (January 2001).
POPULATION: ABS "Regional population" (3218.0): estimated resident population by LGA at 30 June (shared module abs_lga_population.py). The QPS file of rates per 100,000 gives an independent
            implied population (annual sum of the counts / annual sum of the monthly rates x 100,000) that is compared with the ABS one within 5%.
CHECKS      (1) the LGA rows add up to the statewide file QLD_Reported_Offences_Number.csv (equal / within max(5%, 3) / beyond); (2) the Queensland total is compared with the ABS state victims of
            murder + manslaughter (australia_homicide_rate.csv next to this script): offences and victims are different units, so the band is max(25%, 3); (3) the QPS implied population agrees
            with the ABS within 5%; (4) every LGA with homicides must be matched to an ABS LGA or be a known non-LGA category, or the run stops and lists the names (MANUAL_MATCH holds
            verified correspondences); (5) a population of 100,000 or more in that year for a row.
TIERS       A: the LGAs reconcile to the statewide file, the state total agrees with the ABS, and the populations agree; B: anything else. Never tier C.

Folders:    this script sits in <repo>/Pipelines/Oceania/ ; downloads go to <repo>/Data/Raw/Oceania/Australia Queensland/ ; the one output is australia_queensland_homicide_rate.csv next to it.
Commands:   python australia_queensland_homicide_rate.py inspect | build          Options: --reuse (use the files saved by an earlier run), --no-rates (skip the 14.5 MB rates file)
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine
"""
import argparse
import io
import re
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import quote, unquote, urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))             # abs_lga_population.py sits next to this script
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 13:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

from abs_lga_population import load_abs_population as _load_abs_population, norm          # shared with the other Australian LGA pipelines
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "Australia Queensland")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False, "rates": True}
ABS_POP_PAGE = "https://www.abs.gov.au/statistics/people/population/regional-population/latest-release"
ENGINE = "calamine" if __import__("importlib.util").util.find_spec("python_calamine") else "openpyxl"
PAGES = ["https://www.police.qld.gov.au/maps-and-statistics",
         "https://www.data.qld.gov.au/dataset?tags=crime",
         "https://www.data.qld.gov.au/dataset/lga_reported_offences_rates"]
HOMICIDE = re.compile(r"homicide|murder|manslaughter", re.I)
# The data files are not on the portal pages (they answer HTTP 202, a bot challenge, and the police page holds no links): the portal's own metadata names the QPS public storage bucket
# ("Original url: https://open-crime-data.s3-ap-southeast-2.amazonaws.com/Crime%20Statistics/LGA_Reported_Offences_Rates.csv"). The bucket's public listing is read first; if it is not public the
# names below are tried one by one (the first is the one the metadata states; the others are the likely names of the sibling datasets) and the answer of each is printed.
S3 = "https://open-crime-data.s3-ap-southeast-2.amazonaws.com/"
S3_PREFIX = "Crime Statistics/"
S3_CANDIDATES = ["LGA_Reported_Offences_Rates.csv", "LGA_Reported_Offences_Number.csv", "LGA_Reported_Victim_Numbers.csv", "LGA_Reported_Victims_Number.csv",
                 "LGA_Reported_Victim_Number.csv", "LGA_Reported_Victims_Numbers.csv", "LGA_Reported_Offender_Numbers.csv"]


def links_of(url: str, tag: str) -> list[tuple[str, str]]:
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(url, "qld_page_" + tag, reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    except F.RobotsDisallowed:
        print(f"   [robots] {url} does not allow automated reading")
        return []
    except Exception as e:
        print(f"   [skip] {url}: {str(e)[:100]}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = [(a.get_text(" ", strip=True), urljoin(url, a["href"].strip())) for a in soup.find_all("a", href=True)]
    for m in re.finditer(r"https?://[^\s\"'<>]+\.csv", html, re.I):                       # addresses written as text (the resource pages print the URL)
        out.append(("", m.group(0)))
    return out


def s3_files() -> dict:
    """-> {csv url: note} of the LGA files in the QPS public bucket: its public listing if it has one, else the candidate names that answer."""
    found = {}
    try:
        xml = FETCH.get(S3 + "?list-type=2&prefix=" + quote(S3_PREFIX), "qld_s3_listing", reuse=REUSE["on"], suffix=".xml").decode("utf-8", "replace")
        keys = re.findall(r"<Key>([^<]+)</Key>", xml)
        for k in keys:
            if k.lower().endswith(".csv"):
                found[S3 + quote(k)] = "bucket listing"
        print(f"   [bucket] public listing of {S3_PREFIX!r}: {len(keys)} files, {len(found)} CSV")
        if found:
            return found
        print("   [bucket] the listing is empty or not public: the candidate names are tried one by one")
    except F.RobotsDisallowed:
        print("   [bucket] robots.txt does not allow automated reading of the bucket")
        return found
    except Exception as e:
        print(f"   [bucket] no public listing ({str(e)[:70]}): the candidate names are tried one by one")
    for nm in S3_CANDIDATES:
        u = S3 + quote(S3_PREFIX + nm)
        try:
            FETCH.get(u, "qld_probe_" + re.sub(r"[^A-Za-z0-9]+", "_", nm)[:50], reuse=REUSE["on"], suffix=".csv")
            found[u] = "candidate name answered"
            print(f"   [bucket] {nm}: exists")
        except F.RobotsDisallowed:
            print(f"   [bucket] {nm}: robots.txt does not allow it")
        except Exception as e:
            print(f"   [bucket] {nm}: {str(e)[:60]}")
    return found


def find_csvs() -> dict:
    """-> {csv url: text}: the LGA CSV files reachable from the official pages (one hop through the dataset pages) and, above all, the QPS public bucket."""
    found, hop = {}, {}
    for k, page in enumerate(PAGES):
        for t, u in links_of(page, f"p{k}"):
            if re.search(r"\.csv(?:[?#]|$)", u, re.I):
                found.setdefault(u, t)
            elif re.search(r"/dataset/[^/?#]*(lga|victim)", u, re.I):
                hop.setdefault(u.split("?")[0], t)
    for k, u in enumerate(sorted(hop)[:10]):
        for t, v in links_of(u, f"d{k}"):
            if re.search(r"\.csv(?:[?#]|$)", v, re.I):
                found.setdefault(v, t or hop[u])
    for u, t in s3_files().items():
        found.setdefault(u, t)
    return found


def trailing_check(data: bytes, label: str):
    """Every QPS data row has ONE FIELD MORE than the header names (the header lists 94 columns, the rows hold 95 fields): the LAST value column has no label. Read with index_col=False the labels
    line up with the first fields and that last column is dropped. This classifies the extra field (empty / a number = an unlabelled column / anything else stops the run); the alignment of the
    labels is tested separately (alignment_check)."""
    import csv
    rows = csv.reader(io.StringIO(data.decode("utf-8-sig", errors="replace")))
    n = len(next(rows))
    equal = empty = numeric = other = bad_len = 0
    for r in rows:
        if len(r) == n:
            equal += 1
        elif len(r) == n + 1:
            x = r[-1].strip()
            if not x:
                empty += 1
            elif re.fullmatch(r"-?\d+(\.\d+)?", x):
                numeric += 1
            else:
                other += 1
        else:
            bad_len += 1
    if other or bad_len:
        sys.exit(f"[stop] {label}: {other} row(s) have a non-numeric field beyond the header and {bad_len} row(s) have another length: the layout is not the one assumed")
    note = (f"{numeric:,} rows have one extra NUMERIC field (a last column without a header label, not read), {empty:,} an empty one, {equal:,} none" if numeric else
            f"{empty:,} rows have one empty trailing field, {equal:,} none")
    print(f"[layout] {label}: the header names {n} columns; {note}")


def alignment_check(df: pd.DataFrame, label: str):
    """The labels must sit over the right values: the 'Assault' total must equal the sum of its components (Grievous, Serious, Serious (Other), Common) in at least 99% of the rows."""
    cols = [str(c) for c in df.columns]
    tot = next((c for c in cols if c.strip().lower() == "assault"), None)
    comp = [c for c in cols if re.match(r"(grievous assault|serious assault|common assault)", c.strip(), re.I)]
    if not tot or len(comp) < 3:
        print(f"[alignment] {label}: the Assault total and its components are not both present, so the alignment is judged by the reconciliation with the statewide file")
        return
    t = pd.to_numeric(df[tot], errors="coerce")
    c = df[comp].apply(pd.to_numeric, errors="coerce").sum(axis=1)
    ok = float(((t - c).abs() <= 1e-4).mean())          # counts are whole numbers; the rates file carries rounded decimals, and one offence is always far above 1e-4 of a rate
    if ok < 0.99:
        sys.exit(f"[stop] {label}: the Assault total equals the sum of its components in only {ok:.1%} of the rows: the labels are not over the right values")
    print(f"[alignment] {label}: the Assault total equals the sum of its {len(comp)} components in {ok:.2%} of {len(df):,} rows, so the labels sit over the right values")


def read_csv_bytes(data: bytes, label: str = "") -> pd.DataFrame:
    if label:
        trailing_check(data, label)
    for enc in ("utf-8-sig", "latin-1"):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", pd.errors.ParserWarning)          # the dropped trailing field is checked above
                return pd.read_csv(io.BytesIO(data), encoding=enc, dtype=str, low_memory=False, index_col=False)
        except UnicodeDecodeError:
            continue
    sys.exit("[stop] the CSV could not be decoded as UTF-8 or Latin-1")


MONTH_FORMATS = ["%b%y", "%b-%y", "%B-%y", "%b %y", "%B %y", "%b-%Y", "%b %Y", "%B %Y", "%B-%Y", "%Y-%m", "%Y-%m-%d", "%Y/%m", "%d/%m/%Y", "%m/%Y", "%Y%m"]


def parse_months(col: pd.Series):
    """-> (datetimes, format). A label such as 'Jan-23' is ambiguous (month-year or month-day), so the library's guess is not used: explicit formats are tried and the first that reads
    at least 99% of the values wins; if none does, the result is empty and the caller must stop."""
    vals = col.dropna().astype(str).str.strip()
    for fmt in MONTH_FORMATS:
        d = pd.to_datetime(vals, format=fmt, errors="coerce")
        if len(vals) and d.notna().mean() >= 0.99:
            out = pd.to_datetime(col.astype(str).str.strip(), format=fmt, errors="coerce")
            return out, fmt
    return pd.Series(pd.NaT, index=col.index), None


def describe(data: bytes, name: str):
    df = read_csv_bytes(data)
    print(f"   {len(df):,} rows x {len(df.columns)} columns; first columns: {list(df.columns)[:10]}")
    print(f"   homicide-like columns: {[c for c in df.columns if HOMICIDE.search(str(c))]}")
    lga = next((c for c in df.columns if re.search(r"lga|local government", str(c), re.I)), df.columns[0])
    mon = next((c for c in df.columns if re.search(r"month|date|year", str(c), re.I)), None)
    print(f"   LGA column {lga!r}: {df[lga].nunique()} distinct, e.g. {sorted(map(str, df[lga].dropna().unique()))[:8]}")
    if mon:
        d, fmt = parse_months(df[mon])
        print(f"   month column {mon!r}: raw examples {list(df[mon].dropna().unique()[:3])} ... {list(df[mon].dropna().unique()[-2:])}; format read: {fmt}; "
              + (f"{int(d.notna().sum()):,} of {len(df):,} parsed, {d.min():%Y-%m} to {d.max():%Y-%m}" if fmt else "NO explicit format reads the column: the labels must be looked at"))
        hc = [c for c in df.columns if HOMICIDE.search(str(c))]
        if hc and fmt:
            num = df[hc].apply(pd.to_numeric, errors="coerce")
            tot = num.groupby(d.dt.year).sum(min_count=1)
            print("   statewide yearly sums of the homicide columns (all LGAs), last 4 calendar years in the file:")
            print(tot.tail(4).round(1).to_string(max_colwidth=22))
    print(df.head(3).T.head(14).to_string(max_colwidth=30))


def cmd_inspect():
    files = find_csvs()
    print(f"[files] {len(files)} CSV links found on the official pages:")
    for u, t in files.items():
        print(f"   {unquote(u)[:140]}  {t[:40]}")
    pick = [u for u in files if re.search(r"(LGA_Reported_Offences_(Number|Rates)|QLD_Reported_Offences_Number)\.csv", unquote(u), re.I)]
    for u in pick[:5]:
        nm = unquote(u).rsplit("/", 1)[-1]
        print(f"\n===== {nm} =====", flush=True)
        try:
            t0 = time.time()
            data = FETCH.get(u, "qld_" + re.sub(r"[^A-Za-z0-9]+", "_", nm)[:50], reuse=REUSE["on"], suffix=".csv")
            print(f"   downloaded {len(data) / 1e6:.1f} MB in {time.time() - t0:.0f} s", flush=True)
            describe(data, nm)
        except F.RobotsDisallowed:
            print("   [robots] not allowed automatically: save it by hand as manual_qld_<name>.csv in " + str(RAW))
        except Exception as e:
            print(f"   [skip] {str(e)[:120]}")
    for p in sorted(RAW.glob("manual_qld*")):
        print(f"\n===== manual file {p.name} =====")
        describe(p.read_bytes(), p.name)
    if not pick:
        print("   no LGA file link found: save the 'LGA Reported Offences Number' and 'LGA Reported Victim Numbers' CSVs by hand as manual_qld_*.csv in " + str(RAW))
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


LOW_COUNT = F.LOW_COUNT
STATE = "Queensland"
RECON_REL, RECON_ABS = 0.05, 3        # DECISION: the LGAs add up to the statewide file within max(5%, 3)
BAND_REL, BAND_ABS = 0.25, 3          # DECISION: QPS offences and ABS victims agree within max(25%, 3)
POP_TOL = 0.05                        # DECISION: the QPS implied population and the ABS estimate agree within 5%
MANUAL_MATCH: dict = {}               # verified correspondences {QPS name: ABS name}, added only from evidence
NON_LGA = re.compile(r"unknown|unallocated|not stated|queensland|total|state", re.I)        # rows of the file that are not a council area
LINES = {"murder": r"^homicide \(murder\)$", "manslaughter": r"^manslaughter(?!.*driv.*(?<!striking causing death)$)", "attempted_murder": r"^attempted murder$",
         "other_homicide": r"^other homicide$", "conspiracy": r"^conspiracy to murder$", "driving_death": r"^driving causing death$"}


def load_abs_population(links, get):
    return _load_abs_population(links, get, open_excel_stub)


def open_excel_stub(data: bytes, suffix: str = ".xlsx") -> pd.ExcelFile:
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


def load_qps(data: bytes, what: str, area: bool = True):
    """-> frame with columns area (or None), month (datetime) and the numeric offence columns; the layout is checked, not assumed."""
    df = read_csv_bytes(data, what)
    alignment_check(df, what)
    mcol = next((c for c in df.columns if df[c].astype(str).str.fullmatch(r"[A-Za-z]{3}\d{2}").mean() >= 0.99), None)
    if mcol is None:
        print(f"[layout] {what}: no column holds month codes such as JAN01; the first rows:")
        print(df.head(4).T.head(8).to_string(max_colwidth=26))
        sys.exit(f"[stop] {what}: the month column was not found")
    month = pd.to_datetime(df[mcol].astype(str).str.title(), format="%b%y", errors="coerce")
    acol = None
    if area:
        acol = next((c for c in df.columns if c != mcol and df[c].astype(str).str.contains(r"[A-Za-z]{4}", regex=True).mean() >= 0.99 and pd.to_numeric(df[c], errors="coerce").isna().mean() >= 0.99), None)
        if acol is None:
            sys.exit(f"[stop] {what}: no column of area names was found next to the month codes (columns: {list(df.columns)[:6]})")
    num = df.drop(columns=[c for c in (mcol, acol) if c]).apply(pd.to_numeric, errors="coerce")
    out = num.assign(_month=month.values)
    out["_area"] = df[acol].astype(str).str.strip().values if acol else "Queensland"
    return out


def pick_lines(cols):
    got = {}
    for k, rx in LINES.items():
        m = [c for c in cols if re.search(rx, str(c).strip(), re.I) and not str(c).startswith("_")]
        if k == "manslaughter":
            m = [c for c in cols if re.match(r"manslaughter", str(c).strip(), re.I) and "driving causing death" not in str(c).lower().replace("striking causing death", "")]
        got[k] = m
    for need in ("murder", "manslaughter"):
        if not got[need]:
            sys.exit(f"[stop] no column for {need!r} among the QPS columns (columns: {[str(c) for c in cols][:12]})")
    return got


def annual_sums(frame: pd.DataFrame, lines: dict) -> dict:
    """-> {(area, year): {line: n}} summed over the 12 months of each COMPLETE calendar year of the area."""
    d = frame.assign(_year=frame["_month"].dt.year)
    out = {}
    for (a_, y), g in d.groupby(["_area", "_year"]):
        if g["_month"].nunique() == 12:
            out[(a_, int(y))] = {k: (float(g[c].sum().sum()) if len(c) else 0.0) for k, c in lines.items()}
    return out


def cmd_build():
    from bs4 import BeautifulSoup
    files = find_csvs()
    pick = lambda nm: next((u for u in files if unquote(u).rsplit("/", 1)[-1].lower() == nm.lower()), None)
    u_num, u_rate, u_qld = pick("LGA_Reported_Offences_Number.csv"), pick("LGA_Reported_Offences_Rates.csv"), pick("QLD_Reported_Offences_Number.csv")
    if not u_num:
        sys.exit("[stop] LGA_Reported_Offences_Number.csv is not among the files of the QPS bucket")
    get = lambda u, nm: FETCH.get(u, "qld_" + nm, reuse=REUSE["on"], suffix=".csv")
    print("[download] the QPS bucket is slow (minutes per file); the files are kept for the next run", flush=True)
    num = load_qps(get(u_num, "lga_offences_number"), "LGA offences number")
    cols = [c for c in num.columns if not str(c).startswith("_")]
    lines = pick_lines(cols)
    print(f"[columns] murder: {lines['murder']}; manslaughter: {lines['manslaughter']}; kept apart: attempted {lines['attempted_murder']}, other homicide {lines['other_homicide']}, conspiracy {lines['conspiracy']}, driving {lines['driving_death']}")
    ann = annual_sums(num, lines)
    areas = sorted({a_ for a_, _ in ann})
    years = sorted({y for _, y in ann})
    print(f"[qps] {len(areas)} areas, complete calendar years {years[0]}-{years[-1]}; months in the file {num['_month'].min():%Y-%m} to {num['_month'].max():%Y-%m}")
    state_line = None
    if u_qld:
        try:
            q = load_qps(get(u_qld, "qld_offences_number"), "Queensland offences number", area=False)
            state_line = {y: v for (_, y), v in annual_sums(q, lines).items()}
            print(f"[qld line] statewide file: complete years {min(state_line)}-{max(state_line)}")
        except SystemExit as e:
            print(f"[qld line] the statewide file could not be used ({e}); every row is tier B")
    # population
    html = FETCH.get(ABS_POP_PAGE, "abs_page_regional_population", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    links = [(a.get_text(" ", strip=True), urljoin(ABS_POP_PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.xlsx?(?:[?#]|$)", a["href"], re.I)]
    erp, lgas, abs_name = load_abs_population(links, lambda u, n: FETCH.get(u, n, reuse=REUSE["on"], suffix=".xlsx"))
    qld = {c: v[0] for c, v in lgas.items() if v[1] == STATE}
    by_norm = {}
    for c, n in qld.items():
        by_norm.setdefault(norm(n), []).append(c)
    dup = {k: v for k, v in by_norm.items() if len(v) > 1}
    if dup:
        sys.exit(f"[stop] two ABS LGAs of {STATE} share one normalised name: {dup}")
    match, nonlga, unmatched = {}, [], []
    for n in areas:
        key = norm(MANUAL_MATCH.get(n, n))
        if key in by_norm:
            match[n] = by_norm[key][0]
        elif NON_LGA.search(n):
            nonlga.append(n)
        else:
            unmatched.append(n)
    hom = lambda a_, y: ann.get((a_, y), {}).get("murder", 0) + ann.get((a_, y), {}).get("manslaughter", 0)
    bad = [n for n in unmatched if any(hom(n, y) > 0 for y in years)]
    print(f"[abs] population from {abs_name}: {len(qld)} LGAs in {STATE}; [names] {len(match)} of {len(areas)} QPS areas matched; non-LGA categories: {nonlga or 'none'}; unmatched without homicides: {[n for n in unmatched if n not in bad] or 'none'}")
    if bad:
        sys.exit(f"[stop] {len(bad)} QPS area(s) with homicides are neither matched to an ABS LGA of {STATE} nor a known non-LGA category: {bad}. Add the verified correspondence to MANUAL_MATCH (no guessing).")
    # (1) the areas against the statewide file
    recon = {}
    for y in years:
        tot = sum(hom(a_, y) for a_ in areas)
        if not state_line or y not in state_line:
            recon[y] = ("none", 0.0, tot)
            continue
        top = state_line[y]["murder"] + state_line[y]["manslaughter"]
        d = tot - top
        recon[y] = ("equal" if d == 0 else "close" if abs(d) <= max(RECON_REL * top, RECON_ABS) else "far", d, top)
    print("[reconciliation] the areas against the statewide file, by year: " + str(pd.Series([v[0] for v in recon.values()]).value_counts().to_dict()))
    # (2) the ABS state victims
    abs_state, pth = {}, OUT.parent / "australia_homicide_rate.csv"
    if pth.exists():
        d0 = pd.read_csv(pth, dtype=str, keep_default_na=False)
        abs_state = {int(r.year): float(r.homicide_cases) for r in d0[d0["unit"] == STATE].itertuples()}
        print(f"[abs state] {len(abs_state)} years of ABS murder + manslaughter victims for {STATE} read from {pth.name}")
    else:
        print(f"[abs state] {pth.name} is not next to this script: the state-level confirmation is skipped (all rows tier B)")
    total = {y: sum(hom(a_, y) for a_ in areas) for y in years}
    ratio = {y: total[y] / abs_state[y] for y in years if abs_state.get(y)}
    if ratio:
        print(f"[cross-verification] QPS offences / ABS victims for {STATE}: median {pd.Series(ratio).median():.2f} over {len(ratio)} years (range {min(ratio.values()):.2f}-{max(ratio.values()):.2f})")
    # (3) the implied population from the rates file
    implied = {}
    if u_rate and REUSE["rates"]:
        try:
            rt = load_qps(get(u_rate, "lga_offences_rates"), "LGA offences rates")
            common = [c for c in cols if c in rt.columns]
            cn = num.assign(_s=num[common].sum(axis=1))[["_area", "_month", "_s"]].rename(columns={"_s": "n"})
            rr = rt.assign(_s=rt[common].sum(axis=1))[["_area", "_month", "_s"]].rename(columns={"_s": "r"})
            m = cn.merge(rr, on=["_area", "_month"]).assign(_year=lambda x: x["_month"].dt.year)
            for (a_, y), g in m.groupby(["_area", "_year"]):
                if g["_month"].nunique() == 12 and g["r"].sum() > 0:
                    implied[(a_, int(y))] = g["n"].sum() / g["r"].sum() * 1e5
            print(f"[rates] implied populations for {len(implied)} area-years from the rates file")
        except SystemExit as e:
            print(f"[rates] the rates file could not be used ({e}); the population check is skipped")
    else:
        print("[rates] skipped (--no-rates or the file is not in the bucket): the population check is not made")
    rows, small, nopop = [], 0, 0
    for n, code in match.items():
        for y in years:
            if (n, y) not in ann:
                continue
            pop = erp.get((code, y))
            if pop is None:
                nopop += 1
                continue
            if pop < F.MIN_POP:
                small += 1
                continue
            v = ann[(n, y)]
            cnt = int(v["murder"] + v["manslaughter"])
            rec, rdiff, rtop = recon[y]
            va = abs_state.get(y)
            agree = None if va is None else bool(abs(total[y] - va) <= max(BAND_REL * va, BAND_ABS))
            ip = implied.get((n, y))
            pdiff = None if ip is None else (ip - pop) / pop
            pop_ok = None if pdiff is None else bool(abs(pdiff) <= POP_TOL)
            tier = "A" if (rec in ("equal", "close") and agree is True and pop_ok is not False) else "B"
            checks = [("the areas add up exactly to the statewide file" if rec == "equal" else f"the areas are within {abs(rdiff):g} offence(s) of the statewide file ({rtop:g})" if rec == "close"
                       else f"the areas DIFFER from the statewide file by {rdiff:+g} ({rtop:g})" if rec == "far" else "no statewide file to reconcile with"),
                      (f"Queensland total {total[y]:g} offences against {va:g} ABS victims: {'within' if agree else 'OUTSIDE'} the band of max(25%, 3)" if va is not None else "no ABS state-level figure for this year"),
                      (f"the QPS implied population is {pdiff:+.1%} from the ABS estimate: {'within' if pop_ok else 'OUTSIDE'} 5%" if pdiff is not None else "no QPS implied population for this LGA-year")]
            rows.append({"country": "Australia", "unit": qld[code], "unit_local": n, "unit_code": code, "admin_level": "admin2", "unit_type": "local government area", "parent_unit": STATE,
                         "year": y, "homicide_cases": cnt, "population": int(round(pop)), "homicide_rate_per_100k": cnt / pop * 1e5, "flag_low_count": cnt < LOW_COUNT,
                         "flag_outlier_year": False, "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "includes_manslaughter",
                         "validation": "; ".join(checks),
                         "indicator": "QPS reported offences: Homicide (Murder) + Manslaughter (excl. by driving) + Manslaughter Unlawful Striking Causing Death (other homicide, attempts, conspiracy and driving causing death excluded)",
                         "population_method": "ABS estimated resident population at 30 June of the year, persons",
                         "data_notes": "the unit is the reported offence, not the victim; calendar year summed from the monthly counts; the file is revised monthly; the last column of each row has no header label in the file and is not read (alignment tested)",
                         "source_homicide": u_num, "source_population": ABS_POP_PAGE, "retrieved": FETCH.retrieved_on(u_num, ABS_POP_PAGE),
                         "murder_offences": int(v["murder"]), "manslaughter_offences": int(v["manslaughter"]), "attempted_murder_offences": int(v.get("attempted_murder", 0)),
                         "other_homicide_offences": int(v.get("other_homicide", 0)), "abs_state_victims": va,
                         "population_qps_implied": None if ip is None else int(round(ip)), "population_diff_pct": None if pdiff is None else round(pdiff * 100, 2)})
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    print(f"[scope] {df['unit'].nunique()} LGAs with at least one year of {F.MIN_POP:,}+ residents; {small} LGA-years left out below that population; {nopop} without an ABS estimate")
    pdf = df["population_diff_pct"].dropna()
    if len(pdf):
        print(f"[population check] QPS implied population against the ABS: median {pdf.median():+.2f}%, within 5% in {(pdf.abs() <= 5).mean():.0%} of {len(pdf)} LGA-years")
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "australia")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    last = int(df.year.max())
    print(f"\nLatest year {last}:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k", "reliability_tier"]].round(2).head(15).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} LGAs, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--no-rates", action="store_true", help="skip the 14.5 MB rates file (no independent population check)")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    REUSE["rates"] = not a.no_rates
    cmd_inspect() if a.cmd == "inspect" else cmd_build()