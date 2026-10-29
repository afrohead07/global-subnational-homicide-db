#!/usr/bin/env python3
"""
Singapore - police-recorded murder cases per 100,000 residents (a city-state: one national unit).

NUMERATOR   (official): Department of Statistics Singapore (SingStat) Table Builder API, table M890891 "Cases Recorded For Selected Major
            Offences", series "Murder" (annual cases recorded).
DENOMINATOR (official): SingStat Table Builder API, table M810811 "Key Annual Indicators On Population", series "Total Population".
            The table (population by broad age group and sex, at end June) does not itself say whether non-residents are included; the script
            keeps the "Total Population" series of the original, and `inspect` lists the other population rows of the table.
UNITS       The unit of measure is read from each API response ("Number", "Thousand", ...) and applied; the result must be of Singapore's
            scale (SCALE below) or the run stops, so a unit mistake cannot pass silently. The table titles, units of measure, footnotes and
            last-update dates are quoted from the response in `indicator`, `population_method` and `data_notes`.
YEARS       The years present in BOTH series from FIRST_YEAR (the original script's choice) to the current year.
CHECKS      Both series are found by their exact row names; the unit of measure is recognised; the population is of national scale; the
            years overlap; counts are whole numbers >= 0; Total Population = Total Male Population + Total Female Population in every
            year (a difference makes the rows tier C; if those rows are absent the check is reported as not run). `population_age_years` is 0 only if the table's own text says the figure is a
            June / mid-year figure; otherwise it is left blank and the rows are tier B. Every row is tier B anyway: one source, no
            independent second figure (the police annual crime brief is not machine-readable). The text in `validation` is built from
            these results.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Singapore/ ; the one output is
            singapore_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python singapore_homicide_rate.py inspect | build
Needs:      pip install pandas requests
"""
import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 8:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Singapore")       # raw downloads -> Data/Raw/<Region>/Singapore/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)", retries=3)
LOW_COUNT = F.LOW_COUNT

CRIME_API_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M890891"
POP_API_URL = "https://tablebuilder.singstat.gov.sg/api/table/tabledata/M810811"
CRIME_SERIES = "Murder"
POP_SERIES = "Total Population"
FIRST_YEAR = 2011                  # DECISION: first year used (the original script's choice)
SCALE = (1e6, 1e7)                 # a Singapore population in persons lies between these; otherwise the unit of measure is wrong
HEADERS = {"Accept": "application/json"}


def fetch_table(url: str, name: str) -> dict:
    """The API payload of one table (a dated copy is kept in the raw folder)."""
    try:
        payload = json.loads(FETCH.get(url, name, reuse=False, suffix=".json", headers=HEADERS).decode("utf-8"))
    except (RuntimeError, ValueError) as e:
        sys.exit(f"[stop] could not read the SingStat table {url}: {e}")
    data = payload.get("Data") or payload.get("data") or {}
    rows = data.get("row") or data.get("records") or []
    if not rows:
        sys.exit(f"[stop] no rows in the SingStat response of {url} (keys: {list(payload)})")
    return {"url": url, "title": str(data.get("title", "")).strip(), "uom": str(data.get("uoM", "")).strip(),
            "footnote": str(data.get("footnote", "")).strip(), "updated": str(data.get("dataLastUpdated", "")).strip(),
            "frequency": str(data.get("frequency", "")).strip(), "rows": rows}


def series_of(table: dict, series: str) -> dict:
    """One row of a table found by its exact name (case-insensitive) -> values by year, unit of measure and footnote."""
    hit = [r for r in table["rows"] if str(r.get("rowText", "")).strip().lower() == series.lower()]
    if not hit:
        sys.exit(f"[stop] the series '{series}' is not in {table['url']}; the rows are: {[str(r.get('rowText', ''))[:40] for r in table['rows'][:25]]}")
    row = hit[0]
    values = {}
    for col in row.get("columns", []):
        key = "".join(c for c in str(col.get("key", "")) if c.isdigit())
        if len(key) >= 4 and 1900 <= int(key[:4]) <= dt.date.today().year + 1:
            try:
                values[int(key[:4])] = float(str(col.get("value", "")).replace(",", ""))
            except ValueError:
                continue
    if not values:
        sys.exit(f"[stop] the series '{series}' has no yearly values in {table['url']}")
    return {"values": values, "uom": str(row.get("uoM", "")).strip() or table["uom"], "footnote": str(row.get("footnote", "")).strip(),
            "label": str(row.get("rowText", "")).strip()}


def maybe_series(table: dict, series: str) -> dict | None:
    """Like series_of but returns None when the row is absent."""
    if not any(str(r.get("rowText", "")).strip().lower() == series.lower() for r in table["rows"]):
        return None
    return series_of(table, series)


def unit_factor(uom: str) -> float | None:
    """Multiplier from the unit of measure of a population series to persons; None if the unit is not recognised."""
    u = uom.lower()
    if "thousand" in u or "'000" in u or "000" in u:
        return 1_000.0
    if "million" in u:
        return 1_000_000.0
    if u in ("number", "persons", "person", "no.", "no", ""):
        return 1.0
    return None


