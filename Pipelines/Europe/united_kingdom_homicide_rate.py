#!/usr/bin/env python3
"""
United Kingdom (England and Wales) - police-recorded homicide offences per 100,000 residents, by police force area.

NUMERATOR   (official): Home Office "Police recorded crime open data tables", Police Force Area tables from year ending March 2013 onwards (ODS, one
            sheet per financial year, April to March, in quarters). Homicide = the offence SUBGROUP named Homicide (the descriptions inside it are read
            from the file and written into the rows). Four quarters make a financial year: a force-year with fewer than four quarters (the current,
            partial year) has no row. Counts are summed as published (the Home Office notes warn that negative counts may occur).
            NOTE (ONS): the Home Office Homicide Index, not police recorded crime, is the preferred source for homicide counts.
DENOMINATOR (official): ONS "Population estimates for police force areas in England and Wales by single year of age and sex, mid-1991 to mid-2024"
            (ad hoc release 3194; 2023 force boundaries): total population = the sum of the single-year columns F0... and M0... The financial year Y/Y+1
            is paired with the estimate of mid-Y (30 June Y); the period midpoint is 1 October, so the age is 0.25 years (stored as 0.3: the format keeps one decimal). A year without a
            published mid-year estimate has no row (it appears when ONS publishes it).
UNITS       The 43 police force areas of England and Wales that appear in both files (matched by name; the ONS code is `unit_code`); non-territorial
            "forces" (Action Fraud, CIFAS, British Transport Police ...) have no population and are reported. A force of either file with no match
            in the other that is territorial stops the run. Scotland and Northern Ireland are separate jurisdictions with their own sources.
CHECKS      Every year sheet must hold the Homicide subgroup; a force's four quarters must all be present; the force names of the two files must
            match exactly (after normalising "&"/"and" and punctuation); the ONS columns must hold equal numbers of female and male ages; the force
            areas must add up to a population of England and Wales' scale; no negative annual total (such a row would be left out and reported).
            Force notes of the Home Office Notes sheet that name a force are attached to that force's rows. Every row is tier B: one source family and
            no independent second figure, and the Home Office itself prefers the Homicide Index.

Folders:    this script sits in <repo>/Pipelines/Europe/ ; downloads go to <repo>/Data/Raw/Europe/United Kingdom/ ; the one output is
            united_kingdom_homicide_rate.csv next to the script.
Commands:   python united_kingdom_homicide_rate.py inspect | build
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine      (calamine reads the 15 MB ODS in seconds; the odf reader takes hours)
"""
import argparse
import importlib.util
import io
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 12:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP
NAT_RANGE = (50e6, 70e6)         # the 43 force areas of England and Wales must add up to a population of this scale
P = F.paths(__file__, "United Kingdom")  # raw downloads -> Data/Raw/Europe/United Kingdom/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)

HO_PAGE = "https://www.gov.uk/government/statistical-data-sets/police-recorded-crime-and-outcomes-open-data-tables"
ONS_PAGE = ("https://www.ons.gov.uk/peoplepopulationandcommunity/populationandmigration/populationestimates/adhocs/"
            "3194populationestimatesforpoliceforceareasinenglandandwalesbysingleyearofageandsexmid1991tomid2024")


def find_link(page_url: str, want, ext: str) -> str | None:
    """The first link on a page that ends with `ext` and whose text or address satisfies `want`."""
    from bs4 import BeautifulSoup
    try:
        html = FETCH.get(page_url).decode("utf-8", "replace")
    except RuntimeError as e:
        sys.exit(f"[stop] the page could not be read ({e}). Open it in a browser to check the address, or save the file by hand in {RAW}")
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a", href=True):
        href = urljoin(page_url, a["href"].strip())
        low = href.lower()
        if (low.split("?")[0].endswith(ext) or re.search(re.escape(ext) + r"(?:$|[&#])", low)) and want(a.get_text(" ", strip=True).lower() + " " + low):   # ONS: /file?uri=...xlsx
            return href
    return None


