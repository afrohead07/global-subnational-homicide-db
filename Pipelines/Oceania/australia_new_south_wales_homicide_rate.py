#!/usr/bin/env python3
"""
Australia, New South Wales - homicide per 100,000 residents by local government area (LGA) (calendar years, LGAs of 100,000 or more residents).

POLICE (numerator): NSW Bureau of Crime Statistics and Research (BOCSAR), open dataset "Recorded criminal incidents by month - by LGA" (Excel, CC BY, updated
            quarterly, monthly counts from 1995): criminal incidents recorded by NSW Police, EXCEPT that for murder and manslaughter BOCSAR's counting unit is the VICTIM (BOCSAR's definitions
            page and explanatory notes: where one murder incident involves a person killing six people, six murder victims are counted; checked 2026-10-27). Cases = the lines "Murder *" + "Manslaughter *" (the file's own labels; attempted murder and murder accessory / conspiracy are kept out). Only complete
            calendar years (12 months) are used.
POPULATION: ABS "Regional population" (3218.0): estimated resident population by LGA at 30 June, persons (mid-year, age 0); the latest year is preliminary. The cubes are found by
            their CONTENT (a table with 'LGA code', 'LGA name' and 20 or more years; a table with 'S/T code' beside 'LGA code'), not by the numbering of the file names.
CHECKS      (1) the LGAs add up to BOCSAR's own all-of-NSW line (open dataset "Recorded criminal incidents by month - all of NSW", read from its layout; if it cannot be read
            the run goes on without it and every row is tier B) (equal / within max(5%, 3) / beyond); (2) the NSW total of victims is compared with the ABS
            state-level victims of murder + manslaughter from australia_homicide_rate.csv when that file is next to this script (the same unit from two sources that differ in date
            conventions and revisions, so a band of max(25%, 3)); (3) every LGA with homicides in the file must be matched to an ABS LGA, or the run stops and lists the names;
            (4) the LGA population must be 100,000 or more in that year for a row (the smaller LGAs are counted).
TIERS       A: the LGAs reconcile to the NSW line and the NSW total agrees with the ABS state victims in that year; B: anything else (no NSW line, a difference, no ABS file).
            Never tier C: nothing here is contradicted by a hard check.
Series note BOCSAR counts what the police record; the label's asterisk is the file's own mark (its footnote is not in the data sheet) and is copied into the notes.

Folders:    this script sits in <repo>/Pipelines/Oceania/ ; downloads go to <repo>/Data/Raw/Oceania/Australia New South Wales/ ; the one output is
            australia_new_south_wales_homicide_rate.csv next to the script.
Commands:   python australia_new_south_wales_homicide_rate.py inspect | build          Option: --reuse (use the files saved by an earlier run)
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine
"""
import argparse
import importlib.util
import io
import re
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

from abs_lga_population import load_abs_population as _load_abs_population, norm, read_sheet      # shared with the other Australian LGA pipelines
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")        # the BOCSAR macro workbook carries header/footer markup openpyxl cannot read; irrelevant here
P = F.paths(__file__, "Australia New South Wales")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
BOCSAR_URL = "https://bocsarblob.blob.core.windows.net/bocsar-open-data/RCI_offencebymonth.xlsm"
NSW_LINE_URL = "https://bocsar.nsw.gov.au/content/dam/dcj/bocsar/documents/open-datasets/Incident_by_NSW.xlsx"        # BOCSAR: incidents by month, all of NSW
ABS_POP_PAGE = "https://www.abs.gov.au/statistics/people/population/regional-population/latest-release"
HOMICIDE = re.compile(r"homicide|murder|manslaughter", re.I)
ENGINE = "calamine" if importlib.util.find_spec("python_calamine") else "openpyxl"


def open_excel(data: bytes, suffix: str = ".xlsx") -> pd.ExcelFile:
    """Open a workbook ONCE: from the bytes with the fast reader, else from a saved copy with its real extension (the fast reader tells formats apart by
    the name), else with the slower tolerant reader."""
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
        except Exception as e:                      # the next way is tried; the last error is reported if none works
            last = e
    raise last


