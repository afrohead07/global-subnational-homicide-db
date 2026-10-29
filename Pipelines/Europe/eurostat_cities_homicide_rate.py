#!/usr/bin/env python3
"""
Eurostat - police-recorded intentional homicide per 100,000 residents in the LARGEST CITIES of the reporting countries (observed, not modelled).

NUMERATOR   (official): Eurostat `crim_hom_ocit` "Intentional homicide offences in largest cities", annual from 2008. Each jurisdiction reports its
            largest cities, in general as the CITY PROPER (within the official city boundary) or the GREATER CITY; the label says which. The unit is
            the police-recorded offence. Definition as for the regions (see eurostat_homicide_rate.py): unlawful death purposefully inflicted on a
            person by another person, including serious assault leading to death and death from a terrorist attack; excluding attempts, manslaughter,
            legal intervention, justifiable self-defence and armed conflict.
DENOMINATOR (official): Eurostat Urban Audit `urb_cpop1` "Population on 1 January by age groups and sex - cities and greater cities", indicator
            DE1001V (total population on 1 January = the usual resident population). The rate of year Y uses the mean of 1 January Y and
            1 January Y+1 (population_age_years 0), or 1 January Y alone (age 0.5) when Y+1 is not yet published.
CROSS-CHECKS  (1) Eurostat's OWN published rate per 100,000 (`crim_hom_ocit`, unit P_HTHAB) is compared with the rate computed here; (2) a city's
            cases can not exceed its country's national total (`crim_gen_reg` country row); (3) Eurostat's observation flags: p provisional,
            u low reliability, e estimated, s Eurostat estimate, d definition differs, f forecast make a row tier B; b (break) is a note.
            Tier A needs (1) and (2) to pass, no such flag and a population date within 3.5 years; a city above its national total is tier C.
STRUCTURE   The dimensions of both datasets are read from the responses; the run stops with the list of dimensions if something is not as expected
            (no guessing). Cities with no population in the Urban Audit table, or under 100,000 residents, have no row and are reported.
NOT DONE    No modelling and no GHSL: only the cities Eurostat itself reports (a few per country).

Folders:    this script sits in <repo>/Pipelines/Europe/ next to eurostat_homicide_rate.py (whose download and JSON-stat helpers it uses); downloads go to
            <repo>/Data/Raw/Europe/Eurostat/ ; the one output is eurostat_cities_homicide_rate.csv next to the script.
Commands:   python eurostat_cities_homicide_rate.py inspect | build
Needs:      pip install pandas numpy requests
"""
import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
try:
    import homicide_format as F
    import eurostat_homicide_rate as EU       # query(), parse_jsonstat(), flags_text() and the flag rules of the region script
except ImportError as e:
    sys.exit(f"[stop] {e}: homicide_format.py (Pipelines/) and eurostat_homicide_rate.py (this folder) must be next to the scripts that use them")
if getattr(F, "REVISION", 0) < 12:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Eurostat Cities")
OUT = P.out
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP
POP_INDICATOR = "DE1001V"          # Urban Audit: population on 1 January, total


def tidy(df: pd.DataFrame, what: str):
    extra = [c for c in df.columns if c not in ("value", "flag", "geo_label", "year", "time", "geo") and df[c].nunique() > 0]
    dims = {c: sorted(df[c].dropna().unique())[:12] for c in extra if c not in ("cities",)}
    print(f"[{what}] columns: {list(df.columns)}; other dimensions: {dims}")
    return extra


