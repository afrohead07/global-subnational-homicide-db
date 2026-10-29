#!/usr/bin/env python3
"""
Thailand - police-recorded murder cases per 100,000 residents, by province.

NUMERATOR   (official): National Statistical Office of Thailand (NSO) catalogue (https://www.nso.go.th/nsoweb/nso/statistics_and_indicators),
            "Statistics of Crimes against Person by Type of Crimes and Province: 2017-2022", data owner: National Police Agency (id jw).
            Crime 'Murder', first sub-column 'Reported' (cases reported, not arrests / accused; 'Negligent Homicide' is excluded).
DENOMINATOR (official): NSO, "Number of Mid-year Population by Sex, Region and Province: 2012-2024", data owner: Office of the Permanent
            Secretary, Ministry of Public Health (id gQ): the mid-year population estimate (Total).
CROSS-CHECK (official): NSO, registered population 2012-2025, Department of Provincial Administration (id i7). The two populations are
            different measures, so they are expected to be close, not equal: a province-year within XCHECK_TOL passes.
UNITS       Provinces, the finest level of the crime data. The region of the crime file is kept as the extra column `region`.
CHECKS      (1) the first sub-column of every year in the crime file must read 'Reported' (else the run stops); (2) per year, the provinces
            add up to the file's 'Whole Kingdom' row (a difference makes that year's rows tier C); (3) the population provinces are listed
            against the crime provinces: a crime province with no population counterpart is dropped and reported, and a population province
            left over (a spelling mismatch) stops the run (NAME_ALIASES below is for a confirmed same-province spelling difference);
            (4) the mid-year populations add up to a national figure of plausible size and are compared with the 'Whole Kingdom' row;
            (5) the registered population is within XCHECK_TOL of the mid-year estimate (a difference makes the row tier B).
            Tier A: (2) reconciles AND (5) passes AND the population is a mid-year estimate of the same year. The text in `validation`
            is built from these results.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Thailand/ ; the one output is
            thailand_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python thailand_homicide_rate.py inspect   (layouts of all files and the parser checks; no file written)
            python thailand_homicide_rate.py build     (writes the CSV)
Needs:      pip install pandas openpyxl requests
"""
import argparse
import difflib
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
if getattr(F, "REVISION", 0) < 11:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Thailand")        # raw downloads -> Data/Raw/<Region>/Thailand/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

BASE = "https://www.nso.go.th/nsoweb/downloadFile/stat_impt"
FILES = {
    "crime_en": f"{BASE}/jw/file_xls_en",
    "pop_midyear": f"{BASE}/gQ/file_xls_en",     # primary denominator (MoPH mid-year estimate)
    "pop_registered": f"{BASE}/i7/file_xls_en",  # cross-check (DOPA registered population)
}
CRIME_LABEL = "murder"
POP_NATIONAL_RANGE = (55e6, 75e6)     # sanity bounds for Thailand's population
XCHECK_TOL = 0.05                     # DECISION: registered vs mid-year population may differ by this share (different measures)
NAME_ALIASES: dict[str, str] = {}     # crime-file name -> population-file name, ONLY for a confirmed same-province spelling difference
# the registered-population file writes this province differently (mid-year / crime name -> registered name), both read from the real files
REGISTERED_ALIASES = {"phatthalung": "phattalung"}


def reg_key(name: str) -> str:
    """Name key of the registered-population file: its names carry a ' Province' suffix and sometimes double spaces."""
    return nk(re.sub(r"(?i)\s*province\s*$", "", str(name)))


# ---------- helpers ----------
def get_xlsx(key: str) -> tuple[bytes | None, str]:
    """-> (xlsx bytes or None, retrieval date). Live tables: downloaded at every run, a dated copy is kept in the raw folder."""
    url = FILES[key]
    try:
        data = FETCH.get(url, f"nso_{url.split('/')[-2]}", reuse=False, suffix=".xlsx")
    except F.RobotsDisallowed:
        print(f"[fetch] {key}: robots.txt does not allow an automated download; save {url} in {RAW} as nso_{url.split('/')[-2]}_<YYYYMMDD>.xlsx")
        return None, ""
    except Exception as e:
        print(f"[fetch] {key}: FAILED ({e})")
        return None, ""
    if not data.startswith(b"PK"):
        print(f"[fetch] {key}: not an xlsx (first bytes {data[:40]!r})")
        return None, ""
    return data, FETCH.retrieved_on(url)


