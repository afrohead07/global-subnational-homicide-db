#!/usr/bin/env python3
"""
REFRESH EVERYTHING - one command that rebuilds the database in the right order:
    1. every country script of every region:   python <script> build [--reuse]      (each in its own folder, one after the other)
    2. every regional master panel             (Data/Output/<region>_master_panel.csv)
    3. the world panel                         (Data/Output/global_master_panel.csv)
    4. the inventory                           (Data/Output/project_inventory.md)
    5. the documentation                       (Docs/DEFINITIONS.md and .html)
A script that fails is REPORTED and the run goes on (its previous CSV, if any, stays in the panel); a summary and a log (Data/Output/refresh_log.txt) are written at the end.

Which scripts are run is the table PLAN below (edit it if a script is added or uses another command). Scripts that only inspect (Mexico, South Australia, New Zealand while their sources are blocked) are
listed as INSPECT_ONLY and are skipped by default (--include-inspect-only runs their build, which stops with its message).

DOWNLOADS  By default every script USES THE DOWNLOADS ALREADY SAVED. --fresh downloads again. The scripts have two generations of options, and the right one is chosen by reading each script:
            a script with a --reuse option (Africa, Oceania, Americas) gets --reuse unless --fresh is given; a script with a --refresh option (Japan, India, Bangladesh) gets --refresh only with --fresh;
            a script with neither (China, Eurostat, the UK ...) is simply run with `build`.

Usage       python refresh_all.py [--fresh] [--region Africa] [--only kenya,lesotho] [--masters-only] [--dry-run] [--timeout 1800]
            --fresh          download again (default: use the downloads already saved); --reuse is still accepted and means the default
            --region NAME    one region only (Africa, Americas, Asia, Europe, Oceania)
            --only a,b       only the scripts whose file name contains one of these words
            --masters-only   skip the country scripts and rebuild only the panels and the inventory
            --dry-run        print the plan and run nothing
"""
import argparse
import datetime as dt
import os
import subprocess
import sys
import time
from pathlib import Path

PLAN = {
    "Africa": ["south_africa", "nigeria", "tanzania", "lesotho", "kenya"],
    "Asia": ["china", "japan", "india", "bangladesh", "south_korea", "malaysia", "pakistan", "singapore", "taiwan", "thailand", "uzbekistan"],
    "Europe": ["eurostat", "eurostat_cities", "united_kingdom"],
    "Americas": ["igarape"],
    "Oceania": ["australia", "australia_new_south_wales", "australia_victoria", "australia_queensland", "australia_western_australia", "australia_all"],
}
INSPECT_ONLY = {"Americas": ["mexico"], "Oceania": ["australia_south_australia", "new_zealand"]}
ORDER = ["Africa", "Americas", "Asia", "Europe", "Oceania"]


def build_command(py: str, script: Path, fresh: bool):
    """`python <script> build` plus the one download option that THIS script understands (read from its own source)."""
    try:
        txt = script.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        txt = ""
    cmd = [py, script.name, "build"]
    if '"--reuse"' in txt:
        if not fresh:
            cmd.append("--reuse")
    elif '"--refresh"' in txt and fresh:
        cmd.append("--refresh")
    return cmd


def run(cmd, cwd: Path, timeout: int):
    t0 = time.time()
    try:
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}              # a captured child would print in cp1252 on Windows and fail on Japanese, Korean or Latvian letters
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace", env=env)
        tail = [ln for ln in (r.stdout + r.stderr).splitlines() if ln.strip()][-3:]
        return r.returncode, time.time() - t0, tail
    except subprocess.TimeoutExpired:
        return -9, time.time() - t0, [f"timed out after {timeout} s"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fresh", action="store_true", help="download again instead of using the saved downloads")
    ap.add_argument("--reuse", action="store_true", help="accepted for compatibility: using the saved downloads is the default")
    ap.add_argument("--region")
    ap.add_argument("--only", default="")
    ap.add_argument("--masters-only", action="store_true")
    ap.add_argument("--include-inspect-only", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--timeout", type=int, default=1800)
    a = ap.parse_args()
    here = Path(__file__).resolve().parent
    py = sys.executable
    regions = [r for r in ORDER if (not a.region or r.lower() == a.region.lower())]
    if a.region and not regions:
        sys.exit(f"[stop] unknown region {a.region!r}; choose from {ORDER}")
    only = [w.strip() for w in a.only.split(",") if w.strip()]
    steps = []
    if not a.masters_only:
        for r in regions:
            names = list(PLAN.get(r, [])) + (list(INSPECT_ONLY.get(r, [])) if a.include_inspect_only else [])
            for n in names:
                script = here / r / f"{n}_homicide_rate.py"
                if only and not any(w in script.name for w in only):
                    continue
                steps.append((f"{r}/{script.name}", build_command(py, script, a.fresh), script.parent, script.exists()))
    for r in regions:
        steps.append((f"{r}/{r.lower()}_master_panel.py", [py, f"{r.lower()}_master_panel.py"], here / r, (here / r / f"{r.lower()}_master_panel.py").exists()))
    if not a.region:
        steps.append(("global_master_panel.py", [py, "global_master_panel.py"], here, (here / "global_master_panel.py").exists()))
        steps.append(("project_inventory.py", [py, "project_inventory.py"], here, (here / "project_inventory.py").exists()))
        steps.append(("build_docs.py", [py, "build_docs.py"], here, (here / "build_docs.py").exists()))
    print(f"[refresh_all.py] {len(steps)} step(s)" + (" (dry run)" if a.dry_run else ""))
    results = []
    for label, cmd, cwd, exists in steps:
        if a.dry_run:
            print(f"  would run in {cwd.name}: {' '.join(Path(c).name if i == 0 else c for i, c in enumerate(cmd))}" + ("" if exists else "   [script not found: would be skipped]"))
            continue
        if not exists:
            results.append((label, "missing", 0.0, ["the script is not in the folder"]))
            print(f"  [missing] {label}")
            continue
        print(f"  [run] {label} ...", flush=True)
        rc, secs, tail = run(cmd, cwd, a.timeout)
        results.append((label, "ok" if rc == 0 else f"FAILED (exit {rc})", secs, tail))
        print(f"        {'ok' if rc == 0 else 'FAILED'} in {secs:.0f} s" + ("" if rc == 0 else f": {tail[-1][:150] if tail else ''}"))
    if a.dry_run:
        return
    lines = [f"refresh_all.py {dt.datetime.now():%Y-%m-%d %H:%M}  fresh_downloads={a.fresh}", ""]
    for label, status, secs, tail in results:
        lines.append(f"{status:16} {secs:7.0f} s  {label}")
        if status != "ok":
            lines.extend("      " + t for t in tail)
    out = here.parent / "Data" / "Output"
    out.mkdir(parents=True, exist_ok=True)
    (out / "refresh_log.txt").write_text("\n".join(lines), encoding="utf-8")
    bad = [r for r in results if r[1] != "ok"]
    print(f"\n[summary] {len(results) - len(bad)} of {len(results)} step(s) ok" + (f"; NOT ok: {', '.join(r[0] for r in bad)}" if bad else "") + f"; log: {out / 'refresh_log.txt'}")


if __name__ == "__main__":
    main()