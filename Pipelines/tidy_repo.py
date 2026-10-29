#!/usr/bin/env python3
"""
TIDY THE REPOSITORY - one command to leave the folder in its final shape. DRY-RUN BY DEFAULT: it prints what it would do and changes nothing; add --apply to do it.

WHAT IT DOES
  1. creates the folders that must exist: Data/Raw, Data/Output, Docs and Pipelines/<Region> for the five regions;
  2. writes .gitignore, requirements.txt and README.md at the repository root IF THEY ARE ABSENT (never overwrites; --refresh-docs overwrites them);
  3. deletes the __pycache__ folders (and stray .pyc files) under Pipelines only (Python rebuilds them); files whose name starts with a dot (.gitkeep) are never touched;
  4. MOVES (never deletes) to <repo>/_archive/<date-time>/<same relative path> every file that is not part of the final layout:
       - a .py file in Pipelines/<Region>/ that is not a known pipeline, master-panel or helper script of that region (the old Europe and Americas scripts, for example);
       - a file in Pipelines/<Region>/ that is not '<country>_homicide_rate.csv' (stray test CSVs and images);
       - a file in Data/Output that is not a master panel, the inventory or the refresh log (the old igarape_*.csv and .dta, for example);
     test_*.py files are kept where they are (they belong to the developer, not to the data);
  5. prints the resulting layout.
THE FINAL LAYOUT
  <repo>/
    README.md  LICENSE  CITATION.cff  CHANGELOG.md  requirements.txt  .gitignore  .gitattributes
    Pipelines/   homicide_format.py  FORMAT.md  master_panel.py  global_master_panel.py  project_inventory.py  tidy_repo.py  refresh_all.py  build_docs.py  docs_content.py  release_check.py
      Africa/ Americas/ Asia/ Europe/ Oceania/    <country>_homicide_rate.py + its ONE CSV, and <region>_master_panel.py
    Data/
      Raw/<Region>/<Country>/     dated downloads (re-creatable; ignored by git except the files you saved by hand, manual_*)
      Output/                     <region>_master_panel.csv x5, global_master_panel.csv, project_inventory.md / _by_country.csv
    Docs/                         DEFINITIONS.md / .html and definitions_matrix.csv (built by Pipelines/build_docs.py)
    _archive/                     what this script moved aside (ignored by git)

Usage       python tidy_repo.py            (dry run)         python tidy_repo.py --apply            python tidy_repo.py --apply --refresh-docs
"""
import argparse
import datetime as dt
import shutil
from pathlib import Path

REGIONS = ["Africa", "Americas", "Asia", "Europe", "Oceania"]
KNOWN = {
    "Africa": {"south_africa_homicide_rate.py", "nigeria_homicide_rate.py", "tanzania_homicide_rate.py", "lesotho_homicide_rate.py", "kenya_homicide_rate.py", "africa_probe.py", "africa_master_panel.py"},
    "Americas": {"igarape_homicide_rate.py", "americas_master_panel.py"},
    "Asia": {"china_homicide_rate.py", "japan_homicide_rate.py", "india_homicide_rate.py", "bangladesh_homicide_rate.py", "south_korea_homicide_rate.py", "malaysia_homicide_rate.py", "pakistan_homicide_rate.py",
             "singapore_homicide_rate.py", "taiwan_homicide_rate.py", "thailand_homicide_rate.py", "uzbekistan_homicide_rate.py", "asia_master_panel.py"},
    "Europe": {"eurostat_homicide_rate.py", "eurostat_cities_homicide_rate.py", "united_kingdom_homicide_rate.py", "europe_master_panel.py"},
    "Oceania": {"australia_homicide_rate.py", "australia_new_south_wales_homicide_rate.py", "australia_victoria_homicide_rate.py", "australia_queensland_homicide_rate.py", "australia_western_australia_homicide_rate.py",
                "abs_lga_population.py", "australia_all_homicide_rate.py", "oceania_master_panel.py"},
}
PIPELINES_ROOT_KEEP = {"homicide_format.py", "FORMAT.md", "master_panel.py", "global_master_panel.py", "project_inventory.py", "tidy_repo.py", "refresh_all.py", "build_docs.py", "docs_content.py", "release_check.py"}
ROOT_KEEP = {"README.md", "CITATION.cff", "CHANGELOG.md", "requirements.txt", ".gitignore", ".gitattributes", "Pipelines", "Data", "Docs", "_archive", "venv", ".venv", ".git", ".github"}
OUTPUT_KEEP_SUFFIX = ("_master_panel.csv",)
OUTPUT_KEEP = {"project_inventory.md", "project_inventory_by_country.csv", "refresh_log.txt"}

