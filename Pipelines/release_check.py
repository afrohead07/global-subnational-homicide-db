#!/usr/bin/env python3
"""
RELEASE CHECK - run this before publishing the repository.

WHAT IT CHECKS  (each line of the report is OK, WARN or FAIL; the exit code is 1 if there is any FAIL)
  structure   the files and folders a published repository needs (README, LICENSE, CITATION.cff, CHANGELOG, requirements, .gitignore, .gitattributes, FORMAT.md, Docs, the panels);
  tidy        nothing that tidy_repo.py would still archive (scratch folders, old outputs, one-off helpers);
  git rules   .gitignore keeps the environment, caches, archives and raw downloads out (only the files saved by hand, manual_*, stay in);
  scripts     every country script has its one CSV and every CSV its script;
  format      every country CSV passes `homicide_format.py check`;
  panels      the five continental panels add up to the global panel, are not older than the country CSVs, carry a tier on every row, no ISO-code column, no negative counts or ages;
  docs        Docs/ exists, is not older than the panels, and `build_docs.py --strict` (written to a temporary folder) finds no disagreement between the text and the data and no forbidden phrase;
  hygiene     no local path (a Windows user folder, /home/..., /Users/...), key or password in any text file that will be published;
  size        no file above 50 MB (GitHub refuses 100 MB), a warning above 25 MB;
  git         if the folder is a git repository: uncommitted changes and whether the ignore rules really work;
  release     LICENSE and CITATION.cff are filled in, and the README refers to them.

Usage       python release_check.py             (from Pipelines/ or anywhere)         Options:  --skip-docs (do not run build_docs.py)   --skip-format (do not run the format validator)
Needs       pip install pandas
"""
import argparse
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pandas as pd

PIPE = Path(__file__).resolve().parent
ROOT = PIPE.parent
REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
SKIP_DIRS = {"__pycache__", "venv", ".venv", ".git", "_archive", "node_modules"}
TEXT_EXT = {".py", ".md", ".html", ".csv", ".txt", ".cff", ".json", ".yml", ".yaml", ".toml", ".cfg"}
MB = 1024 * 1024
REPORT = []


def add(level, area, text):
    REPORT.append((level, area, text))


def ok(area, text):
    add("OK", area, text)


def warn(area, text):
    add("WARN", area, text)


def fail(area, text):
    add("FAIL", area, text)


def published_files():
    """Every file that is not inside an ignored folder and not a raw download (Data/Raw keeps only manual_* files)."""
    raw = ROOT / "Data" / "Raw"
    for p in ROOT.rglob("*"):
        if not p.is_file() or any(part in SKIP_DIRS for part in p.relative_to(ROOT).parts):
            continue
        if raw in p.parents and not p.name.startswith("manual_"):
            continue
        yield p


