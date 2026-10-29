#!/usr/bin/env python3
"""
Tanzania - people murdered per 100,000 residents, by REGION (26 mainland regions + 5 Zanzibar regions = 31), calendar years of the annual police reports found on the NBS site (2025 and 2024; older ones are tried).

POLICE (numerator): National Bureau of Statistics (NBS) and Tanzania Police Force, "Crime and Traffic Incidents Statistics" annual report (January-December). Table "Number of Reported Murder Cases, Number of Suspects and People
            Killed by Sex and Reason and Police Region": per police region the murder CASES, the PEOPLE MURDERED (total, men, women), the reasons and the suspects. homicide_cases = people murdered (the victims; the number of
            murder cases is kept in murder_cases). The table "Number of Offences Against Persons by Type of Offence and Police Region" gives the murder cases again and is used as a check.
POLICE REGIONS -> REGIONS: the police regions are not the administrative regions, but they PARTITION them exactly: Ilala + Temeke + Kinondoni = Dar es Salaam, Mara + Tarime-Rorya = Mara, Pwani + Rufiji = Pwani; every other
            police region is one region. Marine, Railway, TAZARA, Airports and Port Police have no residents: they are counted in the national total only. No boundary assumption is needed.
POPULATION: 2022 Population and Housing Census (23 August 2022), by region: NBS "2022 PHC Initial Results" (region table of 31 regions). The column is found by itself: the one whose 31 regions add up to the national total of
            61,741,120. The census figure is used for the years from 2022 on; its age (year - 2022.64) goes into population_age_years. Years before 2022 would need the 2012 census projections and are not built.
CHECKS      (1) the police regions add up to the report's totals for Tanzania Mainland, Tanzania Zanzibar and Tanzania; (2) the murder cases of the murder table equal those of the offences-against-persons table in every region;
            (3) men + women = people murdered in every region; (4) the 31 census populations add up to 61,741,120. The tier is B: no independent confirmation exists (no health registry).

Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/Tanzania/ ; the one output is tanzania_homicide_rate.csv next to the script.
Commands:   python tanzania_homicide_rate.py inspect | build          Options: --reuse (use the saved files)     (a report saved by hand as manual_report_<year>.pdf in the raw folder is read too)
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

REVISION = 6
P = F.paths(__file__, "Tanzania")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
CRIME_PAGES = ["https://www.nbs.go.tz/statistics/topic/crime-statistics", "https://www.nbs.go.tz/statistics/topic/crime-statistics?page=2", "https://www.nbs.go.tz/statistics/topic/crime-statistics?page=3"]
CENSUS_PDF = "https://www.nbs.go.tz/uploads/statistics/documents/en-1720088450-2022 PHC Initial Results - English.pdf"
CENSUS_TOTAL = 61_741_120         # the 2022 census total of the United Republic (it identifies the right column of the region table)
CENSUS_MID = 2022.64              # 23 August 2022
LOW_COUNT = F.LOW_COUNT
REGIONS = ["Arusha", "Dar es Salaam", "Dodoma", "Geita", "Iringa", "Kagera", "Katavi", "Kigoma", "Kilimanjaro", "Lindi", "Manyara", "Mara", "Mbeya", "Morogoro", "Mtwara", "Mwanza", "Njombe", "Pwani", "Rukwa", "Ruvuma",
           "Shinyanga", "Simiyu", "Singida", "Songwe", "Tabora", "Tanga", "Kaskazini Unguja", "Kusini Unguja", "Mjini Magharibi", "Kaskazini Pemba", "Kusini Pemba"]
ZANZIBAR = {"Kaskazini Unguja", "Kusini Unguja", "Mjini Magharibi", "Kaskazini Pemba", "Kusini Pemba"}
# police region (normalised) -> region
POLICE_TO_REGION = {"ilala": "Dar es Salaam", "temeke": "Dar es Salaam", "kinondoni": "Dar es Salaam", "tarimerorya": "Mara", "rufiji": "Pwani"}
NO_RESIDENTS = {"marine", "railway", "tazara", "airports", "portpolice", "portspolice", "ports"}
TOTALS = {"tanzaniamainland": "mainland", "tanzaniazanzibar": "zanzibar", "tanzania": "national", "total": "national", "grandtotal": "national"}


def nm(x: str) -> str:
    return re.sub(r"[^a-z]", "", str(x).lower())


REGION_BY_NAME = {nm(r): r for r in REGIONS}
NUMTOK = r"-?\d[\d,]*(?:\.\d+)?"
ROW = re.compile(r"^\s*([A-Za-z][A-Za-z .\-\u2013/]+?)\s+((?:" + NUMTOK + r"\s+){2,}" + NUMTOK + r")\s*$")


def tokens(text: str) -> list:
    """The numbers of a row: whole numbers (with thousands commas) as int, decimals (a growth rate, a percentage) as float."""
    return [float(x.replace(",", "")) if "." in x else int(x.replace(",", "")) for x in re.findall(NUMTOK, text)]


def pdf_pages(data: bytes) -> list:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def links_of(url: str) -> list:
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(url, "tz_page_" + re.sub(r"[^A-Za-z0-9]+", "_", url[-30:]), reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    except Exception as e:
        print(f"   [skip] {url}: {str(e)[:100]}")
        return []
    return [(a.get_text(" ", strip=True), urljoin(url, a["href"].strip())) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.pdf(?:[?#]|$)", a["href"], re.I)]


def find_reports() -> dict:
    """-> {year: url} of the annual (January-December) English reports on the NBS crime page(s): the year is read from the link text or the file name."""
    out = {}
    for pg in CRIME_PAGES:
        for t, u in links_of(pg):
            name = unquote(u).rsplit("/", 1)[-1]
            if not re.search(r"crime.{0,12}(and traffic|statistics)|CRIME STATISTICS REPORT", name, re.I) or re.search(r"kiswahili|ripoti|takwimu|prison", name, re.I):
                continue
            y = re.search(r"(?:Dec\w*\s*|ENGLISH\s*)(20\d\d)", name, re.I)
            if y and not re.search(r"January\s*-\s*June|half", name, re.I):
                out.setdefault(int(y.group(1)), u)
    for p in sorted(RAW.glob("manual_report_*.pdf")):
        y = re.search(r"(20\d\d)", p.name)
        if y:
            out[int(y.group(1))] = str(p)
    return out


def read_rows(pages: list, caption: re.Pattern, min_numbers: int, span: int = 2):
    """The rows (region name, numbers) of the table whose caption matches `caption`: from the caption page and the next `span` pages, stopping at the page that holds the 'Tanzania' total row."""
    start = next((k for k, t in enumerate(pages) if caption.search(t) and len(re.findall(r"\n\s*(?:Arusha|Dodoma|Ilala)\b", t)) >= 1), None)
    if start is None:
        return None
    rows, seen, done = [], set(), False
    for k in range(start, min(start + span + 1, len(pages))):
        for ln in pages[k].splitlines():
            m = ROW.match(ln.replace("\u2013", "-").replace("\u2014", "-"))
            if not m:
                continue
            nums = tokens(m.group(2))
            if len(nums) < min_numbers:
                continue
            n = nm(m.group(1))
            if n in seen and n not in TOTALS and n not in NO_RESIDENTS:     # a REGION name a second time (the units without residents, such as Marine, may repeat): the next table has begun (the murder table of 2024 has no 'Tanzania' total row to stop at)
                done = True
                break
            seen.add(n)
            rows.append((m.group(1).strip(), nums, k + 1))
        if done or any(nm(r[0]) == "tanzania" for r in rows):
            break
    return rows


def text_totals(pages: list):
    """The national murder cases and people murdered stated in the report's text ('A total of 2,193 murder offences were reported ... A total of 2,263 people were murdered'), or None."""
    txt = re.sub(r"\s+", " ", " ".join(pages))
    a = re.search(r"A total of ([\d,]+) murder (?:offences|cases)", txt, re.I)
    b = re.search(r"A total of ([\d,]+)\s*(?:\([^)]*\)\s*)?people were murdered", txt, re.I)
    return (int(a.group(1).replace(",", "")), int(b.group(1).replace(",", ""))) if a and b else None