GITIGNORE = """# Python
__pycache__/
*.pyc
.venv/
venv/
.idea/
.vscode/

# operating system
.DS_Store
Thumbs.db
desktop.ini

# what tidy_repo.py moved aside, and the log of the last refresh
_archive/
Data/Output/refresh_log.txt

# raw downloads are re-created by the pipelines; keep only the files saved by hand (manual_*)
Data/Raw/**
!Data/Raw/**/
!Data/Raw/**/manual_*
"""

GITATTRIBUTES = """* text=auto
*.py text eol=lf
*.md text eol=lf
*.html text eol=lf
*.csv text eol=lf
*.cff text eol=lf
"""

REQUIREMENTS = """# python -m pip install -r requirements.txt   (Python 3.12, pandas 3.x)
pandas>=3.0
numpy
requests
beautifulsoup4
openpyxl
python-calamine
pdfplumber
pypdf
pymupdf
truststore
korean-romanizer
# optical character recognition, used only by Pipelines/Asia/china_homicide_rate.py
rapidocr-onnxruntime
"""

README = """# Global subnational homicide database

A harmonised panel of homicide counts and rates below the national level: about 29,000 observations for roughly 2,850 provinces, states, counties, districts, cities and police units in 78 countries,
1993-2025. One re-runnable pipeline per source extracts the figures from police, statistical-office and health-ministry publications (HTML, Excel, CSV, PDF, OCR, APIs) into a common schema, attaches a
population denominator and its age, validates against the source's national totals and independent series, and grades each row A, B or C. Every series carries its counting unit, definition flags and time
basis, and `Docs/DEFINITIONS.md` compares each source's definition of homicide with the UNODC standard. Built for the Development Data Lab.

Author: Yannick Feussi ([@afrohead07](https://github.com/afrohead07)).

## What is in it
- `Data/Output/global_master_panel.csv`: the rows of every country in one file; `Data/Output/<region>_master_panel.csv`: one file per continent; `Data/Output/project_inventory.md`: the number of countries, units, rows and years.
- `Pipelines/<Region>/<country>_homicide_rate.csv`: the output of each country script, in the common format described in `Pipelines/FORMAT.md`.
- `Docs/DEFINITIONS.md` (also `DEFINITIONS.html` and `definitions_matrix.csv`): what each source counts as homicide, compared with the UNODC definition, with the source of every statement.

## How to read a row
- `homicide_cases` is what the source counts: victims, offences or cases (`count_unit` in the panels, `definition_flags` in every file); `population` and its age (`population_age_years`) come from the source's own
  denominator or an official estimate or census, named in `population_method`.
- `reliability_tier`: A = reconciled, independently confirmed and a recent denominator (age of 3.5 years or less); B = a documented weakness; C = a failed hard check or a proxy. The reason is in `validation`.
- `year` is the calendar year unless `year_basis` says financial year (then it is the start year).
- `homicide_rate_per_100k` is `homicide_cases` / `population` x 100,000. Rates are comparable only within one `comparable_within` key. Rows of different admin levels are never added (a state and its districts are the same people). A victim count, a case count and a proxy are not
  compared without reading the notes in `Docs/DEFINITIONS.md`. Counts below 10 carry `flag_low_count`; a year far outside the unit's own series carries `flag_outlier_year`; the Kenya and South Africa files add `flag_population_break` where the denominator changes basis.

## Layout
- `Pipelines/<Region>/<country>_homicide_rate.py`: one script per country or source layer. `inspect` shows what a source contains; `build` downloads it into `Data/Raw/<Region>/<Country>/` (dated), reconciles it and
  writes one CSV next to the script.
- `Pipelines/homicide_format.py`: the shared output format and its validator; every CSV is validated before it is written.
- `Pipelines/<Region>/<region>_master_panel.py` and `Pipelines/global_master_panel.py`: stack the country CSVs into the panels. `Pipelines/project_inventory.py` counts them.
- `Pipelines/refresh_all.py`: rebuilds everything in order. `Pipelines/build_docs.py` writes `Docs/`. `Pipelines/tidy_repo.py` and `Pipelines/release_check.py` keep and check the folder.

## Running
```
python -m pip install -r requirements.txt
cd Pipelines
python refresh_all.py                    # every country script, then the panels, the inventory and the documentation (a source is downloaded when no saved copy exists; --fresh downloads every source again)
python Africa/kenya_homicide_rate.py build        # one country
python Africa/africa_master_panel.py              # one regional panel
python global_master_panel.py                     # the world panel
python release_check.py                           # the checks to run before publishing
```

The first run downloads each source into `Data/Raw/<Region>/<Country>/` (dated files, which are not part of the repository); a full run takes about half an hour once the downloads are saved, and longer the first time. When a site refuses automated downloads or changes its page, the script says which file to save by hand (named `manual_*`). The Lesotho script reads its census table from `Data/Raw/Africa/Lesotho/manual_census2016.pdf`, which is part of the repository. Tested with Python 3.12.

## Limits of the data
- Police-recorded series reflect reporting and recording, not only violence; health-registry series reflect cause-of-death certification (South Africa's registry covers about a third of police-recorded murders).
- Several denominators are old or projected (Nigeria: a projection of the 2006 census; Lesotho: the 2016 census; Kenya: the 2009 census up to 2017 and the 2019 census from 2021).
- The countries of the Americas are covered through the Igarape Institute's Homicide Monitor, a compilation in which every row cites its official source (`igarape_source_1`, `igarape_source_2`); those rows are never tier A, and a unit whose population series breaks (a change above 25% in one year) is tier C throughout.
- Coverage is uneven across regions and years; `Data/Output/project_inventory.md` lists the units and years of every country.
- Sources that publish no sub-national homicide figures were examined and not used: Tunisia, Mozambique, Sierra Leone, Zimbabwe, Uganda, Botswana.
- South Australia and New Zealand are not covered.

## Licence and citation
Code: MIT (`LICENSE`). Data and documentation: Creative Commons Attribution 4.0 (`LICENSE-DATA.md`). How to cite the database: `CITATION.cff`. The figures come from the official sources named in every row
(`source_homicide`, `source_population`); the terms of those sources apply to their content.
"""