def to_num(v):
    s = str(v).replace(",", "").strip()
    if s in ("-", "–", "—"):
        return 0.0
    try:
        return float(s)
    except ValueError:
        return float("nan")


def year_cell(v):
    """A cell that is exactly a year (CE or Buddhist Era) -> CE year, else None."""
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    s = str(int(v)) if isinstance(v, (int, float)) and float(v).is_integer() else str(v).strip()
    m = re.fullmatch(r"(?:พ\.ศ\.|ปี|year)?\s*(\d{4})", s, flags=re.I)
    if not m:
        return None
    y = int(m.group(1))
    y = y - 543 if y > 2400 else y
    return y if 1990 <= y <= 2040 else None


def nk(s: str) -> str:
    """Name key: lower-case letters/digits only ('Buri Ram' == 'Buriram')."""
    return re.sub(r"[^a-z0-9ก-๙]", "", str(s).lower())


def is_aggregate(name: str) -> bool:
    low = name.lower().strip()
    return (low.startswith("whole") or "kingdom" in low or low.endswith("region")
            or low.endswith("regions") or name.startswith(("ทั้งประเทศ", "ภาค", "ราชอาณาจักร")))


def is_whole(name: str) -> bool:
    low = name.lower().strip()
    return low.startswith("whole") or "kingdom" in low or name.startswith(("ทั้งประเทศ", "ราชอาณาจักร"))


def dump(data: bytes, name: str, rows=14, cols=12):
    xl = pd.ExcelFile(io.BytesIO(data))
    print(f"\n===== {name}  sheets: {xl.sheet_names} =====")
    for sh in xl.sheet_names[:3]:
        d = pd.read_excel(io.BytesIO(data), sheet_name=sh, header=None, dtype=object)
        print(f"--- sheet '{sh}' shape {d.shape}; top-left {rows} rows x {cols} cols ---")
        print(d.iloc[:rows, :cols].to_string(max_colwidth=26))


# ---------- crime parser ----------
def parse_crime(data: bytes) -> pd.DataFrame:
    """Long table: region, province, year, murders (Reported cases); includes 'Whole Kingdom' rows."""
    raw = pd.read_excel(io.BytesIO(data), header=None, sheet_name=0, dtype=object)
    hdr = next((i for i in range(min(15, len(raw))) if str(raw.iat[i, 2]).strip().lower() == "crime"), None)
    if hdr is None:
        dump(data, "crime file")
        sys.exit("[stop] crime file: header row (cell 'Crime' in 3rd column) not found. Layout changed?")
    years = raw.iloc[hdr, 3:].map(year_cell).ffill()
    subs = raw.iloc[hdr + 1, 3:]
    first_col, seen = {}, set()
    for c in years.index:
        y = years[c]
        if y is not None and not pd.isna(y) and y not in seen:
            seen.add(y)
            first_col[int(y)] = c
    wrong = {y: str(subs[c]) for y, c in first_col.items() if "report" not in str(subs[c]).strip().lower()}
    if wrong:
        sys.exit(f"[stop] crime file: the first sub-column of these years is not 'Reported': {wrong}. The murder count would not be reported cases.")
    body = raw.iloc[hdr + 2:].copy()
    body["region"] = body[0].ffill()
    body["province"] = body[1].ffill()
    body["crime"] = body[2].astype(str).str.strip()
    body = body[body["crime"].str.lower() == CRIME_LABEL]
    if body.empty:
        labels = sorted(raw.iloc[hdr + 2:, 2].dropna().astype(str).str.strip().unique())
        sys.exit(f"[stop] crime file: no '{CRIME_LABEL}' rows. Labels present: {labels}")
    rows, dashes = [], 0
    for _, r in body.iterrows():
        for y, c in first_col.items():
            dashes += str(r[c]).strip() in ("-", "–", "—")
            rows.append({"region": str(r["region"]).strip(), "province": str(r["province"]).strip(), "year": y, "murders": to_num(r[c])})
    out = pd.DataFrame(rows)
    if out["murders"].isna().any():
        sys.exit(f"[stop] crime file: non-numeric murder values:\n{out[out['murders'].isna()].head(10)}")
    if dashes:
        print(f"[crime] {dashes} cells were '-' (read as 0, NSO nil convention)")
    return out