def run(cmd, timeout=900):
    r = subprocess.run(cmd, cwd=PIPE, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
    return r.returncode, (r.stdout or "") + (r.stderr or "")


# ------------------------------------------------------------------------------------------------------------------------------------------------------------ checks
def exists_exact(rel: str) -> bool:
    """True if the path exists with exactly this spelling (Windows finds Format.md for FORMAT.md; GitHub does not)."""
    cur = ROOT
    for part in rel.split("/"):
        if not cur.is_dir() or part not in {c.name for c in cur.iterdir()}:
            return False
        cur = cur / part
    return True


def check_structure():
    need = ["README.md", "LICENSE-DATA.md", "CITATION.cff", "CHANGELOG.md", "requirements.txt", ".gitignore", ".gitattributes", "Pipelines/FORMAT.md", "Pipelines/homicide_format.py",
            "Docs/DEFINITIONS.md", "Docs/DEFINITIONS.html", "Docs/definitions_matrix.csv", "Data/Output/global_master_panel.csv", "Data/Output/project_inventory.md"]
    need += [f"Data/Output/{r.lower()}_master_panel.csv" for r in REGIONS]
    missing = [n + (" (found with other capitals: rename it)" if (ROOT / n).exists() else "") for n in need if not exists_exact(n)]
    if not any(p.name.upper().startswith("LICENSE") for p in ROOT.iterdir() if p.is_file()):
        missing.append("LICENSE")
    (fail if missing else ok)("structure", ("missing: " + ", ".join(missing)) if missing else f"all {len(need) + 1} required files are present")
    gone = [r for r in REGIONS if not (PIPE / r).is_dir()]
    (fail if gone else ok)("structure", ("missing region folders: " + ", ".join(gone)) if gone else "the five region folders are present")


def check_tidy():
    try:
        sys.path.insert(0, str(PIPE))
        from tidy_repo import plan
    except Exception as e:                                                    # pragma: no cover
        warn("tidy", f"tidy_repo.py could not be imported ({e})")
        return
    acts = [a for a in plan(ROOT, False) if a[0] == "archive"]
    if acts:
        for _, p, why in acts:
            warn("tidy", f"{p.relative_to(ROOT)}: {why}")
        warn("tidy", "run `python tidy_repo.py --apply` to archive these items")
    else:
        ok("tidy", "nothing to archive: the folders are in their final shape")


def check_gitignore():
    p = ROOT / ".gitignore"
    if not p.exists():
        fail("git rules", ".gitignore is missing")
        return
    txt = p.read_text(encoding="utf-8", errors="replace")
    need = {"venv/": "the virtual environment", "__pycache__/": "Python caches", "_archive/": "archived files", "Data/Raw/**": "raw downloads", "!Data/Raw/**/manual_*": "the files saved by hand"}
    lack = [f"{k} ({v})" for k, v in need.items() if k not in txt]
    (fail if lack else ok)("git rules", ("the .gitignore lacks: " + "; ".join(lack)) if lack else ".gitignore keeps out the environment, caches, archives and raw downloads, and keeps the manual_* files")


def check_scripts_and_csv():
    miss, orphan, n = [], [], 0
    for r in REGIONS:
        d = PIPE / r
        if not d.is_dir():
            continue
        scripts = {f.stem for f in d.glob("*_homicide_rate.py")}
        csvs = {f.stem for f in d.glob("*_homicide_rate.csv")}
        n += len(csvs)
        miss += [f"{r}/{s}.py has no CSV" for s in sorted(scripts - csvs)]
        orphan += [f"{r}/{c}.csv has no script" for c in sorted(csvs - scripts)]
    (warn if miss else ok)("scripts", "; ".join(miss) if miss else f"every country script has its CSV ({n} CSV files)")
    if orphan:
        warn("scripts", "; ".join(orphan))


def check_format(skip):
    files = sorted(str(f) for r in REGIONS for f in (PIPE / r).glob("*_homicide_rate.csv"))
    if skip:
        warn("format", "skipped (--skip-format)")
        return
    if not files:
        fail("format", "no country CSV found")
        return
    rc, out = run([sys.executable, "homicide_format.py", "check", *files])
    bad = [ln for ln in out.splitlines() if "FAIL" in ln.upper() or "ERROR" in ln.upper()]
    if rc == 0 and not bad:
        ok("format", f"all {len(files)} country CSV files pass homicide_format.py check")
    else:
        fail("format", f"homicide_format.py check reported problems (exit {rc}): " + " | ".join(bad[:5] or out.strip().splitlines()[-3:]))


def check_panels():
    out = ROOT / "Data" / "Output"
    g = out / "global_master_panel.csv"
    if not g.exists():
        fail("panels", "global_master_panel.csv is missing")
        return
    gdf = pd.read_csv(g, dtype=str, keep_default_na=False)
    regional = {r: out / f"{r.lower()}_master_panel.csv" for r in REGIONS}
    tot = 0
    for r, p in regional.items():
        if p.exists():
            tot += len(pd.read_csv(p, dtype=str, keep_default_na=False, usecols=[0]))
    (ok if tot == len(gdf) else fail)("panels", f"the five continental panels hold {tot:,} rows, the global panel {len(gdf):,}")
    newest_csv = max((f.stat().st_mtime for r in REGIONS for f in (PIPE / r).glob("*_homicide_rate.csv")), default=0)
    (ok if g.stat().st_mtime >= newest_csv else warn)("panels", "the global panel is newer than every country CSV" if g.stat().st_mtime >= newest_csv else "a country CSV is newer than the global panel: run `python refresh_all.py --masters-only`")
    iso = [c for c in gdf.columns if re.search(r"(^|_)iso(_|\d|$)", c, re.I)]
    (fail if iso else ok)("panels", ("columns that look like ISO codes: " + ", ".join(iso)) if iso else "no ISO-code column (countries are keyed by name)")
    tier = gdf["reliability_tier"] if "reliability_tier" in gdf.columns else pd.Series([""] * len(gdf))
    badtier = int((~tier.isin(["A", "B", "C"])).sum())
    (fail if badtier else ok)("panels", f"{badtier:,} rows without a reliability tier A, B or C" if badtier else f"every row carries a reliability tier ({tier.value_counts().to_dict()})")
    for col, what in (("homicide_cases", "negative counts"), ("population", "non-positive populations"), ("population_age_years", "negative population ages")):
        if col in gdf.columns:
            v = pd.to_numeric(gdf[col], errors="coerce")
            n = int((v < 0).sum()) if col != "population" else int((v <= 0).sum())
            (fail if n else ok)("panels", f"{n:,} rows with {what}" if n else f"no rows with {what}")
    ctry = gdf["country"].nunique() if "country" in gdf.columns else 0
    ok("panels", f"{len(gdf):,} rows, {ctry} countries, years {gdf['year'].min()}-{gdf['year'].max()}")


def check_docs(skip):
    d = ROOT / "Docs"
    g = ROOT / "Data" / "Output" / "global_master_panel.csv"
    if (d / "DEFINITIONS.md").exists() and g.exists():
        (ok if (d / "DEFINITIONS.md").stat().st_mtime >= g.stat().st_mtime else warn)("docs", "Docs/ is newer than the global panel" if (d / "DEFINITIONS.md").stat().st_mtime >= g.stat().st_mtime
                                                                                  else "Docs/ is older than the global panel: run `python build_docs.py`")
    if skip:
        warn("docs", "build_docs.py skipped (--skip-docs)")
        return
    with tempfile.TemporaryDirectory() as tmp:                                  # the check never rewrites Docs/
        rc, out = run([sys.executable, "build_docs.py", "--strict", "--out", tmp])
    lines = [ln.strip() for ln in out.splitlines() if ln.strip().startswith("- ")]
    (ok if rc == 0 else fail)("docs", "build_docs.py --strict: the text and the data agree and no forbidden phrase was found" if rc == 0 else "build_docs.py --strict reports: " + " | ".join(lines[:6] or out.strip().splitlines()[-3:]))


def check_hygiene():
    path_pat = re.compile(r"[A-Za-z]:\\+Users\\+|(?<![\w.])/(?:home|Users)/[A-Za-z0-9_.-]+/")
    secret_pat = re.compile(r"AKIA[0-9A-Z]{16}|-----BEGIN [A-Z ]*PRIVATE KEY-----|(?i:api[_-]?key|secret|passw(?:or)?d|token)\s*[:=]\s*['\"][A-Za-z0-9_\-]{12,}['\"]")
    hits, secrets, scanned = [], [], 0
    for p in published_files():
        if p.suffix.lower() not in TEXT_EXT or p.stat().st_size > 80 * MB:
            continue
        scanned += 1
        txt = p.read_text(encoding="utf-8", errors="ignore")
        m = path_pat.search(txt)
        if m:
            hits.append(f"{p.relative_to(ROOT)}: {m.group(0)}")
        if p.suffix.lower() != ".csv":
            s = secret_pat.search(txt)
            if s:
                secrets.append(f"{p.relative_to(ROOT)}: {s.group(0)[:30]}...")
    (warn if hits else ok)("hygiene", ("local paths in: " + "; ".join(hits[:6])) if hits else f"no local path in {scanned} published text files")
    (fail if secrets else ok)("hygiene", ("possible keys or passwords in: " + "; ".join(secrets[:6])) if secrets else "no key or password pattern in the published text files")


def check_size():
    big, mid, total = [], [], 0
    for p in published_files():
        s = p.stat().st_size
        total += s
        if s > 50 * MB:
            big.append(f"{p.relative_to(ROOT)} ({s / MB:.0f} MB)")
        elif s > 25 * MB:
            mid.append(f"{p.relative_to(ROOT)} ({s / MB:.0f} MB)")
    (fail if big else ok)("size", ("above 50 MB: " + "; ".join(big)) if big else f"no file above 50 MB (published files: {total / MB:.0f} MB in total)")
    if mid:
        warn("size", "above 25 MB: " + "; ".join(mid))


def check_git():
    if not shutil.which("git") or not (ROOT / ".git").exists():
        warn("git", "the folder is not a git repository yet (git init) or git is not installed")
        return
    rc, st = run(["git", "-C", str(ROOT), "status", "--porcelain"])
    n = len([ln for ln in st.splitlines() if ln.strip()])
    ok("git", "no uncommitted change") if n == 0 else warn("git", f"{n} uncommitted change(s)")
    for rel, expect in (("Data/Raw/Africa/Kenya/x.csv", True), ("Data/Raw/Africa/Kenya/manual_x.csv", False), ("venv/x.py", True), ("_archive/x.py", True), ("Pipelines/Africa/kenya_homicide_rate.csv", False)):
        rc, _ = run(["git", "-C", str(ROOT), "check-ignore", "-q", rel])
        ignored = rc == 0
        (ok if ignored == expect else fail)("git", f"{rel} is {'ignored' if ignored else 'tracked'} as intended" if ignored == expect else f"{rel} is {'ignored' if ignored else 'not ignored'}, expected the opposite")


def check_release_files():
    lic = next((p for p in ROOT.iterdir() if p.is_file() and p.name.upper().startswith("LICENSE")), None)
    if lic is None or lic.stat().st_size < 200:
        fail("release", "LICENSE is missing or empty")
    else:
        ok("release", f"{lic.name} present ({lic.stat().st_size:,} bytes)")
    cff = ROOT / "CITATION.cff"
    if cff.exists():
        t = cff.read_text(encoding="utf-8", errors="replace")
        miss = [k for k in ("cff-version:", "title:", "authors:") if k not in t]
        (fail if miss else ok)("release", ("CITATION.cff lacks " + ", ".join(miss)) if miss else "CITATION.cff has version, title and authors")
        if re.search(r"TODO|TBD|XXX|<[^>]+>|your name|example\.com", t, re.I):
            fail("release", "CITATION.cff still contains a placeholder")
    rd = ROOT / "README.md"
    if rd.exists():
        t = rd.read_text(encoding="utf-8", errors="replace")
        (ok if ("LICENSE" in t and "CITATION" in t) else warn)("release", "the README refers to LICENSE and CITATION.cff" if ("LICENSE" in t and "CITATION" in t) else "the README does not refer to LICENSE and CITATION.cff")
        bad = re.search(r"TODO|TBD|coming soon|to be added|work in progress|planned|not yet", t, re.I)
        (fail if bad else ok)("release", f"the README contains '{bad.group(0)}'" if bad else "the README has no to-do wording")
    for name in ("Pipelines/FORMAT.md", "CHANGELOG.md"):
        p = ROOT / name
        if p.exists():
            bad = re.search(r"TODO|TBD|coming soon|to be added|work in progress|planned|not yet", p.read_text(encoding="utf-8", errors="replace"), re.I)
            (fail if bad else ok)("release", f"{name} contains '{bad.group(0)}'" if bad else f"{name} has no to-do wording")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-docs", action="store_true")
    ap.add_argument("--skip-format", action="store_true")
    a = ap.parse_args()
    print(f"[release_check.py] repository: {ROOT}\n")
    for fn, args in ((check_structure, ()), (check_tidy, ()), (check_gitignore, ()), (check_scripts_and_csv, ()), (check_format, (a.skip_format,)), (check_panels, ()), (check_docs, (a.skip_docs,)),
                     (check_hygiene, ()), (check_size, ()), (check_git, ()), (check_release_files, ())):
        try:
            fn(*args)
        except Exception as e:
            fail(fn.__name__.replace("check_", ""), f"the check itself stopped: {type(e).__name__}: {e}")
    area = ""
    for level, ar, text in REPORT:
        if ar != area:
            print(f"-- {ar}")
            area = ar
        print(f"   {level:4}  {text}")
    n = {k: sum(1 for r in REPORT if r[0] == k) for k in ("OK", "WARN", "FAIL")}
    print(f"\n[summary] {n['OK']} OK, {n['WARN']} WARN, {n['FAIL']} FAIL" + ("  ->  not ready to publish" if n["FAIL"] else "  ->  no blocking problem" if not n["WARN"] else "  ->  no blocking problem; read the warnings"))
    sys.exit(1 if n["FAIL"] else 0)


if __name__ == "__main__":
    main()