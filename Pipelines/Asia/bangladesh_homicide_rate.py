#!/usr/bin/env python3
"""
Bangladesh - police-recorded murder cases per 100,000 residents, 8 metropolitan police units matched to their cities.

NUMERATOR   (official): Bangladesh Bureau of Statistics (BBS), Statistical Yearbook of Bangladesh, chapter "Health, Family
            Planning and Social Statistics", table "Number of Crimes by Type as Registered with the Police" (source line of
            the yearbook: Police Head Quarter), column "Total No. of Murder", for the metropolitan police units (DMP, CMP,
            KMP, RMP, BMP, SMP, RPMP, GMP). Years in the available yearbooks: 2010, 2011, 2013, 2014, 2017, 2025.
DENOMINATOR (official): BBS Population and Housing Census 2022, Urban Area Report: the population of the city corporation(s)
            matching each police unit, and the census reference date, both READ from the report by this script.
MATCHING    DMP -> Dhaka North + Dhaka South; CMP -> Chattogram; KMP -> Khulna; RMP -> Rajshahi; BMP -> Barishal;
            SMP -> Sylhet; RPMP -> Rangpur; GMP -> Gazipur. A police unit's jurisdiction is not necessarily the city
            corporation's boundary: this is an approximation and is stated in every row's data_notes.
METHOD      The only city-level census is 2022, so a rate is produced only for crime years within MAX_YEARS (3.5) of the
            census date (in practice 2025), using the census count as it is (no growth assumption: the rate is therefore
            somewhat high). Earlier years get no rate. If a 2011 city source is ever configured in CENSUS, cities whose
            derived area is unchanged (within 5%) are interpolated geometrically. The police ranges (multi-district
            regions, not cities) are not used.
CHECKS      Every yearbook table: the unit rows add up exactly to the TOTAL row; for 2010/2011 also non-political +
            political + riot = total murder in every unit; the table page carries the header "Total No. of Murder"
            (the last column is taken as that column, which only the 2010/2011 identity proves, so the header is reported
            in `validation` only when found). Census: Total = Male + Female (+ Hijra) in every city-corporation row used;
            the reference date comes from the report text. The text in `validation` is built from these results.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Bangladesh/ ; the one output is
            bangladesh_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python bangladesh_homicide_rate.py inspect   (the murder tables and the census rows exactly as read; no file written)
            python bangladesh_homicide_rate.py build     (writes the CSV)
Options:    --refresh   download the PDFs again instead of reusing the saved copies
Needs:      pip install pandas requests pymupdf
"""
from __future__ import annotations
import argparse
import datetime as dt
import re
import sys
from pathlib import Path

import pandas as pd

try:
    import pymupdf
except ImportError:
    sys.exit("[stop] this script needs PyMuPDF:  python -m pip install pymupdf")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 6:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "Bangladesh")      # raw downloads -> Data/Raw/<Region>/Bangladesh/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)")      # the BBS file host is addressed with this User-Agent
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

O = "https://objectstorage.ap-dcc-gazipur-1.oraclecloud15.com/n/axvjbnqprylg/b/V2Ministry/o/office-bbs"
PDFS = {   # key: (url, years whose table is in this PDF) - each year is confirmed by the year printed in the table's own title
    "yearbook_2025": (f"{O}/2026/7/49661c30-24aa-4c70-b22f-c5600836eacc.pdf", [2025]),
    "yearbook_2017": (f"{O}/2024/12/519cf2b793f142d98c7ee3f698acb27f.pdf", [2017]),
    "yearbook_2013_14": (f"{O}/2024/12/ffb37c608146492ca4bd2127f2efb3eb.pdf", [2014, 2013]),
    "yearbook_2010_11": (f"{O}/2024/12/0ff53120d3264978936a3006952d3e36.pdf", [2011, 2010]),
}
CENSUS = {
    2022: {"url": f"{O}/2024/12/fe6eeb0c1f364676877a4a7ef77989cc.pdf",
           "doc": "BBS Population and Housing Census 2022: Urban Area Report"},
    2011: {"url": None, "doc": "BBS Population and Housing Census 2011: Urban Area Report"},  # not available
}
METROS = {"DMP", "CMP", "KMP", "RMP", "BMP", "SMP", "RPMP", "GMP"}
CITY = {"DMP": "Dhaka", "CMP": "Chattogram", "KMP": "Khulna", "RMP": "Rajshahi",
        "BMP": "Barishal", "SMP": "Sylhet", "RPMP": "Rangpur", "GMP": "Gazipur"}
