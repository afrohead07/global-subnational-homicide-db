#!/usr/bin/env python3
"""
MASTER PANELS - one file per continent (and one for the world), built from the country files.

WHAT THIS IS  A combiner, not a scraper. Every country script keeps its own source, its own definition and its own CSV next to it (<repo>/Pipelines/<Region>/<country>_homicide_rate.csv). A region's master
            panel stacks those CSVs into ONE file, <repo>/Data/Output/<region>_master_panel.csv, and the world panel stacks the continental ones. Nothing is recomputed: every row is a row of a country file.
ADDED COLUMNS region, source_file (the CSV the row comes from), layer (the file's name without '_homicide_rate'), count_unit (victims / cases / deaths / convictions), year_basis (calendar year, or financial
            year with `year` = its START year) and comparable_within (a key: rates are comparable ONLY between rows that share it, the same year basis and, for proxies, the same reliability tier).
            A source file that already carries one of these columns (the Australian combined file does) keeps its own values.
RULES FOR USE 1. Never compare or pool rates across layers or across countries without reading `definition_flags`, `count_unit`, `indicator`, `reliability_tier` and `population_age_years`: a victim count, a
                 police-recorded case count and a broad proxy are different things.
              2. Never add rows across admin levels (a state and its districts describe the same people).
              3. `year` is the calendar year, except where year_basis says financial year (then it is the START year).
              4. Units of different layers of one country are different units (states and municipalities, say); the panels do not net nested units against each other.
UNIT-NAME COLLISIONS  The shared format's key is (country, parent_unit, unit, year). If two layers of one country use the same unit name and parent (for example a region and a police area both called
            'Scotland'), the later layer's unit is suffixed with ' [layer]' (its `unit_local` is untouched) and the note is added to data_notes; the first layer keeps its name. Collisions are reported.
VALIDATION    The union is validated with the shared format (homicide_format.py) before it is written.

Usage       Each continent has a thin script (africa_master_panel.py, asia_master_panel.py, europe_master_panel.py, oceania_master_panel.py, americas_master_panel.py); global_master_panel.py stacks them.
Needs       pip install pandas numpy
"""
import argparse
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    import homicide_format as F
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder next to master_panel.py")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date: replace it with the latest version (revision 14)")

REVISION = 3
ADDED = ["region", "source_file", "layer", "count_unit", "year_basis", "comparable_within"]
# What a layer COUNTS when its source documents a unit other than the default of its indicator type (police_recorded_cases -> cases). Keep in step with docs_content.LAYERS[layer]['unit']: build_docs.py checks it.
LAYER_COUNT_UNIT = {"eurostat": "offences", "eurostat_cities": "offences", "united_kingdom": "offences"}


def _plain(v):
    """A value for a cell: None for any kind of missing value, a Python int for a whole number, a Python float otherwise, booleans and text as they are."""
    if v is None or v is pd.NA or (isinstance(v, float) and np.isnan(v)):
        return None
    if isinstance(v, (bool, np.bool_)):
        return bool(v)
    if isinstance(v, (int, np.integer)):
        return int(v)
    if isinstance(v, (float, np.floating)):
        return int(v) if float(v).is_integer() and abs(v) < 1e15 else float(v)
    return v


def typed(df: pd.DataFrame, source: str) -> pd.DataFrame:
    """A country CSV is read as text (so that codes such as '10050' stay text); the extras that are plainly numbers or booleans get their type back; the core columns are typed by the shared finalize."""
    out = df.copy()
    for c in F.BOOL_COLS:
        if c in out.columns:
            out[c] = out[c].map({"True": True, "False": False})
            if out[c].isna().any():
                sys.exit(f"[stop] {source}: column {c} holds a value that is neither True nor False")
    for c in out.columns:
        if c in F.CORE_COLUMNS:
            continue
        vals = out[c].astype(str)
        nonblank = vals[vals != ""]
        if len(nonblank) == 0:
            continue
        if set(nonblank) <= {"True", "False"} and len(nonblank) == len(vals):
            out[c] = vals.map({"True": True, "False": False})
            continue
        num = pd.to_numeric(vals.where(vals != ""), errors="coerce")
        if num.notna().sum() == len(nonblank):
            out[c] = num.astype("Int64") if (num.dropna() % 1 == 0).all() else num
    return out