def plan(root: Path, refresh_docs: bool):
    acts = []                                    # (kind, path, detail)
    for d in (root / "Data" / "Raw", root / "Data" / "Output", root / "Docs", *[root / "Pipelines" / r for r in REGIONS]):
        if not d.exists():
            acts.append(("mkdir", d, ""))
    for name, text in ((".gitignore", GITIGNORE), (".gitattributes", GITATTRIBUTES), ("requirements.txt", REQUIREMENTS), ("README.md", README)):
        p = root / name
        if not p.exists() or refresh_docs:
            acts.append(("write", p, text))
    pr0 = root / "Pipelines"
    if pr0.exists():
        for pc in sorted(d for d in pr0.rglob("__pycache__") if d.is_dir()):
            acts.append(("delete", pc, "cache"))
        for pc in sorted(f for f in pr0.rglob("*.pyc") if f.parent.name != "__pycache__"):
            acts.append(("delete", pc, "cache"))
    # the repository root: known items only (a licence file may be called LICENSE, LICENSE.md, LICENSE-DATA.md ...)
    for f in sorted(root.iterdir()):
        canon = {n.lower(): n for n in ROOT_KEEP}.get(f.name.lower())
        if canon and f.name != canon:
            acts.append(("rename", f, canon))                                  # Windows ignores the case of a name, GitHub does not
            continue
        if f.name.startswith(".") or f.name in ROOT_KEEP or f.name.upper().startswith("LICENSE"):
            continue
        acts.append(("archive", f, "not part of the final repository root"))
    # Pipelines root: known files and the five region folders only
    pr = root / "Pipelines"
    if pr.exists():
        for f in sorted(pr.iterdir()):
            if f.name.startswith("."):
                continue
            if f.is_dir() and f.name not in REGIONS and f.name != "__pycache__":
                acts.append(("archive", f, "a folder that is not a region (old proof of concept or scratch)"))
                continue
            canon = {n.lower(): n for n in PIPELINES_ROOT_KEEP}.get(f.name.lower())
            if f.is_file() and canon and f.name != canon:
                acts.append(("rename", f, canon))
                continue
            if f.is_file() and f.name not in PIPELINES_ROOT_KEEP and not f.name.startswith("test_") and f.suffix in (".py", ".csv", ".dta", ".md", ".txt", ".json"):
                acts.append(("archive", f, "not part of the final Pipelines folder"))
    for r in REGIONS:
        d = pr / r
        if not d.exists():
            continue
        for f in sorted(d.iterdir()):
            if f.is_dir() or f.name.startswith("."):
                continue
            if f.suffix == ".py":
                if f.name not in KNOWN[r] and not f.name.startswith("test_"):
                    acts.append(("archive", f, f"a .py file that is not a known {r} script"))
            elif f.name.endswith("_homicide_rate.csv"):
                continue
            elif f.suffix == ".pyc":
                continue
            else:
                acts.append(("archive", f, "not a '<country>_homicide_rate.csv' (stray output, test file or image)"))
    out = root / "Data" / "Output"
    if out.exists():
        for f in sorted(out.iterdir()):
            if f.is_file() and not f.name.startswith(".") and not (f.name.endswith(OUTPUT_KEEP_SUFFIX) or f.name in OUTPUT_KEEP):
                acts.append(("archive", f, "not a master panel, the inventory or the refresh log (old output)"))
    return acts