UNIT_COMPONENTS = {   # police unit -> city-corporation row labels per census year
    "DMP": {2022: ["DHAKA NORTH", "DHAKA SOUTH"], 2011: ["DHAKA"]},
    "CMP": {2022: ["CHATTOGRAM"], 2011: ["CHATTOGRAM"]}, "KMP": {2022: ["KHULNA"], 2011: ["KHULNA"]},
    "RMP": {2022: ["RAJSHAHI"], 2011: ["RAJSHAHI"]}, "BMP": {2022: ["BARISHAL"], 2011: ["BARISHAL"]},
    "SMP": {2022: ["SYLHET"], 2011: ["SYLHET"]}, "RPMP": {2022: ["RANGPUR"], 2011: ["RANGPUR"]},
    "GMP": {2022: ["GAZIPUR"], 2011: ["GAZIPUR"]},
}
ALIASES = {"CHITTAGONG": "CHATTOGRAM", "CHATTOGAM": "CHATTOGRAM", "CHATTAGONG": "CHATTOGRAM", "BARISAL": "BARISHAL"}
KNOWN_RANGES = {"DHAKA", "MYMENSINGH", "CHATTOGRAM", "SYLHET", "KHULNA", "BARISHAL", "RAJSHAHI", "RANGPUR", "RAILWAY"}
MAX_YEARS = F.MAX_DENOMINATOR_AGE   # no rate further than this from a census date (one threshold for every pipeline)
AREA_TOLERANCE = 0.05    # DECISION (only used if two censuses are configured)
MONTHS = "January|February|March|April|May|June|July|August|September|October|November|December"
NUM = re.compile(r"\d[\d,]*")
REFRESH = False


# ---------- download ----------
def fetch_pdf(url: str, name: str) -> bytes:
    data = FETCH.get(url, name, reuse=not REFRESH, suffix=".pdf", reject_html=True)
    if not data[:5].startswith(b"%PDF"):
        raise RuntimeError(f"{name}: the download is not a PDF ({url})")
    return data


# ---------- yearbook murder tables ----------
def candidate_pages(doc, years):
    found = {}
    for i, page in enumerate(doc):
        text = page.get_text()
        if not re.search(r"Crimes\s+by\s+Type\s+as\s+Registered", text, re.I):
            continue
        if "DMP" not in text or "TOTAL" not in text.upper():
            continue
        m = re.search(r"with\s+the\s+Police,?\s*(\d{4})", text, re.I)
        if m and int(m.group(1)) in years:
            found.setdefault(int(m.group(1)), []).append(i)
    missing = [y for y in years if y not in found]
    if missing:
        sys.exit(f"Table for {missing} not found in the PDF.")
    return found


def page_lines(page, tol=3.0):
    words = sorted(page.get_text("words"), key=lambda w: (w[1] + w[3]) / 2)
    lines, cur, cur_y = [], [], None
    for w in words:
        yc = (w[1] + w[3]) / 2
        if cur_y is None or abs(yc - cur_y) <= tol:
            cur.append(w)
            cur_y = yc if cur_y is None else (cur_y + yc) / 2
        else:
            lines.append(sorted(cur, key=lambda x: x[0]))
            cur, cur_y = [w], yc
    if cur:
        lines.append(sorted(cur, key=lambda x: x[0]))
    return [[w[4] for w in ln] for ln in lines]


def unit_key(label):
    k = re.sub(r"\s*RANGE$", "", re.sub(r"\s+", " ", label.upper()).strip()).strip()
    return ALIASES.get(k, k)