def dump(df: pd.DataFrame, title: str, rows=12, cols=10):
    print(f"--- {title}: shape {df.shape} ---")
    print(df.iloc[:rows, :cols].to_string(max_colwidth=28))


def read_sheet(data: bytes, sheet, engine: str, nrows=None) -> pd.DataFrame:
    """A sheet of the XLSX through pandas (small file)."""
    t = time.time()
    df = pd.read_excel(io.BytesIO(data), sheet_name=sheet, header=None, engine=engine, dtype=object, nrows=nrows)
    print(f"   [read] sheet '{sheet}' {df.shape} in {time.time() - t:.1f} s", flush=True)
    return df


def ods_sheet(wb, sheet: str, nrows=None) -> pd.DataFrame:
    """A sheet of the already opened ODS (calamine opens the 15 MB file ONCE; every pandas call would parse it again)."""
    t = time.time()
    rows = wb.get_sheet_by_name(sheet).to_python(skip_empty_area=False)
    df = pd.DataFrame(rows[:nrows] if nrows else rows).astype(object).replace({"": None})
    print(f"   [read] sheet '{sheet}' {df.shape} in {time.time() - t:.1f} s", flush=True)
    return df


def cmd_inspect():
    if importlib.util.find_spec("python_calamine") is None:
        sys.exit("[stop] reading the Home Office ODS needs python-calamine (the odf reader takes hours on a 15 MB file):  python -m pip install python-calamine")
    ho = find_link(HO_PAGE, lambda t: "police force area" in t and "2013" in t and "2008" not in t, ".ods")
    print(f"[home office] Police Force Area tables (year ending March 2013 onwards): {ho}")
    ons = find_link(ONS_PAGE, lambda t: "police" in t, ".xlsx")
    print(f"[ons] police force area population file: {ons}")
    if not ho or not ons:
        sys.exit("[stop] a link was not found on the page (see above); save the file by hand in the raw folder and tell me its name")
    ho_raw = FETCH.get(ho, "home_office_prc_pfa", reuse=True, suffix=".ods")
    ons_raw = FETCH.get(ons, "ons_pfa_population_3194", reuse=True, suffix=".xlsx")
    print("\n===== HOME OFFICE ODS =====", flush=True)
    from python_calamine import CalamineWorkbook
    t = time.time()
    print("opening the ODS once (about 15 MB; this can take a minute or two) ...", flush=True)
    wb = CalamineWorkbook.from_object(io.BytesIO(ho_raw))
    names = wb.sheet_names
    print(f"opened in {time.time() - t:.1f} s; sheets: {names}", flush=True)
    years = [n for n in names if re.fullmatch(r"\d{4}_\d{2}", n)]
    for sh in [n for n in ("Notes_",) if n in names]:
        dump(ods_sheet(wb, sh, nrows=40), f"sheet '{sh}'", rows=25, cols=4)
    probe = years[-2] if len(years) > 1 else years[-1]          # the latest sheet is a partial year: probe the one before it
    for sh in dict.fromkeys([years[0], probe, years[-1]]):
        dump(ods_sheet(wb, sh, nrows=14), f"sheet '{sh}' (first rows)", rows=14, cols=12)
    raw = ods_sheet(wb, probe)
    hdr = next((i for i in range(min(25, len(raw))) if any("force" in str(v).lower() for v in raw.iloc[i]) and any("offence" in str(v).lower() or "number" in str(v).lower() for v in raw.iloc[i])), None)
    if hdr is None:
        print(f"\n[data sheet] '{probe}': no header row with a force and an offences/number column among the first 25 rows (see the dump above)")
    else:
        df = raw.iloc[hdr + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[hdr]]
        print(f"\n[data sheet] '{probe}': header row {hdr + 1}, {len(df):,} data rows, columns {list(df.columns)}")
        for c in df.columns:
            vals = sorted(df[c].dropna().astype(str).unique())
            if len(vals) < 400:
                hit = [v for v in vals if re.search(r"homicide|murder|manslaughter|infanticide", v, re.I)]
                print(f"   {c}: {len(vals)} distinct" + (f"; homicide-like values: {hit}" if hit else f"; e.g. {vals[:6]}"))
    print("\n===== ONS POPULATION XLSX =====", flush=True)
    xo = pd.ExcelFile(io.BytesIO(ons_raw))
    print(f"sheets ({len(xo.sheet_names)}):", xo.sheet_names[:12], "..." if len(xo.sheet_names) > 12 else "", flush=True)
    for sh in xo.sheet_names[:3] + xo.sheet_names[-1:]:
        dump(read_sheet(ons_raw, sh, "openpyxl", nrows=25), f"sheet '{sh}'", rows=16, cols=12)
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


