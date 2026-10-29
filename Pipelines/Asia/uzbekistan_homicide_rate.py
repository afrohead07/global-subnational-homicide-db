#!/usr/bin/env python3
"""
Uzbekistan - registered intentional murders and attempted murders per 100,000 residents, 14 regions.

NUMERATOR   (official): National Statistics Committee (NSC) "Crime and Justice" open data, indicator 2.04.09.0036 "Registered murder and
            attempted murder by regions" (sdmx_data_807), annual, unit of measurement 'units'. The file's metadata names its source (printed
            at run time). The indicator INCLUDES attempted murder (stated in the indicator's own name, which is checked), hence
            definition_flags = includes_attempts. The file does not say whether the unit is cases or victims.
DENOMINATOR (official): NSC "Demography" open data, indicator 2.01.02.0001 "Permanent population - Total" (sdmx_data_246), thousand people,
            ON 1 JANUARY of each year (the periodicity in the file's metadata says 'на начало года', which is checked).
            Rate for year Y uses the mean of 1-Jan-Y and 1-Jan-(Y+1) (mid-year proxy, so population_age_years = 0). 'Permanent
            population' is the NSC concept; if it includes people registered in an area but living elsewhere, rates are understated there.
JOIN        Both files use the official SOATO region codes (4-digit; 1700 = whole country), kept as `unit_code`.
CHECKS      * the indicator name / unit / periodicity in each file's own metadata must match what we expect (the portal's page titles are
              NOT trusted: dataset 908 is titled 'murders' on the page but its metadata says 'grievous bodily harm');
            * crime: the 14 regions must not sum to more than the national row and the shortfall (cases the file does not allocate to a
              region) must be <= 5% of the national figure; the shortfall is reported every year and written into the rows;
            * population: the 14 regions must sum to the national row (+-0.5 thousand) in every year;
            * both files must contain the same 14 region codes; no missing / zero values;
            * population discontinuities (a region's change differing from the national change by more than BREAK_PP) are computed from
              the file and flagged; the file does not state their cause.
            Tier B for every row: one source, no independent second figure, and some years have unallocated cases. The text in
            `validation` is built from these results.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Uzbekistan/ ; the one output is
            uzbekistan_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python uzbekistan_homicide_rate.py inspect | build
Options:    --no-discover  (use the pinned dataset ids 807 / 246 instead of reading them from the portal pages)
Needs:      pip install pandas requests
"""
from __future__ import annotations
import argparse, html as htmllib, json, re, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 12:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Uzbekistan")      # raw downloads -> Data/Raw/<Region>/Uzbekistan/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="global-subnational-homicide-db research pipeline", retries=3)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP
MAX_UNALLOCATED = 0.05     # DECISION: tolerated share of national cases not allocated to a region
N_REGIONS = 14             # 12 regions + Republic of Karakalpakstan + Tashkent city
BREAK_PP = 2.5             # DECISION: flag a region-year when its population change differs from the national change by more than this many
                           # percentage points (the median difference over all region-years is ~0.2)

CRIME_PAGE = "https://stat.uz/en/official-statistics/crime-and-justice"
DEMO_PAGE = "https://stat.uz/en/official-statistics/demography"
CRIME_TITLE = "The number of registered intentional murders and attempted murders by region"
POP_TITLE = "Permanent population-Total"
PINNED = {"crime": 807, "pop": 246}                 # read from the NSC pages
API = "https://api.siat.stat.uz/media/uploads/sdmx/sdmx_data_{id}.json"


def find_id(page_url: str, title: str, label: str) -> int | None:
    """Read the dataset id that the portal page lists under `title` (first sdmx_data_N.json link after it)."""
    try:
        html = htmllib.unescape(FETCH.get(page_url).decode("utf-8", "replace"))
    except F.RobotsDisallowed:
        raise
    except Exception as e:
        print(f"[{label}] portal page failed: {e}")
        return None
    flat = re.sub(r"\s+", " ", html)
    i = flat.lower().find(title.lower())
    if i < 0:
        print(f"[{label}] title not found on the portal page")
        return None
    m = re.search(r"sdmx_data_(\d+)\.json", flat[i: i + 2500])
    return int(m.group(1)) if m else None


def load_sdmx(raw: bytes) -> tuple[dict, list]:
    obj = json.loads(raw.decode("utf-8-sig"))
    block = obj[0] if isinstance(obj, list) else obj
    meta = {m.get("name_en", ""): m for m in block["metadata"]}
    return meta, block["data"]


def mval(meta: dict, name: str, lang="value_en") -> str:
    return str(meta.get(name, {}).get(lang, ""))


def check_meta(kind: str, meta: dict):
    name, unit = mval(meta, "Indicator name"), mval(meta, "Unit of measurement")
    if kind == "crime":
        ok = re.search(r"murder", name, re.I) and re.search(r"attempt", name, re.I) and "region" in name.lower() and unit.lower() == "units"
    else:
        ok = "permanent population" in name.lower() and "total" in name.lower() and "thousand" in unit.lower() \
            and "начало года" in mval(meta, "Periodicity", "value_ru").lower()
    if not ok:
        raise ValueError(f"metadata does not match the expected {kind} indicator: name='{name}', unit='{unit}', "
                         f"periodicity='{mval(meta, 'Periodicity')}' / '{mval(meta, 'Periodicity', 'value_ru')}'")


