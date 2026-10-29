#!/usr/bin/env python3
"""
Igarape Institute Homicide Monitor - homicides per 100,000 residents, by city and by state, for the AMERICAS.

WHAT THIS IS  A SECONDARY COMPILATION, not an official source: the Igarape Institute (Brazil) collects the figures of national and local authorities
            and publishes them as an ArcGIS feature service (https://geo.igarape.org.br). Every row carries the compiler's own citation of the
            official source (fields source_1 / source_2); these are copied into `data_notes` and the extras `igarape_source_1` / `igarape_source_2`.
            The project author compared the series with the official sources by hand (under 1% variance); that comparison is NOT repeated by this
            script. Rows are therefore never tier A: the intended path is that official country pipelines (health registries, police statistics)
            validate and later replace this layer country by country.
SCOPE       The 32 countries and territories of the Americas that occur in the layer (SCOPE below, a visible setting). The layer's other regions are not
            used: Europe and Asia have official pipelines in this project, and Oceania and Africa are built from their own official sources.
LEVELS      CITIES (layer HM_Dados_Cidades, admin_level city) and STATES (layer HM_Dados_Estados, admin_level admin1). Never add rows across levels.
NUMERATOR   `homicide` (a count) of the row; DENOMINATOR `population` of the same row. The rate of this file is cases / population x 100,000,
            computed here; the compiler's `rate` (rounded to its own precision, checked row by row) is only a check.
EXCLUDED    * rows whose source_1 is an international aggregator or a non-official compilation (UNODC, Eurostat, MINUSTAH, AOAV): in this layer such
              rows are NATIONAL figures placed on a capital, not subnational data;
            * rows without a count, without a population, or with a population under 100,000 (counted);
            * rows whose source text is neither a police/security body nor a health/forensic body (listed; extend the word tables).
TIER C      the compiler's rate differs from cases / population by more than 10% (a factor of 10 or 100 is called out as a unit slip); no cited source;
            a city or state with more cases than its country's national total (national layer, rows tipo = 'Pais'); a source that is a non-official
            third-party compilation or an estimate (WEAK_WORDS). Within 1-10% of the compiler's rate: tier B with a note. Everything else: tier B.
INDICATOR   police_recorded_cases or health_registry_deaths, from the text of `source_1` with the word tables HEALTH_WORDS / POLICE_WORDS.
CHECKS      the rows fetched equal the server's own count (a failed or partial download never becomes a file); object ids unique; the same unit and
            year may not appear twice with different counts; a city is identified by the compiler's `id_city` (names repeat inside a country).

Folders:    this script sits in <repo>/Pipelines/Americas/ ; the pages of the service are kept dated in <repo>/Data/Raw/Americas/Igarape/ ; the one
            output is igarape_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python igarape_homicide_rate.py inspect | build            Option: --reuse (use the saved pages of an earlier run instead of downloading)
Needs:      pip install pandas requests
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlencode

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 12:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Igarape")         # raw pages -> Data/Raw/Americas/Igarape/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=4)
REGION = "the Americas"
# SCOPE: the countries and territories of the Americas, spelled as the layer spells them (from the `inspect` listing of country_name)
SCOPE = ["Anguilla (British overseas territories)", "Argentina", "Barbados", "Belize", "Bolivia (Plurinational State of)", "Brazil", "Canada", "Chile",
         "Colombia", "Costa Rica", "Dominican Republic", "Ecuador", "El Salvador", "Grenada", "Guatemala", "Guyana", "Haiti", "Honduras", "Jamaica",
         "Mexico", "Nicaragua", "Panama", "Paraguay", "Peru", "Puerto Rico", "Saint Kitts and Nevis", "Saint Lucia", "The Bahamas",
         "Trinidad and Tobago", "United States of America", "Uruguay", "Venezuela (Bolivarian Republic of)"]
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

SERVICE = "https://geo.igarape.org.br/server/rest/services/Hosted/{layer}/FeatureServer/0"
LAYERS = {"cities": "HM_Dados_Cidades", "states": "HM_Dados_Estados", "national": "HM_Dados"}      # weapons / sex / age layers are not rates by unit
PAGE = 1000
RATE_TOL_REL = 0.01      # DECISION: the compiler's rate agrees with cases / population within 1%, or half a unit of its own last digit (rounding)
RATE_BAND = 0.10         # DECISION: a difference up to 10% (usually another population vintage) keeps tier B with a note; beyond it tier C
REUSE = {"on": False}
# Word tables for source_1 (word-boundary, case-insensitive). Typed knowledge about institution types: check them against the printed list.
HEALTH_WORDS = [r"salud", r"sa[uú]de", r"health", r"\bsim\b", r"datasus", r"minsa", r"defunc", r"mortal", r"[oó]bito", r"vital", r"\bdane\b", r"sinadef",
                r"medicina legal", r"forens"]
POLICE_WORDS = [r"polic", r"pol[ií]cia", r"segur", r"securit", r"fiscal", r"delit", r"crim", r"interior", r"justic", r"public safety", r"carabinero",
                r"\bfbi\b", r"\bucr\b", r"sheriff", r"\bsspc?\b", r"sesnsp", r"observatorio", r"investigaci", r"investigation", r"statistics canada", r"dinased", r"\bcicpc\b", r"delict", r"incidencia", r"recorded (crime|statistics)"]
AGGREGATOR_WORDS = [r"unodc", r"eurostat", r"minustah", r"\baoav\b"]          # international aggregators / non-official: national figures on a capital
WEAK_WORDS = [r"observatorio venezolano", r"council on criminal justice", r"\bccj\b", r"brennan", r"rochester", r"estimate"]   # third-party compilations: tier C


# ---------------------------------------------------------------- fetching a layer
def api(layer: str, name: str, soft: bool = False, **params) -> dict:
    url = SERVICE.format(layer=LAYERS[layer]) + "/query?" + urlencode(params)
    try:
        payload = json.loads(FETCH.get(url, name, reuse=REUSE["on"], suffix=".json").decode("utf-8"))
    except F.RobotsDisallowed:
        raise
    except Exception as e:
        sys.exit(f"[stop] the Igarape service did not answer for layer {layer} ({name}): {e}. Nothing is written (an incomplete download is never saved as complete).")
    if "error" in payload and not soft:
        sys.exit(f"[stop] the service returned an error for layer {layer}: {payload['error']}")
    payload["_url"] = url
    return payload


def fetch_layer(layer: str, where: str = "1=1", tag: str = "") -> pd.DataFrame:
    """The whole layer (or the rows matching `where`), paged. Stops unless the rows fetched equal the server's own count and the object ids are unique."""
    n = api(layer, f"igarape_{layer}{tag}_count", where=where, returnCountOnly="true", f="json").get("count")
    if not isinstance(n, int) or n <= 0:
        sys.exit(f"[stop] layer {layer}{tag}: the server's row count is {n!r}")
    rows, offset, ordered = [], 0, True
    while offset < n:
        base = dict(where=where, outFields="*", resultOffset=offset, resultRecordCount=PAGE, f="json", returnGeometry="false")
        nm = f"igarape_{layer}{tag}_p{offset:07d}"
        js = api(layer, nm, soft=True, orderByFields="OBJECTID", **base) if ordered else api(layer, nm, **base)
        if ordered and "error" in js:                       # the field is not called OBJECTID: page without an order (overlaps are caught below)
            ordered = False
            js = api(layer, nm, **base)
        feats = js.get("features", [])
        if not feats:
            sys.exit(f"[stop] layer {layer}{tag}: the server returned no rows at offset {offset} of {n}")
        rows += [f["attributes"] for f in feats]
        offset += len(feats)
        if offset % 5000 < PAGE or offset >= n:
            print(f"   [{layer}{tag}] {min(offset, n):,} of {n:,} rows", flush=True)
    df = pd.DataFrame(rows)
    if len(df) != n:
        sys.exit(f"[stop] layer {layer}{tag}: fetched {len(df):,} rows but the server counts {n:,}")
    oid = next((c for c in df.columns if c.lower() == "objectid"), None)
    if oid is not None and df[oid].duplicated().any():
        sys.exit(f"[stop] layer {layer}{tag}: object ids are not unique ({int(df[oid].duplicated().sum())} repeated): paging returned overlapping rows")
    df.attrs["url"] = SERVICE.format(layer=LAYERS[layer])
    df.attrs["retrieved"] = FETCH.retrieved_on(df.attrs["url"] + "/query")
    return df