def norm(name: str) -> str:
    return re.sub(r"[^a-z]", "", str(name).lower().replace("&", "and"))


def open_sources():
    if importlib.util.find_spec("python_calamine") is None:
        sys.exit("[stop] reading the Home Office ODS needs python-calamine:  python -m pip install python-calamine")
    from python_calamine import CalamineWorkbook
    ho = find_link(HO_PAGE, lambda t: "police force area" in t and "2013" in t and "2008" not in t, ".ods")
    ons = find_link(ONS_PAGE, lambda t: "police" in t, ".xlsx")
    if not ho or not ons:
        sys.exit("[stop] a download link was not found (Home Office: %s; ONS: %s)" % (ho, ons))
    ho_raw = FETCH.get(ho, "home_office_prc_pfa", reuse=True, suffix=".ods")
    ons_raw = FETCH.get(ons, "ons_pfa_population_3194", reuse=True, suffix=".xlsx")
    return ho, ons, CalamineWorkbook.from_object(io.BytesIO(ho_raw)), ons_raw


def load_crime(wb):
    """-> ({(force, start_year): (cases, descriptions)}, {(force, start_year)} incomplete, force-note paragraph list, set of forces)."""
    out, partial, forces, hom_forces = {}, set(), set(), set()
    for sh in [n for n in wb.sheet_names if re.fullmatch(r"\d{4}_\d{2}", n)]:
        raw = ods_sheet(wb, sh)
        df = raw.iloc[1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[0]]
        need = {"Financial Year", "Financial Quarter", "Force Name", "Offence Description", "Offence Subgroup", "Number of Offences"}
        if need - set(df.columns):
            sys.exit(f"[stop] sheet {sh}: columns missing {sorted(need - set(df.columns))}; found {list(df.columns)}")
        y = int(sh[:4])
        df["q"] = pd.to_numeric(df["Financial Quarter"], errors="coerce")
        qs = df.groupby("Force Name")["q"].agg(lambda v: set(int(x) for x in v.dropna()))
        h = df[df["Offence Subgroup"].astype(str).str.strip().str.lower() == "homicide"].copy()
        if h.empty:
            sys.exit(f"[stop] sheet {sh} has no Offence Subgroup 'Homicide'; subgroups: {sorted(df['Offence Subgroup'].dropna().astype(str).unique())}")
        h["n"] = pd.to_numeric(h["Number of Offences"], errors="coerce")
        if h["n"].isna().any():
            sys.exit(f"[stop] sheet {sh}: non-numeric homicide counts")
        for force, g in h.groupby("Force Name"):
            forces.add(force)
            hom_forces.add(force)
            if qs.get(force, set()) != {1, 2, 3, 4}:
                partial.add((force, y))
                continue
            out[(force, y)] = (float(g["n"].sum()), sorted(set(g["Offence Description"].astype(str))))
        for force in qs.index:
            forces.add(force)
            if qs[force] != {1, 2, 3, 4}:
                partial.add((force, y))
    notes = ods_sheet(wb, "Notes_")[0].dropna().astype(str).tolist() if "Notes_" in wb.sheet_names else []
    return out, partial, notes, forces, hom_forces


