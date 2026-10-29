#!/usr/bin/env python3
"""
Australia - ALL LAYERS in one file: states and territories, and the sub-state layers of New South Wales, Victoria, Queensland and Western Australia.

WHAT THIS IS  A combiner, not a scraper. Each layer keeps its own script, its own source and its own definition (one script, one source, one CSV, so that a change at one host breaks only that
            layer). This script reads the CSVs of the layers, adds four columns that say what each row IS, validates the union with the shared format and writes ONE file.
LAYERS      states            ABS Recorded Crime - Victims: VICTIMS of murder + manslaughter, 8 states and territories, calendar years from 1993; cross-checked with health deaths
            new_south_wales   BOCSAR: VICTIMS of murder + manslaughter (BOCSAR counts these two offences by victim), LGAs of 100,000+ residents, calendar years from 2001
            victoria          Crime Statistics Agency: OFFENCES of 'A10 Homicide and related offences' (broader than murder + manslaughter; counts of 3 or less are masked to 2), LGAs, from 2016
            queensland        Queensland Police: OFFENCES of murder + manslaughter, LGAs of 100,000+ residents, calendar years from 2001
            western_australia WA Police: OFFENCES of murder + manslaughter, Police Districts of 100,000+ residents, FINANCIAL years (start year) 2020-2025 with gaps
ADDED COLUMNS layer, count_unit (victims / incidents / offences), year_basis (calendar year / financial year starting July), comparable_within (a key: rates are comparable ONLY between rows that
            share it and the year basis).
RULES FOR USE  1. Never compare or pool rates across layers: the units and definitions differ (Victoria's LGA rates are about three times the state's murder + manslaughter rate by definition).
            2. Never add rows across levels: a state and its LGAs describe the same people (admin1 against admin2 / police_unit).
            3. `year` is the calendar year, except in the western_australia layer where it is the START year of the financial year.
            4. The reliability_tier of each row is the one given by its own layer.
SOURCE      the rows keep their own source_homicide and source_population; this file adds no data of its own.

Folders:    this script sits in <repo>/Pipelines/Oceania/ next to the layer scripts and their CSVs; the one output is australia_all_homicide_rate.csv next to it.
Commands:   python australia_all_homicide_rate.py build [--refresh] [--reuse]
            --refresh  runs the build of every layer first (each in turn; a layer that fails is reported and its previous CSV, if any, is used); --reuse is passed to them (use the saved downloads)
Needs:      pip install pandas
"""
import argparse
import subprocess
import sys

from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format and folder layout shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 13:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

HERE = Path(__file__).resolve().parent
P = F.paths(__file__, "Australia All")
OUT = HERE / "australia_all_homicide_rate.csv"
# layer, script, csv, count unit, year basis, the definition that makes rates comparable within the layer
LAYERS = [
    ("states", "australia_homicide_rate.py", "australia_homicide_rate.csv", "victims", "calendar year", "ABS victims of murder + manslaughter recorded by the police, states and territories"),
    ("new_south_wales", "australia_new_south_wales_homicide_rate.py", "australia_new_south_wales_homicide_rate.csv", "victims", "calendar year", "BOCSAR victims of murder + manslaughter, LGAs"),
    ("victoria", "australia_victoria_homicide_rate.py", "australia_victoria_homicide_rate.csv", "offences", "calendar year", "CSA offences of A10 Homicide and related offences (counts of 3 or less masked to 2), LGAs"),
    ("queensland", "australia_queensland_homicide_rate.py", "australia_queensland_homicide_rate.csv", "offences", "calendar year", "QPS reported offences of murder + manslaughter, LGAs"),
    ("western_australia", "australia_western_australia_homicide_rate.py", "australia_western_australia_homicide_rate.csv", "offences", "financial year starting July", "WA Police offences of murder + manslaughter, Police Districts"),
]
ADDED = ["layer", "count_unit", "year_basis", "comparable_within"]


