#!/usr/bin/env python3
"""
Lesotho - murder cases per 100,000 residents, by DISTRICT (10 districts; the 11 policing districts with Maseru Urban + Maseru Rural = Maseru), calendar years of the Bureau of Statistics crime reports (2019-2022 confirmed).

POLICE (numerator): Lesotho Bureau of Statistics (BOS), "Crime Statistics Report <year>" (the data are the Lesotho Mounted Police Service's reported cases): the appendix table "Number of Reported Serious Cases of Crime by
            Policing Districts" gives, per policing district, the number of cases of each serious crime; the column "Murder" is used (the column whose total equals the national murder count printed in Table 2.1; "Attempted
            Murder" is a different column). homicide_cases = murder CASES reported to the police. The 11 policing districts are the 10 administrative districts with Maseru split into Maseru Urban and Maseru Rural: the two are added.
POPULATION: 2016 Population and Housing Census (10 April 2016), by district, from a Bureau of Statistics file: a census report or table saved in the raw folder as manual_census2016.pdf / .xlsx / .csv (the script has no address
            for it: the Bureau's site gives none that could be confirmed). The column of district totals is found by itself: the one whose ten districts add up to the national census total of 2,007,201. The census figure
            is used unchanged for every year; its distance in years (the absolute value of year + 0.5 - 2016.27: the census is AFTER the report of 2015 and before the others) goes into population_age_years and exceeds the project limit of 3.5 years from 2020 on, which the notes say.
CHECKS      (1) the policing districts add up to the report's total row; (2) the total of the murder column equals the national murder count of Table 2.1; (3) the percentage table of the same report (Table 2.2) agrees with the
            counts to within 0.1 point for every district; (4) the ten census populations add up to 2,007,201. The tier is B: no independent confirmation exists and the denominator is the 2016 census.

Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/Lesotho/ ; the one output is lesotho_homicide_rate.csv next to the script.
Commands:   python lesotho_homicide_rate.py inspect | build          Options: --reuse (use the saved files)
Needs:      pip install pandas requests pdfplumber openpyxl truststore
"""
import argparse
import io
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version (revision 14)")

REVISION = 10
P = F.paths(__file__, "Lesotho")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=2)
REUSE = {"on": False}
REPORT = "https://www.bos.gov.ls/BoS_reports/Copy of Demography/{year}_Crime_Statistics_report.pdf"
YEARS = range(2014, 2024)         # the years tried: a missing one (HTTP 404) is skipped
CENSUS_TOTAL = 2_007_201          # the 2016 census total of Lesotho (it identifies the right column of the district table)
CENSUS_MID = 2016.27              # 10 April 2016
LOW_COUNT = F.LOW_COUNT
DISTRICTS = ["Butha-Buthe", "Leribe", "Berea", "Maseru", "Mafeteng", "Mohale's Hoek", "Quthing", "Qacha's Nek", "Mokhotlong", "Thaba-Tseka"]
NUMTOK = r"-?\d[\d,]*(?:\.\d+)?"


def nm(x: str) -> str:
    n = re.sub(r"[^a-z]", "", str(x).lower())
    return n.replace("botha", "butha").replace("bothe", "buthe")                  # the report writes Botha-Bothe, the census Butha-Buthe


DISTRICT_BY_NAME = {nm(d): d for d in DISTRICTS}
POLICING_TO_DISTRICT = {"maseruurban": "Maseru", "maserurural": "Maseru"}      # the one split: the two Maseru policing districts are the Maseru district
ROW = re.compile(r"^\s*([A-Za-z][A-Za-z' .\-]+?)\s+((?:" + NUMTOK + r"\s+){3,}" + NUMTOK + r")\s*$")


def tokens(text: str) -> list:
    return [float(x.replace(",", "")) if "." in x else int(x.replace(",", "")) for x in re.findall(NUMTOK, text)]


def pdf_pages(data: bytes) -> list:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def policing_rows(page_text: str, ncols: int):
    """The rows of a policing-district table of this page: {normalised name: numbers}, with the 'Total' row; only rows with exactly ncols numbers."""
    out = {}
    for ln in page_text.splitlines():
        ln = re.sub(r"(?<=\s)[-\u2013\u2014](?=\s|$)", "0", ln)                 # a standalone dash is a zero (the reports of some years write zeros that way)
        m = ROW.match(ln)
        if not m:
            continue
        nums = tokens(m.group(2))
        if len(nums) == ncols:
            out[nm(m.group(1))] = nums
    return out