def parse_report(pages: list, year: int):
    """-> (units, notes): {region: (cases, killed, men, women)}, plus the checks. Aggregates police regions to regions."""
    murder = read_rows(pages, re.compile(r"Reported Murder Cases", re.I), 8)
    persons = read_rows(pages, re.compile(r"Offences Against Person\w* by (?:Type|type) of Offence and Police Region", re.I), 5)
    if not murder:
        sys.exit(f"[stop] {year}: the table 'Number of Reported Murder Cases ... by Police Region' (rows of at least 8 numbers) was not found")
    police, totals = {}, {}
    for name, nums, pg in murder:
        n = nm(name)
        cases, killed, men, women = nums[0], nums[1], nums[2], nums[3]
        if n in TOTALS:
            totals[TOTALS[n]] = (cases, killed, men, women)
            continue
        if men + women != killed:
            raw = ", ".join(f"{a}: {' '.join(str(x) for x in b[:10])}" for a, b, _ in murder[:3])
            sys.exit(f"[stop] {year}: {name!r}: men + women = {men + women} but people murdered = {killed} (the first four numbers of the row are cases, people murdered, men, women). The first rows of the table, ten numbers each: {raw}. "
                     f"The table was read from page {murder[0][2]}")
        if n in police:                                       # a name that appears twice (Marine appears for the sea police and for Zanzibar): the first one with residents counts, a zero row is ignored
            if sum(nums[:4]) == 0:
                continue
        police[n] = (name, cases, killed, men, women)
    p2 = {}
    for name, nums, pg in (persons or []):
        if nm(name) not in TOTALS and nm(name) not in p2:
            p2[nm(name)] = nums[0]
    unit, no_res = {}, {}
    for n, (name, c, k, m, w) in police.items():
        if n in NO_RESIDENTS:
            no_res[name] = (c, k)
            continue
        reg = POLICE_TO_REGION.get(n) or REGION_BY_NAME.get(n)
        if reg is None:
            sys.exit(f"[stop] {year}: the police region {name!r} is neither a region nor a known part of one; known splits: {sorted(POLICE_TO_REGION)}; regions: {sorted(REGION_BY_NAME)[:6]}...")
        a = unit.get(reg, (0, 0, 0, 0))
        unit[reg] = (a[0] + c, a[1] + k, a[2] + m, a[3] + w)
    missing = [r for r in REGIONS if r not in unit]
    filled = []
    for r in list(missing):                                   # a region absent from the murder table is accepted only if the offences-against-persons table lists it with no murder
        parts = [n for n, reg in list(POLICE_TO_REGION.items()) + [(nm(x), x) for x in REGIONS] if reg == r]
        if persons and any(p2.get(n) == 0 for n in parts) and all(p2.get(n, 0) == 0 for n in parts):
            unit[r] = (0, 0, 0, 0)
            filled.append(r)
            missing.remove(r)
    if missing:
        sys.exit(f"[stop] {year}: regions with no police region in the murder table (and not listed with zero murders in the offences-against-persons table): {missing}")
    notes = []
    if filled:
        notes.append(f"{', '.join(filled)}: absent from the murder table, zero murders in the offences-against-persons table")

    def total_of(key):
        sel = [v for r, v in unit.items() if key == "national" or ((r in ZANZIBAR) == (key == "zanzibar"))]
        cases, killed = sum(v[0] for v in sel), sum(v[1] for v in sel)
        if key in ("mainland", "national"):
            cases += sum(v[0] for v in no_res.values())
            killed += sum(v[1] for v in no_res.values())
        return cases, killed
    for key, label in (("mainland", "Tanzania Mainland"), ("zanzibar", "Tanzania Zanzibar"), ("national", "Tanzania")):
        if key not in totals:
            continue
        mine = total_of(key)
        notes.append(f"the regions add up to the report's {label} total ({mine[0]} cases, {mine[1]} people murdered): " + ("equal" if mine == tuple(totals[key][:2]) else f"DIFFERENT ({totals[key][0]} cases, {totals[key][1]} people)"))
    if "national" not in totals:
        tt = text_totals(pages)
        if tt:
            mine = total_of("national")
            notes.append(f"the regions add up to the national totals stated in the report's text ({mine[0]} cases, {mine[1]} people murdered; text: {tt[0]} and {tt[1]}): " + ("equal" if mine == tt else "DIFFERENT"))
        else:
            notes.append("the murder table has no total row and the report's text states no national total: not compared")
    if persons:
        diffs = [(name, c, p2.get(nm(name))) for n, (name, c, k, m, w) in police.items() if p2.get(n) is not None and p2[n] != c]
        notes.append("the murder cases of the murder table equal those of the offences-against-persons table in every police region" if not diffs else f"murder cases differ between the two tables in {len(diffs)} police region(s): {diffs[:3]}")
    else:
        notes.append("the offences-against-persons table was not found: its murder column could not be compared")
    return unit, no_res, notes