# ---------- population parsers (two known NSO layouts; both fail loudly) ----------
def _header_years(raw, hdr):
    """Year per column from the nearest row at/above hdr holding year cells (merged cells carry right)."""
    years = [None] * raw.shape[1]
    for i in range(hdr, -1, -1):
        ys = [year_cell(v) for v in raw.iloc[i].tolist()]
        if any(y is not None for y in ys):
            last = None
            for j, y in enumerate(ys):
                last = y if y is not None else last
                years[j] = last
            break
    return years


def _find_row(raw, label):
    return next((i for i in range(min(25, len(raw))) if any(str(v).strip().lower() == label for v in raw.iloc[i].tolist())), None)


def _find_col(raw, hdr, label):
    return next((j for j, v in enumerate(raw.iloc[hdr].tolist()) if str(v).strip().lower() == label), None)


def _pop_midyear_layout(raw):
    """Header 'Province'; per year a merged block with Total / Male / Female columns."""
    hdr = _find_row(raw, "province")
    if hdr is None:
        return None
    pc, years = _find_col(raw, hdr, "province"), _header_years(raw, hdr)
    cols = {}
    for j, v in enumerate(raw.iloc[hdr].tolist()):
        if str(v).strip().lower() == "total" and years[j] is not None and years[j] not in cols:
            cols[years[j]] = j
    if not cols:
        return None
    body, recs = raw.iloc[hdr + 1:], []
    for idx in body.index:
        nm = body.at[idx, pc]
        if isinstance(nm, str) and nm.strip():
            recs += [(nm.strip(), y, to_num(body.at[idx, j])) for y, j in cols.items()]
    return pd.DataFrame(recs, columns=["province", "year", "population"])


def _pop_item_layout(raw):
    """Header 'Item'; one row per item ('Population total', male, female, area...), years across."""
    hdr = _find_row(raw, "item")
    if hdr is None:
        return None
    ic, pc = _find_col(raw, hdr, "item"), _find_col(raw, hdr, "province")
    ycols = {j: year_cell(v) for j, v in enumerate(raw.iloc[hdr].tolist()) if year_cell(v) is not None}
    if pc is None or not ycols:
        return None
    body = raw.iloc[hdr + 1:].copy()
    body["_prov"] = body[pc].ffill()
    sel = body[body[ic].astype(str).str.strip().str.lower().str.startswith("population total")]
    recs = [(str(r["_prov"]).strip(), y, to_num(r[j])) for _, r in sel.iterrows() for j, y in ycols.items()]
    return pd.DataFrame(recs, columns=["province", "year", "population"])


