#!/usr/bin/env python3
"""
Eurostat - police-recorded intentional homicide per 100,000 residents, by NUTS 3 region (all reporting countries).

NUMERATOR   (official): Eurostat `crim_gen_reg` "Police-recorded offences by NUTS 3 region", ICCS0101 Intentional homicide, unit NR (number of
            offences), annual, from 2008. The statistical unit is the police-recorded OFFENCE. Eurostat's definition: unlawful death purposefully
            inflicted on a person by another person, including serious assault leading to death and death as a result of a terrorist attack;
            EXCLUDING attempted homicide (a separate category, ICCS0102), manslaughter, death due to legal intervention, justifiable homicide in
            self-defence and death due to armed conflict. Countries report to Eurostat/UNODC and may diverge from the standard definition
            (flag 'd'); counting and recording rules differ between countries, so rates are not strictly comparable across countries.
DENOMINATOR (official): Eurostat `demo_r_gind3` "Population change - demographic balance and crude rates at regional level (NUTS 3)", indicator JAN
            (population on 1 January). The rate of year Y uses the mean of 1 January Y and 1 January Y+1 (mid-year proxy, population_age_years 0);
            when 1 January Y+1 is not yet published it uses 1 January Y (age 0.5) and says so.
CROSS-CHECKS  (1) per country and year the NUTS 3 values plus the extra-regio codes add up to the country row of the same dataset (equal = pass; a
            shortfall of up to 10%, or regions without a value, = incomplete coverage, tier B; an excess or a larger shortfall = tier C); (2) Eurostat's OWN published rate per 100,000 (`crim_gen_reg`, unit P_HTHAB) is
            compared with the rate computed here (within RATE_TOL passes; the two use different population dates, so they are close, not equal);
            (3) Eurostat's observation flags are carried into the rows: p provisional, u low reliability, e estimated, s Eurostat estimate, d
            definition differs make a row tier B; b break in time series is a note. Tier A needs (1) and (2) to pass, no such flag and a population
            date within 3.5 years. The text in `validation` is built from these results.
UNITS       The NUTS 3 regions Eurostat reports (counties, districts, provinces, departments ...: their size differs a lot between countries); the
            country name is `parent_unit`; the NUTS code is `unit_code`; regions under 100,000 residents are dropped. Extra-regio codes (...ZZZ) have
            no population and are reported. A region whose code exists in the crime data but not in the population data (a different NUTS version) is
            excluded and reported with its cases: Eurostat itself says its rate is unavailable for some regions of BE, DE, NL, PL, NO for that reason.
NOT DONE    No modelling: cities are not estimated from a population grid. Observed city data are a separate Eurostat source.

Folders:    this script sits in <repo>/Pipelines/Europe/ ; downloads go to <repo>/Data/Raw/Europe/Eurostat/ ; the one output is
            eurostat_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python eurostat_homicide_rate.py inspect | build
Needs:      pip install pandas numpy requests
"""
import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 12:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Eurostat")        # raw downloads -> Data/Raw/Europe/Eurostat/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="EurostatDataPipeline/1.0 (research pipeline)", retries=4)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

API = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{code}"
FIRST_YEAR = 2008          # Eurostat's crime coverage starts in 2008
RATE_TOL = 0.02            # DECISION: our rate may differ from Eurostat's published rate by this share (different population dates)
MAX_SHORTFALL = 0.10      # DECISION: regions + extra-regio up to this share BELOW the country row = incomplete regional coverage (tier B); more, or any excess, = tier C
RATE_ABS = 0.01            # ... or by this much per 100,000 (Eurostat publishes the rate rounded to two decimals, which matters for very small rates)
NUTS3 = re.compile(r"^[A-Z]{2}[A-Z0-9]{3}$")
COUNTRY = re.compile(r"^[A-Z]{2}$")
# Eurostat's observation-flag dictionary (the official list of status flags); unknown flags are shown by their code
FLAG_LABELS = {"b": "break in time series", "c": "confidential", "d": "definition differs", "e": "estimated", "p": "provisional",
               "s": "Eurostat estimate", "u": "low reliability", "r": "revised", "n": "not significant", "z": "not applicable", "f": "forecast"}
