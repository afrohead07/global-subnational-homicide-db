#!/usr/bin/env python3
"""
Australia, Victoria - homicide per 100,000 residents by local government area (LGA), calendar years (LGAs of 100,000 or more residents).

POLICE (numerator): Crime Statistics Agency (CSA) Victoria, "Data Tables - LGA Recorded Offences", the newest workbook for the YEAR ENDING DECEMBER (Excel, CC BY, quarterly releases; each
            holds ten calendar years). Table 02, offence subdivision "A10 Homicide and related offences": the OFFENCES recorded by Victoria Police in the LGA (not victims, not incidents).
            The file gives only the subdivision total, with no split. By the CSA offence classification (read in full on 2026-10-27) A10 = A11 Murder + A12 Attempted murder + A13 Accessory or conspiracy to murder + A14 Manslaughter + A15 Driving causing death, so the count includes attempts and driving deaths (flag includes_attempts). A row that is absent means none recorded (the table lists
            only offences that occurred) and is read as 0 for an LGA that has other offences that year.
CONFIDENTIALITY  The CSA writes on the Contents sheet that homicide counts of 3 or less are given the value 2: a count of 2 is therefore a masked value (the true count is 1 to 3) and the row
            is flagged (flag_count_masked) and kept at tier B. Counts are extracted 18 days after the reference period and are revised between releases: the newest workbook wins.
EXCLUSIONS  Tables 02 to 06 exclude offences at justice institutions and immigration facilities, in Unincorporated Victoria and with an unknown location, so the LGAs do not add up to the
            whole state; the sum is compared with the ABS state victims.
POPULATION: ABS "Regional population" (3218.0): estimated resident population by LGA at 30 June (mid-year, age 0), shared module abs_lga_population.py. The CSA's own rate per 100,000 gives an
            independent implied population (offences of Table 01 / rate x 100,000) that is compared with the ABS one; for the latest year the CSA uses a Victorian government estimate.
CHECKS      (1) LGA names of the CSA must match the ABS LGAs of Victoria (an unmatched name with homicides stops the run); (2) the implied CSA population agrees with the ABS within 5%;
            (3) the Victoria total of the table is compared with the ABS state murder + manslaughter victims (australia_homicide_rate.csv next to this script), band max(25%, 3).
TIERS       A: the count is not masked (not 2), the populations agree and the state total agrees; B: anything else. Never tier C.

Folders:    this script sits in <repo>/Pipelines/Oceania/ ; downloads go to <repo>/Data/Raw/Oceania/Australia Victoria/ ; the one output is australia_victoria_homicide_rate.csv next to it.
Commands:   python australia_victoria_homicide_rate.py inspect | build          Option: --reuse (use the files saved by an earlier run)
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

from abs_lga_population import load_abs_population as _load_abs_population, norm          # shared with the other Australian LGA pipelines
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "Australia Victoria")
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
REUSE = {"on": False}
PAGES = ["https://www.crimestatistics.vic.gov.au/crime-statistics/latest-victorian-crime-data/download-data",
         "https://discover.data.vic.gov.au/dataset/data-tables-recorded-offences",
         "https://discover.data.vic.gov.au/dataset/data-tables-recorded-offences/historical"]
FILE_RE = re.compile(r"LGA[_ ]Recorded[_ ]Offences[_ ]Year[_ ]Ending[_ ]([A-Za-z]+)[_ ](\d{4})", re.I)
MONTHS = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"], 1)}
HOMICIDE = re.compile(r"homicide|murder|manslaughter", re.I)
ABS_POP_PAGE = "https://www.abs.gov.au/statistics/people/population/regional-population/latest-release"
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


def show(data: bytes, max_sheets: int = 10):
    """Structure of the workbook; for the homicide table also the full texts of Contents and Footnotes and a test of how the homicide counts are repeated."""
    t0 = time.time()
    xl = open_excel(data)
    print(f"   opened in {time.time() - t0:.0f} s; sheets ({len(xl.sheet_names)}): {xl.sheet_names[:20]}", flush=True)
    for sh in xl.sheet_names[:2]:                                          # Contents and Footnotes: every text in full (the confidentiality rule is written there)
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        print(f"   --- sheet '{sh}' ({raw.shape}), every non-empty text:")
        for i in range(len(raw)):
            txt = " | ".join(str(x).strip() for x in raw.iloc[i] if not pd.isna(x))
            if txt:
                print(f"      row {i:2d}: {txt[:700]}")
    for sh in xl.sheet_names[2:4]:                                         # Table 01 (all offences by LGA) and Table 02 (offence subgroups by Police Service Area and LGA)
        df = pd.read_excel(xl, sheet_name=sh, dtype=object)
        print(f"   --- sheet '{sh}': {df.shape}; columns {[(i, str(c)[:34]) for i, c in enumerate(df.columns)]}")
        yc = next((c for c in df.columns if str(c).strip().lower() == "year"), None)
        if yc is not None:
            print(f"      years: {sorted(map(str, df[yc].dropna().unique()))}; 'Year ending': {sorted(map(str, df.iloc[:, 1].dropna().unique()))}")
        if sh.endswith("02"):
            psa, lga, sub, grp = df.columns[2], df.columns[3], df.columns[5], df.columns[6]
            cnt = next(c for c in df.columns if str(c).lower().startswith("offence count"))
            h = df[df[sub].astype(str).str.contains(r"A10\b|homicide", case=False, regex=True)]
            print(f"      homicide subdivision labels: {sorted(map(str, h[sub].unique()))}; subgroup labels: {sorted(map(str, h[grp].unique()))}")
            print(f"      Police Service Areas: {df[psa].nunique()}; LGAs: {df[lga].nunique()}; homicide rows: {len(h)}")
            h = h.assign(_n=pd.to_numeric(h[cnt], errors="coerce"))
            multi = h.groupby([psa, yc])[lga].nunique()
            multi = multi[multi > 1]
            same = h.groupby([psa, yc])["_n"].nunique().reindex(multi.index)
            print(f"      Police Service Area-years with 2+ LGAs: {len(multi)}; of these the homicide count is IDENTICAL on every LGA row: {int((same == 1).sum())}"
                  + (f"; DIFFERENT on some: {[k for k in same.index[same > 1]][:5]}" if (same > 1).any() else ""))
            mp = df.groupby(psa)[lga].unique()
            print("      Police Service Areas with 2+ LGAs (first 12): " + "; ".join(f"{k}: {sorted(v)}" for k, v in mp[mp.map(len) > 1].head(12).items()))
            inm = df.groupby(lga)[psa].nunique()
            print(f"      LGAs that belong to more than one Police Service Area: {inm[inm > 1].to_dict() or 'none'}")
        else:
            print(df.head(3).to_string(max_colwidth=26))
    print(f"   (the other sheets, {xl.sheet_names[4:]}, hold locations, investigation status and drugs and are not needed)")


def find_files():
    """-> {(year, month): (url, source page)} of the LGA recorded offences workbooks listed on the official pages."""
    from bs4 import BeautifulSoup
    found = {}
    for page in PAGES:
        try:
            html = FETCH.get(page, "vic_page_" + re.sub(r"[^A-Za-z0-9]+", "_", page)[-40:], reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
        except F.RobotsDisallowed:
            print(f"   [robots] {page} does not allow automated reading")
            continue
        except Exception as e:
            print(f"   [skip] {page}: {e}")
            continue
        for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
            u = urljoin(page, a["href"])
            m = FILE_RE.search(unquote(u))
            if m and re.search(r"\.xlsx?(?:[?#]|$)", u, re.I) and m.group(1).lower() in MONTHS:
                found.setdefault((int(m.group(2)), MONTHS[m.group(1).lower()]), (u, page))
    return found


def cmd_inspect():
    files = find_files()
    print(f"[files] {len(files)} LGA recorded offences workbooks found on the official pages:")
    for (y, m), (u, pg) in sorted(files.items(), reverse=True):
        print(f"   year ending month {m:2d} {y}: {u}")
    if not files:
        print("   none: save a workbook by hand as manual_vic_lga.xlsx in " + str(RAW))
    todo = []
    dec = [k for k in files if k[1] == 12]
    if dec:
        todo.append(max(dec))
    if files and max(files) not in todo:
        todo.append(max(files))
    for k in todo:
        u = files[k][0]
        print(f"\n===== year ending month {k[1]} {k[0]} =====", flush=True)
        try:
            t0 = time.time()
            data = FETCH.get(u, f"vic_lga_offences_{k[0]}_{k[1]:02d}", reuse=REUSE["on"], suffix=".xlsx")
            print(f"   downloaded {len(data) / 1e6:.1f} MB in {time.time() - t0:.0f} s", flush=True)
            show(data)
        except F.RobotsDisallowed:
            print("   [robots] not allowed automatically: save it by hand as manual_vic_lga.xlsx in " + str(RAW))
        except Exception as e:
            print(f"   [skip] {e}")
    for p in sorted(RAW.glob("manual_vic*")):
        print(f"\n===== manual file {p.name} =====")
        show(p.read_bytes())
    print("\n[inspect only] nothing written; paste this output and the parser will be written against it")


LOW_COUNT = F.LOW_COUNT
STATE = "Victoria"
BAND_REL, BAND_ABS = 0.25, 3          # DECISION: the Victoria total of the CSA table and the ABS victims agree within max(25%, 3)
POP_TOL = 0.05                        # DECISION: the CSA's implied population and the ABS estimate agree within 5%


def load_abs_population(links, get):
    return _load_abs_population(links, get, open_excel)


def pick(df: pd.DataFrame, pattern: str, what: str) -> str:
    c = [x for x in df.columns if re.search(pattern, str(x), re.I)]
    if not c:
        sys.exit(f"[stop] CSA workbook: no column matching {pattern!r} for {what}; the columns are {[str(x) for x in df.columns]}")
    return c[0]


def load_csa(data: bytes):
    """-> (homicide counts {(lga, year): n}, universe of (lga, year) with any offence, implied population {(lga, year): n}, psa {lga: name}, texts of the Contents notes)."""
    xl = open_excel(data)
    for need in ("Table 01", "Table 02"):
        if need not in xl.sheet_names:
            sys.exit(f"[stop] CSA workbook: no sheet {need!r} (sheets: {xl.sheet_names})")
    t1 = pd.read_excel(xl, sheet_name="Table 01", dtype=object)
    t2 = pd.read_excel(xl, sheet_name="Table 02", dtype=object)
    y1, e1, l1, c1, r1 = (pick(t1, r"^year$", "year"), pick(t1, r"year ending", "year ending"), pick(t1, r"local government", "LGA"), pick(t1, r"offence count", "count"),
                          pick(t1, r"^rate per 100,000", "rate"))
    y2, e2, p2, l2, s2, c2 = (pick(t2, r"^year$", "year"), pick(t2, r"year ending", "year ending"), pick(t2, r"police service area", "PSA"), pick(t2, r"local government", "LGA"),
                              pick(t2, r"offence subdivision", "subdivision"), pick(t2, r"offence count", "count"))
    ends = set(map(str, t2[e2].dropna().unique())) | set(map(str, t1[e1].dropna().unique()))
    if ends != {"December"}:
        sys.exit(f"[stop] CSA workbook: 'Year ending' is {sorted(ends)}, not December: calendar years need the December workbook")
    t2 = t2.assign(_y=pd.to_numeric(t2[y2], errors="coerce"), _n=pd.to_numeric(t2[c2], errors="coerce"))
    universe = {(str(l).strip(), int(y)) for l, y in zip(t2[l2], t2["_y"]) if y == y}
    psa = {}
    for l, p_ in zip(t2[l2], t2[p2]):
        psa.setdefault(str(l).strip(), set()).add(str(p_).strip())
    multi = {k: v for k, v in psa.items() if len(v) > 1}
    if multi:
        sys.exit(f"[stop] LGAs in more than one Police Service Area: {dict(list(multi.items())[:5])}")
    hom = t2[t2[s2].astype(str).str.strip().str.upper().str.startswith("A10")]
    if hom["_n"].isna().any():
        sys.exit(f"[stop] {int(hom['_n'].isna().sum())} homicide count(s) are not numbers")
    grp = hom.groupby([hom[l2].astype(str).str.strip(), "_y"])["_n"].agg(["sum", "size"])
    if (grp["size"] > 1).any():
        print(f"[note] {int((grp['size'] > 1).sum())} LGA-years have more than one A10 row: summed")
    counts = {(l, int(y)): float(v) for (l, y), v in grp["sum"].items()}
    t1 = t1.assign(_y=pd.to_numeric(t1[y1], errors="coerce"), _n=pd.to_numeric(t1[c1], errors="coerce"), _r=pd.to_numeric(t1[r1], errors="coerce"))
    imp = {(str(l).strip(), int(y)): n / r * 1e5 for l, y, n, r in zip(t1[l1], t1["_y"], t1["_n"], t1["_r"]) if y == y and r == r and r > 0 and n == n}
    notes = []
    for sh in xl.sheet_names[:2]:
        raw = pd.read_excel(xl, sheet_name=sh, header=None, dtype=object)
        notes += [" | ".join(str(x).strip() for x in raw.iloc[i] if not pd.isna(x)) for i in range(len(raw))]
    return counts, universe, imp, {k: next(iter(v)) for k, v in psa.items()}, [n for n in notes if n]


def cmd_build():
    from bs4 import BeautifulSoup
    files = find_files()
    dec = [k for k in files if k[1] == 12]
    if not dec:
        sys.exit("[stop] no workbook for the year ending December was found on the official pages")
    key = max(dec)
    url = files[key][0]
    print(f"[csa] newest December workbook: year ending December {key[0]}  {url}")
    counts, universe, imp, psa, notes = load_csa(FETCH.get(url, f"vic_lga_offences_{key[0]}_12", reuse=REUSE["on"], suffix=".xlsx"))
    rule = next((n for n in notes if "given a value of 2" in n), None)
    if not rule:
        print("[warn] the confidentiality note about the value 2 was not found on the Contents sheet: counts of 2 are still flagged as masked")
    else:
        print(f"[confidentiality] {rule[:230]}")
    years = sorted({y for _, y in universe})
    vals = pd.Series(list(counts.values())).value_counts().sort_index()
    print(f"[counts] homicide offences per LGA-year read: {int(vals.sum())} non-zero LGA-years; distribution of the counts: {({int(k): int(v) for k, v in vals.head(8).items()})}; values 1 or 3 present: {int(vals.get(1.0, 0) + vals.get(3.0, 0))} (expected 0 if the rule holds)")
    html = FETCH.get(ABS_POP_PAGE, "abs_page_regional_population", reuse=REUSE["on"], suffix=".html").decode("utf-8", "replace")
    links = [(a.get_text(" ", strip=True), urljoin(ABS_POP_PAGE, a["href"])) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True) if re.search(r"\.xlsx?(?:[?#]|$)", a["href"], re.I)]
    erp, lgas, abs_name = load_abs_population(links, lambda u, n: FETCH.get(u, n, reuse=REUSE["on"], suffix=".xlsx"))
    vic = {c: v[0] for c, v in lgas.items() if v[1] == STATE}
    by_norm = {}
    for c, n in vic.items():
        by_norm.setdefault(norm(n), []).append(c)
    dup = {k: v for k, v in by_norm.items() if len(v) > 1}
    if dup:
        sys.exit(f"[stop] two ABS LGAs of {STATE} share one normalised name: {dup}")
    names = sorted({l for l, _ in universe})
    match = {n: by_norm[norm(n)][0] for n in names if norm(n) in by_norm}
    unmatched = [n for n in names if n not in match]
    bad = [n for n in unmatched if any(counts.get((n, y), 0) > 0 for y in years)]
    print(f"[abs] population from {abs_name}: {len(vic)} LGAs in {STATE}; [names] {len(match)} of {len(names)} CSA LGAs matched; unmatched: {unmatched or 'none'}")
    if bad:
        sys.exit(f"[stop] {len(bad)} CSA LGA(s) with homicides are not matched to an ABS LGA of {STATE}: {bad}. Add the correspondence from the lists above (no guessing).")
    abs_state, pth = {}, OUT.parent / "australia_homicide_rate.csv"
    if pth.exists():
        d0 = pd.read_csv(pth, dtype=str, keep_default_na=False)
        abs_state = {int(r.year): float(r.homicide_cases) for r in d0[d0["unit"] == STATE].itertuples()}
        print(f"[abs state] {len(abs_state)} years of ABS murder + manslaughter victims for {STATE} read from {pth.name}")
    else:
        print(f"[abs state] {pth.name} is not next to this script: the state-level confirmation is skipped (all rows tier B)")
    total = {y: sum(v for (l, yy), v in counts.items() if yy == y) for y in years}
    ratio = {y: total[y] / abs_state[y] for y in years if abs_state.get(y)}
    if ratio:
        print(f"[cross-verification] CSA A10 offences (sum of the LGAs) / ABS victims for {STATE}: median {pd.Series(ratio).median():.2f} over {len(ratio)} years (range {min(ratio.values()):.2f}-{max(ratio.values()):.2f})")
    rows, small, nopop = [], 0, 0
    for n, code in match.items():
        for y in years:
            if (n, y) not in universe:
                continue
            pop = erp.get((code, y))
            if pop is None:
                nopop += 1
                continue
            if pop < F.MIN_POP:
                small += 1
                continue
            cnt = int(counts.get((n, y), 0))
            masked = cnt == 2
            ip = imp.get((n, y))
            pdiff = None if ip is None else (ip - pop) / pop
            pop_ok = None if pdiff is None else bool(abs(pdiff) <= POP_TOL)
            va = abs_state.get(y)
            agree = None if va is None else bool(abs(total[y] - va) <= max(BAND_REL * va, BAND_ABS))
            tier = "A" if (not masked and pop_ok is True and agree is True) else "B"
            checks = [("the count is 2, the value the CSA gives to homicide counts of 3 or less (the true count is 1 to 3): masked" if masked else "the count is not a masked value"),
                      (f"the CSA's own rate implies a population {pdiff:+.1%} from the ABS estimate: {'within' if pop_ok else 'OUTSIDE'} 5%" if pdiff is not None else "no CSA population could be implied for this LGA-year"),
                      (f"Victoria total {total[y]:g} offences against {va:g} ABS victims: {'within' if agree else 'OUTSIDE'} the band of max(25%, 3)" if va is not None else "no ABS state-level figure for this year")]
            rows.append({"country": "Australia", "unit": vic[code], "unit_local": n, "unit_code": code, "admin_level": "admin2", "unit_type": "local government area", "parent_unit": STATE,
                         "year": y, "homicide_cases": cnt, "population": int(round(pop)), "homicide_rate_per_100k": cnt / pop * 1e5, "flag_low_count": cnt < LOW_COUNT,
                         "flag_outlier_year": False, "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "includes_attempts;includes_manslaughter",
                         "validation": "; ".join(checks),
                         "indicator": "CSA Victoria recorded offences: subdivision A10 Homicide and related offences = murder (A11), attempted murder (A12), accessory or conspiracy to murder (A13), manslaughter (A14) and driving causing death (A15) (CSA offence classification); the data tables do not split the subdivision",
                         "population_method": "ABS estimated resident population at 30 June of the year, persons",
                         "data_notes": "the unit is the recorded offence; counts of 3 or less are replaced by 2 by the CSA; an absent row is read as 0; the data are extracted 18 days after the reference period and revised between "
                                       "releases (the newest workbook is used); excludes justice institutions, immigration facilities, Unincorporated Victoria and unknown locations",
                         "source_homicide": url, "source_population": ABS_POP_PAGE, "retrieved": FETCH.retrieved_on(url, ABS_POP_PAGE),
                         "police_service_area": psa.get(n, ""), "flag_count_masked": masked, "population_csa_implied": None if ip is None else int(round(ip)),
                         "population_diff_pct": None if pdiff is None else round(pdiff * 100, 2), "abs_state_victims": va})
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    print(f"[scope] {df['unit'].nunique()} LGAs with at least one year of {F.MIN_POP:,}+ residents; {small} LGA-years left out below that population; {nopop} without an ABS estimate")
    pdf = df["population_diff_pct"].dropna()
    print(f"[population check] CSA implied population against the ABS: median {pdf.median():+.2f}%, within 5% in {(pdf.abs() <= 5).mean():.0%} of {len(pdf)} LGA-years; by year, share within 5%: "
          + ", ".join(f"{y}: {(g.abs() <= 5).mean():.0%}" for y, g in df.dropna(subset=['population_diff_pct']).groupby('year')['population_diff_pct']))
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "australia")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}; masked counts (2): {int(df['flag_count_masked'].astype(bool).sum())} rows")
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