def typed(df: pd.DataFrame) -> pd.DataFrame:
    """A layer CSV is read as text (so codes such as '10050' stay text); the extras that are plainly numbers or booleans get their type back, the core columns are typed by the shared finalize."""
    out = df.copy()
    for c in F.BOOL_COLS:
        if c in out.columns:
            out[c] = out[c].map({"True": True, "False": False})
            if out[c].isna().any():
                sys.exit(f"[stop] column {c}: a value that is neither True nor False")
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
        if num.notna().sum() == len(nonblank):                                   # every non-blank value is a number
            out[c] = num.astype("Int64") if (num.dropna() % 1 == 0).all() else num
    return out


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


def run_layer(script: str, reuse: bool) -> bool:
    cmd = [sys.executable, str(HERE / script), "build"] + (["--reuse"] if reuse else [])
    print(f"[refresh] {script} build{' --reuse' if reuse else ''} ...", flush=True)
    r = subprocess.run(cmd, cwd=str(HERE))
    ok = r.returncode == 0
    print(f"[refresh] {script}: {'done' if ok else f'FAILED (exit {r.returncode}); its previous CSV, if any, is used'}")
    return ok


def cmd_build(refresh: bool, reuse: bool):
    if refresh:
        for _, script, _, _, _, _ in LAYERS:
            if (HERE / script).exists():
                run_layer(script, reuse)
            else:
                print(f"[refresh] {script} is not in {HERE}: skipped")
    frames, missing = [], []
    for layer, _, csv, unit, basis, comp in LAYERS:
        p = HERE / csv
        if not p.exists():
            missing.append(layer)
            continue
        d = pd.read_csv(p, dtype=str, keep_default_na=False)
        if d.empty:
            missing.append(layer)
            continue
        miss = [c for c in F.CORE_COLUMNS if c not in d.columns]
        if miss:
            sys.exit(f"[stop] {csv}: core column(s) {miss} are missing: the layer does not follow the shared format")
        d = typed(d)
        d["layer"], d["count_unit"], d["year_basis"] = layer, unit, basis
        d["comparable_within"] = f"australia:{layer}:{unit}:{d['admin_level'].iloc[0] if d['admin_level'].nunique() == 1 else 'mixed'}"
        frames.append(d)
        print(f"[layer] {layer:18} {len(d):5,} rows, {d['unit'].nunique():3d} units, years {int(d['year'].astype(int).min())}-{int(d['year'].astype(int).max())}, "
              f"tiers {d['reliability_tier'].value_counts().to_dict()}  ({csv})")
    if not frames:
        sys.exit("[stop] none of the layer CSVs was found next to this script: run the layer builds first (or use --refresh)")
    if missing:
        print(f"[note] layers not included (no CSV): {missing}")
    df = pd.concat(frames, ignore_index=True, sort=False)
    for c in F.CORE_COLUMNS:
        if c not in df.columns:
            sys.exit(f"[stop] core column {c} is missing from the union")
    # a layer-specific extra that other layers lack stays BLANK there. No nullable-integer column may reach the validator (its missing value can print as '<NA>' or 'nan' depending on the
    # pandas version): every extra becomes plain Python numbers, booleans or text, with None for a missing cell.
    for c in df.columns:
        if c in F.CORE_COLUMNS:
            continue
        df[c] = pd.Series([_plain(v) for v in df[c].astype(object)], index=df.index, dtype=object)
    df = F.finalize(df)
    F.require_valid(df, "australia")
    keep = [c for c in df.columns if c not in ADDED] + ADDED
    df = df[keep]
    levels = df.groupby(["layer", "admin_level"]).agg(rows=("unit", "size"), units=("unit", "nunique"), first=("year", "min"), last=("year", "max")).reset_index()
    print("\n" + levels.to_string(index=False))
    print(f"\nReliability tiers (each row keeps its own layer's tier): {df.reliability_tier.value_counts().to_dict()}")
    print("Remember: rates are comparable only inside one `comparable_within` (and one year basis); never add rows across admin levels.")
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df):,} rows, {df['layer'].nunique()} layers, {df['unit'].nunique()} units, years {int(df.year.min())}-{int(df.year.max())})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build"])
    ap.add_argument("--refresh", action="store_true", help="run the build of every layer first")
    ap.add_argument("--reuse", action="store_true", help="with --refresh: pass --reuse to the layer builds")
    a = ap.parse_args()
    cmd_build(a.refresh, a.reuse)