def force_notes(notes: list[str]) -> list[str]:
    try:
        i = next(k for k, t in enumerate(notes) if t.strip().lower().startswith("force notes"))
    except StopIteration:
        return []
    j = next((k for k in range(i + 1, len(notes)) if notes[k].strip().lower().startswith("additional notes")), len(notes))
    return [t.strip() for t in notes[i + 1:j] if t.strip()]


def load_population(ons_raw: bytes):
    xo = pd.ExcelFile(io.BytesIO(ons_raw), engine="openpyxl")
    pops, codes = {}, {}
    for sh in [n for n in xo.sheet_names if re.match(r"Mid-\d{4} to Mid-\d{4}", n)]:
        raw = pd.read_excel(io.BytesIO(ons_raw), sheet_name=sh, header=None, engine="openpyxl", dtype=object)
        hdr = next((i for i in range(min(15, len(raw))) if str(raw.iat[i, 0]).strip().lower().startswith("pfa") and "code" in str(raw.iat[i, 0]).lower()), None)
        if hdr is None:
            sys.exit(f"[stop] ONS sheet '{sh}': no header row starting with 'PFA ... Code' in the first 15 rows")
        df = raw.iloc[hdr + 1:].copy()
        df.columns = [str(c).strip() for c in raw.iloc[hdr]]
        cname, ncol = df.columns[0], df.columns[1]
        ycol = next((c for c in df.columns if c.lower() == "year"), None)
        fcols = [c for c in df.columns if re.fullmatch(r"F\d+\+?(?: and over)?", c, re.I)]
        mcols = [c for c in df.columns if re.fullmatch(r"M\d+\+?(?: and over)?", c, re.I)]
        if ycol is None or len(fcols) != len(mcols) or len(fcols) < 80:
            sys.exit(f"[stop] ONS sheet '{sh}': year column {ycol}, {len(fcols)} female and {len(mcols)} male single-age columns (expected equal and at least 80)")
        df = df[df[ncol].notna() & df[ycol].notna()].copy()
        tot = df[fcols + mcols].apply(pd.to_numeric, errors="coerce")
        if tot.isna().any().any():
            sys.exit(f"[stop] ONS sheet '{sh}': non-numeric single-age values")
        df["pop"] = tot.sum(axis=1)
        for name, code, y, v in zip(df[ncol].astype(str), df[cname].astype(str), df[ycol].astype(int), df["pop"]):
            if (name, y) in pops:
                sys.exit(f"[stop] ONS: {name} {y} appears twice")
            pops[(name, y)] = float(v)
            codes[name] = code
    return pops, codes