def parse_report(pages: list, year: int):
    """-> ({district: murder cases}, notes, national murder) for one report. The table of counts is found by its STRUCTURE (no caption needed): a page with the rows of the 11 policing districts and a 'Total' row, all whole
    numbers, in which exactly one column has both its total row and the sum of its districts equal to the national murder count of Table 2.1 (tables of 11, 12 or 13 columns, which depend on the year)."""
    nat = None
    for t in pages:
        m = re.search(r"^\s*Murder\s+([\d,]+)\s+(\d{1,2}\.\d)\s*$", t, re.M)
        if m:
            nat = int(m.group(1).replace(",", ""))
            break
    if nat is None:
        sys.exit(f"[stop] {year}: the national murder count of Table 2.1 ('Murder 944 7.9') was not found")
    counts = None
    for k, t in enumerate(pages):
        for ncols in (11, 12, 13):
            rows = policing_rows(t, ncols)
            dist = {n: v for n, v in rows.items() if n != "total"}
            if "total" not in rows or len(dist) < 11 or not all(isinstance(x, int) for v in rows.values() for x in v):
                continue
            hits = [j for j in range(ncols) if rows["total"][j] == nat and sum(v[j] for v in dist.values()) == nat]
            if len(hits) == 1:
                counts = (k + 1, rows, hits[0], ncols)
                break
        if counts:
            break
    if counts is None:                                      # the layout of 2015: one small table per crime type, rows of (policing district, count, percent) ending with a Total row
        for k, t in enumerate(pages):
            block = {}
            for ln in t.splitlines():
                ln2 = re.sub(r"(?<=\s)[-\u2013\u2014](?=\s|$)", "0", ln)
                m = ROW.match(ln2) or re.match(r"^\s*([A-Za-z][A-Za-z' .\u2019\-]+?)\s+(" + NUMTOK + r"(?:\s+" + NUMTOK + r")?)\s*$", ln2)
                if not m:
                    continue
                nums = tokens(m.group(2))
                if len(nums) not in (1, 2):
                    continue
                n = nm(m.group(1))
                if n == "total":
                    dist = {a: v for a, v in block.items() if a != "total"}
                    if len(dist) >= 11 and isinstance(nums[0], int) and nums[0] == nat and sum(v[0] for v in dist.values()) == nat and all(len(v) == 1 or abs(v[0] / nat * 100 - v[1]) <= 0.15 for v in dist.values()):
                        counts = (k + 1, {**{a: [v[0]] for a, v in dist.items()}, "total": [nat]}, 0, 1)
                    block = {}
                elif nm(m.group(1)) in DISTRICT_BY_NAME or n in POLICING_TO_DISTRICT:
                    block[n] = nums
            if counts:
                break
    if counts is None:
        hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if re.match(r"^\s*(?:Maseru Urban|Maseru Rural|Mohale|Qacha|Total)\b", ln) and re.search(r"\d", ln)]
        print(f"   [diagnostic] {year}: lines that start with a policing district or Total and hold a number ({len(hit)}), the first 8:")
        for k, ln in hit[:8]:
            print(f"      p{k}: {ln[:170]}")
        for k, t in enumerate(pages):
            L = t.splitlines()
            for i, ln in enumerate(L):
                if re.match(rf"^\s*Total\s+{nat:,}\b|^\s*Total\s+{nat}\b", ln):
                    print(f"   [diagnostic] {year}: a 'Total {nat}' line on page {k + 1}, with the lines before it:")
                    for x in L[max(0, i - 14):i + 1]:
                        print(f"      {x[:150]}")
                    break
        sys.exit(f"[stop] {year}: no page has a table of the 11 policing districts and a total row (whole numbers) with exactly one column that adds up to the national murder count {nat}")
    pg, rows, j, ncols = counts
    pol = {n: v[j] for n, v in rows.items() if n != "total"}
    notes = [f"the policing districts add up to the total row of the murder column ({sum(pol.values())} against {nat}): equal (table on page {pg}" + (f", {ncols} columns)" if ncols > 1 else ", the small table of murder cases by policing district)")]
    pct = None
    for t in pages:
        rows2 = policing_rows(t, ncols)
        if "total" in rows2 and len(rows2) >= 12 and all(isinstance(x, float) or x == 100 for x in rows2["total"]) and abs(rows2["total"][j] - 100) < 0.2 and all(isinstance(v[j], float) for v in rows2.values()):
            pct = rows2
            break
    if pct:
        diffs = [(n, round(pol[n] / nat * 100, 1), pct[n][j]) for n in pol if n in pct and abs(pol[n] / nat * 100 - pct[n][j]) > 0.1]
        notes.append("the percentage table agrees with the counts to within 0.1 point in every district" if not diffs else f"the percentage table disagrees with the counts in {len(diffs)} district(s): {diffs[:3]}")
    else:
        notes.append("the percentage table of the same report was not found: not compared")
    unit = {}
    for n, v in pol.items():
        d = POLICING_TO_DISTRICT.get(n) or DISTRICT_BY_NAME.get(n)
        if d is None:
            sys.exit(f"[stop] {year}: the policing district {n!r} is neither a district nor a known part of one")
        unit[d] = unit.get(d, 0) + v
    missing = [d for d in DISTRICTS if d not in unit]
    if missing:
        sys.exit(f"[stop] {year}: districts missing from the table: {missing}")
    return unit, notes, nat