def parse_census(pages: list):
    """-> ({region: population 2022}, how) from the region table: the pages that hold the region rows (the first run of pages with at least 10 of them, so that the regions named in the text or in other tables are
    ignored); the column whose 31 regions add up to the census total is the population. On failure the second value says why and the sums of every column."""
    by_page = {}
    for k, t in enumerate(pages):
        rows = {}
        for ln in t.splitlines():
            m = ROW.match(ln)
            if not m:
                continue
            n = nm(m.group(1))
            if n in REGION_BY_NAME and n not in rows:
                nums = tokens(m.group(2))
                if len(nums) >= 3:
                    rows[n] = nums
        if rows:
            by_page[k + 1] = rows
    start = next((k for k, r in sorted(by_page.items()) if len(r) >= 10), None)
    if start is None:
        return None, f"no page has 10 or more region rows (pages with some: {sorted(by_page)[:10]})"
    rows, k = {}, start
    while k in by_page:
        for n, v in by_page[k].items():
            rows.setdefault(n, v)
        k += 1
    if len(rows) < 31:
        return None, f"pages {start}-{k - 1}: only {len(rows)} of the 31 regions were found ({sorted(set(REGION_BY_NAME) - set(rows))[:6]} missing)"
    width = min(len(v) for v in rows.values())
    sums = [sum(v[j] for v in rows.values()) if all(isinstance(v[j], int) for v in rows.values()) else None for j in range(width)]
    hit = [j for j in range(width) if sums[j] is not None and abs(sums[j] - CENSUS_TOTAL) <= CENSUS_TOTAL * 0.0005]
    if len(hit) != 1:
        return None, f"pages {start}-{k - 1}: {len(hit)} column(s) add up to the census total {CENSUS_TOTAL:,}; the column sums are {sums}"
    return {REGION_BY_NAME[n]: int(v[hit[0]]) for n, v in rows.items()}, f"pages {start}-{k - 1}, column {hit[0] + 1} of {width}"


