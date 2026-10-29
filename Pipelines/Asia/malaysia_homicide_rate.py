#!/usr/bin/env python3
"""
Malaysia - police-recorded murder cases per 100,000 residents, by district.

NUMERATOR   (official): Royal Malaysia Police (PDRM) crime by district, published by the Department of Statistics Malaysia (DOSM)
            on data.gov.my: crime_district.parquet, crime type 'murder'. Cases recorded, one row per state / district / year.
DENOMINATOR (official): DOSM population by administrative district, population_district.parquet (2020-2024, in '000), the
            all-sexes / all-ages / all-ethnicities / all-strata total. Rates are produced for the years both files cover.
LEVELS      Two levels, never to be added together (filter on `admin_level`):
            STATES (admin1): all police districts of the state against the sum of the state's administrative districts. No name
            matching is involved and every police district is counted, so the states cover the whole national total. Kuala Lumpur
            uses the population of Kuala Lumpur + Putrajaya, because the crime file has no Putrajaya rows (checked in the data; if
            Putrajaya ever had crime rows of its own the run stops).
            DISTRICTS (admin2): a police district matched to the administrative district of the SAME NAME (accents and punctuation
            ignored). No hand-made mapping is used: a police district without an exact name match is left out of this level and
            reported, with the share of national murders it takes out. Two districts of the same name in different states would be
            merged by a name-only match, so the run stops if that occurs.
CHECKS      Per year: the police districts add up to the national murder total of the same file; for each state they add up to
            the file's own state-level 'All' row; one category only for the murder type; no duplicate state / district / year rows;
            the district populations add up to a national figure of plausible size; for each state the sum of its districts equals
            DOSM's own state population table (population_state.parquet, a second official table; if it cannot be fetched the state
            rows stay tier B). State rows are tier A when both state checks pass; district rows are tier B (approximate name match).
            The text in `validation` is built from these results.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Malaysia/ ; the one output is
            malaysia_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python malaysia_homicide_rate.py inspect   (schemas, values, name-matching report; no file written)
            python malaysia_homicide_rate.py build     (writes the CSV)
Needs:      pip install pandas pyarrow requests
"""
import argparse
import difflib
import importlib.util
import io
import re
import sys
import unicodedata
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 7:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")
if importlib.util.find_spec("pyarrow") is None:          # pandas needs it to read parquet
    sys.exit("[stop] this script needs pyarrow:  python -m pip install pyarrow")

P = F.paths(__file__, "Malaysia")        # raw downloads -> Data/Raw/<Region>/Malaysia/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

CRIME_URL = "https://storage.data.gov.my/publicsafety/crime_district.parquet"
POP_URL = "https://storage.dosm.gov.my/population/population_district.parquet"
STATE_POP_URL = "https://storage.dosm.gov.my/population/population_state.parquet"      # second official table, used as a check
CRIME_TYPE = "murder"
POP_TOL_PER_DISTRICT = 0.05     # thousand persons: each district figure is rounded to 0.1 thousand, so a state sum can differ from the state table by this much per district
POP_SANITY = (20e6, 45e6)       # the district populations must add up to a figure of Malaysia's scale (30M+); otherwise the unit is wrong

KL_CRIME_STATE = "W.P. Kuala Lumpur"
KL_POP_STATES = ("W.P. Kuala Lumpur", "W.P. Putrajaya")
PUTRAJAYA = "W.P. Putrajaya"
KL_UNIT = "kuala lumpur incl putrajaya"
KL_LABEL = "Kuala Lumpur (incl. Putrajaya)"


# ---------- helpers ----------
def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def read_parquet(url: str, name: str) -> pd.DataFrame:
    """Live dataset: downloaded at every run (a dated copy is kept in the raw folder)."""
    return pd.read_parquet(io.BytesIO(FETCH.get(url, name, reuse=False, suffix=".parquet")))


def load_crime() -> pd.DataFrame:
    df = read_parquet(CRIME_URL, "dosm_crime_district")
    df["date"] = pd.to_datetime(df["date"])
    df["year"] = df["date"].dt.year
    return df


def load_pop() -> pd.DataFrame:
    df = read_parquet(POP_URL, "dosm_population_district")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"])
        df["year"] = df["date"].dt.year
    return df


def pop_district_col(df: pd.DataFrame) -> str:
    for c in ("district", "lga", "admin_district"):
        if c in df.columns:
            return c
    sys.exit(f"No district column in population file. Columns: {list(df.columns)}")