def cmd_build():
    ho_url, ons_url, wb, ons_raw = open_sources()
    crime, partial, notes, ho_forces, hom_forces = load_crime(wb)
    pops, codes = load_population(ons_raw)
    ons_names = sorted(codes)
    by_norm = {norm(n): n for n in ons_names}
    ho_match = {f: by_norm.get(norm(f)) for f in ho_forces}
    unmatched = sorted(f for f, m in ho_match.items() if m is None)
    leftover = sorted(set(ons_names) - set(ho_match.values()))
    print(f"[forces] Home Office: {len(ho_forces)} forces; ONS: {len(ons_names)} force areas; matched {sum(m is not None for m in ho_match.values())}")
    print(f"[forces] in the Home Office file with no ONS force area (left out; no population): {unmatched}")
    unexpected = sorted(f for f in unmatched if f in hom_forces and norm(f) != norm("British Transport Police"))
    if unexpected:
        sys.exit(f"[stop] Home Office forces with homicide counts but no ONS police force area of the same name: {unexpected}. A new or renamed force? "
                 f"Their homicides would be silently lost; nothing is guessed. (Only British Transport Police and forces without homicide rows may be left out.)")
    if leftover:
        sys.exit(f"[stop] ONS force areas with no Home Office force of the same name: {leftover}. Spelling difference? Nothing is guessed.")
    nat = {y: sum(v for (n, yy), v in pops.items() if yy == y) for y in sorted({y for _, y in pops})}
    for y, v in nat.items():
        if not NAT_RANGE[0] <= v <= NAT_RANGE[1]:
            sys.exit(f"[stop] the force areas add up to {v:,.0f} in mid-{y}: not of the scale of England and Wales {NAT_RANGE}")
    print(f"[population] the force areas add up to {min(nat.values()):,.0f} - {max(nat.values()):,.0f} (mid-{min(nat)} to mid-{max(nat)}); latest mid-year estimate: {max(nat)}")
    fnotes = force_notes(notes)
    if fnotes:
        print("[force notes] from the Home Office Notes sheet (attached to the forces they name):")
        for t in fnotes:
            print("   " + t[:230])
    rows, neg, nopop = [], [], []
    for (force, y), (cases, descs) in sorted(crime.items()):
        name = ho_match.get(force)
        if name is None:
            continue
        pv = pops.get((name, y))
        if pv is None:
            nopop.append((name, y))
            continue
        if cases < 0 or cases != int(cases):
            neg.append((name, y, cases))
            continue
        pop_i = int(round(pv))
        if pop_i < MIN_POP:
            continue
        cases = int(cases)
        mine = [t for t in fnotes if force.lower() in t.lower() or name.lower() in t.lower()]
        rows.append({
            "country": "United Kingdom", "unit": name, "unit_local": "", "unit_code": codes[name], "admin_level": "police_unit", "unit_type": "police_force_area",
            "parent_unit": "England and Wales", "year": y, "homicide_cases": cases, "population": pop_i, "homicide_rate_per_100k": cases / pop_i * 1e5,
            "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": 0.3, "indicator_type": "police_recorded_cases",
            "reliability_tier": "B", "definition_flags": ";".join(f for f, k in (("includes_manslaughter", "manslaughter"), ("includes_attempts", "attempt")) if any(k in d.lower() for d in descs)),
            "validation": f"all four quarters of {y}/{str(y + 1)[2:]} are present; the force name matches an ONS police force area exactly; the 43-area population adds up to {nat[y]:,.0f} "
                          f"(England and Wales scale); the homicide subgroup holds: {', '.join(descs)}",
            "indicator": "Home Office police recorded crime, Offence Subgroup 'Homicide' (" + ", ".join(descs) + "), financial year April to March; unit: offences",
            "population_method": f"ONS police force area estimate of mid-{y} (30 June {y}), total of single years of age, both sexes; the financial year's midpoint is 1 October, so the age is 0.25 years (stored rounded to 0.3)",
            "data_notes": "the Home Office prefers the Homicide Index to police recorded crime for homicide; the year is the financial year's start year (April " + str(y) + " to March " + str(y + 1) + ")"
                          + ("; force note: " + " | ".join(t[:260] for t in mine) if mine else ""),
            "source_homicide": ho_url, "source_population": ons_url, "retrieved": FETCH.retrieved_on(ho_url, ons_url), "financial_year": f"{y}/{str(y + 1)[2:]}"})
    if partial:
        late = sorted({y for _, y in partial})
        print(f"[partial] force-years with fewer than four quarters (no row): {len(partial)}; years {late}")
    if nopop:
        print(f"[no population] force-years without an ONS estimate (no row): years {sorted({y for _, y in nopop})}")
    if neg:
        print(f"[negative or fractional totals] left out: {neg}")
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "united_kingdom")
    last = int(df.year.max())
    print(f"\nLatest year {last}/{str(last + 1)[2:]} (highest rates first):")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].head(12).round(2).to_string(index=False))
    yearly = df.groupby("year").agg(forces=("unit", "size"), cases=("homicide_cases", "sum"))
    print("\n" + yearly.to_string())
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} force areas, financial years {int(df.year.min())}/{str(int(df.year.min()) + 1)[2:]} to {last}/{str(last + 1)[2:]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    a = ap.parse_args()
    cmd_inspect() if a.cmd == "inspect" else cmd_build()