def to_frame(data: list) -> tuple[pd.DataFrame, list[int]]:
    years = sorted({int(k) for r in data for k in r if re.fullmatch(r"\d{4}", k)})
    rows = []
    for r in data:
        rows.append({"code": str(r["Code"]), "name_en": re.sub(r"\s+", " ", str(r.get("Klassifikator_en", ""))).strip(),
                     "name_local": re.sub(r"\s+", " ", str(r.get("Klassifikator", ""))).strip(), **{y: r.get(str(y)) for y in years}})
    return pd.DataFrame(rows), years


def fetch_dataset(kind: str, discover: bool) -> dict:
    page, title = (CRIME_PAGE, CRIME_TITLE) if kind == "crime" else (DEMO_PAGE, POP_TITLE)
    cands = []
    if discover:
        d = find_id(page, title, kind)
        if d:
            cands.append(d)
    if PINNED[kind] not in cands:
        cands.append(PINNED[kind])
    last_err = None
    for ds in cands:
        url = API.format(id=ds)
        try:
            raw = FETCH.get(url, f"nsc_{kind}_sdmx_{ds}", reuse=False, suffix=".json")
            meta, data = load_sdmx(raw)
            check_meta(kind, meta)
        except F.RobotsDisallowed:
            raise
        except Exception as e:
            last_err = f"dataset {ds}: {type(e).__name__}: {e}"
            print(f"[{kind}] {last_err}")
            continue
        print(f"[{kind}] dataset {ds}: '{mval(meta, 'Indicator name')}' (code {mval(meta, 'Indicator identification number (code)')}), "
              f"last modified {mval(meta, 'Last modified date')}, source: {mval(meta, 'Source') or mval(meta, 'Primary source of information')}")
        if discover and ds != PINNED[kind]:
            print(f"    note: the portal page now lists id {ds}, pinned id is {PINNED[kind]}")
        df, years = to_frame(data)
        return {"id": ds, "url": url, "meta": meta, "df": df, "years": years, "modified": mval(meta, "Last modified date"),
                "source": mval(meta, "Source") or mval(meta, "Primary source of information"), "retrieved": FETCH.retrieved_on(url)}
    sys.exit(f"[stop] no valid {kind} dataset: {last_err}")


def regions(df: pd.DataFrame) -> pd.DataFrame:
    r = df[(df.code.str.len() == 4) & (df.code != "1700")]
    return r.set_index("code")