def show(data: bytes, label: str, suffix: str = ".xlsx", max_sheets: int = 8, pat=HOMICIDE, quiet: bool = False):
    t0 = time.time()
    xl = open_excel(data, suffix)
    print(f"   opened in {time.time() - t0:.0f} s; sheets ({len(xl.sheet_names)}): {xl.sheet_names[:20]}", flush=True)
    found = False
    for sh in xl.sheet_names[:max_sheets]:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        first = raw.iloc[:, :4].fillna("").astype(str)
        hit = raw[[bool(pat.search(" ".join(row))) for row in first.itertuples(index=False)]]
        head = raw.iloc[:8, :8].fillna("").astype(str)
        mention = bool(re.search(r"local government|\bLGA\b", " ".join(head.to_numpy().ravel()), re.I))
        found |= mention
        print(f"   --- sheet '{sh}': {raw.shape}" + ("  [mentions Local Government Area]" if mention else ""))
        if not quiet or mention:
            print(raw.iloc[:7, :8].to_string(max_colwidth=26, header=False))
        if len(hit) and not quiet:
            print(f"   rows mentioning the pattern ({len(hit)}), the first 8, first 8 columns:")
            print(hit.iloc[:8, :8].to_string(max_colwidth=26, header=False))
    return found


def cmd_inspect():
    print(f"[bocsar] {BOCSAR_URL}", flush=True)
    try:
        t0 = time.time()
        data = FETCH.get(BOCSAR_URL, "bocsar_rci_offencebymonth", reuse=REUSE["on"], suffix=".xlsm")
        print(f"   downloaded {len(data) / 1e6:.1f} MB in {time.time() - t0:.0f} s", flush=True)
        show(data, "BOCSAR", ".xlsm")
    except F.RobotsDisallowed:
        print("   [robots] not allowed automatically: save the file by hand as manual_bocsar.xlsm in " + str(RAW))
    except Exception as e:
        print(f"   [skip] {e}")
    for p in sorted(RAW.glob("manual_bocsar*")):
        print(f"\n===== manual file {p.name} =====")
        show(p.read_bytes(), p.name, p.suffix)
    print(f"\n[abs] regional population page: {ABS_POP_PAGE}", flush=True)
    try:
        from bs4 import BeautifulSoup
        html = FETCH.get(ABS_POP_PAGE, "abs_page_regional_population", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
        links = [(a.get_text(" ", strip=True), urljoin(ABS_POP_PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.xlsx?(?:[?#]|$)", a["href"], re.I)]
    except Exception as e:
        print(f"   [skip] {e}")
        links = []
    for t, u in links:
        print(f"   {unquote(u).rsplit('/', 1)[-1][:70]:70} {t[-24:]}")
    for t, u in links[:8]:                                                  # the file names no longer say what a cube holds: every small cube is opened and described
        nm = unquote(u).rsplit("/", 1)[-1]
        print(f"\n===== [abs] {nm} =====", flush=True)
        try:
            show(FETCH.get(u, "abs_pop_" + re.sub(r"[^A-Za-z0-9]+", "_", nm)[:40], reuse=REUSE["on"], suffix=".xlsx"), nm, ".xlsx", max_sheets=5,
                 pat=re.compile(r"sydney|blacktown|parramatta", re.I), quiet=True)
        except F.RobotsDisallowed:
            print("   [robots] not allowed automatically: save it by hand as manual_abs_<name>.xlsx in " + str(RAW))
        except Exception as e:
            print(f"   [skip] {e}")
    for p in sorted(RAW.glob("manual_abs*")):
        print(f"\n===== manual file {p.name} =====")
        show(p.read_bytes(), p.name, ".xlsx", max_sheets=5, pat=re.compile(r"sydney|blacktown", re.I), quiet=True)
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


LOW_COUNT = F.LOW_COUNT
STATE = "New South Wales"
RECON_REL, RECON_ABS = 0.05, 3        # DECISION: the LGAs add up to the all-NSW line within max(5%, 3)
BAND_REL, BAND_ABS = 0.25, 3          # DECISION: BOCSAR victims and ABS victims agree within max(25%, 3) (two sources, different dating and revisions)


def load_bocsar(data: bytes):
    """-> (frame of annual counts per LGA and line, the month columns used). One row per LGA, offence category and subcategory; the months run across."""
    xl = open_excel(data, ".xlsm")
    if "Data" not in xl.sheet_names:
        sys.exit(f"[stop] BOCSAR: no sheet 'Data' (sheets: {xl.sheet_names})")
    raw = read_sheet(xl, "Data")
    if [str(x).strip().lower() for x in raw.iloc[0, :3]] != ["lga", "offence category", "subcategory"]:
        sys.exit(f"[stop] BOCSAR: the first row is not 'LGA | Offence category | Subcategory | months' but {list(raw.iloc[0, :6])}")
    months = pd.to_datetime(raw.iloc[0, 3:], errors="coerce")
    if months.isna().any():
        sys.exit(f"[stop] BOCSAR: {int(months.isna().sum())} month header(s) are not dates")
    body = raw.iloc[1:, :].copy()
    body.columns = ["lga", "cat", "sub"] + list(months)
    hom = body[body["cat"].astype(str).str.strip().str.lower() == "homicide"].copy()
    lab = hom["sub"].astype(str).str.replace(r"\s*\*+\s*$", "", regex=True).str.strip().str.lower()
    hom["line"] = lab.map(lambda x: "murder" if x == "murder" else "manslaughter" if x == "manslaughter" else "attempted_murder" if x == "attempted murder"
                          else "murder_accessory" if x.startswith("murder accessory") else None)
    if hom["line"].isna().any():
        sys.exit(f"[stop] BOCSAR: an unknown homicide subcategory {sorted(set(hom.loc[hom['line'].isna(), 'sub'].astype(str)))}")
    if not {"murder", "manslaughter"} <= set(hom["line"]):
        sys.exit("[stop] BOCSAR: no 'Murder *' or 'Manslaughter *' line found in the homicide category")
    vals = hom[list(months)].apply(pd.to_numeric, errors="coerce")
    if vals.isna().any().any():
        sys.exit(f"[stop] BOCSAR: {int(vals.isna().sum().sum())} homicide cell(s) are not numbers")
    long = vals.copy()
    long["lga"], long["line"] = hom["lga"].astype(str).str.strip().values, hom["line"].values
    by_year = {}
    for y in sorted({m.year for m in months}):
        cols = [m for m in months if m.year == y]
        if len(cols) == 12:
            by_year[y] = long.groupby(["lga", "line"])[cols].sum().sum(axis=1)
    part = sorted({m.year for m in months} - set(by_year))
    ann = pd.DataFrame(by_year)
    return ann, part, str(hom["sub"].astype(str).iloc[0]), sorted(set(hom["sub"].astype(str)))


def load_nsw_line(data: bytes):
    """-> {year: murder + manslaughter incidents} for all of NSW from BOCSAR's second file, or None (the layout is printed) if it cannot be read. Layout expected: label columns
    (offence category and/or subcategory) followed by monthly columns with dates; only complete calendar years are used."""
    try:
        xl = open_excel(data, ".xlsx")
        for sh in xl.sheet_names:
            raw = read_sheet(xl, sh)
            if raw.empty:
                continue
            isd = lambda v: hasattr(v, "year") and not isinstance(v, (int, float, str))
            hr = max(range(min(15, len(raw))), key=lambda i: sum(isd(v) for v in raw.iloc[i]))
            mcols = [j for j, v in enumerate(raw.iloc[hr]) if isd(v)]
            if len(mcols) < 24:
                continue
            lab = list(range(0, mcols[0]))
            mon = {}
            for i in range(hr + 1, len(raw)):
                txt = [str(raw.iat[i, j]).strip() for j in lab if not pd.isna(raw.iat[i, j])]
                line = next((("murder" if re.sub(r"\s*\*+$", "", t).strip().lower() == "murder" else "manslaughter") for t in txt
                             if re.sub(r"\s*\*+$", "", t).strip().lower() in ("murder", "manslaughter")), None)
                if line is None or (len(lab) > 1 and not any(t.lower() == "homicide" for t in txt)):
                    continue
                for j in mcols:
                    v = pd.to_numeric(raw.iat[i, j], errors="coerce")
                    mon.setdefault((line, pd.Timestamp(raw.iat[hr, j]).year), []).append(0.0 if v != v else float(v))
            years = sorted({y for _, y in mon})
            out = {y: sum(sum(mon.get((l, y), [])) for l in ("murder", "manslaughter")) for y in years
                   if all(len(mon.get((l, y), [])) == 12 for l in ("murder", "manslaughter"))}
            if out and any(l == "murder" for l, _ in mon) and any(l == "manslaughter" for l, _ in mon):
                return out
        print("[nsw line] no sheet of BOCSAR's all-NSW file holds Murder and Manslaughter lines with monthly dates: the first rows of the first sheet are shown, the run goes on without the line")
        print(read_sheet(xl, xl.sheet_names[0]).iloc[:8, :8].to_string(max_colwidth=26, header=False))
    except Exception as e:
        print(f"[nsw line] the all-NSW file could not be read ({e}); the run goes on without it, every row tier B")
    return None


def load_abs_population(links, get):
    return _load_abs_population(links, get, open_excel)


def cmd_build():
    from bs4 import BeautifulSoup
    data = FETCH.get(BOCSAR_URL, "bocsar_rci_offencebymonth", reuse=REUSE["on"], suffix=".xlsm")
    ann, partial, label0, labels = load_bocsar(data)
    print(f"[bocsar] {len(set(i[0] for i in ann.index))} LGA rows, complete calendar years {int(ann.columns.min())}-{int(ann.columns.max())}; partial year(s) left out: {partial}; "
          f"labels of the homicide lines: {labels}")
    html = FETCH.get(ABS_POP_PAGE, "abs_page_regional_population", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    links = [(a.get_text(" ", strip=True), urljoin(ABS_POP_PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.xlsx?(?:[?#]|$)", a["href"], re.I)]
    erp, lgas, abs_name = load_abs_population(links, lambda u, n: FETCH.get(u, n, reuse=REUSE["on"], suffix=".xlsx"))
    nsw = {c: v[0] for c, v in lgas.items() if v[1] == STATE}
    print(f"[abs] population from {abs_name}: {len(lgas)} LGAs, {len(nsw)} in {STATE}; years {min(y for _, y in erp)}-{max(y for _, y in erp)}")
    by_norm = {}
    for c, n in nsw.items():
        by_norm.setdefault(norm(n), []).append(c)
    dup = {k: v for k, v in by_norm.items() if len(v) > 1}
    if dup:
        sys.exit(f"[stop] two ABS LGAs of {STATE} share one normalised name: {dup}")
    # the LGAs of the file: matched to ABS, or aggregates (all of NSW, Greater Sydney ...), or unmatched
    names = sorted({i[0] for i in ann.index})
    agg_re = re.compile(r"^(nsw|new south wales|all nsw|greater sydney|regional nsw|rest of nsw|sydney region|total)$", re.I)
    non_lga_re = re.compile(r"in custody|unincorporated|offshore|migratory|no fixed|unknown", re.I)        # categories of the file that are not a council area: no geography or no council, so no population
    match, aggs, unmatched, nonlga = {}, [], [], []
    for n in names:
        if norm(n) in by_norm:
            match[n] = by_norm[norm(n)][0]
        elif agg_re.match(n.strip()):
            aggs.append(n)
        elif non_lga_re.search(n):
            nonlga.append(n)
        else:
            unmatched.append(n)
    tot = lambda n, y: float(sum(ann[y].get((n, l), 0) for l in ("murder", "manslaughter")))
    bad = [n for n in unmatched if any(tot(n, y) > 0 for y in ann.columns)]
    print(f"[names] {len(match)} BOCSAR LGAs matched to the ABS; aggregates in the file: {aggs or 'none'}; unmatched without homicides: {[n for n in unmatched if n not in bad] or 'none'}")
    for n in nonlga:
        print(f"[non-LGA category] {n!r}: {int(sum(tot(n, y) for y in ann.columns))} murder + manslaughter incidents in {int(ann.columns.min())}-{int(ann.columns.max())}; counted in the NSW total, no row (not a council area)")
    if bad:
        sys.exit(f"[stop] {len(bad)} BOCSAR LGA(s) with recorded homicides are neither matched to an ABS LGA of {STATE} nor a known non-LGA category: {bad}. Add the correspondence from the two lists above (no guessing).")
    # (1) the LGAs against the all-NSW line
    nsw_line = next((a for a in aggs if re.fullmatch(r"nsw|new south wales|all nsw", a.strip(), re.I)), None)
    ext, man = None, sorted(RAW.glob("manual_nsw_line*"))
    try:
        if man:
            print(f"[nsw line] using the file saved by hand: {man[0].name}")
            ext = load_nsw_line(man[0].read_bytes())
        else:
            ext = load_nsw_line(FETCH.get(NSW_LINE_URL, "bocsar_incident_by_nsw", reuse=REUSE["on"], suffix=".xlsx"))
    except Exception as e:                     # a refused download (HTTP 403 / robots) or an unreadable file: the run goes on without the line
        print(f"[nsw line] BOCSAR's all-NSW file could not be fetched by the script ({str(e)[:90]}). To reach tier A, open {NSW_LINE_URL} in a browser, save the file as "
              f"manual_nsw_line.xlsx in {RAW} and run again; for now every row is tier B.")
    if ext is not None:
        print(f"[nsw line] BOCSAR all-NSW file: murder + manslaughter incidents for {len(ext)} complete calendar years ({min(ext)}-{max(ext)})")
    recon = {}
    for y in ann.columns:
        lga_sum = sum(tot(n, y) for n in list(match) + unmatched + nonlga)
        if nsw_line is None and (ext is None or y not in ext):
            recon[y] = ("none", 0.0, lga_sum)
        else:
            top = tot(nsw_line, y) if nsw_line is not None else ext[y]
            d = lga_sum - top
            recon[y] = ("equal" if d == 0 else "close" if abs(d) <= max(RECON_REL * top, RECON_ABS) else "far", d, top)
    print("[reconciliation] LGAs against the all-NSW line, by year: " + str(pd.Series([v[0] for v in recon.values()]).value_counts().to_dict()))
    # (2) the ABS state-level victims, when that output is next to this script
    abs_state = {}
    pth = OUT.parent / "australia_homicide_rate.csv"
    if pth.exists():
        d0 = pd.read_csv(pth, dtype=str, keep_default_na=False)
        d0 = d0[d0["unit"] == STATE]
        abs_state = {int(r.year): float(r.homicide_cases) for r in d0.itertuples()}
        print(f"[abs state] {len(abs_state)} years of ABS murder + manslaughter victims for {STATE} read from {pth.name}")
    else:
        print(f"[abs state] {pth.name} is not next to this script: the state-level confirmation is skipped (all rows tier B)")
    inc_nsw = {y: sum(tot(n, y) for n in list(match) + unmatched + nonlga) for y in ann.columns}
    ratio = {y: inc_nsw[y] / abs_state[y] for y in ann.columns if abs_state.get(y)}
    if ratio:
        print(f"[cross-verification] BOCSAR victims / ABS victims for {STATE}: median {pd.Series(ratio).median():.2f} over {len(ratio)} years (range {min(ratio.values()):.2f}-{max(ratio.values()):.2f})")
    used = [l for l in labels if re.match(r"(murder|manslaughter)\b", l.strip().lower()) and "accessory" not in l.lower()]
    rows, small, nomatch_pop = [], 0, 0
    for n, code in match.items():
        for y in ann.columns:
            pop = erp.get((code, int(y)))
            if pop is None:
                nomatch_pop += 1
                continue
            if pop < F.MIN_POP:
                small += 1
                continue
            mu, ma = float(ann[y].get((n, "murder"), 0)), float(ann[y].get((n, "manslaughter"), 0))
            cases = int(mu + ma)
            rec, rdiff, rtop = recon[y]
            va = abs_state.get(int(y))
            agree = None if va is None else bool(abs(inc_nsw[y] - va) <= max(BAND_REL * va, BAND_ABS))
            tier = "A" if (rec in ("equal", "close") and agree is True) else "B"
            checks = [("the LGAs add up exactly to BOCSAR's all-NSW line" if rec == "equal" else f"the LGAs are within {abs(rdiff):g} incident(s) of BOCSAR's all-NSW line ({rtop:g})" if rec == "close"
                       else f"the LGAs DIFFER from BOCSAR's all-NSW line by {rdiff:+g} ({rtop:g})" if rec == "far" else "BOCSAR's all-NSW file could not be used to reconcile the LGAs"),
                      (f"NSW total {inc_nsw[y]:g} BOCSAR victims against {va:g} ABS victims: {'within' if agree else 'OUTSIDE'} the band of max(25%, 3)" if va is not None else "no ABS state-level figure for this year"),
                      "population: ABS estimated resident population at 30 June"]
            rows.append({"country": "Australia", "unit": nsw[code], "unit_local": n, "unit_code": code, "admin_level": "admin2", "unit_type": "local government area", "parent_unit": STATE,
                         "year": int(y), "homicide_cases": cases, "population": int(round(pop)), "homicide_rate_per_100k": cases / pop * 1e5,
                         "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": 0.0, "indicator_type": "police_recorded_cases",
                         "reliability_tier": tier, "definition_flags": "includes_manslaughter;counts_victims", "validation": "; ".join(checks),
                         "indicator": "BOCSAR recorded victims of murder + manslaughter (BOCSAR counts murder and manslaughter by victim; attempted murder, murder accessory and conspiracy excluded)",
                         "population_method": "ABS estimated resident population at 30 June of the year, persons; the latest year is preliminary",
                         "data_notes": f"the unit is the victim (BOCSAR's counting unit for murder and manslaughter); the lines used are labelled {used!r} in the file (the asterisk is the file's own mark); calendar year summed from the monthly counts",
                         "source_homicide": BOCSAR_URL, "source_population": ABS_POP_PAGE, "retrieved": FETCH.retrieved_on(BOCSAR_URL, ABS_POP_PAGE),
                         "murder_victims": int(mu), "manslaughter_victims": int(ma), "abs_state_victims": va})
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    print(f"[scope] {df['unit'].nunique()} LGAs with at least one year of {F.MIN_POP:,}+ residents; {small} LGA-years left out below that population; {nomatch_pop} LGA-years without an ABS estimate")
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
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_inspect() if a.cmd == "inspect" else cmd_build()