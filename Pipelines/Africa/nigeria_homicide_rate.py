#!/usr/bin/env python3
"""
Nigeria - murder and manslaughter reported to the police, per 100,000 residents, by STATE (36 states + the Federal Capital Territory), 2017 (the 2016 edition is a PDF and follows once its layout is seen).

POLICE (numerator): National Bureau of Statistics (NBS), "Crime Statistics: Reported Offences by Type and State", edition 2017: workbook `CRIME STATISTICS 2017.xlsx`, sheet `Offences Against Persons`, one row per state,
            columns MURDER and MAN SLAUGHTER (manslaughter). homicide_cases = murder + manslaughter: offences REPORTED TO THE POLICE (cases, not victims), as compiled by the Nigeria Police Force. The workbook says nothing
            about incompleteness; reporting and recording in Nigeria are known to be far from complete, which is why no row can be tier A.
POPULATION: National Population Commission / NBS projections BY STATE from the 2006 census: the table of the NBS Demographic Statistics Bulletin 2020 (Annex 1, 2016-2019). It is a PROJECTION from a census 11 years
            older than the year (flag_population_projection), so the denominator is only as good as the 3.2% a year growth assumed.
CHECKS      (1) the states add up to the total row of the workbook's sheet when it has one; (2) the 37 projected populations add up to the national total of the table within 0.5%; (3) every state of the workbook is matched to
            one state of the population table (a matching table for the known spelling variants is printed). The tier is B for every row: no independent confirmation exists (no health registry is published) and the denominator
            is a projection.

Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/Nigeria/ ; the one output is nigeria_homicide_rate.csv next to the script.
Commands:   python nigeria_homicide_rate.py inspect | build          Options: --reuse (use the saved files)     (a file saved by hand as manual_*.xlsx / manual_*.pdf in the raw folder is read too)
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine pdfplumber truststore
"""
import argparse
import importlib.util
import io
import re
import sys
import warnings
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version (revision 14)")

REVISION = 3
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "Nigeria")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
ENGINE = "calamine" if importlib.util.find_spec("python_calamine") else "openpyxl"
CRIME_XLSX = "https://nigerianstat.gov.ng/resource/CRIME%20STATISTICS%202017.xlsx"
CRIME_PAGE = "https://nigerianstat.gov.ng/elibrary/read/786"
POP_BULLETIN = "https://nigerianstat.gov.ng/download/1241121"         # Demographic Statistics Bulletin 2020: projections 2016-2019 by state (Annex 1)
POP_FORECAST = "https://nigerianstat.gov.ng/download/474"             # Population forecasts 2006-2016 by state
YEAR = 2017
POP_TOL_NATIONAL = 0.005          # DECISION: the states add up to the national total of the table within 0.5%
LOW_COUNT = F.LOW_COUNT
# spelling variants between the crime workbook and the population table: normalised name (letters only, upper case) -> normalised name of the other
NON_STATE = {"PAP", "RAILWAY"}   # police commands without territory listed in the workbook beside the states: counted in the national total, no rate row
VARIANTS = {"CRIVER": "CROSSRIVER", "NASSARAWA": "NASARAWA", "FCT": "FCTABUJA", "ABUJA": "FCTABUJA", "FEDERALCAPITALTERRITORY": "FCTABUJA", "AKWAIBOM": "AKWAIBOM", "CROSSRIVER": "CROSSRIVER"}


def norm(x: str) -> str:
    n = re.sub(r"[^A-Z]", "", str(x).upper().replace("STATE", ""))
    return VARIANTS.get(n, n)


def pretty(x: str) -> str:
    if norm(x) == "CROSSRIVER":
        return "Cross River"
    t = re.sub(r"\s+", " ", str(x).replace("-", " ")).strip().title().replace("Fct", "FCT")
    return t


def open_excel(data: bytes):
    last = None
    for how in ("bytes", "openpyxl"):
        try:
            return pd.ExcelFile(io.BytesIO(data), engine=ENGINE if how == "bytes" else "openpyxl")
        except Exception as e:
            last = e
    raise last


def pdf_pages(data: bytes) -> list:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def get(url: str, name: str, suffix: str):
    man = sorted(RAW.glob(f"manual_{name}*"))
    if man:
        print(f"[manual] {man[0].name}")
        return man[0].read_bytes()
    return FETCH.get(url, name, reuse=REUSE["on"], suffix=suffix, reject_html=True)