TIER_B_FLAGS = {"p", "u", "e", "s", "d", "f"}      # flags that make a row tier B (b is only a note)


# ---------------------------------------------------------------- Eurostat JSON-stat
def query(code: str, name: str, **params) -> dict:
    """One JSON-stat response (a dated copy is kept in the raw folder). Filters go into the URL as the dissemination API expects."""
    q = {"format": "JSON", "lang": "EN", "sinceTimePeriod": str(FIRST_YEAR), **params}
    url = API.format(code=code) + "?" + "&".join(f"{k}={v}" for k, v in q.items())
    try:
        raw = FETCH.get(url, name, reuse=False, suffix=".json", headers={"Accept": "application/json"})
        payload = json.loads(raw.decode("utf-8"))
    except F.RobotsDisallowed:
        raise
    except Exception as e:
        sys.exit(f"[stop] Eurostat request failed for {code} {params}: {e}")
    if "error" in payload and "value" not in payload:
        sys.exit(f"[stop] Eurostat answered with an error for {code} {params}: {str(payload['error'])[:300]}")
    payload["_url"] = url
    return payload


def parse_jsonstat(js: dict) -> pd.DataFrame:
    """JSON-stat 2.0 -> long table with the dimension codes, the geo label, the value and Eurostat's status flag."""
    ids, sizes, dims = js.get("id"), js.get("size"), js.get("dimension")
    if not ids or not sizes or not dims:
        sys.exit("[stop] the Eurostat response lacks the JSON-stat structure ('id', 'size', 'dimension')")
    codes, labels = [], {}
    for d in ids:
        cat = dims[d]["category"]
        idx = cat.get("index")
        c = sorted(idx, key=idx.get) if isinstance(idx, dict) else list(idx) if isinstance(idx, list) else list((cat.get("label") or {}).keys())
        codes.append(c)
        labels[d] = cat.get("label", {})
    if [len(c) for c in codes] != list(sizes):
        sys.exit(f"[stop] the JSON-stat sizes {sizes} do not match the category counts {[len(c) for c in codes]}")
    val, sta = js.get("value", {}), js.get("status", {})
    get = (lambda o, i: o.get(str(i)) if isinstance(o, dict) else (o[i] if isinstance(o, list) and i < len(o) else None))
    n = int(np.prod(sizes))
    keys = [i for i in range(n) if get(val, i) is not None or get(sta, i) is not None]
    rows = []
    for i in keys:
        pos = np.unravel_index(i, sizes)
        r = {d: codes[k][pos[k]] for k, d in enumerate(ids)}
        r["value"] = get(val, i)
        r["flag"] = get(sta, i) or ""
        rows.append(r)
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] the Eurostat response holds no observations")
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    place = next((d for d in ids if d in ("geo", "cities")), None)
    if place is None:
        sys.exit(f"[stop] the Eurostat response has no place dimension (dimensions: {ids})")
    if place != "geo":
        df["geo"] = df[place]
    df["geo_label"] = df["geo"].map(labels[place])
    df["year"] = pd.to_numeric(df["time"], errors="coerce").astype("Int64")
    df.attrs["url"] = js.get("_url", "")
    return df


def flags_text(flags) -> str:
    fs = sorted({c for f in flags for c in str(f) if c.strip() and c.isalpha()})
    return ", ".join(f"{c} ({FLAG_LABELS.get(c, 'see Eurostat')})" for c in fs)