def apply(root: Path, acts: list):
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    arch = root / "_archive" / stamp
    for kind, p, detail in acts:
        if kind == "mkdir":
            p.mkdir(parents=True, exist_ok=True)
        elif kind == "write":
            p.write_text(detail, encoding="utf-8")
        elif kind == "delete":
            if p.is_dir():
                shutil.rmtree(p, ignore_errors=True)
            elif p.exists():
                p.unlink()
        elif kind == "rename":
            tmp = p.with_name(p.name + ".renaming")                           # two steps, because a rename that changes only the case fails on Windows
            p.rename(tmp)
            tmp.rename(p.with_name(detail))
        elif kind == "archive":
            dest = arch / p.relative_to(root)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(p), str(dest))
    return arch


def layout(root: Path):
    print("\nLayout:")
    for r in REGIONS:
        d = root / "Pipelines" / r
        if d.exists():
            py = [f.name for f in d.glob("*.py") if not f.name.startswith("test_")]
            csv = [f.name for f in d.glob("*_homicide_rate.csv")]
            print(f"  Pipelines/{r:9} {len(py):2d} scripts, {len(csv):2d} country CSV(s)")
    out = root / "Data" / "Output"
    if out.exists():
        print(f"  Data/Output     {len([f for f in out.iterdir() if f.is_file()])} file(s): {sorted(f.name for f in out.iterdir() if f.is_file())}")
    raw = root / "Data" / "Raw"
    if raw.exists():
        print(f"  Data/Raw        {sum(1 for _ in raw.rglob('*') if _.is_file()):,} downloaded file(s) in {len([d for d in raw.glob('*/*') if d.is_dir()])} country folder(s)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="do it (default: only print the plan)")
    ap.add_argument("--refresh-docs", action="store_true", help="overwrite .gitignore, .gitattributes, requirements.txt and README.md")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    acts = plan(root, a.refresh_docs)
    print(f"[tidy_repo.py] repository: {root}")
    counts = {}
    for kind, p, detail in acts:
        counts[kind] = counts.get(kind, 0) + 1
        if kind != "delete":
            print(f"  {kind.upper():8} {p.relative_to(root)}" + (f"   ({detail})" if kind == "archive" else f" -> {detail}" if kind == "rename" else ""))
    dels = [p for k, p, _ in acts if k == "delete"]
    if dels:
        print(f"  DELETE   {len(dels)} __pycache__ folder(s) / stray .pyc file(s) under Pipelines, for example: " + "; ".join(str(p.relative_to(root)) for p in dels[:3]))
    if not acts:
        print("  nothing to do: the folder is already in its final shape")
    if a.apply:
        arch = apply(root, acts)
        print(f"\n[done] {len(acts)} action(s) applied" + (f"; moved-aside files are in {arch}" if counts.get("archive") else ""))
        layout(root)
    else:
        print(f"\n[dry run] {len(acts)} action(s) planned ({counts}); nothing was changed. Run again with --apply.")
        layout(root)


if __name__ == "__main__":
    main()