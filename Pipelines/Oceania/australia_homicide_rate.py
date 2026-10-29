#!/usr/bin/env python3
"""
Australia - homicide per 100,000 residents, by state and territory (two official families, cross-verified).

POLICE (numerator): Australian Bureau of Statistics (ABS), "Recorded Crime - Victims" (Excel data cubes, one release per year, calendar years from 1993): victims of
            crime recorded by the state and territory police under the National Crime Recording Standard. The cube lists "Homicide" (murder + attempted murder +
            manslaughter) and, separately, Murder, Attempted murder and Manslaughter. This script counts MURDER + MANSLAUGHTER victims (the like-for-like
            partner of deaths by assault) and keeps the attempted murder victims as an extra column; the ABS footnote on the category is copied into the notes.
            The unit is the VICTIM (definition_flags includes_manslaughter;counts_victims).
HEALTH (cross-check): ABS "Causes of Death, Australia": underlying cause "Assault (X85-Y09)", persons, one workbook per state and territory, year of registration
            (2015 onwards). Status of each year (final / revised / preliminary) is read from the name of the ABS revisions workbook in the release listing.
POPULATION: ABS "National, state and territory population" (3101.0, table 4): estimated resident population at 30 June (the June quarter), persons; mid-year, so
            population_age_years = 0.
CHECKS      (1) the 8 states and territories add up to the Australia cube for murder + manslaughter within max(5%, 3 victims) (the ABS national table is NOT an
            exact sum of the states: the differences are a few victims with random signs and the footnotes give no reason; the difference is written into the rows); (2) a count may not be a rate: the first block of each line must hold whole numbers; (3) police victims and health deaths are compared per
            state and year: they agree when the difference is within max(25%, 3) of the police count (they measure different things: incidents recorded against
            deaths registered); (4) population: the June estimate must exist for the year. Tier A needs (1) within the tolerance, (3) agreeing, a final or revised health year, and a
            June population; tier B: one family only, preliminary health data, a difference between states and Australia, or disagreement of the families.
            Never tier C: nothing here is contradicted by a hard check. The text in `validation` is built from these results.
BELOW STATE LEVEL (later): each state's police publish local government area data (NSW BOCSAR, Victoria CSA, Queensland, Western Australia, South Australia ...).

Folders:    this script sits in <repo>/Pipelines/Oceania/ ; downloads go to <repo>/Data/Raw/Oceania/Australia/ ; the one output is australia_homicide_rate.csv next to it.
Commands:   python australia_homicide_rate.py inspect | build        Option: --reuse (use the files saved by an earlier run)
Needs:      pip install pandas requests beautifulsoup4 openpyxl
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
if getattr(F, "REVISION", 0) < 13:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Australia")       # raw downloads -> Data/Raw/Oceania/Australia/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
LOW_COUNT = F.LOW_COUNT
PAGES = {
    "crime": "https://www.abs.gov.au/statistics/people/crime-and-justice/recorded-crime-victims/latest-release",
    "deaths": "https://www.abs.gov.au/statistics/health/causes-death/causes-death-australia/latest-release",
    "population": "https://www.abs.gov.au/statistics/people/population/national-state-and-territory-population/latest-release",
}
XLSX = re.compile(r"\.xlsx?(?:[?#]|$)", re.I)
HOMICIDE = re.compile(r"homicide|murder|manslaughter|assault", re.I)


def page_links(url: str, tag: str) -> list[tuple[str, str]]:
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(url, f"abs_page_{tag}", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    except F.RobotsDisallowed:
        print(f"   [robots] {url} does not allow automated reading")
        return []
    except Exception as e:
        print(f"   [skip] {url}: {e}")
        return []
    soup = BeautifulSoup(html, "html.parser")
    return [(a.get_text(" ", strip=True), urljoin(url, a["href"].strip())) for a in soup.find_all("a", href=True) if XLSX.search(a["href"])]


def show_cube(data: bytes, label: str, max_sheets: int = 12, head_sheets: int = 1):
    xl = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    print(f"   sheets ({len(xl.sheet_names)}): {xl.sheet_names[:24]}")
    for k, sh in enumerate(xl.sheet_names[:max_sheets]):
        raw = pd.read_excel(io.BytesIO(data), sheet_name=sh, header=None, engine="openpyxl", dtype=object)
        title = next((str(v) for v in raw.iloc[:6, 0].dropna()), "")
        print(f"   --- sheet '{sh}': {raw.shape}; title: {title[:110]}")
        first = raw.iloc[:, :2].fillna("").astype(str)
        hit = raw[[bool(HOMICIDE.search(" ".join(row))) for row in first.itertuples(index=False)]]
        if len(hit):
            print(hit.iloc[:10, :10].to_string(max_colwidth=34, header=False))
        if k < head_sheets or not len(hit) and re.search(r"table\s*(9|4)\b|data1", sh, re.I):
            print(raw.iloc[:14, :9].to_string(max_colwidth=30, header=False))


# which files of each page to download for a structure sample (matched against the decoded address)
SAMPLES = {
    "crime": re.compile(r"states and territories|Tables 1 to 8", re.I),
    "deaths": re.compile(r"Underlying causes of death \((Australia|New South Wales)\)", re.I),
    "population": re.compile(r"/310104\.xlsx", re.I),
}


def cmd_inspect():
    found = {}
    for key, url in PAGES.items():
        links = page_links(url, key)
        found[key] = [(t, u, unquote(u)) for t, u in links]
        print(f"\n[{key}] {url}: {len(links)} Excel links")
        for t, u, d in found[key]:
            print(f"   {d.rsplit('/', 1)[-1][:92]:92} {t[-22:]}")
    for key, items in found.items():
        for t, url, dec in items:
            if not SAMPLES[key].search(dec):
                continue
            nm = dec.rsplit("/", 1)[-1]
            print(f"\n===== [{key}] {nm} =====", flush=True)
            try:
                data = FETCH.get(url, f"abs_{key}_" + re.sub(r"[^A-Za-z0-9]+", "_", nm)[:46], reuse=REUSE["on"], suffix=".xlsx")
            except F.RobotsDisallowed:
                print("   [robots] the host does not allow automated downloads of this file; save it by hand as manual_<name>.xlsx in " + str(RAW))
                continue
            except Exception as e:
                print(f"   [skip] {e}")
                continue
            show_cube(data, nm, head_sheets=2 if key != "crime" else 1)
    for p in sorted(RAW.glob("manual_*.xlsx")):
        print(f"\n===== manual file {p.name} =====")
        show_cube(p.read_bytes(), p.name)
    print("\n[inspect only] nothing written; paste this output and the parsers (police, health, population) will be written against it")


STATES = ["New South Wales", "Victoria", "Queensland", "South Australia", "Western Australia", "Tasmania", "Northern Territory", "Australian Capital Territory"]
ABBR = {"NSW": "New South Wales", "Vic": "Victoria", "Vic.": "Victoria", "Qld": "Queensland", "SA": "South Australia", "WA": "Western Australia", "Tas": "Tasmania",
        "Tas.": "Tasmania", "NT": "Northern Territory", "ACT": "Australian Capital Territory"}
TERRITORIES = {"Northern Territory", "Australian Capital Territory"}
OFFENCES = {"homicide": "homicide", "murder": "murder", "attempted murder": "attempted_murder", "manslaughter": "manslaughter"}
BAND_REL, BAND_ABS = 0.25, 3          # DECISION: police victims and health deaths agree within max(25%, 3)
RECON_REL, RECON_ABS = 0.05, 3        # DECISION: the 8 states add up to the Australia cube within max(5%, 3) for murder + manslaughter (the ABS national table is not an exact sum)


def clean_label(v) -> str:
    return "" if v is None or (isinstance(v, float) and pd.isna(v)) else re.sub(r"\s*\([a-z]\)$", "", str(v).strip())


def marker(v) -> str:
    m = re.search(r"\(([a-z])\)$", str(v).strip())
    return m.group(1) if m else ""


def jurisdiction(v):
    c = clean_label(v)
    return c if c in STATES else ABBR.get(c)


def heading_state(v):
    """A heading row names its state or territory somewhere in the text ('New South Wales', 'Victims, Victoria (number)', ...)."""
    t = str(v)
    for n in sorted(STATES, key=len, reverse=True):
        if re.search(r"\b" + re.escape(n) + r"\b", t, re.I):
            return n
    return jurisdiction(v)


def year_of(v):
    """A calendar year in a header cell; a footnote marker may follow it: 2019, 2019.0, '2019 ', '2019(a)'."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    m = re.fullmatch(r"((?:19|20)\d{2})(?:\.0)?\s*(?:\([a-z]\)\s*)*", str(v).strip())
    return int(m.group(1)) if m else None