def get_pdf(url: str, name: str):
    if not url.startswith("http"):
        return pdf_pages(Path(url).read_bytes())
    return pdf_pages(FETCH.get(url, name, reuse=REUSE["on"], suffix=".pdf", reject_html=True))


def cmd_inspect():
    print(f"[tanzania_homicide_rate.py revision {REVISION}]")
    reps = find_reports()
    print(f"[reports] annual English reports found on the NBS crime pages: {sorted(reps)}")
    for y in sorted(reps, reverse=True)[:2]:
        try:
            pages = get_pdf(reps[y], f"tz_report_{y}")
            res = parse_report(pages, y)
            print(f"[{y}] read: {len(res[0])} regions, no-resident units {res[1]}")
            for n in res[2]:
                print("   " + n)
        except SystemExit as e:
            print(f"[{y}] {e}")
    try:
        pages = get_pdf(CENSUS_PDF, "tz_census_initial")
        pop, how = parse_census(pages)
        print(f"[census 2022] {('read ' + str(len(pop)) + ' regions, ' + how) if pop else how}")
        if not pop:
            hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if re.search(r"Dodoma|Dar es Salaam|Mjini Magharibi", ln)]
            for k, ln in hit[:10]:
                print(f"      p{k}: {ln[:150]}")
    except Exception as e:
        print(f"[census 2022] {str(e)[:150]}")
    print("\n[inspect only] nothing written")