def parse_page(page, year):
    """-> (units, total, checks). Raises (SystemExit) if the unit rows do not add up to the TOTAL row."""
    rows, raw_lines = {}, []
    for toks in page_lines(page):
        label_toks = []
        for t in toks:
            if NUM.fullmatch(t):
                break
            label_toks.append(t)
        nums = [int(t.replace(",", "")) for t in toks[len(label_toks):] if NUM.fullmatch(t)]
        label = " ".join(label_toks).strip()
        if not label or len(nums) < 10:
            continue
        key = unit_key(label)
        kind = "total" if key == "TOTAL" else "metro" if key in METROS else "range"
        if kind == "range" and key not in KNOWN_RANGES:
            print(f"[warn] {year}: unrecognised unit '{label}' -> '{key}'")
        if key in rows:
            sys.exit(f"{year}: unit '{key}' appears twice on the page.")
        rows[key] = {"kind": kind, "murders": nums[-1], "tail": nums[-4:]}
        raw_lines.append((label, nums))
    if "TOTAL" not in rows:
        sys.exit(f"{year}: TOTAL row not found; parsed units: {list(rows)}")
    units = {k: v for k, v in rows.items() if k != "TOTAL"}
    total, ssum = rows["TOTAL"]["murders"], sum(v["murders"] for v in units.values())
    if ssum != total:
        for lab, nums in raw_lines:
            print(f"   {lab:26s} {nums}")
        sys.exit(f"{year}: sum of units {ssum} != TOTAL {total}. Extraction misread a row (lines above).")
    checks = [f"{year} yearbook table: the {len(units)} police units add up exactly to the TOTAL row ({total:,})"]
    text = page.get_text()
    if "riot" in text.lower():                   # 2010/2011: Non-political + Political + Riot = Total
        for k, v in units.items():
            a, b, c, t = v["tail"]
            if a + b + c != t:
                sys.exit(f"{year}: {k}: components {a}+{b}+{c} != total murder {t}")
        checks.append(f"non-political + political + riot = total murder in all {len(units)} units (this identifies the last column)")
    if re.search(r"Total\s+No\.?\s+of\s+Murder", text, re.I):
        checks.append("the table page carries the column header 'Total No. of Murder'")
    else:
        print(f"[warn] {year}: the header 'Total No. of Murder' was not found in the page text - the last column is assumed to be it")
    return units, total, checks


def extract_all():
    """({year: {unit: (kind, murders)}}, {year: pdf url}, {year: [checks]}). Every table must reconcile to its TOTAL row."""
    out, src, chk = {}, {}, {}
    for key, (url, years) in PDFS.items():
        doc = pymupdf.open(stream=fetch_pdf(url, f"bbs_{key}"), filetype="pdf")
        cands = candidate_pages(doc, years)
        for y in sorted(cands):
            err = None
            for idx in cands[y]:          # a table can continue on a 2nd page: first page that reconciles
                try:
                    units, total, checks = parse_page(doc[idx], y)
                    print(f"[parse] {y}: PDF page {idx + 1}, {len(units)} units, total {total} (units sum to TOTAL)")
                    out[y] = {k: (v["kind"], v["murders"]) for k, v in units.items()}
                    src[y], chk[y] = url, checks
                    break
                except SystemExit as e:
                    err = e
            else:
                sys.exit(err)
    return out, src, chk