def num(v):
    """ABS conventions: 'np' not published -> missing; a dash is a nil (0); anything else must be a number."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return float("nan")
    t = str(v).strip().replace(",", "")
    if t in ("—", "–", "-", "- "):
        return 0.0
    try:
        return float(t)
    except ValueError:
        return float("nan")


def sheet(data: bytes, name_re: str) -> tuple[str, pd.DataFrame]:
    xl = pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
    nm = next((n for n in xl.sheet_names if re.fullmatch(name_re, n, re.I)), None)
    if nm is None:
        sys.exit(f"[stop] no sheet matching {name_re!r}; the sheets are {xl.sheet_names}")
    return nm, pd.read_excel(io.BytesIO(data), sheet_name=nm, header=None, engine="openpyxl", dtype=object)


def parse_crime(data: bytes, table: str, by_state: bool):
    """-> ({(state, offence, year): value}, {offence: footnote text}). Only the FIRST block of each line is read (a later block holds rates)."""
    nm, raw = sheet(data, table)
    hy = max(range(min(20, len(raw))), key=lambda i: sum(year_of(v) is not None for v in raw.iloc[i]))
    years = {j: year_of(v) for j, v in enumerate(raw.iloc[hy]) if year_of(v) is not None}
    if len(years) < 10:
        sys.exit(f"[stop] {nm}: no header row with years found (best row {hy + 1} has {len(years)} years)")
    first = next((i for i in range(hy + 1, len(raw)) if clean_label(raw.iat[i, 0]).lower() in OFFENCES), None)
    if first is not None:
        unread = [j for j in range(1, raw.shape[1]) if j not in years and not pd.isna(raw.iat[first, j])]
        if unread:
            print(f"[warn] {nm}: {len(unread)} column(s) hold numbers but their header is not a year, so they are NOT read: "
                  + ", ".join(repr(str(raw.iat[hy, j])[:24]) for j in unread[:8]))
    notes, out, seen, state, marks = {}, {}, set(), (None if by_state else "Australia"), {}
    for i in range(hy + 1, len(raw)):
        v0 = raw.iat[i, 0]
        lab = clean_label(v0)
        if not lab:
            if by_state:                                   # the heading names the state in a data column of a row with an empty first cell
                cells = [str(x) for x in raw.iloc[i, 1:] if isinstance(x, str)]
                hs = next((heading_state(c) for c in cells if heading_state(c)), None)
                if hs and len(cells) <= 2:
                    state = hs
            continue
        m = re.match(r"\(([a-z])\)\s*(.+)", str(v0).strip())
        if m:
            notes[m.group(1)] = m.group(2)
            continue
        vals = [raw.iat[i, j] for j in years]
        if by_state and all(pd.isna(x) for x in vals) and heading_state(v0):
            state = heading_state(v0)
            continue
        off = OFFENCES.get(lab.lower())
        if off and state and (state, off) not in seen:
            seen.add((state, off))
            marks[off] = marker(v0)
            for j, y in years.items():
                out[(state, off, y)] = num(raw.iat[i, j])
    if not out:
        print(f"[layout] {nm}: the first 45 rows (first column, and how many cells of the year columns hold a value):")
        for i in range(min(45, len(raw))):
            print(f"   row {i:3d}: {str(raw.iat[i, 0])[:70]!r:74} values: {sum(not pd.isna(raw.iat[i, j]) for j in years)}")
        sys.exit(f"[stop] {nm}: no homicide, murder or manslaughter line found" + (" under a state heading" if by_state else "") + "; the layout above shows what the sheet holds")
    odd = [(k, v) for k, v in out.items() if v == v and abs(v - round(v)) > 1e-9]
    if odd:
        sys.exit(f"[stop] {nm}: a count is not a whole number ({odd[:3]}): the first block of the line is not the numbers block")
    return out, {off: notes.get(mk, "") for off, mk in marks.items()}, notes


def parse_health(data: bytes, state: str):
    """-> {year: deaths} for 'Assault (X85-Y09)', persons, from the 'Table N.2' sheet of a state workbook."""
    nm, raw = sheet(data, r"Table \d+\.2")
    yr = max(range(min(15, len(raw))), key=lambda i: sum(year_of(v) is not None for v in raw.iloc[i]))
    sx = next((i for i in range(min(15, len(raw))) if sum(str(v).strip().lower() == "persons" for v in raw.iloc[i]) >= 3), None)
    if sx is None or sum(year_of(v) is not None for v in raw.iloc[yr]) < 3:
        sys.exit(f"[stop] {state}: sheet {nm} has no year row / 'Persons' row in its first 15 rows")
    cols, cur = [], None
    for j in range(raw.shape[1]):
        cur = year_of(raw.iat[yr, j]) or cur
        if str(raw.iat[sx, j]).strip().lower() == "persons" and cur:
            cols.append((j, cur))
    row = next((i for i in range(len(raw)) if re.fullmatch(r"assault \(x85.{0,3}y09\)", clean_label(raw.iat[i, 0]).lower())), None)
    if row is None:
        sys.exit(f"[stop] {state}: no row 'Assault (X85-Y09)' in {nm}")
    return {y: num(raw.iat[row, j]) for j, y in cols}


def parse_population(data: bytes):
    """-> {(jurisdiction, year): persons at 30 June} from the quarterly ERP time-series workbook (series descriptions in the first rows)."""
    nm, raw = sheet(data, r"Data1")
    sid = next((i for i in range(min(25, len(raw))) if str(raw.iat[i, 0]).strip().lower() == "series id"), None)
    if sid is None:
        sys.exit(f"[stop] {nm}: no 'Series ID' row found")
    names = sorted(STATES, key=len, reverse=True)
    col, chosen = {}, {}
    for j in range(1, raw.shape[1]):
        d0 = str(raw.iat[0, j]) if isinstance(raw.iat[0, j], str) else ""
        d = d0 if re.search(r"estimated resident population", d0, re.I) else " ".join(str(raw.iat[i, j]) for i in range(sid) if not pd.isna(raw.iat[i, j]))
        if re.search(r"\b(fe)?males?\b", d, re.I):               # the sex of the series is in its description: 'Male', 'Female' (the word 'Persons' is also the UNIT of every series)
            continue
        jur = next((n for n in names if n.lower() in d.lower()), None)
        if jur and jur not in col:
            col[jur] = j
            chosen[jur] = (j, d)
    print("[population] series used (column: description):")
    for jur in STATES:
        if jur in chosen:
            print(f"   {jur:30} col {chosen[jur][0]:2d}: {chosen[jur][1][:110]}")
    if set(col) != set(STATES):
        sys.exit(f"[stop] population: series found for {sorted(col)} only; expected all 8 states and territories")
    out = {}
    for i in range(sid + 1, len(raw)):
        d = pd.to_datetime(raw.iat[i, 0], errors="coerce")
        if pd.isna(d) or d.month != 6:
            continue
        for jur, j in col.items():
            v = num(raw.iat[i, j])
            if v == v:
                out[(jur, d.year)] = v
    return out


def get(url: str, name: str) -> bytes:
    return FETCH.get(url, name, reuse=REUSE["on"], suffix=".xlsx")


def cmd_build():
    links = {k: [(t, u, unquote(u)) for t, u in page_links(url, k)] for k, url in PAGES.items()}
    def find(key, rx):
        hit = [(t, u, d) for t, u, d in links[key] if re.search(rx, d, re.I)]
        if not hit:
            sys.exit(f"[stop] no link matching {rx!r} on the {key} page (found: {[d.rsplit('/', 1)[-1] for _, _, d in links[key]][:6]})")
        return hit
    cr_url = find("crime", r"states and territories")[0][1]
    au_url = find("crime", r"Tables 1 to 8")[0][1]
    pop_url = find("population", r"/310104\.xlsx")[0][1]
    cube, notes, all_notes_st = parse_crime(get(cr_url, "abs_crime_states"), r"Table 9", True)
    nat, _, all_notes_au = parse_crime(get(au_url, "abs_crime_australia"), r"Table 1", False)
    pops = parse_population(get(pop_url, "abs_population_310104"))
    # status of each causes-of-death year, read from the name of the revisions workbook: '2022F 2023R 2024PR'
    rev = [d for _, _, d in links["deaths"] if re.search(r"revisions", d, re.I)]
    status = {int(y): ("preliminary" if t == "PR" else "revised" if t == "R" else "final") for y, t in re.findall(r"(\d{4})(PR|R|F)\b", rev[0].rsplit("/", 1)[-1])} if rev else {}
    health, first_final = {}, min(status) if status else None
    for t, u, d in links["deaths"]:
        m = re.search(r"Underlying causes of death \(([^)]+)\)", d)
        if m and m.group(1) in STATES:
            for y, v in parse_health(get(u, "abs_deaths_" + re.sub(r"[^A-Za-z]+", "_", m.group(1))), m.group(1)).items():
                health[(m.group(1), y)] = v
    missing = [s_ for s_ in STATES if not any(k[0] == s_ for k in health)]
    if missing:
        sys.exit(f"[stop] no causes-of-death workbook found for {missing}")
    print(f"[health] deaths by assault for {len(STATES)} states and territories, years {min(y for _, y in health)}-{max(y for _, y in health)}; year status from the ABS revisions workbook: {status or 'not found'}")
    # (1) the 8 states against the Australia cube, for murder + manslaughter (the line used), with the ABS's own noise allowed for
    yrs = sorted({k[2] for k in cube})
    recon = {}
    for y in yrs:
        parts = [cube.get((s_, o, y), float("nan")) for s_ in STATES for o in ("murder", "manslaughter")]
        n = nat.get(("Australia", "murder", y), float("nan")) + nat.get(("Australia", "manslaughter", y), float("nan"))
        if n != n or any(p != p for p in parts):
            recon[y] = ("none", 0, n)
            continue
        d = sum(parts) - n
        recon[y] = ("equal" if d == 0 else "close" if abs(d) <= max(RECON_REL * n, RECON_ABS) else "far", d, n)
    cnt = pd.Series([v[0] for v in recon.values()]).value_counts().to_dict()
    print(f"[reconciliation] murder + manslaughter, sum of the 8 states against Australia, {len(recon)} years: {cnt} "
          f"(equal / within max({RECON_REL:.0%}, {RECON_ABS}) = close / beyond = far); largest difference {max((abs(v[1]) for v in recon.values()), default=0):g} victims")
    for title, nts in (("Table 9 (states)", all_notes_st),):
        print(f"[footnotes] {title}:")
        for k, t in list(nts.items())[:14]:
            print(f"   ({k}) {t[:200]}")
    # series breaks: the footnotes about the National Crime Recording Standard (its implementation years end the break) and about 'no crime' records
    ncrs = {k: t for k, t in all_notes_st.items() if re.search(r"Recording Standard", t, re.I) and re.search(r"implementation|began|finished", t, re.I)}
    nocrime = {k: t for k, t in all_notes_st.items() if re.search(r"no crime", t, re.I) and re.search(r"onwards|from (19|20)\d{2}", t, re.I)}
    break_end = max((int(y) for t in ncrs.values() for y in re.findall(r"(?:19|20)\d{2}", t)), default=None)
    break_note = " | ".join(list(ncrs.values()) + list(nocrime.values()))[:420]
    far = sorted((y, int(v[1])) for y, v in recon.items() if v[0] == "far")
    if far:
        print(f"[reconciliation] years beyond the tolerance (year, sum of states minus Australia): {far}")
    if break_end:
        print(f"[series break] footnotes used: {sorted(ncrs) + sorted(nocrime)}; the recording standard was implemented up to {break_end}, so years up to {break_end} are "
              f"noted as not strictly comparable with later years")
    rows = []
    for s_ in STATES:
        for y in yrs:
            mu, ma, am = cube.get((s_, "murder", y), float("nan")), cube.get((s_, "manslaughter", y), float("nan")), cube.get((s_, "attempted_murder", y), float("nan"))
            pop = pops.get((s_, y))
            if mu != mu or ma != ma or pop is None:
                continue
            cases, pop_i = int(mu + ma), int(round(pop))
            rec, rdiff, rnat = recon[y]
            h = health.get((s_, y))
            h = None if h is None or h != h else h
            agree = None if h is None else bool(abs(h - cases) <= max(BAND_REL * cases, BAND_ABS))
            hs = status.get(y, "final" if (first_final and y < first_final) else "unknown") if h is not None else None
            tier = "A" if (rec in ("equal", "close") and agree is True and hs in ("final", "revised")) else "B"
            checks = [("the 8 states and territories add up exactly to the Australia cube for murder + manslaughter" if rec == "equal" else
                       f"the 8 states and territories are within {abs(rdiff):g} victim(s) of the Australia cube for murder + manslaughter ({rnat:g}): within the ABS's own noise, the footnotes give no reason" if rec == "close" else
                       f"the 8 states and territories DIFFER from the Australia cube by {rdiff:+g} victims ({rnat:g} nationally), beyond the tolerance" if rec == "far" else
                       "murder or manslaughter is not published for every state (np), so the Australia cube cannot be reconciled"),
                      ("health registry: %d deaths by assault (X85-Y09) against %d police victims: %s" % (h, cases, "within the band" if agree else "OUTSIDE the band of max(25%, 3)") if h is not None
                       else "no causes-of-death figure for this year (the ABS release ends earlier): one family only")
                      + (f"; the ABS status of that year is {hs}" if hs else ""),
                      "population: ABS estimated resident population at 30 June"]
            rows.append({
                "country": "Australia", "unit": s_, "unit_local": "", "unit_code": "", "admin_level": "admin1", "unit_type": "territory" if s_ in TERRITORIES else "state",
                "parent_unit": "", "year": y, "homicide_cases": cases, "population": pop_i, "homicide_rate_per_100k": cases / pop_i * 1e5,
                "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": 0.0, "indicator_type": "police_recorded_cases",
                "reliability_tier": tier, "definition_flags": "includes_manslaughter;counts_victims", "validation": "; ".join(checks),
                "indicator": "ABS Recorded Crime - Victims: victims of murder + manslaughter recorded by the state or territory police (attempted murder excluded)",
                "population_method": "ABS estimated resident population at 30 June of the year (June quarter), persons",
                "data_notes": "the unit is the victim, not the incident; ABS footnote on the category: " + (notes.get("homicide") or "see the data cube")
                              + (f"; series break (ABS footnotes): {break_note}" if break_end and y <= break_end else ""),
                "source_homicide": cr_url, "source_population": pop_url, "retrieved": FETCH.retrieved_on(cr_url, pop_url),
                "murder_victims": int(mu), "manslaughter_victims": int(ma), "attempted_murder_victims": None if am != am else int(am),
                "health_assault_deaths": h, "health_year_status": hs or "", "health_agrees": agree, "health_over_police": None if h is None or cases == 0 else round(h / cases, 3)})
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    small = df[df["population"] < F.MIN_POP]
    if len(small):
        print("[population] state-years below 100,000 residents (impossible for an Australian state: a series was mapped to the wrong column):")
        print(small[["unit", "year", "population"]].to_string(index=False))
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "australia")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    last = int(df.year.max())
    print(f"\nLatest year {last}:")
    print(df[df.year == last][["unit", "homicide_cases", "population", "homicide_rate_per_100k", "health_assault_deaths", "reliability_tier"]].round(2).to_string(index=False))
    h = df.dropna(subset=["health_over_police"])
    if len(h):
        print(f"\n[cross-verification] health deaths / police victims over {len(h)} state-years: median {h['health_over_police'].median():.2f}; "
              f"the two families agree (within max({BAND_REL:.0%}, {BAND_ABS})) in {h['health_agrees'].astype(bool).mean():.0%} of them")
        t = h.groupby("unit").agg(years=("year", "size"), police=("homicide_cases", "sum"), health=("health_assault_deaths", "sum"),
                                  agree=("health_agrees", lambda x: f"{x.astype(bool).mean():.0%}"))
        t["health_over_police"] = (t["health"] / t["police"]).round(2)
        print(t.to_string())
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} states and territories, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()