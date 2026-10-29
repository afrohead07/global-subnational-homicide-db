#!/usr/bin/env python3
"""
PROJECT INVENTORY - how much does the database cover? Reads the continental master panels in <repo>/Data/Output and reports, from the data itself (nothing typed):

  * countries, rows, units (provinces / states / regions, counties / districts / municipalities, cities, police units), unit-years, the years covered, per region and in total;
  * rows and units by admin level and by unit type; by reliability tier, indicator type, count unit and layer;
  * a per-country table (rows, units, first and last year, number of distinct years, tiers, layers, indicator types);
  * rows per year, the thinnest and the densest parts of the panel.
It writes Data/Output/project_inventory_by_country.csv and Data/Output/project_inventory.md (the whole report, tables included).

COUNTING RULES (stated here because every number depends on them)
  * a COUNTRY is a distinct value of `country` (Australia is one country however many layers it has);
  * a UNIT is a distinct (country, parent_unit, unit): units of different layers of one country are counted separately and nested units are not netted (the 8 Australian states and the LGAs of New South Wales
    are all units); a unit that moves between layers under different names counts twice;
  * a UNIT-YEAR is a row;
  * a unit that sits in two continental panels (a country on the Europe-Asia border) is counted once in the totals and once per region in the regional tables;
  * the groups 'provinces / states / regions', 'counties / districts / municipalities', 'cities' and 'police units' are the format's `admin_level` values admin1, admin2, city and police_unit; the exact
    names (state, province, county, LGA, prefecture, district ...) are in the unit-type table.

Usage       python project_inventory.py            (reads the five continental panels; add --world to read global_master_panel.csv instead)
Needs       pip install pandas
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

REGIONS = ["africa", "americas", "asia", "europe", "oceania"]
GROUPS = {"admin1": "provinces / states / regions (first level)", "admin2": "counties / districts / municipalities (second level)", "city": "cities", "police_unit": "police units"}


def to_md(df: pd.DataFrame, floatfmt: str = "{:,.0f}") -> str:
    """A Markdown table; counts get thousands separators, the columns that hold years or periods do not."""
    cols = [str(c) for c in df.columns]
    plain = {i for i, c in enumerate(cols) if "year" in c.lower() or "period" in c.lower() or c.lower() in ("number",) and False}
    lines = ["| " + " | ".join(cols) + " |", "|" + "|".join("---" for _ in cols) + "|"]
    for _, r in df.iterrows():
        cells = []
        for i, v in enumerate(r.values):
            if i in plain or isinstance(v, str):
                cells.append(str(v))
            elif isinstance(v, float) and v == v:
                cells.append(floatfmt.format(v) if abs(v) >= 100 else f"{v:.1f}")
            elif isinstance(v, (int,)) or hasattr(v, "dtype"):
                cells.append(f"{int(v):,}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def load(root: Path, world: bool):
    folder = root / "Data" / "Output"
    names = ["global"] if world else REGIONS
    frames, missing = [], []
    for n in names:
        p = folder / f"{n}_master_panel.csv"
        if not p.exists():
            missing.append(n)
            continue
        d = pd.read_csv(p, dtype=str, keep_default_na=False)
        if "region" not in d.columns:
            d["region"] = n.capitalize()
        d["panel"] = n
        frames.append(d)
    if not frames:
        sys.exit(f"[stop] no master panel found in {folder}: run the continental *_master_panel.py scripts first")
    df = pd.concat(frames, ignore_index=True, sort=False)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["unit_key"] = df["country"] + "|" + df["parent_unit"] + "|" + df["unit"]
    for c in ("layer", "count_unit", "indicator_type", "unit_type", "admin_level", "reliability_tier"):
        if c not in df.columns:
            df[c] = ""
    return df, missing


def span(s: pd.Series) -> str:
    return f"{int(s.min())}-{int(s.max())}" if s.notna().any() else "-"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--world", action="store_true", help="read global_master_panel.csv instead of the five continental panels")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    df, missing = load(root, a.world)
    out_dir = root / "Data" / "Output"
    md = ["# Project inventory", "", f"Built from {', '.join(sorted(df['panel'].unique()))} master panel(s)" + (f"; **not found: {', '.join(missing)}**" if missing else "") + ".", ""]

    def section(title, table, note=None):
        md.extend([f"## {title}", ""])
        if note:
            md.extend([note, ""])
        md.extend([to_md(table), ""])
        print(f"\n=== {title} ===")
        print(table.to_string(index=False))

    # ---- totals
    tot = pd.DataFrame([{"what": "rows (unit-years)", "number": len(df)}, {"what": "countries", "number": df["country"].nunique()}, {"what": "units (country, parent, unit)", "number": df["unit_key"].nunique()},
                        {"what": "distinct years", "number": df["year"].nunique()}, {"what": "first year", "number": f"{int(df['year'].min())}"}, {"what": "last year", "number": f"{int(df['year'].max())}"},
                        {"what": "layers (source files)", "number": df["layer"].nunique() if df["layer"].ne("").any() else df["source_file"].nunique()}])
    section("Totals", tot)
    # ---- by region
    reg = df.groupby("region").agg(countries=("country", "nunique"), units=("unit_key", "nunique"), rows=("unit_key", "size"), first_year=("year", "min"), last_year=("year", "max"), distinct_years=("year", "nunique")).reset_index()
    section("By region", reg)
    # ---- by admin level
    lvl = df.groupby("admin_level").agg(units=("unit_key", "nunique"), rows=("unit_key", "size"), countries=("country", "nunique")).reset_index()
    lvl.insert(1, "meaning", lvl["admin_level"].map(GROUPS).fillna(""))
    section("Units by admin level (the groups you asked about)", lvl, "admin1 = provinces, states, regions; admin2 = counties, districts, municipalities; city = cities; police_unit = police units.")
    lr = df.groupby(["region", "admin_level"]).agg(units=("unit_key", "nunique"), rows=("unit_key", "size")).reset_index()
    section("Units by region and admin level", lr)
    ut = df.groupby(["admin_level", "unit_type"]).agg(units=("unit_key", "nunique"), rows=("unit_key", "size"), countries=("country", "nunique")).reset_index().sort_values(["admin_level", "units"], ascending=[True, False])
    section("Units by exact unit type", ut, "The names the sources use (state, province, county, LGA, prefecture, district, region, city ...).")
    # ---- quality
    tier = df.groupby("reliability_tier").agg(rows=("unit_key", "size"), countries=("country", "nunique"), units=("unit_key", "nunique")).reset_index()
    tier["share_of_rows"] = (tier["rows"] / len(df) * 100).round(1)
    section("Reliability tiers", tier, "A = reconciled with an independent confirmation and a recent denominator; B = a documented weakness; C = a failed hard check or a proxy.")
    for col, title in (("indicator_type", "Indicator type"), ("count_unit", "What is counted")):
        if df[col].ne("").any():
            t = df.groupby(col).agg(rows=("unit_key", "size"), countries=("country", "nunique"), units=("unit_key", "nunique")).reset_index()
            section(title, t)
    if df["layer"].ne("").any():
        ly = df.groupby(["region", "layer"]).agg(countries=("country", "nunique"), units=("unit_key", "nunique"), rows=("unit_key", "size"), first_year=("year", "min"), last_year=("year", "max")).reset_index()
        section("Layers (one per source file)", ly)
    # ---- by country
    def mode_join(s):
        return ", ".join(sorted({x for x in s if x}))
    cty = df.groupby(["region", "country"]).agg(rows=("unit_key", "size"), units=("unit_key", "nunique"), first_year=("year", "min"), last_year=("year", "max"), distinct_years=("year", "nunique"),
                                                 tiers=("reliability_tier", mode_join), admin_levels=("admin_level", mode_join), layers=("layer", mode_join)).reset_index()
    cty["span_years"] = cty["last_year"] - cty["first_year"] + 1
    cty = cty.sort_values(["region", "rows"], ascending=[True, False])
    section("By country", cty)
    cty.to_csv(out_dir / "project_inventory_by_country.csv", index=False, encoding="utf-8-sig")
    # ---- time
    ry = df.groupby("year").agg(rows=("unit_key", "size"), countries=("country", "nunique")).reset_index()
    bins = ry.assign(period=lambda x: (x["year"] // 5 * 5).astype(int).astype(str) + "-" + (x["year"] // 5 * 5 + 4).astype(int).astype(str)).groupby("period").agg(rows=("rows", "sum"), max_countries_in_a_year=("countries", "max")).reset_index()
    section("Rows by five-year period", bins)
    thin = cty.sort_values("rows").head(8)[["region", "country", "rows", "units", "first_year", "last_year"]]
    section("The eight thinnest countries", thin)
    dense = cty.sort_values("rows", ascending=False).head(8)[["region", "country", "rows", "units", "first_year", "last_year"]]
    section("The eight densest countries", dense)
    (out_dir / "project_inventory.md").write_text("\n".join(md), encoding="utf-8")
    print(f"\n[ok] wrote {out_dir / 'project_inventory.md'} and {out_dir / 'project_inventory_by_country.csv'}")


if __name__ == "__main__":
    main()