def region_type(name: str) -> str:
    n = name.lower()
    return "autonomous_republic" if "republic" in n else ("city" if "city" in n else "region")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--no-discover", action="store_true")
    a = ap.parse_args()
    cr = fetch_dataset("crime", not a.no_discover)
    pp = fetch_dataset("pop", not a.no_discover)

    # ---- region sets
    rc, rp = regions(cr["df"]), regions(pp["df"])
    if len(rc) != N_REGIONS or set(rc.index) != set(rp.index):
        sys.exit(f"[stop] region codes differ: crime {sorted(rc.index)} vs population {sorted(rp.index)}")
    nat_c = cr["df"][cr["df"].code == "1700"]
    nat_p = pp["df"][pp["df"].code == "1700"]
    if nat_c.empty or nat_p.empty:
        sys.exit("[stop] national row (code 1700) missing")
    nat_c, nat_p = nat_c.iloc[0], nat_p.iloc[0]
    print(f"\n[regions] {N_REGIONS} region codes identical in both files: {', '.join(sorted(rc.index))}")

    # ---- crime checks
    rows_chk = []
    for y in cr["years"]:
        vals = rc[y]
        if vals.isna().any() or (vals < 0).any():
            sys.exit(f"[stop] crime {y}: missing or negative regional value")
        s, n = float(vals.sum()), float(nat_c[y])
        short = n - s
        if short < 0 or short > MAX_UNALLOCATED * n:
            sys.exit(f"[stop] crime {y}: sum of regions {s:.0f} vs national {n:.0f} (shortfall {short:.0f}, allowed 0..{MAX_UNALLOCATED:.0%} of national)")
        rows_chk.append((y, int(s), int(n), int(short)))
    uns = [r for r in rows_chk if r[3] > 0]
    print(f"[crime] regions sum <= national in all {len(rows_chk)} years; years with cases not allocated to a region: "
          + (", ".join(f"{y}: {k}" for y, s, n, k in uns) or "none"))

    # ---- population checks
    for y in pp["years"]:
        vals = rp[y]
        if vals.isna().any() or (vals <= 0).any():
            sys.exit(f"[stop] population {y}: missing or non-positive regional value")
        if abs(float(vals.sum()) - float(nat_p[y])) > 0.5:
            sys.exit(f"[stop] population {y}: sum of regions {vals.sum():.1f} != national {nat_p[y]:.1f} (thousand)")
    print(f"[population] regions sum to the national population in all {len(pp['years'])} years ({pp['years'][0]}-{pp['years'][-1]}, 1 January)")

    # ---- population discontinuities: computed from the file, nothing typed in
    tab = []
    for y in pp["years"][:-1]:
        gn = (float(nat_p[y + 1]) / float(nat_p[y]) - 1) * 100
        for code in rp.index:
            g = (float(rp.loc[code, y + 1]) / float(rp.loc[code, y]) - 1) * 100
            tab.append((code, y, g - gn, g, gn))
    med = float(pd.Series([abs(t[2]) for t in tab]).median())
    flagged = sorted([t for t in tab if abs(t[2]) > BREAK_PP], key=lambda t: (t[0], t[1]))
    dev = {(t[0], t[1]): t for t in tab}
    print(f"[population] year-to-year discontinuities: |region change - national change| > {BREAK_PP} pp "
          f"(median over all {len(tab)} region-years: {med:.2f} pp); the file does not state the cause")
    for code, y, d, g, gn in flagged:
        print(f"    {rc.loc[code, 'name_en']} {y}->{y + 1}: {g:+.1f}% vs national {gn:+.1f}%")
    if not flagged:
        print("    none")

    # ---- rows
    out = []
    unalloc = {y: k for y, s, n, k in rows_chk}
    nat_by_year = {y: n for y, s, n, k in rows_chk}
    for y in cr["years"]:
        if y not in pp["years"] or y + 1 not in pp["years"]:
            print(f"[skip] {y}: needs population on 1 Jan {y} and 1 Jan {y + 1}")
            continue
        for code, r in rc.iterrows():
            pop = round((float(rp.loc[code, y]) + float(rp.loc[code, y + 1])) / 2 * 1000)     # whole persons; the rate uses exactly this figure
            n = int(r[y])
            d = dev[(code, y)]
            flag = abs(d[2]) > BREAK_PP
            notes = [f"{unalloc[y]} of the national {nat_by_year[y]} cases of {y} are not allocated to any region in the file" if unalloc[y] else
                     f"all {nat_by_year[y]} national cases of {y} are allocated to regions"]
            if flag:
                notes.append(f"the population changes by {d[3]:+.1f}% between 1 Jan {y} and {y + 1} against {d[4]:+.1f}% nationally (a discontinuity the file does not explain)")
            notes.append("'permanent population' is the NSC concept; if it includes people registered in the area but living elsewhere, the rate is understated there")
            out.append({
                "country": "Uzbekistan", "unit": r["name_en"], "unit_local": r["name_local"], "unit_code": code, "admin_level": "admin1",
                "unit_type": region_type(r["name_en"]), "parent_unit": "", "year": y, "homicide_cases": n, "population": pop,
                "homicide_rate_per_100k": n / pop * 1e5, "flag_low_count": n < LOW_COUNT, "flag_outlier_year": False,
                "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": "B", "definition_flags": "includes_attempts",
                "validation": f"the 14 regions + {unalloc[y]} unallocated = the national row ({nat_by_year[y]}) of {y} (shortfall within {MAX_UNALLOCATED:.0%}); "
                              f"the 14 regions sum to the national population on 1 Jan {y} and {y + 1}; the indicator names, units and periodicity in both files' metadata "
                              f"were checked; both files carry the same 14 SOATO codes",
                "indicator": f"NSC indicator '{mval(cr['meta'], 'Indicator name')}' (units; murders AND attempted murders; source per the file's metadata: {cr['source'] or 'not stated'})",
                "population_method": f"mean of the NSC permanent population on 1 January {y} and 1 January {y + 1} ('{mval(pp['meta'], 'Indicator name')}', thousand people)",
                "data_notes": "; ".join(notes), "source_homicide": cr["url"], "source_population": pp["url"], "retrieved": min(cr["retrieved"], pp["retrieved"]),
                "national_total_cases": nat_by_year[y], "unallocated_national_cases": unalloc[y],
                "population_change_vs_national_pp": round(d[2], 3), "population_discontinuity_flag": flag,
                "homicide_file_last_modified": cr["modified"], "population_file_last_modified": pp["modified"]})
    df = pd.DataFrame(out)
    if df.empty:
        sys.exit("[stop] no overlapping years")
    df = df[df["population"] >= MIN_POP]
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[uzbekistan] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "uzbekistan")
    last = df.year.max()
    print(f"\nRate per 100k, {last} (highest first):")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)
          [["unit", "homicide_cases", "population", "homicide_rate_per_100k"]].round(3).to_string(index=False))
    g = df.groupby("year")[["homicide_cases", "population"]].sum()
    print("\nRate implied by the 14 regions (cases / population x 100k):\n" + (g.homicide_cases / g.population * 1e5).round(3).to_string())
    print(f"\nflag_low_count marks regions with fewer than {LOW_COUNT} cases ({int(df['flag_low_count'].sum())} rows); "
          f"population_discontinuity_flag marks {int(df['population_discontinuity_flag'].sum())} rows (see the list above).")
    if a.cmd == "build":
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit'].nunique()} regions, years {int(df.year.min())}-{int(df.year.max())})")
    else:
        print("\n[inspect only] no CSV written")


if __name__ == "__main__":
    main()