def census_tables(texts: list):
    """The tables of district populations in a census report, found PAGE BY PAGE: a page with at least 9 of the 10 districts followed by numbers; the column whose districts add up to the census total (2,007,201,
    within 0.1%) is the 2016 population. Returns [(page, {district: population}, column)] for every page where exactly one column matches (a percentage table or an earlier census year never does)."""
    found = []
    for k, t in enumerate(texts):
        rows = {}
        for ln in t.splitlines():
            m = re.match(r"^\s*([A-Za-z][A-Za-z\u2019' .\-]+?)\s+((?:" + NUMTOK + r"\s+){1,}" + NUMTOK + r")\s*$", ln.replace("\xa0", " "))
            if not m:
                continue
            d = DISTRICT_BY_NAME.get(nm(m.group(1)))
            if d and d not in rows:
                nums = tokens(m.group(2))
                if len(nums) >= 2:
                    rows[d] = nums
        if len(rows) < 9:
            continue
        width = min(len(v) for v in rows.values())
        for j in range(width):
            if not all(isinstance(v[j], int) for v in rows.values()):
                continue
            tot = sum(v[j] for v in rows.values())
            # Butha-Buthe can be missing from a page (it is written Botha-Bothe or is split over two lines): then the page is accepted only if the districts found add up to the census total minus nothing, i.e. all ten are needed
            if len(rows) == 10 and abs(tot - CENSUS_TOTAL) <= CENSUS_TOTAL * 0.001:
                found.append((k + 1, {d: int(v[j]) for d, v in rows.items()}, j + 1))
    return found


def load_census():
    """-> {district: population 2016}, how: from manual_census2016.* in the raw folder (the Bureau's census report): the first page whose table adds up to the census total; other pages that agree are counted."""
    files = sorted(RAW.glob("manual_census2016*"))
    if not files:
        return None, ("no file manual_census2016.pdf / .xlsx / .csv in " + str(RAW) + ": save there a Bureau of Statistics file that lists the 2016 census population of the ten districts "
                      "(for example the Population and Housing Census 2016 analytic report or its district table)")
    f = files[0]
    if f.suffix.lower() == ".pdf":
        texts = pdf_pages(f.read_bytes())
    else:
        try:
            frames = pd.read_excel(f, sheet_name=None, header=None, dtype=object) if f.suffix.lower().startswith(".xls") else {"csv": pd.read_csv(f, header=None, dtype=object)}
        except Exception as e:
            return None, f"{f.name} could not be read: {str(e)[:100]}"
        texts = ["\n".join(" ".join(str(c) for c in r if str(c) != "nan") for r in df.itertuples(index=False)) for df in frames.values()]
    found = census_tables(texts)
    if not found:
        have = [(k + 1, len(re.findall(r"Leribe|Berea|Maseru|Mafeteng", t))) for k, t in enumerate(texts) if re.search(r"Leribe", t)][:8]
        return None, f"{f.name}: no page has a table of the ten districts whose column adds up to the census total {CENSUS_TOTAL:,} (pages that name Leribe: {have})"
    k, pop, col = found[0]
    agree = all(f2[1] == pop for f2 in found)
    return pop, f"{f.name}, page {k}, column {col}" + (f"; {len(found) - 1} other page(s) give the same table" if len(found) > 1 and agree else ("; WARNING: other pages give different populations" if len(found) > 1 else ""))