def has(words, text: str) -> bool:
    return any(re.search(w, str(text).lower()) for w in words)


def classify(text: str) -> str:
    """police_recorded_cases | health_registry_deaths | EXCLUDED_AGGREGATOR | AMBIGUOUS | UNKNOWN (from the text of source_1)."""
    if has(AGGREGATOR_WORDS, text):
        return "EXCLUDED_AGGREGATOR"
    h, p = has(HEALTH_WORDS, text), has(POLICE_WORDS, text)
    return "AMBIGUOUS" if h and p else "health_registry_deaths" if h else "police_recorded_cases" if p else "UNKNOWN"


def clean_name(name, country: str) -> str:
    """'Tirana (Albania)' -> 'Tirana' when the parenthesis is the country (the layer appends it)."""
    n = re.sub(r"\s+", " ", str(name)).strip()
    m = re.fullmatch(r"(.*\S)\s*\(([^()]*)\)", n)
    if m and (m.group(2).lower() in country.lower() or country.lower() in m.group(2).lower()):
        return m.group(1).strip()
    return n


# ---------------------------------------------------------------- build
def prepare(df: pd.DataFrame, level: str) -> pd.DataFrame:
    unit_col, id_col = ("city_name", "id_city") if level == "cities" else ("state_name", "id_state")
    need = ["country_name", unit_col, id_col, "year", "homicide", "population", "source_1"]
    if set(need) - set(df.columns):
        sys.exit(f"[stop] layer {level} lacks the fields {sorted(set(need) - set(df.columns))}; found {list(df.columns)}")
    for c in ("year", "homicide", "population", "rate"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    for c in ("country_name", "city_name", "state_name", "source_1", "source_2", id_col):
        df[c] = df[c].where(df[c].notna(), "").astype(str).str.strip().str.replace(r"\s+", " ", regex=True) if c in df.columns else ""
    df["level"], df["unit_raw"], df["unit_id"] = level, df[unit_col], df[id_col]
    return df


def cmd_build(inspect_only: bool):
    layers = {lv: prepare(fetch_layer(lv), lv) for lv in ("cities", "states")}
    nat = fetch_layer("national", where="tipo='Pais'", tag="_pais")
    for c in ("year", "homicide_number"):
        nat[c] = pd.to_numeric(nat[c], errors="coerce")
    national = {(r.country_name, int(r.year)): float(r.homicide_number) for r in nat.itertuples() if r.homicide_number == r.homicide_number}
    print(f"[national] {len(national):,} country-years with a national homicide count (rows tipo = 'Pais')")
    frames = []
    for lv, df in layers.items():
        data = df[df["homicide"].notna() | df["population"].notna() | (df["source_1"] != "")]
        out_scope = data[~data["country_name"].isin(SCOPE)]
        print(f"\n[{lv}] {len(df):,} rows in the layer, {len(data):,} with data; outside {REGION} (not built): {len(out_scope):,} rows in "
              f"{out_scope['country_name'].nunique()} countries")
        frames.append(df[df["country_name"].isin(SCOPE)])
        if inspect_only and len(out_scope):
            names = out_scope.groupby("country_name").size().sort_values(ascending=False)
            print(f"   countries with data outside {REGION} ({len(names)}): " + ", ".join(f"{k} ({v})" for k, v in names.head(70).items()) + (" ..." if len(names) > 70 else ""))
    df = pd.concat(frames, ignore_index=True)
    df = df[df["year"].notna()].copy()
    df["year"] = df["year"].astype(int)
    url_c, got = layers["cities"].attrs["url"], layers["cities"].attrs["retrieved"]
    url_s = layers["states"].attrs["url"]
    drop = {"no count": df["homicide"].isna(), "negative or fractional count": df["homicide"].notna() & ((df["homicide"] < 0) | (df["homicide"] % 1 != 0)),
            "no population": df["population"].isna(), f"population under {MIN_POP:,}": df["population"].notna() & (df["population"] < MIN_POP)}
    has_data = df["homicide"].notna() | df["population"].notna() | (df["source_1"] != "")
    print(f"\n[rows] in {REGION}: {len(df):,} grid rows, {int(has_data.sum()):,} with any data")
    gone = pd.Series(False, index=df.index)
    for why, m in drop.items():
        k = int((m & has_data).sum())
        print(f"[exclude] {k:,} rows with data: {why}")
        gone |= m
    df = df[~gone].copy()
    df["indicator_type"] = df["source_1"].map(classify)
    agg = df[df["indicator_type"] == "EXCLUDED_AGGREGATOR"]
    if len(agg):
        print(f"[exclude] {len(agg):,} rows whose source is an international aggregator or non-official compilation (national figures on a capital):")
        print(agg.groupby(["country_name", "source_1"]).size().reset_index(name="rows").to_string(index=False, max_colwidth=60))
    unk = df[df["indicator_type"].isin(["UNKNOWN", "AMBIGUOUS"])]
    if len(unk):
        print(f"[exclude] {len(unk):,} rows whose source text is empty or not classified as police statistics or health/forensic deaths (add a word to HEALTH_WORDS / POLICE_WORDS):")
        print(unk.groupby(["country_name", "source_1", "indicator_type"]).size().reset_index(name="rows").to_string(index=False, max_colwidth=60))
    df = df[~df["indicator_type"].isin(["EXCLUDED_AGGREGATOR", "UNKNOWN", "AMBIGUOUS"])].copy()
    dup = df.duplicated(["level", "country_name", "unit_id", "year"], keep=False)
    if dup.any():
        d = df[dup].groupby(["level", "country_name", "unit_id", "year"])["homicide"].nunique()
        if (d > 1).any():
            sys.exit("[stop] the same unit and year appears with different counts: " + str(d[d > 1].head(8).to_dict()))
        df = df.drop_duplicates(["level", "country_name", "unit_id", "year"])
    if df.empty:
        sys.exit("[stop] no usable row is left (see the exclusions above)")
    rows, odd_parent, reasons, misses = [], 0, [], []
    def rate_tol(rate: float) -> float:
        """Half a unit of the last digit the compiler's rate carries: 0.5 for an integer-valued rate, 0.05 for one decimal, 0.005 for more."""
        if abs(rate - round(rate)) < 1e-9:
            return 0.5
        return 0.05 if abs(rate * 10 - round(rate * 10)) < 1e-6 else 0.005
    if "rate" in df.columns:
        rt = df[df["rate"].notna()]
        shape = np.where((rt["rate"] - rt["rate"].round()).abs() < 1e-9, "integer-valued", np.where((rt["rate"] * 10 - (rt["rate"] * 10).round()).abs() < 1e-6, "one decimal", "more decimals"))
        sh = pd.crosstab(rt["country_name"], shape, normalize="index").mul(100).round(0)
        print("[rate rounding] the compiler's rate is rounded to its own precision; share of integer-valued rates is high in: "
              + (", ".join(f"{c} ({v:.0f}%)" for c, v in sh.get("integer-valued", pd.Series(dtype=float)).sort_values(ascending=False).items() if v >= 50) or "no country")
              + " (each row is checked to within half a unit of its own last digit)")
    for r in df.sort_values(["country_name", "level", "unit_raw", "year"]).itertuples():
        cases, pop = int(r.homicide), int(round(r.population))
        mine = cases / pop * 1e5
        rate = getattr(r, "rate", np.nan)
        rate_ok = None if rate != rate else bool(abs(mine - rate) <= max(RATE_TOL_REL * rate, rate_tol(rate)) + 1e-9)
        ratio = rate / mine if (rate == rate and mine > 0) else float("nan")
        rate_far = rate_ok is False and not (abs(ratio - 1) <= RATE_BAND + 1e-9)              # beyond the 10% band
        rate_near = rate_ok is False and not rate_far                                         # 1% to 10%: a note only
        slip = rate_far and any(abs(ratio / k - 1) < 0.03 for k in (0.1, 10, 0.01, 100))     # almost exactly 10x or 100x: a unit slip in the compiler's rate
        if rate_far:
            misses.append((r.country_name, r.level, clean_name(r.unit_raw, r.country_name), r.year, cases, pop, mine, rate))
        nat_v = national.get((r.country_name, r.year))
        cap_ok = None if nat_v is None else bool(cases <= nat_v)
        weak = has(WEAK_WORDS, r.source_1)
        cited = "; ".join(t for t in (r.source_1, r.source_2) if t)
        why = [t for t, c in (("compiler's rate differs from cases / population by more than 10%" + (" (a factor of 10 or 100: a unit slip)" if slip else ""), rate_far), ("above the national total", cap_ok is False),
                              ("third-party compilation or estimate", weak), ("no source cited", not cited)) if c]
        reasons.append("; ".join(why))
        tier = "C" if why else "B"
        unit = clean_name(r.unit_raw, r.country_name)
        city = r.level == "cities"
        parent = r.country_name
        if city:
            st = clean_name(r.state_name, r.country_name)
            if st in ("", ".", "-") or st == unit or st == r.unit_raw:
                odd_parent += 1
            else:
                parent = st
        rows.append({
            "country": r.country_name, "unit": unit, "unit_local": "", "unit_code": "", "admin_level": "city" if city else "admin1", "unit_type": "city" if city else "state",
            "parent_unit": parent, "year": r.year, "homicide_cases": cases, "population": pop, "homicide_rate_per_100k": mine,
            "flag_low_count": cases < LOW_COUNT, "flag_outlier_year": False, "population_age_years": float("nan"),
            "indicator_type": r.indicator_type, "reliability_tier": tier, "definition_flags": "",
            "validation": "the whole layer was fetched (rows equal the server's count) and the object ids are unique; "
                          + (f"the compiler's own rate ({rate:.2f}) {'agrees with' if rate_ok else 'DIFFERS from' if rate_far else 'differs slightly from'} cases / population ({mine:.2f})"
                             + (", probably a different population vintage" if rate_near else ", a factor of 10 or 100 (a unit slip in the compiler's rate)" if slip else "")
                             if rate_ok is not None else "the compiler gives no rate to compare with")
                          + ("; " + (f"cases ({cases}) do not exceed the national total ({int(nat_v)})" if cap_ok else f"cases ({cases}) EXCEED the national total ({int(nat_v)})") if cap_ok is not None else "; no national total to compare with")
                          + ("; the compiler cites its source" if cited else "; NO source is cited for this row")
                          + ("; the source is a third-party compilation or an estimate (not an official publication)" if weak else ""),
            "indicator": "Igarape Institute Homicide Monitor: homicides by " + ("city" if city else "state") + ", a secondary compilation of the official figures cited in the row",
            "population_method": "the population of the same row as published by the compiler (the date within the year is not stated)",
            "data_notes": f"secondary compilation; cited source(s): {cited or 'none'}; the definition (homicide, intentional homicide, deaths by aggression ...) follows the cited source",
            "source_homicide": url_c if city else url_s, "source_population": url_c if city else url_s, "retrieved": got,
            "igarape_id": r.unit_id, "igarape_source_1": r.source_1, "igarape_source_2": r.source_2,
            "latitude": getattr(r, "latitude", np.nan), "longitude": getattr(r, "longitude", np.nan)})
    out = pd.DataFrame(rows)
    out["tier_reason"] = reasons
    out = out.sort_values(["igarape_id", "year"]).reset_index(drop=True)
    pct = out.groupby("igarape_id")["population"].pct_change()
    gap = out.groupby("igarape_id")["year"].diff()
    out["flag_population_break"] = (pct.abs() > 0.25) & (gap == 1)
    out.loc[out["flag_population_break"], "data_notes"] += "; the compiler's population changes by more than 25% from the previous year (a break in the series): rates across it are not comparable"
    # DECISION: a break means that the denominators on its two sides do not describe the same area, and either side can be the wrong one (for example a department whose early population is smaller than
    # a city inside it). So the WHOLE series of a unit with a break is tier C, not only the year that follows the jump; the break year alone keeps flag_population_break.
    brk = out.loc[out["flag_population_break"]].groupby("igarape_id")["year"].agg(lambda y: ", ".join(str(int(v)) for v in sorted(y)))
    for uid, yrs in brk.items():
        m = out["igarape_id"] == uid
        out.loc[m, "reliability_tier"] = "C"
        out.loc[m, "tier_reason"] = out.loc[m, "tier_reason"].map(lambda t: (t + "; " if t else "") + f"the compiler's population series for this unit breaks in {yrs}")
        out.loc[m, "validation"] += f"; FAILED: the compiler's population for this unit changes by more than 25% in {yrs}, so the denominators before and after do not describe the same area and no rate of the series is reliable"
        m2 = m & ~out["flag_population_break"]
        out.loc[m2, "data_notes"] += f"; the unit's population series has a break above 25% in {yrs}: rates across it are not comparable"
    print(f"[population breaks] {len(brk)} unit(s) have a break in their population series; all their rows are tier C")
    key = ["country", "parent_unit", "unit"]
    clash = out.groupby(key)["igarape_id"].nunique()
    clash = clash[clash > 1]
    if len(clash):                                     # different units with the same name and parent (two cities without a state, a city and a state): keep both
        m = out.set_index(key).index.isin(clash.index)
        out.loc[m, "unit"] = out.loc[m, "unit"] + " [" + out.loc[m, "igarape_id"] + "]"
        print(f"[names] {len(clash)} name(s) belong to more than one unit with the same parent; the compiler's id is appended to them, e.g. {sorted(set(out.loc[m, 'unit']))[:4]}")
    out = F.add_outlier_flags(out)
    if out["robust_z"].isna().all():
        out = out.drop(columns="robust_z")
    out = F.finalize(out)
    F.require_valid(out, "igarape")
    print(f"\n[parents] {odd_parent:,} city rows have no real state in the layer (placeholder or the city's own name): their parent_unit is the country")
    print(f"Reliability tiers: {out.reliability_tier.value_counts().to_dict()}; indicator types: {out.indicator_type.value_counts().to_dict()}; levels: {out.admin_level.value_counts().to_dict()}")
    c = out[out.reliability_tier == "C"]
    if len(c):
        print("[tier C reasons] rows by country and reason:")
        print(c.groupby(["country", "tier_reason"]).size().reset_index(name="rows").sort_values("rows", ascending=False).to_string(index=False, max_colwidth=60))
    if misses:
        m = pd.DataFrame(misses, columns=["country", "level", "unit", "year", "cases", "population", "ours", "compiler"])
        m["ratio"] = m["compiler"] / m["ours"]
        print("[rate disagreements] the worst three per country (ours = cases / population x 100,000; ratio = compiler / ours):")
        print(m.assign(d=(m["ours"] - m["compiler"]).abs()).sort_values("d", ascending=False).groupby("country").head(3).sort_values(["country", "d"], ascending=[True, False])
              .drop(columns="d").round(2).to_string(index=False))
    print(f"[population breaks] {int(out['flag_population_break'].sum())} rows follow a year-to-year population change above 25% (flag_population_break)")
    g = out.groupby(["country", "admin_level"]).agg(units=("igarape_id", "nunique"), rows=("year", "size"), first=("year", "min"), last=("year", "max"),
                                                    A_or_B=("reliability_tier", lambda s: int((s == "B").sum())), C=("reliability_tier", lambda s: int((s == "C").sum())))
    print(g.to_string())
    if inspect_only:
        print("\n[inspect only] no CSV written")
    else:
        F.write_csv(out, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(out):,} rows, {out['igarape_id'].nunique()} units, {out['country'].nunique()} countries, years {int(out.year.min())}-{int(out.year.max())})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--reuse", action="store_true", help="use the pages saved by an earlier run instead of downloading again")
    a = ap.parse_args()
    REUSE["on"] = a.reuse
    cmd_build(a.cmd == "inspect")