def build() -> tuple[pd.DataFrame, dict]:
    crime_t, pop_t = fetch_table(CRIME_API_URL, "singstat_M890891"), fetch_table(POP_API_URL, "singstat_M810811")
    crime, pop = series_of(crime_t, CRIME_SERIES), series_of(pop_t, POP_SERIES)
    cf, pf = unit_factor(crime["uom"]), unit_factor(pop["uom"])
    if cf != 1.0:
        sys.exit(f"[stop] the unit of measure of the '{CRIME_SERIES}' series ('{crime['uom']}') is not a plain count")
    if pf is None:
        sys.exit(f"[stop] the unit of measure of the '{POP_SERIES}' series ('{pop['uom']}') is not recognised")
    years = sorted(y for y in set(crime["values"]) & set(pop["values"]) if y >= FIRST_YEAR)
    if not years:
        sys.exit("[stop] the two series have no year in common from " + str(FIRST_YEAR))
    rows = []
    for y in years:
        cases, persons = crime["values"][y], int(round(pop["values"][y] * pf))
        if cases != int(cases) or cases < 0:
            sys.exit(f"[stop] {y}: the murder count {cases} is not a whole number >= 0")
        if not SCALE[0] <= persons <= SCALE[1]:
            sys.exit(f"[stop] {y}: the population {persons:,} (value {pop['values'][y]}, unit '{pop['uom']}') is not of Singapore's scale {SCALE[0]:,.0f}-{SCALE[1]:,.0f}")
        rows.append((y, int(cases), persons))
    male, female = maybe_series(pop_t, "Total Male Population"), maybe_series(pop_t, "Total Female Population")
    identity = {}
    for y, _, persons in rows:
        if male and female and y in male["values"] and y in female["values"]:
            identity[y] = abs(persons - round((male["values"][y] + female["values"][y]) * pf)) <= 1
        else:
            identity[y] = None
    midyear_text = " ".join([pop["footnote"], pop_t["footnote"], pop_t["title"], pop["label"]])
    midyear = bool(re.search(r"june|mid-?\s?year", midyear_text, re.I))
    meta = {"identity": None, "crime_t": crime_t, "pop_t": pop_t, "crime": crime, "pop": pop, "pf": pf, "midyear": midyear, "years": years}
    out = []
    for y, cases, persons in rows:
        ident = ("Total Population = Total Male + Total Female Population" if identity[y] is True
                 else "Total Population DIFFERS from Total Male + Total Female Population" if identity[y] is False
                 else "the male / female rows were not found, so Total = Male + Female was not checked")
        out.append({
            "country": "Singapore", "unit": "Singapore", "unit_local": "", "unit_code": "", "admin_level": "city", "unit_type": "city_state",
            "parent_unit": "", "year": y, "homicide_cases": cases, "population": persons, "homicide_rate_per_100k": cases / persons * 1e5,
            "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False,
            "population_age_years": 0.0 if midyear else float("nan"),
            "indicator_type": "police_recorded_cases", "reliability_tier": "C" if identity[y] is False else "B", "definition_flags": "",
            "validation": f"series '{crime['label']}' found in table M890891 and '{pop['label']}' in table M810811 by their exact names; "
                          f"unit of measure of the population is '{pop['uom'] or 'not stated'}' (x{pf:g} to persons) and the result is of Singapore's scale ({persons:,}); "
                          f"the two series overlap in {len(years)} years ({years[0]}-{years[-1]}); counts are whole numbers >= 0; {ident}",
            "indicator": f"SingStat table M890891 '{crime_t['title']}', series '{crime['label']}' (unit of measure '{crime['uom']}'): cases recorded",
            "population_method": f"SingStat table M810811 '{pop_t['title']}', series '{pop['label']}' (unit of measure '{pop['uom']}')"
                                 + (f"; footnote: {pop['footnote'][:160]}" if pop["footnote"] else "")
                                 + ("; the table's own text says a June / mid-year figure" if midyear else "; the table's text does not say which date in the year the figure refers to"),
            "data_notes": "the denominator is the table's 'Total Population' series; the table does not say whether non-residents are included, and if they are, "
                          "rates on the resident population would be higher"
                          + (f"; crime table last updated {crime_t['updated']}" if crime_t["updated"] else "")
                          + (f"; population table last updated {pop_t['updated']}" if pop_t["updated"] else ""),
            "source_homicide": CRIME_API_URL, "source_population": POP_API_URL, "retrieved": FETCH.retrieved_on(CRIME_API_URL, POP_API_URL)})
    meta["identity"] = identity
    return pd.DataFrame(out), meta


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["inspect", "build"])
    a = ap.parse_args()
    df, meta = build()
    print(f"[tables] crime: M890891 '{meta['crime_t']['title']}' (unit '{meta['crime']['uom']}', {meta['crime_t']['frequency'] or 'frequency not stated'}); "
          f"population: M810811 '{meta['pop_t']['title']}' (unit '{meta['pop']['uom']}')")
    print("[series] population-related rows of the population table (the script uses '" + POP_SERIES + "'):")
    for r in meta["pop_t"]["rows"]:
        if re.search(r"popul|resident", str(r.get("rowText", "")), re.I):
            print(f"   {str(r.get('rowText', '')).strip()[:70]}  [unit '{r.get('uoM', '')}']")
    idn = meta["identity"]
    print(f"[identity] Total Population = Total Male + Total Female: {sum(v is True for v in idn.values())} of {len(idn)} years agree"
          + (f", {sum(v is False for v in idn.values())} differ" if any(v is False for v in idn.values()) else "")
          + (f", {sum(v is None for v in idn.values())} not checked" if any(v is None for v in idn.values()) else ""))
    print(f"[date] mid-year evidence in the table text: {'yes' if meta['midyear'] else 'NO - population_age_years is left blank'}")
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[singapore] statistical outlier: {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "singapore")
    print(df[["unit", "year", "homicide_cases", "population", "homicide_rate_per_100k", "flag_low_count"]].round(3).to_string(index=False))
    if a.cmd == "build":
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows, years {int(df.year.min())}-{int(df.year.max())})")
    else:
        print("\n[inspect only] no CSV written")


if __name__ == "__main__":
    main()