def count_unit_of(row_flags: str, indicator_type: str) -> str:
    if "counts_victims" in str(row_flags):
        return "victims"
    return {"health_registry_deaths": "deaths", "court_convictions": "convictions"}.get(str(indicator_type), "cases")


def derive(df: pd.DataFrame, region: str, source_file: str, layer: str) -> pd.DataFrame:
    """Add region, source_file, layer, count_unit, year_basis, comparable_within; a column the file already has keeps its non-blank values."""
    d = df.copy()
    fy = d["financial_year"].astype(str).str.strip().ne("") if "financial_year" in d.columns else pd.Series(False, index=d.index)
    new = {
        "region": pd.Series(region, index=d.index),
        "source_file": pd.Series(source_file, index=d.index),
        "layer": pd.Series(layer, index=d.index),
        "count_unit": pd.Series([LAYER_COUNT_UNIT.get(layer) or count_unit_of(f, t) for f, t in zip(d["definition_flags"], d["indicator_type"])], index=d.index),
        "year_basis": pd.Series(np.where(fy, "financial year (year = start year)", "calendar year"), index=d.index),
    }
    for c, series in new.items():
        if c in d.columns:
            have = d[c].astype(str).str.strip()
            d[c] = np.where(have.ne("") & have.ne("<NA>") & have.ne("nan"), d[c].astype(str), series.astype(str))
        else:
            d[c] = series
    cw = (d["layer"].astype(str) + ":" + d["count_unit"].astype(str) + ":" + d["admin_level"].astype(str) + ":" + np.where(d["year_basis"].astype(str).str.startswith("financial"), "fy", "cy"))
    if "comparable_within" in d.columns:
        have = d["comparable_within"].astype(str).str.strip()
        d["comparable_within"] = np.where(have.ne("") & have.ne("<NA>") & have.ne("nan"), d["comparable_within"].astype(str), cw)
    else:
        d["comparable_within"] = cw
    return d


def resolve_collisions(df: pd.DataFrame) -> pd.DataFrame:
    """Rows whose (country, parent_unit, unit, year) repeats a row of an EARLIER layer get their unit suffixed with ' [layer]'; a repeat inside one layer is a data error and stops the build."""
    d = df.copy()
    if not d.duplicated(F.KEY).any():
        return d
    inside = d[d.duplicated(F.KEY + ["layer"], keep=False)]
    if len(inside):
        sys.exit(f"[stop] the same unit and year appears twice inside one layer: {inside[F.KEY + ['layer']].head(3).values.tolist()}")
    first_layer = {}
    for _, r in d[F.KEY + ["layer"]].iterrows():
        first_layer.setdefault(tuple(r[F.KEY]), r["layer"])
    rename = [i for i, r in d[F.KEY + ["layer"]].iterrows() if first_layer[tuple(r[F.KEY])] != r["layer"]]
    note = "unit renamed with its layer because another layer of the same country uses the same name and parent"
    for i in rename:
        d.at[i, "unit"] = f"{d.at[i, 'unit']} [{d.at[i, 'layer']}]"
        d.at[i, "data_notes"] = (str(d.at[i, "data_notes"]) + "; " + note).strip("; ")
    print(f"[collisions] {len(rename)} row(s) of {sorted(set(d.loc[rename, 'layer']))} share a unit name, parent and year with an earlier layer of the same country: their unit name now carries the layer in brackets")
    if d.duplicated(F.KEY).any():
        sys.exit("[stop] unit-name collisions remain after the layer suffix")
    return d