def load_crime(data: bytes):
    """-> {state name as written: (murder, manslaughter)} and the total row (murder, manslaughter) if the sheet has one."""
    xl = open_excel(data)
    sh = next((n for n in xl.sheet_names if re.search(r"person", n, re.I)), None)
    if sh is None:
        sys.exit(f"[stop] no sheet about offences against persons in the workbook (sheets: {xl.sheet_names})")
    raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
    hdr = next((i for i in range(min(8, len(raw))) if str(raw.iat[i, 0]).strip().upper() == "STATE"), None)
    if hdr is None:
        sys.exit(f"[stop] sheet {sh!r}: no row whose first cell is STATE in its first 8 rows")
    cols = {re.sub(r"[^A-Z]", "", str(v).upper()): j for j, v in enumerate(raw.iloc[hdr]) if str(v) != "nan"}
    if "MURDER" not in cols or "MANSLAUGHTER" not in cols:
        sys.exit(f"[stop] sheet {sh!r}: the columns MURDER and MAN SLAUGHTER were not found (columns: {list(cols)[:14]})")
    out, total = {}, None
    for i in range(hdr + 1, len(raw)):
        name = str(raw.iat[i, 0]).strip()
        if name in ("", "nan"):
            continue
        m, s = pd.to_numeric(raw.iat[i, cols["MURDER"]], errors="coerce"), pd.to_numeric(raw.iat[i, cols["MANSLAUGHTER"]], errors="coerce")
        if re.match(r"^(grand\s+)?total|^nigeria$", name, re.I):
            total = (int(m), int(s)) if m == m and s == s else None
            continue
        if m != m or s != s:
            sys.exit(f"[stop] sheet {sh!r}: the murder or manslaughter count of {name!r} is not a number ({raw.iat[i, cols['MURDER']]!r}, {raw.iat[i, cols['MANSLAUGHTER']]!r})")
        out[name] = (int(m), int(s))
    return out, total


NUM = re.compile(r"\d{1,3}(?:,\d{3})+|\d{6,9}")


def load_projection(pages: list, year: int):
    """-> ({normalised state: population}, national total or None, how) for `year` from the table of state populations that has one column per year (2016-2019) or male/female/total triples per year. The table can run over
    several pages (the real one has Abia and Kano on one page and Lagos on the next); lines with other numbers of figures (birth registrations, nine numbers) are ignored."""
    rows, nat, pg = {}, None, []
    for k, t in enumerate(pages):
        for ln in t.splitlines():
            m = re.match(r"^\s*([A-Za-z][A-Za-z .\-/]+?)\s+((?:\d[\d,]*\s+){3,}\d[\d,]*)\s*$", ln)      # a mandatory separator between the numbers: no catastrophic backtracking
            if not m:
                continue
            nums = [int(x.replace(",", "")) for x in NUM.findall(m.group(2))]
            if len(nums) not in (4, 12):
                continue
            name = norm(m.group(1))
            vals = nums if len(nums) == 4 else [nums[3 * i + 2] for i in range(4)]
            if len(nums) == 12 and any(abs(nums[3 * i] + nums[3 * i + 1] - nums[3 * i + 2]) > 1 for i in range(4)):
                continue
            if name in ("NIGERIA", "TOTAL"):
                nat = vals
            elif len(name) >= 3 and name not in rows:
                rows[name] = vals
                pg.append(k + 1)
    if len(rows) < 36:
        return None, None, f"{len(rows)} states with four yearly populations (or four male/female/total triples) were found in the whole document (36 or more are needed)"
    yrs = sorted({y for t in pages[min(pg) - 1:max(pg)] for y in re.findall(r"\b(20[01]\d)\b", t)})
    first = int(yrs[0]) if yrs else 2016
    idx = year - first
    if not 0 <= idx <= 3:
        return None, None, f"the table (pages {min(pg)}-{max(pg)}, years {yrs}) does not cover {year}"
    return {n: v[idx] for n, v in rows.items()}, (nat[idx] if nat else None), f"pages {min(pg)}-{max(pg)}, column {idx + 1} of 4, years found {yrs}"


def cmd_inspect():
    print(f"[nigeria_homicide_rate.py revision {REVISION}]")
    try:
        crime, total = load_crime(get(CRIME_XLSX, "crime2017", ".xlsx"))
        print(f"[crime 2017] {len(crime)} states; murder + manslaughter {sum(a + b for a, b in crime.values()):,}; total row of the sheet: {total}")
        print("   the first 6:", list(crime.items())[:6])
    except Exception as e:
        print(f"[crime 2017] {str(e)[:200]}")
    for label, url, name in (("Demographic Statistics Bulletin 2020", POP_BULLETIN, "popbulletin"), ("Population forecasts 2006-2016", POP_FORECAST, "popforecast")):
        try:
            pages = pdf_pages(get(url, name, ".pdf"))
            print(f"\n[{label}] {len(pages)} pages")
            hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if re.search(r"\b(KANO|LAGOS|ABIA|FCT|BAYELSA|NIGERIA)\b", ln, re.I) and re.search(r"\d{1,3},\d{3}", ln)]
            print(f"   lines with a state and a number ({len(hit)}), the first 16:")
            for k, ln in hit[:16]:
                print(f"      p{k}: {ln[:150]}")
            res = load_projection(pages, 2017)
            print("   read for 2017:", (len(res[0]), "states, national", res[1], res[2]) if res[0] else res[2])
        except Exception as e:
            print(f"\n[{label}] {str(e)[:200]}")
    print("\n[inspect only] nothing written")