# ---------- census report ----------
def cc_key(label):
    s = re.sub(r"[().,]", " ", label.upper())
    s = re.sub(r"\b(CITY CORPORATION|CITY CORP|CC)\b", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return ALIASES.get(s, s)


def find_block(nums):
    """(Total, density, all numbers) for the (Total, Male, Female[, Hijra]) block: Total == Male+Female(+Hijra)."""
    for k in range(min(len(nums) - 2, 6)):
        t = nums[k]
        if t < 50_000:
            continue
        if k + 3 < len(nums) and t == nums[k + 1] + nums[k + 2] + nums[k + 3]:
            return t, (nums[k + 4] if k + 4 < len(nums) else None), nums
        if t == nums[k + 1] + nums[k + 2]:
            return t, (nums[k + 3] if k + 3 < len(nums) else None), nums
    return None


def census_rows(doc, year):
    wanted = {c for comps in UNIT_COMPONENTS.values() for c in comps[year]}
    best = (0, None, {})
    for i, page in enumerate(doc):
        rows = {}
        for toks in page_lines(page):
            label_toks = []
            for t in toks:
                if NUM.fullmatch(t):
                    break
                label_toks.append(t)
            nums = [int(t.replace(",", "")) for t in toks[len(label_toks):] if NUM.fullmatch(t)]
            key = cc_key(" ".join(label_toks))
            if key in wanted and nums:
                blk = find_block(nums)
                if blk:
                    rows[key] = blk
        if len(rows) > best[0]:
            best = (len(rows), i, rows)
    return best


def census_date(doc, year):
    """Reference date from the report text (stated census night, else midpoint of a stated enumeration period)."""
    cands = []
    rng = re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s*(?:-|–|—|to)\s*(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS}),?\s+{year}", re.I)
    one = re.compile(rf"(\d{{1,2}})(?:st|nd|rd|th)?\s+({MONTHS}),?\s+{year}", re.I)
    month_no = {m.lower(): i + 1 for i, m in enumerate(MONTHS.split("|"))}
    for pi in range(min(len(doc), 150)):
        flat = re.sub(r"\s+", " ", doc[pi].get_text())
        for sent in re.split(r"(?<=[.;])\s+", flat):
            if str(year) not in sent:
                continue
            low, r, o = sent.lower(), rng.search(sent), one.findall(sent)
            if re.search(r"census night|reference (night|date|time)|midnight", low) and len(o) == 1 and not r:
                cands.append((1, pi, dt.date(year, month_no[o[0][1].lower()], int(o[0][0])), "stated census night", sent))
            elif r and re.search(r"enumerat|conducted|census|count", low):
                d1, d2, m = int(r.group(1)), int(r.group(2)), month_no[r.group(3).lower()]
                cands.append((2, pi, dt.date(year, m, (d1 + d2) // 2), "midpoint of stated enumeration period", sent))
    if not cands:
        print(f"[warn] census {year}: no reference date in the report text; using 1 July {year} (flagged).")
        return dt.date(year, 7, 1), "year label only (1 July convention)", "", 0
    cands.sort(key=lambda c: (c[0], c[1]))
    _, pi, d, rule, sent = cands[0]
    return d, rule, sent[:220], pi + 1


def read_census(year):
    url = CENSUS[year]["url"]
    if not url:
        return None
    doc = pymupdf.open(stream=fetch_pdf(url, f"bbs_census{year}"), filetype="pdf")
    n, idx, rows = census_rows(doc, year)
    if idx is None or n < 3:
        sys.exit(f"Census {year}: could not find the city-corporation table (best page had {n} valid rows).")
    d, rule, sent, dpage = census_date(doc, year)
    units = {}
    for unit, comps in UNIT_COMPONENTS.items():
        names = comps[year]
        if all(c in rows for c in names):
            dens = [rows[c][1] for c in names]
            units[unit] = {"pop": sum(rows[c][0] for c in names),
                           "area": sum(rows[c][0] / dv for c, dv in zip(names, dens)) if all(dens) else None,
                           "rows": {c: rows[c][2] for c in names}}
    header = [" ".join(t) for t in page_lines(doc[idx])[:6]]
    print(f"[census {year}] table on PDF page {idx + 1}; reference date {d} ({rule}{f', p{dpage}' if dpage else ''})")
    return {"units": units, "date": d, "rule": rule, "sent": sent, "page": idx + 1, "header": header,
            "doc": CENSUS[year]["doc"], "url": url,
            "check": f"census {year} table (PDF page {idx + 1}): Total = Male + Female (+ Hijra) in every one of the {sum(len(c[year]) for c in UNIT_COMPONENTS.values())} "
                     f"city-corporation rows used"}


def build_anchors():
    cens = {y: read_census(y) for y in CENSUS}
    if cens[2022] is None:
        sys.exit("Census 2022 URL missing.")
    missing = [u for u in UNIT_COMPONENTS if u not in cens[2022]["units"]]
    if missing:
        sys.exit(f"Census 2022: city corporations not found for units {missing}.")
    return {u: {y: {"pop": c["units"][u]["pop"], "area": c["units"][u]["area"], "date": c["date"],
                    "doc": c["doc"], "page": c["page"], "rule": c["rule"], "url": c["url"], "check": c["check"]}
                for y, c in cens.items() if c and u in c["units"]} for u in UNIT_COMPONENTS}


def estimate(anchors, year):
    """Population at 1 July of `year`. Returns (pop or None, method, census years used, distance in years)."""
    t = dt.date(year, 7, 1)
    pts = sorted(anchors.items(), key=lambda kv: kv[1]["date"])
    if (len(pts) == 2 and all(v["area"] for _, v in pts)
            and abs(pts[1][1]["area"] / pts[0][1]["area"] - 1) <= AREA_TOLERANCE):
        (y0, a0), (y1, a1) = pts
        dist = 0.0 if a0["date"] <= t <= a1["date"] else min(abs((t - a0["date"]).days), abs((t - a1["date"]).days)) / 365.25
        if dist > MAX_YEARS:
            return None, "no_census_within_range", f"{y0}&{y1}", dist
        return (a0["pop"] * (a1["pop"] / a0["pop"]) ** ((t - a0["date"]).days / (a1["date"] - a0["date"]).days),
                "interpolated" if dist == 0 else "extrapolated", f"{y0}&{y1}", dist)
    y, a = min(pts, key=lambda kv: abs((t - kv[1]["date"]).days))
    dist = abs((t - a["date"]).days) / 365.25
    if dist > MAX_YEARS:
        return None, "no_census_within_range", str(y), dist
    return a["pop"], "census_count_used_as_is", str(y), dist


# ---------- commands ----------
def cmd_inspect():
    data, _, chk = extract_all()
    df = pd.DataFrame({y: {k: v[1] for k, v in u.items()} for y, u in data.items()}).sort_index(axis=1)
    kinds = {k: v[0] for u in data.values() for k, v in u.items()}
    df.insert(0, "kind", df.index.map(kinds))
    print("\nMurder cases by police unit:")
    print(df.sort_values(["kind", df.columns[1]], ascending=[True, False]).fillna("").to_string())
    print("\nWhat was verified for each year's table:")
    for y in sorted(chk):
        for c in chk[y]:
            print(f"  {y}: {c}")
    print("\n===== CENSUS 2022 AS READ =====")
    c = read_census(2022)
    print("  table header lines:", *[f"\n     {h}" for h in c["header"]])
    print(f"  date sentence: {c['sent']}")
    for u, v in c["units"].items():
        print(f"  {u:5s} pop {v['pop']:>10,}  area {v['area'] and round(v['area'], 1)} km2   numbers in row: {v['rows']}")
    print("\n[inspect only] no CSV written")


def cmd_build():
    anchors = build_anchors()
    data, src, chk = extract_all()
    rows = []
    for y, units in sorted(data.items()):
        for unit, (kind, murders) in units.items():
            if kind != "metro":
                continue
            pop, method, used, dist = estimate(anchors[unit], y)
            if pop is None:
                continue
            pop = round(pop)                                   # whole persons; the rate below uses exactly this figure
            a = anchors[unit][int(used.split("&")[0])]
            comps = " + ".join(c.title() for c in UNIT_COMPONENTS[unit][int(used.split("&")[0])])
            rows.append({
                "country": "Bangladesh", "unit": CITY[unit], "unit_local": "", "unit_code": "", "admin_level": "city",
                "unit_type": "metropolitan_police_unit", "parent_unit": "", "year": y, "homicide_cases": murders,
                "population": pop, "homicide_rate_per_100k": murders / pop * 1e5, "flag_low_count": murders < LOW_COUNT,
                "flag_outlier_year": False, "indicator_type": "police_recorded_cases", "reliability_tier": "B",
                "definition_flags": "",
                "validation": "; ".join(chk[y] + [a["check"], f"census reference date taken from the report text ({a['rule']})"]),
                "indicator": f"BBS Statistical Yearbook, 'Number of Crimes by Type as Registered with the Police' (source: Police Head Quarter), "
                             f"column 'Total No. of Murder', police unit {unit}",
                "population_method": f"{method}: BBS Population and Housing Census {used} count of the city corporation(s) {comps} "
                                     f"(reference date {a['date'].isoformat()}), used as is, {dist:.1f} years from the crime year, no growth adjustment",
                "data_notes": f"police unit {unit} is matched to the city corporation(s) {comps}; the police jurisdiction may not equal the city-corporation "
                              f"boundary; the census count is {dist:.1f} years old, so the rate is likely somewhat high",
                "source_homicide": src[y], "source_population": f"{a['url']} (PDF page {a['page']})",
                "retrieved": FETCH.retrieved_on(src[y], a["url"]),
                "police_unit": unit, "census_year": used, "census_reference_date": a["date"].isoformat(),
                "census_date_basis": a["rule"], "population_age_years": round(dist, 1),
            })
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("No city-year has a census count within range; nothing to write.")
    small = df[df["population"] < MIN_POP]
    if len(small):
        print(f"[filter] dropping {len(small)} rows under {MIN_POP:,} residents: {sorted(set(small.unit))}")
        df = df.drop(small.index)
    skipped = sorted({y for y in data} - set(df["year"]))
    df = F.add_outlier_flags(df)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "bangladesh")
    print(f"\n[skipped] no rate for years {skipped}: no city census count within {MAX_YEARS} years of those years.")
    print(df[["unit", "year", "homicide_cases", "population", "homicide_rate_per_100k", "population_age_years"]].round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df.unit.nunique()} cities)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()
    REFRESH = a.refresh
    cmd_inspect() if a.cmd == "inspect" else cmd_build()