def fetch_reports() -> dict:
    out = {}
    for y in YEARS:
        try:
            out[y] = pdf_pages(FETCH.get(REPORT.format(year=y), f"ls_report_{y}", reuse=REUSE["on"], suffix=".pdf", reject_html=True))
        except F.RobotsDisallowed:
            print(f"[{y}] robots.txt does not allow it")
        except Exception as e:
            print(f"[{y}] not available ({str(e)[:70]})")
    return out


def cmd_inspect():
    print(f"[lesotho_homicide_rate.py revision {REVISION}]")
    for y, pages in sorted(fetch_reports().items()):
        try:
            unit, notes, nat = parse_report(pages, y)
            print(f"[{y}] murder {nat}: " + ", ".join(f"{d} {unit[d]}" for d in DISTRICTS))
            for n in notes:
                print("   " + n)
        except SystemExit as e:
            print(f"[{y}] {e}")
    pop, how = load_census()
    print(f"[census 2016] {how if pop is None else str(len(pop)) + ' districts, ' + how}")


def cmd_build():
    print(f"[lesotho_homicide_rate.py revision {REVISION}]")
    pop, how = load_census()
    if pop is None:
        sys.exit(f"[stop] the 2016 census populations of the districts are needed: {how}")
    print(f"[census 2016] {len(pop)} districts, {how}; they add up to {sum(pop.values()):,}")
    below = [d for d in DISTRICTS if pop[d] < F.MIN_POP]
    print(f"[scope] {len(DISTRICTS) - len(below)} districts with {F.MIN_POP:,}+ residents" + (f"; not published (below the minimum population): {', '.join(f'{d} ({pop[d]:,})' for d in below)}, counted in the national total only" if below else ""))
    rows = []
    for y, pages in sorted(fetch_reports().items()):
        try:
            unit, notes, nat = parse_report(pages, y)
        except SystemExit as e:
            print(f"[{y}] skipped: {str(e)[:200]}")
            continue
        print(f"[{y}] murder {nat}; the districts add up")
        for n in notes:
            print("   " + n)
        age = round(abs(y + 0.5 - CENSUS_MID), 1)                      # a distance in years: the census may also be AFTER the year (the report of 2015, a census of April 2016)
        when = "after" if y + 0.5 < CENSUS_MID else "before"
        for d in DISTRICTS:
            if d in below:
                continue
            k = unit[d]
            rows.append({"country": "Lesotho", "unit": d, "unit_local": d, "unit_code": "", "admin_level": "admin1", "unit_type": "district", "parent_unit": "", "year": y, "homicide_cases": int(k), "population": int(pop[d]),
                         "homicide_rate_per_100k": k / pop[d] * 1e5, "flag_low_count": k < LOW_COUNT, "flag_outlier_year": False, "population_age_years": age, "indicator_type": "police_recorded_cases",
                         "reliability_tier": "B", "definition_flags": "", "validation": "; ".join(notes + [f"the denominator is the 2016 census, taken {age} years {when} the middle of this year" + (" (beyond the project limit of 3.5 years)" if age > 3.5 else ""),
                                                                                                                  "no independent confirmation exists"]),
                         "indicator": "murder cases reported to the Lesotho Mounted Police Service (BOS Crime Statistics Report, table of serious cases by policing district, column Murder)",
                         "population_method": "2016 Population and Housing Census (10 April 2016), district totals, used unchanged for the year",
                         "data_notes": f"calendar year {y}; murder cases reported; policing districts aggregated to districts (Maseru Urban + Maseru Rural = Maseru); national total {nat}" + (f"; districts below the minimum population are in the national total only: {', '.join(f'{d} {unit[d]}' for d in below)}" if below else ""),
                         "source_homicide": REPORT.format(year=y), "source_population": f"Lesotho Bureau of Statistics, 2016 Population and Housing Census, table of the population by district ({how})", "retrieved": FETCH.retrieved_on(REPORT.format(year=y)) if hasattr(FETCH, "retrieved_on") else ""})
    if not rows:
        sys.exit("[stop] no report could be read")
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "lesotho")
    last = int(df.year.max())
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}; years {sorted(df.year.unique())}")
    print(f"\nLatest year {last}:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} districts, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()