def parse_population(data: bytes, label: str, check_years=None):
    """-> (provinces long table, {year: sum of provinces - 'Whole Kingdom' row} or {} if no such row)."""
    xl = pd.ExcelFile(io.BytesIO(data))
    df = None
    for sh in xl.sheet_names:
        raw = pd.read_excel(io.BytesIO(data), sheet_name=sh, header=None, dtype=object)
        for fn in (_pop_midyear_layout, _pop_item_layout):
            d = fn(raw)
            if d is not None and len(d):
                print(f"[pop:{label}] sheet '{sh}' parsed with {fn.__name__}")
                df = d
                break
        if df is not None:
            break
    if df is None:
        dump(data, f"population file ({label})")
        sys.exit(f"[stop] population file ({label}): layout not recognised (see dump above).")
    if df["population"].isna().any():
        sys.exit(f"[stop] population file ({label}): non-numeric population values:\n{df[df['population'].isna()].head(10)}")
    if df.duplicated(["province", "year"], keep=False).any():
        dump(data, f"population file ({label})")
        sys.exit(f"[stop] population file ({label}): duplicate province-year rows.")
    whole = df[df["province"].map(is_whole)].set_index("year")["population"]
    prov = df[~df["province"].map(is_aggregate)].copy()
    nat = prov.groupby("year")["population"].sum()
    bad = nat[~nat.between(*POP_NATIONAL_RANGE)]
    if len(bad):
        fatal = [y for y in bad.index if check_years is not None and y in check_years]
        if fatal:
            dump(data, f"population file ({label})")
            sys.exit(f"[stop] population sanity check failed ({label}) for years in use:\n{nat}")
        print(f"[warn] {label}: national sum of provinces looks implausible in years not used here: { {int(y): int(v) for y, v in bad.items()} }")
    diffs = (nat - whole.reindex(nat.index)).dropna()
    print(f"[pop:{label}] sum of provinces vs 'Whole Kingdom' row:")
    print(pd.DataFrame({"sum_of_provinces": nat, "whole_kingdom_row": whole}).assign(diff=lambda x: x.sum_of_provinces - x.whole_kingdom_row))
    print(f"[pop:{label}] provinces: {prov['province'].nunique()}  years: {int(prov['year'].min())}-{int(prov['year'].max())}")
    return prov, {int(y): float(v) for y, v in diffs.items()}


def split_kingdom(df: pd.DataFrame):
    return (df[~df["province"].map(is_aggregate)].copy(), df[df["province"].map(is_whole)].set_index("year")["murders"])


# ---------- name matching ----------
def match_names(crime_names, pop_names):
    """Returns ({crime_name: pop_name}, [unmatched crime names]). Crime units with no population counterpart are dropped and reported -- unless
    population provinces are also left over (a spelling mismatch): then the run stops."""
    alias = {nk(k): v for k, v in NAME_ALIASES.items()}
    pop_by_key = {}
    for n in pop_names:
        pop_by_key.setdefault(nk(n), n)
    mapping, unmatched = {}, []
    for c in crime_names:
        if nk(c) in alias and alias[nk(c)] in pop_names:
            mapping[c] = alias[nk(c)]
            print(f"[match] alias: {c} -> {alias[nk(c)]}")
        elif nk(c) in pop_by_key:
            mapping[c] = pop_by_key[nk(c)]
        else:
            unmatched.append(c)
    leftover = sorted(set(pop_names) - set(mapping.values()))
    if unmatched:
        print("\n[match] crime units with no population match:")
        for c in unmatched:
            sug = difflib.get_close_matches(nk(c), [nk(x) for x in leftover], n=3, cutoff=0.5)
            print(f"   {c:34s} suggestions: {[pop_by_key[x] for x in sug]}")
    if leftover:
        print(f"[match] population provinces with no crime match: {leftover}")
        sys.exit("[stop] spelling mismatch between the two files. If both names are the same province, add the pair to NAME_ALIASES in this script.")
    return mapping, unmatched


# ---------- commands ----------
def cmd_inspect():
    files = {k: get_xlsx(k) for k in FILES}
    for k, (d, _) in files.items():
        if d is not None:
            dump(d, k)
    if files["crime_en"][0] is None:
        sys.exit("[stop] English crime file unavailable.")
    print("\n===== CRIME PARSE CHECK =====")
    prov, kingdom = split_kingdom(parse_crime(files["crime_en"][0]))
    print(pd.DataFrame({"sum_of_provinces": prov.groupby("year")["murders"].sum(), "whole_kingdom_row": kingdom})
          .assign(diff=lambda x: x.sum_of_provinces - x.whole_kingdom_row))
    print(f"units: {prov['province'].nunique()}\n{sorted(prov['province'].unique())}")
    for k in ("pop_midyear", "pop_registered"):
        if files[k][0] is not None:
            print(f"\n===== POPULATION PARSE CHECK: {k} =====")
            p, _ = parse_population(files[k][0], k)
            print(sorted(p["province"].unique()))
    print("\n[inspect only] no CSV written")