def build_panel(region: str, files: list, out: Path, label: str, expected=None) -> pd.DataFrame:
    """files: [Path of country CSVs, in priority order]; returns the panel and writes it to `out`."""
    frames = []
    for p in files:
        d = pd.read_csv(p, dtype=str, keep_default_na=False)
        miss = [c for c in F.CORE_COLUMNS if c not in d.columns]
        if miss:
            sys.exit(f"[stop] {p.name}: core column(s) {miss} are missing: the file does not follow the shared format")
        layer = re.sub(r"_homicide_rate$", "", p.stem).replace("_master_panel", "")
        if not p.name.endswith("_master_panel.csv"):                      # a country file may have a column of its own called region (Thailand's regions): it must not replace the continent
            for clash, keep in (("region", "country_region"), ("source_file", "source_file_local")):
                if clash in d.columns:
                    d = d.rename(columns={clash: keep})
                    print(f"[note] {p.name}: its own column '{clash}' is kept as '{keep}'")
        d = typed(d, p.name)
        d = derive(d, region, p.name, layer)
        frames.append(d)
        yrs = pd.to_numeric(d["year"], errors="coerce")
        print(f"[file] {p.name:46} {len(d):7,} rows, {d['country'].nunique():3d} countr{'y' if d['country'].nunique() == 1 else 'ies'}, {d[['country', 'parent_unit', 'unit']].drop_duplicates().shape[0]:5d} units, years {int(yrs.min())}-{int(yrs.max())}, tiers {d['reliability_tier'].value_counts().to_dict()}")
    if not frames:
        sys.exit(f"[stop] no country file was found for {label}")
    df = pd.concat(frames, ignore_index=True, sort=False)
    for c in df.columns:
        if c in F.CORE_COLUMNS or c in ADDED:
            continue
        df[c] = pd.Series([_plain(v) for v in df[c].astype(object)], index=df.index, dtype=object)
    df = resolve_collisions(df)
    df = F.finalize(df)
    F.require_valid(df, label)
    first = [c for c in ADDED if c in df.columns]
    df = df[[c for c in df.columns if c not in ADDED] + first]
    out.parent.mkdir(parents=True, exist_ok=True)
    F.write_csv(df, out)
    yrs = pd.to_numeric(df["year"], errors="coerce")
    print(f"\n[ok] wrote {out}\n     {len(df):,} rows | {df['country'].nunique()} countries | {df[['country', 'parent_unit', 'unit']].drop_duplicates().shape[0]:,} units | years {int(yrs.min())}-{int(yrs.max())} | tiers {df['reliability_tier'].value_counts().to_dict()}")
    if expected:
        got = {re.sub(r"_homicide_rate$", "", p.stem) for p in files}
        print(f"     layers missing from the panel (expected but no CSV yet): {sorted(set(expected) - got) or 'none'}")
    return df


def main(script_file: str, region: str, expected: list, include=None, exclude=()):
    """Entry point of a continental script: its country CSVs are the *_homicide_rate.csv files of its own folder (or the files named in `include`), minus `exclude`."""
    ap = argparse.ArgumentParser(description=f"{region} master panel")
    ap.add_argument("--out", help="output path (default: <repo>/Data/Output/<region>_master_panel.csv)")
    a = ap.parse_args()
    here = Path(script_file).resolve().parent
    if here.parent.name != "Pipelines":
        sys.exit(f"[stop] this script must live in <repo>/Pipelines/<Region>/ (it is in {here})")
    root = here.parents[1]
    out = Path(a.out) if a.out else root / "Data" / "Output" / f"{region.lower()}_master_panel.csv"
    if include:
        files = [here / n for n in include if (here / n).exists()]
    else:
        files = sorted(p for p in here.glob("*_homicide_rate.csv") if p.name not in set(exclude))
    other = sorted(p.name for p in here.glob("*_homicide_rate.csv") if p not in files)
    print(f"[master_panel.py revision {REVISION}] {region}: {len(files)} country file(s) in {here}" + (f"; not included (their rows are inside another file): {other}" if other else ""))
    build_panel(region, files, out, f"{region.lower()}_master_panel", expected)


def main_global(script_file: str):
    ap = argparse.ArgumentParser(description="world master panel")
    ap.add_argument("--out")
    a = ap.parse_args()
    root = Path(script_file).resolve().parent.parent
    folder = root / "Data" / "Output"
    names = ["africa", "americas", "asia", "europe", "oceania"]
    files = [folder / f"{n}_master_panel.csv" for n in names if (folder / f"{n}_master_panel.csv").exists()]
    print(f"[master_panel.py revision {REVISION}] world: continental panels found: {[p.name for p in files]}; missing: {[n for n in names if not (folder / (n + '_master_panel.csv')).exists()]}")
    out = Path(a.out) if a.out else folder / "global_master_panel.csv"
    build_panel("World", files, out, "global_master_panel")