def pick_total(df: pd.DataFrame, col: str) -> pd.DataFrame:
    """Select the 'all groups' row for a breakdown column (sex/age/ethnicity...)."""
    if col not in df.columns:
        return df
    vals = set(df[col].astype(str).str.lower().unique())
    for cand in ("both", "overall", "all", "total"):
        if cand in vals:
            return df[df[col].astype(str).str.lower() == cand]
    sys.exit(f"Cannot find a 'total' value in population column '{col}'. Values: {sorted(vals)[:30]}")


def crime_murders(crime: pd.DataFrame) -> pd.DataFrame:
    m = crime[(crime["type"] == CRIME_TYPE) & (crime["district"] != "All") & (crime["state"] != "Malaysia")]
    cats = m["category"].unique()
    print(f"[crime] category values for type='{CRIME_TYPE}': {list(cats)}")
    if len(cats) != 1:
        sys.exit("Multiple categories for murder -- decide which one to use before continuing.")
    if m.duplicated(["state", "district", "year"]).any():
        sys.exit("Duplicate state/district/year rows in crime data.")
    return m[["state", "district", "year", "crimes"]].rename(columns={"crimes": "murders"})


def pop_totals(df: pd.DataFrame, need_district: bool = True) -> pd.DataFrame:
    if not need_district:                                  # DOSM's state table: state / year / population
        for col in ("sex", "age", "ethnicity", "strata", "citizenship"):
            df = pick_total(df, col)
        out = df[["state", "year", "population"]].copy()
        if out["population"].max() < 100_000:
            out["population"] *= 1000
        return out
    dcol = pop_district_col(df)
    for col in ("sex", "age", "ethnicity", "strata", "citizenship"):
        df = pick_total(df, col)
    df = df[df[dcol].notna() & (df[dcol].astype(str).str.lower() != "all")]
    cols = ([] if "state" not in df.columns else ["state"]) + [dcol, "year", "population"]
    out = df[cols].rename(columns={dcol: "district"}).copy()
    if "state" not in out.columns:
        out["state"] = ""
    if out.duplicated(["district", "year"]).any():
        sys.exit("Duplicate district/year rows in population (same district name in two states, "
                 "or an unhandled breakdown column). Inspect before continuing.")
    nat = out.groupby("year")["population"].sum()
    if nat.max() < 100_000:                               # Malaysia is 30M+: a tiny sum means the values are in thousands
        print("[pop] values look like thousands -> multiplying by 1000")
        out["population"] *= 1000
        nat *= 1000
    if not nat.between(*POP_SANITY).all():
        sys.exit(f"National population sanity check failed:\n{nat}")
    print(f"[pop] years: {out['year'].min()}-{out['year'].max()}; national totals OK")
    return out


def with_unit(df: pd.DataFrame) -> pd.DataFrame:
    """Unit key = normalised district name (the population file has no reliable state column)."""
    df = df.copy()
    df["unit"] = [norm(d) for d in df["district"]]
    return df


# ---------- commands ----------
def cmd_inspect():
    crime, pop = load_crime(), load_pop()
    for name, df in (("CRIME", crime), ("POPULATION", pop)):
        print(f"\n===== {name} =====")
        print(df.dtypes)
        print(df.head())
        for c in df.select_dtypes(include=["object", "string"]).columns:
            u = df[c].unique()
            print(f"{c}: {len(u)} unique", list(u[:15]))
        if "year" in df:
            print("years:", sorted(df["year"].unique()))
    m = crime_murders(crime)
    p = pop_totals(pop)
    pop_names = {norm(d) for d in p["district"].unique()}
    rows = []
    for s_, d in m[["state", "district"]].drop_duplicates().values:
        exact = norm(d) in pop_names
        cands = difflib.get_close_matches(norm(d), list(pop_names), n=3, cutoff=0.5)
        rows.append({"state": s_, "crime_district": d, "exact_match": exact, "suggestions": "; ".join(cands)})
    rep = pd.DataFrame(rows).sort_values(["exact_match", "state"])
    print(f"\nExact name matches: {rep.exact_match.sum()} / {len(rep)}")
    print("\n--- CRIME (police) districts with NO exact population match ---")
    print(rep[~rep.exact_match].to_string(index=False))
    crime_names = {norm(d) for d in m["district"].unique()}
    pop_un = p[~p["district"].map(norm).isin(crime_names)][["state", "district"]].drop_duplicates()
    print("\n--- POPULATION (admin) districts with NO crime-district match ---")
    print(pop_un.sort_values(["state", "district"]).to_string(index=False))
    print("\n[inspect only] no CSV written")