def cmd_build():
    print(f"[nigeria_homicide_rate.py revision {REVISION}]")
    crime, total = load_crime(get(CRIME_XLSX, "crime2017", ".xlsx"))
    print(f"[crime {YEAR}] {len(crime)} states; murder {sum(a for a, _ in crime.values()):,}, manslaughter {sum(b for _, b in crime.values()):,}")
    commands = {k: v for k, v in crime.items() if norm(k) in NON_STATE}
    crime = {k: v for k, v in crime.items() if norm(k) not in NON_STATE}
    if commands:
        print(f"[commands without territory] {', '.join(f'{k}: murder {a}, manslaughter {b}' for k, (a, b) in commands.items())}: counted in the national total, no rate row")
    if len(crime) != 37:
        sys.exit(f"[stop] {len(crime)} states in the sheet, expected 36 states + the FCT = 37 (after setting aside the commands without territory): {sorted(crime)}")
    if total is not None:
        ok = total == (sum(a for a, _ in crime.values()) + sum(a for a, _ in commands.values()), sum(b for _, b in crime.values()) + sum(b for _, b in commands.values()))
        print(f"[reconciliation] the states add up to the total row of the sheet: {'equal' if ok else 'DIFFERENT: ' + str(total)}")
    else:
        ok = None
        print("[reconciliation] the sheet has no total row: the states could not be compared with one")
    pops = None
    for label, url, name in (("Demographic Statistics Bulletin 2020", POP_BULLETIN, "popbulletin"),):
        pages = pdf_pages(get(url, name, ".pdf"))
        pops, nat, how = load_projection(pages, YEAR)
        if pops is None:
            hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if re.search(r"\b(KANO|LAGOS|ABIA|NIGERIA)\b", ln, re.I) and re.search(r"\d{1,3},\d{3}", ln)]
            print(f"   [diagnostic] {label}: {how}; lines with a state and a number ({len(hit)}), the first 12:")
            for k, ln in hit[:12]:
                print(f"      p{k}: {ln[:150]}")
            sys.exit("[stop] the population projections could not be read: save the bulletin by hand as manual_popbulletin.pdf or send the diagnostic")
        print(f"[population] {label}: {len(pops)} states, {how}")
    state_pop = {}
    miss = []
    for st in crime:
        n = norm(st)
        if n in pops:
            state_pop[st] = pops[n]
        else:
            miss.append(st)
    if miss:
        sys.exit(f"[stop] states of the crime workbook with no match in the population table: {miss}; the table has {sorted(pops)[:40]}")
    tot_pop = sum(state_pop.values())
    nat_ok = None if not nat else abs(tot_pop - nat) / nat <= POP_TOL_NATIONAL
    print(f"[population] the 37 states add up to {tot_pop:,}" + ("" if not nat else f"; the table's national total {nat:,}: {'within 0.5%' if nat_ok else 'DIFFERENT by ' + format((tot_pop - nat) / nat, '+.2%')}"))
    rows = []
    for st, (m, s) in crime.items():
        cases, pop = m + s, state_pop[st]
        rows.append({"country": "Nigeria", "unit": pretty(st), "unit_local": st, "unit_code": "", "admin_level": "admin1", "unit_type": "state" if "ABUJA" not in st.upper() else "federal_capital_territory", "parent_unit": "",
                     "year": YEAR, "homicide_cases": cases, "population": int(pop), "homicide_rate_per_100k": cases / pop * 1e5, "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False,
                     "population_age_years": 0.5, "indicator_type": "police_recorded_cases", "reliability_tier": "B", "definition_flags": "includes_manslaughter",
                     "validation": "; ".join([("the states add up to the total row of the sheet" if ok else "the states do NOT add up to the total row of the sheet" if ok is False else "no total row in the sheet to compare with"),
                                              ("the 37 projected populations add up to the table's national total within 0.5%" if nat_ok else "the projected populations do NOT add up to the table's national total" if nat_ok is False else "no national total in the table to compare with"),
                                              "no independent confirmation exists (no health registry is published); reporting to the police is known to be incomplete"]),
                     "indicator": "murder + manslaughter reported to the police (NBS: Offences against persons: MURDER and MAN SLAUGHTER), cases",
                     "population_method": "NPC / NBS population projection from the 2006 census, by state (NBS Demographic Statistics Bulletin 2020, Annex 1), column 2017",
                     "data_notes": f"calendar year {YEAR}; murder {m}, manslaughter {s}; counts are offences reported to the police, not victims; the workbook also lists commands without territory (" + ", ".join(commands) + f") with {sum(a + b for a, b in commands.values())} cases that are in the national total but in no state; the denominator is a projection from the 2006 census, 11 years older than the year",
                     "source_homicide": CRIME_XLSX, "source_population": POP_BULLETIN, "retrieved": FETCH.retrieved_on(CRIME_XLSX, POP_BULLETIN),
                     "murder_cases": m, "manslaughter_cases": s, "flag_population_projection": True})
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "nigeria")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}; national murder + manslaughter {int(df.homicide_cases.sum()):,} over {int(df.population.sum()):,} people = {df.homicide_cases.sum() / df.population.sum() * 1e5:.2f} per 100,000")
    print(df.sort_values("homicide_rate_per_100k", ascending=False)[["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].head(10).round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} states, year {YEAR})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()