def cmd_build():
    (cd, c_got), (pd_, p_got) = get_xlsx("crime_en"), get_xlsx("pop_midyear")
    if cd is None or pd_ is None:
        sys.exit("[stop] a required file could not be downloaded (see [fetch] messages).")
    crime_raw = parse_crime(cd)
    crime, kingdom = split_kingdom(crime_raw)
    region_of = crime.drop_duplicates("province").set_index("province")["region"]
    print(f"[crime] units {crime['province'].nunique()}, years {crime['year'].min()}-{crime['year'].max()}")
    sums = crime.groupby("year")["murders"].sum()
    print(pd.DataFrame({"sum_of_provinces": sums, "whole_kingdom_row": kingdom}).assign(diff=lambda x: x.sum_of_provinces - x.whole_kingdom_row))
    recon = {int(y): (None if y not in kingdom.index else bool(sums[y] == kingdom[y])) for y in sums.index}

    pop, pop_diff = parse_population(pd_, "midyear", check_years=set(crime["year"]))
    mapping, unmatched = match_names(sorted(crime["province"].unique()), sorted(pop["province"].unique()))
    if unmatched:
        lost = crime[crime["province"].isin(unmatched)].groupby("province")["murders"].sum()
        print(f"[drop] {len(unmatched)} crime units without population are excluded; murders lost (all years):\n{lost.to_string()}")
        crime = crime[~crime["province"].isin(unmatched)]
    crime["pop_name"] = crime["province"].map(mapping)
    bureaus = {int(y): (int(g["murders"].sum()), ", ".join(sorted(set(g["province"])))) for y, g in crime_raw[crime_raw["province"].isin(unmatched)].groupby("year")} if unmatched else {}
    years = sorted(set(crime["year"]) & set(pop["year"]))
    print(f"[years] crime {crime['year'].min()}-{crime['year'].max()}, population {int(pop['year'].min())}-{int(pop['year'].max())} -> using {years[0]}-{years[-1]}")
    df = crime[crime["year"].isin(years)].merge(pop.rename(columns={"province": "pop_name"}), on=["pop_name", "year"], how="left")
    if df["population"].isna().any():
        sys.exit(f"[stop] missing population for:\n{df[df['population'].isna()][['province', 'year']]}")

    # cross-check against the registered-population series (a second official source)
    reg_alt, reg_got = None, ""
    rd, reg_got = get_xlsx("pop_registered")
    if rd is not None:
        try:
            reg, _ = parse_population(rd, "registered", check_years=set(crime["year"]))
            reg["k"] = reg["province"].map(reg_key)
            reg_alt = reg.set_index(["k", "year"])["population"]
            missing_reg = sorted(set(df["pop_name"]) - {n for n in df["pop_name"] if (REGISTERED_ALIASES.get(nk(n), nk(n))) in set(reg["k"])})
            if missing_reg:
                print(f"[xcheck] provinces with no registered-population figure (their rows stay tier B): {missing_reg}")
        except SystemExit as e:
            print(f"[xcheck] the registered-population file could not be used: {e}")
    if reg_alt is not None:
        alt = [reg_alt.get(k, float("nan")) for k in zip(df["pop_name"].map(lambda n: REGISTERED_ALIASES.get(nk(n), nk(n))), df["year"])]
        df["xdiff"] = [(a / p - 1) if a == a else float("nan") for a, p in zip(alt, df["population"])]
        print(f"[xcheck] registered vs mid-year population: median |diff| {df['xdiff'].abs().median():.1%}, max |diff| {df['xdiff'].abs().max():.1%} "
              f"(tolerance {XCHECK_TOL:.0%}; {int((df['xdiff'].abs() > XCHECK_TOL).sum())} province-years outside it)")
        print(df.assign(abs_diff=df["xdiff"].abs()).sort_values("abs_diff", ascending=False).drop_duplicates("province").head(5)[["province", "year", "xdiff"]].to_string(index=False))
    else:
        df["xdiff"] = float("nan")

    rows = []
    for r in df.sort_values(["province", "year"]).itertuples():
        y = int(r.year)
        pop_i = int(round(r.population))
        if pop_i < MIN_POP:
            continue
        rc = recon.get(y)
        pop_ok = None if r.xdiff != r.xdiff else bool(abs(r.xdiff) <= XCHECK_TOL)
        tier = "C" if rc is False else ("A" if (rc is True and pop_ok is True) else "B")
        checks = [("the provinces add up to the file's 'Whole Kingdom' row" if rc is True else
                   "the provinces DIFFER from the file's 'Whole Kingdom' row" if rc is False else "no 'Whole Kingdom' row to reconcile against"),
                  "the first sub-column of every year reads 'Reported'",
                  ("the mid-year populations add up to the 'Whole Kingdom' row" if pop_diff.get(y) == 0 else
                   f"the mid-year populations differ from the 'Whole Kingdom' row by {pop_diff[y]:+,.0f}" if y in pop_diff else "no 'Whole Kingdom' population row to compare"),
                  (f"the registered population (DOPA) is {r.xdiff:+.1%} of the mid-year estimate" + (" (within the tolerance)" if pop_ok else " (OUTSIDE the tolerance)")
                   if pop_ok is not None else "the registered population was not available for this province-year")]
        rows.append({
            "country": "Thailand", "unit": r.province, "unit_local": "", "unit_code": "", "admin_level": "admin1", "unit_type": "province",
            "parent_unit": "", "year": y, "homicide_cases": int(r.murders), "population": pop_i,
            "homicide_rate_per_100k": int(r.murders) / pop_i * 1e5, "flag_low_count": int(r.murders) < LOW_COUNT, "flag_outlier_year": False,
            "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "",
            "validation": "; ".join(checks),
            "indicator": "NSO table 'Statistics of Crimes against Person by Type of Crimes and Province' (National Police Agency): 'Murder', Reported cases "
                         "(not arrests or accused; negligent homicide excluded)",
            "population_method": "mid-year population estimate (Ministry of Public Health) via NSO, Total, same year",
            "data_notes": "the registered population (Department of Provincial Administration) is used only as a cross-check"
                          + (f"; {bureaus[y][0]} of the year's murders are with national police units that no province contains ({bureaus[y][1]}) and are not in any rate" if y in bureaus else ""),
            "source_homicide": FILES["crime_en"], "source_population": FILES["pop_midyear"] + (f" ; {FILES['pop_registered']}" if reg_alt is not None else ""),
            "retrieved": min(c_got, p_got, reg_got or c_got), "region": region_of.get(r.province, "")})
    out = pd.DataFrame(rows)
    out = F.add_outlier_flags(out)
    for _, r in out[out.flag_outlier_year].iterrows():
        print(f"[thailand] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if out["robust_z"].isna().all():
        out = out.drop(columns="robust_z")
    out = F.finalize(out)
    F.require_valid(out, "thailand")
    kept = out.groupby("year")["homicide_cases"].sum()
    cov = pd.DataFrame({"murders_in_output": kept, "whole_kingdom": kingdom.reindex(kept.index)})
    cov["coverage"] = (cov["murders_in_output"] / cov["whole_kingdom"]).map("{:.1%}".format)
    print("\n[coverage] share of 'Whole Kingdom' murders represented:")
    print(cov)
    print(f"\nReliability tiers: {out.reliability_tier.value_counts().to_dict()}")
    F.write_csv(out, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(out)} rows, {out['unit'].nunique()} provinces, years {years[0]}-{years[-1]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    a = ap.parse_args()
    cmd_inspect() if a.cmd == "inspect" else cmd_build()