def state_population_check(p_state_sum: dict, n_districts: dict, members: dict):
    """Compare each state's district sum (persons) with DOSM's own state table. members: normalised state -> the state-table names to add up
    (Kuala Lumpur + Putrajaya for Kuala Lumpur). -> (set of (state, year) that agree or None, message)."""
    try:
        raw_state = read_parquet(STATE_POP_URL, "dosm_population_state")
        if "year" not in raw_state.columns:
            raw_state["year"] = pd.to_datetime(raw_state["date"]).dt.year
        st = pop_totals(raw_state, need_district=False)
    except (RuntimeError, SystemExit, KeyError, ValueError) as e:
        return None, f"the DOSM state population table could not be used ({str(e)[:100]})"
    st_sum = st.groupby([st["state"].map(norm), "year"])["population"].sum()
    ok = set()
    for (state_n, y), v in p_state_sum.items():
        parts = [(n, y) for n in members[state_n]]
        if all(k in st_sum.index for k in parts):
            expected = sum(st_sum[k] for k in parts)
            if abs(v - expected) <= (POP_TOL_PER_DISTRICT * n_districts[(state_n, y)] + 0.1) * 1000:
                ok.add((state_n, y))
    return ok, None


def cmd_build():
    crime_all = load_crime()
    m = with_unit(crime_murders(crime_all))
    p = with_unit(pop_totals(load_pop()))

    # a name-only merge is unsafe if one name belongs to two states in the crime file
    states_per_name = m.groupby("unit")["state"].nunique()
    if (states_per_name > 1).any():
        sys.exit("[stop] the same district name occurs in more than one state, so a name-only match would merge them: "
                 + ", ".join(sorted(states_per_name[states_per_name > 1].index)))
    if (crime_all["state"] == PUTRAJAYA).any():
        sys.exit("[stop] the crime file has rows for W.P. Putrajaya, so adding Putrajaya's population to Kuala Lumpur would understate "
                 "Kuala Lumpur's rate; decide how to treat Putrajaya before continuing.")

    # national total reconciliation
    nat = crime_all[(crime_all.type == CRIME_TYPE) & (crime_all.district == "All") & (crime_all.state == "Malaysia")].set_index("year")["crimes"]
    dist_sum = m.groupby("year")["murders"].sum()
    print("\n[check] sum of police districts vs national murder total:")
    print(pd.DataFrame({"districts": dist_sum, "national": nat}).assign(diff=lambda x: x.districts - x.national))
    state_all = crime_all[(crime_all.type == CRIME_TYPE) & (crime_all.district == "All") & (crime_all.state != "Malaysia")].set_index(["state", "year"])["crimes"]

    years = sorted(set(m["year"]) & set(p["year"]))
    print(f"[years] crime {m['year'].min()}-{m['year'].max()}, population {p['year'].min()}-{p['year'].max()} -> using overlap {years[0]}-{years[-1]}")
    nat_pop = p.groupby("year")["population"].sum()
    labels = p.drop_duplicates("unit").set_index("unit")["district"]
    pop_state_by_norm = {norm(x): x for x in p["state"].unique()}

    # ---------------- STATES (admin1)
    crime_states = sorted(m["state"].unique())
    pop_only = sorted(set(pop_state_by_norm.values()) - set(crime_states) - {PUTRAJAYA})
    police_names = m[["state", "district"]].drop_duplicates()
    assigned = {}                      # population-only state -> the crime state that has a police district of that name (e.g. W.P. Labuan)
    for ps_name in pop_only:
        dn = {norm(d) for d in p[p["state"] == ps_name]["district"]} | {norm(ps_name)}
        hit = sorted({st_ for st_, d in police_names.values if norm(d) in dn})
        if len(hit) > 1:
            sys.exit(f"[stop] a police district named like {ps_name} exists in several states {hit}; decide where its population belongs")
        if hit:
            assigned[ps_name] = hit[0]
            print(f"[match] the police district '{ps_name}' is inside the crime state {hit[0]}, so {ps_name}'s population is added to {hit[0]}")
    no_crime = [x for x in pop_only if x not in assigned]
    state_rows, p_state_sum, n_dist, members, names_of = [], {}, {}, {}, {}
    for s_ in crime_states:
        names = [s_] + ([PUTRAJAYA] if s_ == KL_CRIME_STATE else []) + [ps for ps, cs in assigned.items() if cs == s_]
        names_of[s_] = names
        if any(norm(n) not in pop_state_by_norm for n in names):
            sys.exit(f"[stop] the population file has no state '{[n for n in names if norm(n) not in pop_state_by_norm]}' for the crime state {s_}")
        members[norm(s_)] = [norm(n) for n in names]
        ps = p[p["state"].map(norm).isin({norm(n) for n in names})]
        for y, g in ps.groupby("year"):
            p_state_sum[(norm(s_), y)] = g["population"].sum()
            n_dist[(norm(s_), y)] = len(g)
    ok_pop, why_not = state_population_check(p_state_sum, n_dist, members)
    print("[check] state populations vs the DOSM state table:", why_not or f"{len(ok_pop)} of {len(p_state_sum)} state-years agree")
    for s_ in crime_states:
        ms = m[m["state"] == s_].groupby("year")["murders"].sum()
        names = names_of[s_]
        ps = p[p["state"].map(norm).isin({norm(n) for n in names})].groupby("year")["population"].sum()
        for y in years:
            if y not in ms.index or y not in ps.index:
                continue
            all_row = state_all.get((s_, y))
            recon_ok = all_row is not None and int(ms[y]) == int(all_row)
            pop_ok = None if ok_pop is None else ((norm(s_), y) in ok_pop)
            kl = s_ == KL_CRIME_STATE
            checks = [f"the police districts of the state add up to the file's state-level 'All' row ({int(all_row):,})" if recon_ok
                      else (f"the police districts ({int(ms[y]):,}) DIFFER from the state-level 'All' row ({int(all_row):,})" if all_row is not None
                            else "no state-level 'All' row to reconcile against")]
            checks.append("the sum of the state's districts equals DOSM's own state population table" if pop_ok is True
                          else ("the sum of the state's districts DIFFERS from DOSM's state population table" if pop_ok is False else "DOSM's state population table not used"))
            pop = int(round(ps[y]))
            state_rows.append({
                "country": "Malaysia", "unit": KL_LABEL if kl else s_, "unit_local": "", "unit_code": "", "admin_level": "admin1",
                "unit_type": "federal_territory" if kl else "state", "parent_unit": "", "year": int(y), "homicide_cases": int(ms[y]),
                "population": pop, "homicide_rate_per_100k": int(ms[y]) / pop * 1e5, "flag_low_count": int(ms[y]) < LOW_COUNT,
                "flag_outlier_year": False, "indicator_type": "police_recorded_cases",
                "reliability_tier": "A" if (recon_ok and pop_ok is True) else "B", "definition_flags": "",
                "validation": "; ".join(checks + [f"all the police districts of the file add up to the national total ({int(dist_sum[y]):,} against {int(nat[y]):,})"
                                                  if y in nat.index and int(dist_sum[y]) == int(nat[y]) else "the police districts do not add up to the national total of the file"]),
                "indicator": f"PDRM murder cases by police district (crime type '{CRIME_TYPE}'), summed over the state's police districts; published by DOSM on data.gov.my",
                "population_method": "sum of the DOSM population estimates of the state's administrative districts for the year"
                                     + (f", including {' + '.join(n for n in names[1:])}" if len(names) > 1 else ""),
                "population_age_years": 0.0,
                "data_notes": ("Kuala Lumpur's crime rows include Putrajaya (the file has none for Putrajaya), so the population is Kuala Lumpur + Putrajaya. " if kl else "")
                              + "".join(f"the file has a police district named {ps_n} inside {s_}, so {ps_n}'s population is added to {s_}'s denominator. "
                                        for ps_n, cs in assigned.items() if cs == s_)
                              + (f"{', '.join(no_crime)} has population rows but no crime rows in the file and is in no state's denominator" if no_crime else ""),
                "source_homicide": CRIME_URL, "source_population": POP_URL + (f" ; {STATE_POP_URL}" if ok_pop is not None else ""),
                "retrieved": FETCH.retrieved_on(CRIME_URL, POP_URL), "match_type": "state_sum"})

    # ---------------- DISTRICTS (admin2): exact name matches only, Kuala Lumpur's police districts have no admin district of their own
    m_d, p_d = m[m["state"] != KL_CRIME_STATE], p[~p["state"].map(norm).isin({norm(x) for x in KL_POP_STATES})]
    m_d, p_d = m_d[m_d["year"].isin(years)], p_d[p_d["year"].isin(years)]
    state_of = m_d.drop_duplicates("unit").set_index("unit")["state"]
    m_u = m_d.groupby(["unit", "year"], as_index=False)["murders"].sum()
    p_u = p_d.groupby(["unit", "year"], as_index=False)["population"].sum()
    merged = m_u.merge(p_u, on=["unit", "year"], how="outer", indicator=True)
    dropped = merged[merged["_merge"] == "left_only"].groupby("unit")["murders"].sum().sort_values(ascending=False).rename("murders_dropped")
    print(f"[drop] {len(dropped)} police districts have no exact population match and have no district row (they are inside their state's row). Largest:")
    print(dropped.head(12).to_string())
    df = merged[merged["_merge"] == "both"].drop(columns="_merge")
    df["population"] = df["population"].round().astype("int64")
    kept_d = df.groupby("year")["murders"].sum()
    district_rows = []
    for _, r in df.sort_values(["unit", "year"]).iterrows():
        y = int(r["year"])
        cov = f"the district rows hold {int(kept_d[y]):,} of the national {int(nat[y]):,} murders ({kept_d[y] / nat[y]:.1%}); the rest is in the state rows" if y in nat.index else ""
        district_rows.append({
            "country": "Malaysia", "unit": labels.get(r["unit"], r["unit"]), "unit_local": "", "unit_code": "", "admin_level": "admin2",
            "unit_type": "district", "parent_unit": str(state_of.get(r["unit"], "")), "year": y, "homicide_cases": int(r["murders"]),
            "population": int(r["population"]), "homicide_rate_per_100k": int(r["murders"]) / int(r["population"]) * 1e5,
            "flag_low_count": int(r["murders"]) < LOW_COUNT, "flag_outlier_year": False, "indicator_type": "police_recorded_cases",
            "reliability_tier": "B", "definition_flags": "",
            "validation": "; ".join(t for t in ("exact name match between the police district and the DOSM administrative district",
                                                 "one category only for murder and no duplicate state/district/year rows",
                                                 f"the district populations add up to {int(nat_pop[y]):,} (national scale)", cov) if t),
            "indicator": f"PDRM murder cases by police district (crime type '{CRIME_TYPE}'), published by DOSM on data.gov.my",
            "population_method": "DOSM population estimate of the year for the administrative district of the same name", "population_age_years": 0.0,
            "data_notes": "police district matched to the administrative district of the same name; the two boundaries may differ; "
                          "police districts with no exact name match have no district row and are inside their state's row",
            "source_homicide": CRIME_URL, "source_population": POP_URL, "retrieved": FETCH.retrieved_on(CRIME_URL, POP_URL), "match_type": "exact_name"})

    out = pd.DataFrame(state_rows + district_rows)
    small = out[out["population"] < MIN_POP]                    # the rule is per row: a unit below 100,000 residents in a year has no row for that year
    if len(small):
        by_unit = small.groupby("unit")["population"].agg(["size", "max"]).sort_values("max", ascending=False)
        print(f"[filter] {len(small)} unit-years ({len(by_unit)} units) under {MIN_POP:,} residents have no row. The largest of them: "
              + "; ".join(f"{u} ({int(r['size'])} yr, up to {int(r['max']):,})" for u, r in by_unit.head(10).iterrows())
              + (f"; ... and {len(by_unit) - 10} smaller units" if len(by_unit) > 10 else ""))
        out = out.drop(small.index).reset_index(drop=True)
    out = F.add_outlier_flags(out)
    for _, r in out[out.flag_outlier_year].iterrows():
        print(f"[malaysia] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if out["robust_z"].isna().all():
        out = out.drop(columns="robust_z")
    out = F.finalize(out)
    F.require_valid(out, "malaysia")
    st_kept = out[out.admin_level == "admin1"].groupby("year")["homicide_cases"].sum()
    cov = pd.DataFrame({"states": st_kept, "districts": kept_d.reindex(st_kept.index), "national": nat.reindex(st_kept.index)})
    cov["states_cover"] = (cov["states"] / cov["national"]).map("{:.1%}".format)
    cov["districts_cover"] = (cov["districts"] / cov["national"]).map("{:.1%}".format)
    print("\n[coverage] share of national murders represented, per level:")
    print(cov)
    print(f"\nReliability tiers: {out.reliability_tier.value_counts().to_dict()}   by level: {out.groupby('admin_level').reliability_tier.value_counts().to_dict()}")
    F.write_csv(out, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(out)} rows: {int((out.admin_level == 'admin1').sum())} state rows, {int((out.admin_level == 'admin2').sum())} district rows, years {years[0]}-{years[-1]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    a = ap.parse_args()
    cmd_inspect() if a.cmd == "inspect" else cmd_build()