def cmd(inspect_only: bool):
    crime = EU.parse_jsonstat(EU.query("crim_hom_ocit", "eurostat_crim_hom_ocit"))
    url_crime = crime.attrs.get("url", "")
    tidy(crime, "crim_hom_ocit")
    if "unit" not in crime.columns:
        sys.exit(f"[stop] crim_hom_ocit has no 'unit' dimension (columns {list(crime.columns)}); cannot tell counts from rates")
    if "iccs" in crime.columns:
        crime = crime[crime["iccs"] == "ICCS0101"]
    units = sorted(crime["unit"].unique())
    if "NR" not in units:
        sys.exit(f"[stop] crim_hom_ocit has no unit NR (number of offences); units: {units}")
    nr, rate = crime[crime["unit"] == "NR"], crime[crime["unit"] == "P_HTHAB"]
    cities = nr.drop_duplicates("geo")[["geo", "geo_label"]].sort_values("geo")
    print(f"[cities] {len(cities)} places in crim_hom_ocit ({', '.join(units)}); years {int(nr['year'].min())}-{int(nr['year'].max())}; "
          f"{int(nr['value'].isna().sum())} observations without a value")
    print(cities.to_string(index=False))
    pop = EU.parse_jsonstat(EU.query("urb_cpop1", "eurostat_urb_cpop1_DE1001V", indic_ur=POP_INDICATOR))
    url_pop = pop.attrs.get("url", "")
    ctry = EU.parse_jsonstat(EU.query("crim_gen_reg", "eurostat_crim_gen_reg_NR_country", unit="NR", iccs="ICCS0101", geoLevel="country"))
    cname = pop[pop["geo"].str.match(EU.COUNTRY)].drop_duplicates("geo").set_index("geo")["geo_label"].to_dict()
    cs = ctry.set_index(["geo", "year"])["value"]
    pv = pop.set_index(["geo", "year"])["value"]
    rv = rate.set_index(["geo", "year"])["value"]
    rows, nopop, small, over = [], [], set(), []
    for r in nr[nr["value"].notna()].itertuples():
        g, y = r.geo, int(r.year)
        a, b = pv.get((g, y)), pv.get((g, y + 1))
        c = g[:2]
        if a is None or pd.isna(a) or c not in cname:
            nopop.append((g, r.geo_label, y))
            continue
        if b is not None and not pd.isna(b):
            popn, age, how = (float(a) + float(b)) / 2, 0.0, "mean of the population on 1 January Y and 1 January Y+1"
        else:
            popn, age, how = float(a), 0.5, "population on 1 January Y (1 January Y+1 is not yet published)"
        pop_i = int(round(popn))
        if pop_i < MIN_POP:
            small.add(r.geo_label)
            continue
        cases = int(round(r.value))
        mine = cases / pop_i * 1e5
        pub = rv.get((g, y))
        rate_ok = None if pub is None or pd.isna(pub) else bool(abs(mine - pub) <= max(EU.RATE_TOL * pub, EU.RATE_ABS))
        nat = cs.get((c, y))
        cap_ok = None if nat is None or pd.isna(nat) else bool(cases <= nat)
        fl = str(r.flag)
        bad = sorted(set(fl) & EU.TIER_B_FLAGS)
        tier = "C" if cap_ok is False else ("A" if (cap_ok is True and rate_ok is True and not bad and age <= F.MAX_DENOMINATOR_AGE) else "B")
        if cap_ok is False:
            over.append((r.geo_label, y, cases, nat))
        greater = "greater" in str(r.geo_label).lower()
        checks = [f"cases ({cases}) do not exceed the national total of {cname[c]} ({int(nat)})" if cap_ok is True else
                  f"cases ({cases}) EXCEED the national total of {cname[c]} ({int(nat)})" if cap_ok is False else "no national total to compare with",
                  (f"Eurostat's own published rate is {pub:.2f} per 100,000 against {mine:.2f} computed here ({'within' if rate_ok else 'OUTSIDE'} the tolerance)"
                   + ("" if rate_ok or pub == 0 else f"; the published rate implies a population of about {cases / pub * 1e5:,.0f} against {pop_i:,} used here "
                      f"(the two may refer to different aggregates, city proper and greater city)")
                   if rate_ok is not None else "Eurostat publishes no rate for this city-year"),
                  f"observation flag: {EU.flags_text([fl])}" if fl.strip() else "no observation flag"]
        rows.append({
            "country": cname[c], "unit": r.geo_label, "unit_local": "", "unit_code": g, "admin_level": "city", "unit_type": "greater_city" if greater else "city",
            "parent_unit": cname[c], "year": y, "homicide_cases": cases, "population": pop_i, "homicide_rate_per_100k": mine,
            "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": age,
            "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "", "validation": "; ".join(checks),
            "indicator": "Eurostat crim_hom_ocit: police-recorded intentional homicide offences in the largest cities (city proper or greater city, as the label says); unit: offences",
            "population_method": f"Eurostat Urban Audit urb_cpop1, {POP_INDICATOR} (population on 1 January): {how}",
            "data_notes": "countries may diverge from the standard definition and report either the city proper or the greater city; rates are not strictly comparable"
                          + (f"; observation flag(s): {EU.flags_text([fl])}" if fl.strip() else ""),
            "source_homicide": url_crime, "source_population": url_pop, "retrieved": EU.FETCH.retrieved_on(url_crime, url_pop),
            "eurostat_rate_per_100k": float(pub) if pub is not None and not pd.isna(pub) else np.nan})
    if nopop:
        lost = pd.DataFrame(nopop, columns=["geo", "label", "year"]).groupby(["geo", "label"])["year"].agg(["min", "max", "size"])
        print(f"\n[no population] {len(lost)} places have cases but no population in urb_cpop1 (or no country name) for some years; no row for those years:")
        print(lost.head(15).to_string())
    if small:
        print(f"[filter] under {MIN_POP:,} residents, no row: {sorted(small)}")
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no city row could be built (see the messages above)")
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "eurostat_cities")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    ok = df.dropna(subset=["eurostat_rate_per_100k"]).copy()
    ok["d"] = (ok["homicide_rate_per_100k"] - ok["eurostat_rate_per_100k"]).abs()
    ok["inside"] = ok["d"] <= np.maximum(EU.RATE_TOL * ok["eurostat_rate_per_100k"], EU.RATE_ABS)
    print(f"[xcheck] computed vs Eurostat's published rate: {len(ok)} city-years, median |diff| {ok['d'].median():.3f}, inside the tolerance: {ok['inside'].mean():.1%}")
    if (~ok["inside"]).any():
        print(ok[~ok["inside"]].sort_values("d", ascending=False).head(10)[["country", "unit", "year", "homicide_rate_per_100k", "eurostat_rate_per_100k"]].round(3).to_string(index=False))
    if over:
        print(f"[above the national total] {over[:6]}")
    last = int(df.year.max())
    print(f"\nLatest year {last}:")
    print(df[df.year == last].sort_values("homicide_rate_per_100k", ascending=False)[["country", "unit", "unit_type", "homicide_cases", "population", "homicide_rate_per_100k", "reliability_tier"]]
          .round(2).to_string(index=False))
    if inspect_only:
        print("\n[inspect only] no CSV written")
    else:
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df['unit_code'].nunique()} cities, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    cmd(ap.parse_args().cmd == "inspect")