# ---------------------------------------------------------------- build
def recon_text(rc, country: str) -> str:
    """The reconciliation sentence for ONE status (built only for the status that applies: a country row can be 0)."""
    st, regions, nat = rc
    if st == "equal":
        return f"the NUTS 3 regions of {country} add up to the country row ({int(regions):,})"
    if st == "missing":
        return (f"{country} has NUTS 3 regions without a value this year, so the regions ({int(regions):,}) cannot be reconciled to the country row "
                f"({int(nat):,})")
    if st == "short":
        return (f"the NUTS 3 regions of {country} ({int(regions):,}) fall short of the country row ({int(nat):,}) by {(nat - regions) / nat:.1%}: "
                f"incomplete regional coverage")
    if st == "differs":
        return (f"the NUTS 3 regions of {country} ({int(regions):,}) DIFFER from the country row ({int(nat):,}) by more than {MAX_SHORTFALL:.0%} or exceed it")
    return f"no country row to reconcile {country} against"


# ---------------------------------------------------------------- build
def cmd_build(inspect_only: bool):
    crime = parse_jsonstat(query("crim_gen_reg", "eurostat_crim_gen_reg_NR_nuts3", unit="NR", iccs="ICCS0101", geoLevel="nuts3"))
    ctry = parse_jsonstat(query("crim_gen_reg", "eurostat_crim_gen_reg_NR_country", unit="NR", iccs="ICCS0101", geoLevel="country"))
    rate = parse_jsonstat(query("crim_gen_reg", "eurostat_crim_gen_reg_P_HTHAB_nuts3", unit="P_HTHAB", iccs="ICCS0101", geoLevel="nuts3"))
    pop = parse_jsonstat(query("demo_r_gind3", "eurostat_demo_r_gind3_JAN_nuts3", indic_de="JAN", geoLevel="nuts3"))
    url_crime, url_pop = crime.attrs["url"], pop.attrs["url"]

    crime = crime[crime["geo"].str.match(NUTS3)].copy()
    rate = rate[rate["geo"].str.match(NUTS3)]
    pop = pop[pop["geo"].str.match(NUTS3)]
    ctry = ctry[ctry["geo"].str.match(COUNTRY)]
    cname = ctry.drop_duplicates("geo").set_index("geo")["geo_label"].to_dict()
    print(f"[crime] {crime['geo'].nunique()} NUTS 3 codes, {len(cname)} country rows, years {int(crime['year'].min())}-{int(crime['year'].max())}; "
          f"{int(crime['value'].isna().sum())} observations without a value")
    extra = sorted(c for c in crime["geo"].unique() if "ZZ" in c)

    # national reconciliation per country and year: the regions PLUS the extra-regio codes (cases not attributed to a region) = the country row
    recon = {}
    cs = ctry.set_index(["geo", "year"])["value"]
    for (c, y), g in crime.groupby([crime["geo"].str[:2], "year"]):
        if (c, y) not in cs.index or pd.isna(cs[(c, y)]):
            recon[(c, int(y))] = ("none", 0, 0)
            continue
        miss = int(g["value"].isna().sum())
        tot = float(g["value"].sum())
        nat_v = float(cs[(c, y)])
        recon[(c, int(y))] = ("equal" if tot == nat_v and not miss else "missing" if miss
                              else "short" if (tot < nat_v and (nat_v - tot) / nat_v <= MAX_SHORTFALL) else "differs", tot, nat_v)

    st = pd.Series([v[0] for v in recon.values()]).value_counts().to_dict()
    gaps = sorted(((abs(v[1] - v[2]), c, y, v[1], v[2]) for (c, y), v in recon.items() if v[0] == "differs"), reverse=True)
    print(f"[reconciliation] {len(recon)} country-years: {st} (regions + extra-regio codes against the country row)")
    by_c = {}
    for (c, y), v in recon.items():
        by_c.setdefault(cname.get(c, c), []).append((y, v))
    bad_c = {k: v for k, v in by_c.items() if any(t[0] != "equal" for _, t in v)}
    if bad_c:
        print("[reconciliation by country] years that do not reconcile (status, regions + extra-regio against the country row):")
        for k, v in sorted(bad_c.items()):
            ys = [(y, t) for y, t in sorted(v) if t[0] != "equal"]
            print(f"   {k}: {len(ys)} of {len(v)} years; " + "; ".join(f"{y} {t[0]} {t[1]:.0f} vs {t[2]:.0f}" for y, t in ys[:5]) + (" ..." if len(ys) > 5 else ""))
    for d, c, y, a, b in gaps[:8]:
        print(f"   {cname.get(c, c)} {y}: regions + extra-regio {a:.0f} against the country row {b:.0f} (difference {a - b:+.0f})")
    if extra:
        xs = crime[crime["geo"].isin(extra)].groupby("geo")["value"].sum()
        print(f"[extra-regio] {len(extra)} codes (cases not attributed to a region, no population): {int(xs.sum())} cases in all years, counted in the "
              f"reconciliation and left out of the rates")
    crime = crime[~crime["geo"].isin(extra)]
    pv = pop.set_index(["geo", "year"])["value"]
    rv = rate.set_index(["geo", "year"])["value"]
    rows, nopop, small = [], {}, []
    for r in crime[crime["value"].notna()].itertuples():
        g, y = r.geo, int(r.year)
        a, b = pv.get((g, y)), pv.get((g, y + 1))
        if a is None or pd.isna(a):
            nopop.setdefault(g[:2], []).append((g, y, float(r.value)))
            continue
        if b is not None and not pd.isna(b):
            popn, age, how = (float(a) + float(b)) / 2, 0.0, "mean of the population on 1 January Y and 1 January Y+1"
        else:
            popn, age, how = float(a), 0.5, "population on 1 January Y (1 January Y+1 is not yet published)"
        pop_i = int(round(popn))
        if pop_i < MIN_POP:
            small.append(g)
            continue
        c = g[:2]
        if c not in cname:
            nopop.setdefault(c, []).append((g, y, float(r.value)))
            continue
        cases = int(round(r.value))
        mine = cases / pop_i * 1e5
        pub = rv.get((g, y))
        rate_ok = None if pub is None or pd.isna(pub) else bool(abs(mine - pub) <= max(RATE_TOL * pub, RATE_ABS))
        rc = recon.get((c, y), ("none", 0, 0))
        fl = str(r.flag)
        bad = sorted(set(fl) & TIER_B_FLAGS)
        tier = "C" if rc[0] == "differs" else "B" if rc[0] == "short" else ("A" if (rc[0] == "equal" and rate_ok is True and not bad and age <= F.MAX_DENOMINATOR_AGE) else "B")
        checks = [recon_text(rc, cname[c]),
                  (f"Eurostat's own published rate is {pub:.2f} per 100,000 against {mine:.2f} computed here ({'within' if rate_ok else 'OUTSIDE'} the tolerance of {RATE_TOL:.0%} or {RATE_ABS} per 100,000)"
                   if rate_ok is not None else "Eurostat publishes no rate for this region-year (its population is not available on the same NUTS version)"),
                  f"observation flag: {flags_text([fl])}" if fl.strip() else "no observation flag"]
        rows.append({
            "country": cname[c], "unit": r.geo_label, "unit_local": "", "unit_code": g, "admin_level": "admin2", "unit_type": "nuts3_region",
            "parent_unit": cname[c], "year": y, "homicide_cases": cases, "population": pop_i, "homicide_rate_per_100k": mine,
            "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": age,
            "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "",
            "validation": "; ".join(checks),
            "indicator": "Eurostat crim_gen_reg: police-recorded offences, ICCS0101 intentional homicide (unlawful death purposefully inflicted on a person by "
                         "another person; includes serious assault leading to death and death from a terrorist attack; excludes attempts, manslaughter, legal intervention, "
                         "justifiable self-defence and armed conflict); unit: offences",
            "population_method": f"Eurostat demo_r_gind3 (population on 1 January): {how}",
            "data_notes": "countries may diverge from the standard definition and recording rules differ between them (Eurostat's metadata), so rates are not "
                          "strictly comparable across countries" + (f"; observation flag(s): {flags_text([fl])}" if fl.strip() else ""),
            "source_homicide": url_crime, "source_population": url_pop, "retrieved": FETCH.retrieved_on(url_crime, url_pop),
            "eurostat_rate_per_100k": float(pub) if pub is not None and not pd.isna(pub) else np.nan, "nuts3_in_country_total": rc[0]})
    if nopop:
        print("\n[no population] NUTS 3 codes with cases but no usable population (usually a different NUTS version in the two datasets); excluded:")
        for c, lst in sorted(nopop.items()):
            print(f"   {cname.get(c, c)}: {len({g for g, _, _ in lst})} regions, {int(sum(v for _, _, v in lst))} cases, e.g. {sorted({g for g, _, _ in lst})[:6]}")
    if small:
        print(f"[filter] {len(set(small))} NUTS 3 regions are under {MIN_POP:,} residents in some years and have no row for those years (e.g. {sorted(set(small))[:8]})")
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no row could be built")
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].head(10).iterrows():
        print(f"[eurostat] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "eurostat")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    ok = df.dropna(subset=["eurostat_rate_per_100k"]).copy()
    ok["d"] = (ok["homicide_rate_per_100k"] - ok["eurostat_rate_per_100k"]).abs()
    ok["inside"] = ok["d"] <= np.maximum(RATE_TOL * ok["eurostat_rate_per_100k"], RATE_ABS)
    print(f"[xcheck] computed vs Eurostat's published rate: {len(ok):,} region-years, median |diff| {ok['d'].median():.3f} per 100,000, inside the tolerance: {ok['inside'].mean():.1%}")
    if (~ok["inside"]).any():
        print(ok[~ok["inside"]].sort_values("d", ascending=False).head(8)[["country", "unit", "year", "homicide_rate_per_100k", "eurostat_rate_per_100k"]].round(3).to_string(index=False))
    ct = pd.crosstab(df["country"], df["reliability_tier"]).reindex(columns=["A", "B", "C"], fill_value=0)
    print("\n[tiers by country] countries with tier C rows (C = a check failed; A/B/C row counts):")
    print(ct[ct["C"] > 0].sort_values("C", ascending=False).head(14).to_string())
    cs_by_name = {(cname[c], int(y)): float(v) for (c, y), v in cs.items() if c in cname and not pd.isna(v)}
    rep = df.groupby(["country", "year"])["homicide_cases"].sum()
    last = int(df.year.max())
    share = pd.Series({k: v / cs_by_name[k] for k, v in rep.items() if k in cs_by_name and cs_by_name[k] > 0})
    low = share[[k for k in share.index if k[1] == last]].sort_values().head(10)
    print(f"\n[coverage {last}] share of each country's national total that the output rows represent (lowest ten; the rest is regions without population, "
          f"regions under {MIN_POP:,} residents and extra-regio cases):")
    for (c, y), v in low.items():
        print(f"   {c}: {v:.0%}")
    print(f"\nCountries and rows (latest year {last}):")
    print(df[df.year == last].groupby("country").agg(regions=("unit", "size"), cases=("homicide_cases", "sum"), pop=("population", "sum"))
          .assign(rate=lambda x: (x.cases / x["pop"] * 1e5).round(2)).sort_values("rate", ascending=False).head(15).to_string())
    if inspect_only:
        print("\n[inspect only] no CSV written")
    else:
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df):,} rows, {df['unit_code'].nunique()} NUTS 3 regions, {df['country'].nunique()} countries, years {int(df.year.min())}-{last})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    a = ap.parse_args()
    cmd_build(a.cmd == "inspect")