def cmd_build():
    print(f"[tanzania_homicide_rate.py revision {REVISION}]")
    reps = find_reports()
    if not reps:
        sys.exit("[stop] no annual crime report was found on the NBS crime pages (save one by hand as manual_report_<year>.pdf in the raw folder)")
    print(f"[reports] annual English reports found: {sorted(reps)}")
    pages_c = get_pdf(CENSUS_PDF, "tz_census_initial")
    pop, how = parse_census(pages_c)
    if pop is None:
        hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages_c) for ln in t.splitlines() if re.search(r"Dodoma|Dar es Salaam|Mjini Magharibi", ln)]
        print(f"   [diagnostic] census region table: {how}; lines naming a region ({len(hit)}), the first 10:")
        for k, ln in hit[:10]:
            print(f"      p{k}: {ln[:150]}")
        sys.exit("[stop] the census populations could not be read: save the Initial Results by hand or send the diagnostic")
    print(f"[census 2022] {len(pop)} regions, {how}; they add up to {sum(pop.values()):,}")
    rows = []
    for y in sorted(reps):
        if y < 2022:
            print(f"[{y}] skipped: the report is older than the 2022 census, whose region populations are the only denominator built here (the 2012 census projections would be needed)")
            continue
        try:
            unit, no_res, notes = parse_report(get_pdf(reps[y], f"tz_report_{y}"), y)
        except SystemExit as e:
            print(f"[{y}] skipped: {str(e)[:220]}")
            continue
        print(f"[{y}] {len(unit)} regions; people murdered {sum(v[1] for v in unit.values()):,}; no-resident units: {dict(no_res)}")
        for n in notes:
            print("   " + n)
        age = max(0.0, round(y + 0.5 - CENSUS_MID, 1))
        for reg in REGIONS:
            c, k, m, w = unit[reg]
            rows.append({"country": "Tanzania", "unit": reg, "unit_local": reg, "unit_code": "", "admin_level": "admin1", "unit_type": "region", "parent_unit": "", "year": y, "homicide_cases": int(k), "population": int(pop[reg]),
                         "homicide_rate_per_100k": k / pop[reg] * 1e5, "flag_low_count": k < LOW_COUNT, "flag_outlier_year": False, "population_age_years": age, "indicator_type": "police_recorded_cases",
                         "reliability_tier": "B", "definition_flags": "counts_victims",
                         "validation": "; ".join(notes + ["no independent confirmation exists (no health registry is published)"]),
                         "indicator": "people murdered (victims) recorded by the Tanzania Police Force: Table 'Reported Murder Cases, Number of Suspects and People Killed ... by Police Region'",
                         "population_method": "2022 Population and Housing Census (23 August 2022), region totals, used unchanged for the year",
                         "data_notes": f"calendar year {y}; people murdered {k} (men {m}, women {w}) in {c} murder cases; police regions aggregated to regions (Ilala + Temeke + Kinondoni = Dar es Salaam, Mara + Tarime-Rorya = Mara, Pwani + Rufiji = Pwani); "
                                       "units without residents (" + ", ".join(no_res) + ") are in the national total only; the census figure is " + f"{age} years old for this year",
                         "source_homicide": reps[y], "source_population": CENSUS_PDF, "retrieved": FETCH.retrieved_on(reps[y], CENSUS_PDF) if reps[y].startswith("http") else "manual", "murder_cases": int(c), "murder_victims_men": int(m), "murder_victims_women": int(w)})
    if not rows:
        sys.exit("[stop] no report could be read")
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "tanzania")
    last = int(df.year.max())
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}; years {sorted(df.year.unique())}")
    print(f"\nLatest year {last}, the ten highest rates:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].head(10).round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} regions, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()