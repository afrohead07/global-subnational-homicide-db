#!/usr/bin/env python3
"""
Taiwan - police-recorded homicide cases per 100,000 residents, by city / county (22 first-level units).

NUMERATOR   (official): Statistical Yearbook of the Republic of China (DGBAS), one PDF per edition. Table 31 "All kinds of illegal cases
            and the number of offenders (continued)", Homicide (Cases) -> "Cases known to the police", by agency (= city / county police).
            Original source of the table: National Police Agency.
DENOMINATOR (official): the same yearbook, Table 3 "General situation of population" -> Total population (1,000 persons), by city / county.
            Original source: Ministry of the Interior. The end-of-year (31 December) reference is read from the page text; the figures are
            published rounded to thousands.
YEARS       Each edition gives the city / county breakdown for its own latest year (read from the table itself), so editions 2023, 2024 and
            2025 give the years 2023, 2024 and 2025. Self-renewing: add ONE line to YEARBOOKS (the new edition's URL); the data year is read
            from the PDF.
UNITS       The 22 cities / counties; the two tables use the same names, so they match exactly. "Affiliation with the NPA" (national police
            units, not tied to a city) has no population and is left out of the rates (its cases are reported). Units under 100,000
            residents are dropped (Lienchiang).
CHECKS      The run stops unless: the 22 agency rows + the NPA row add up to the national homicide figure of the year (Table 31); the 22
            populations add up to the national population within the table's rounding (Table 3); both tables refer to the same year. Each
            number's cells are read with a gap setting that is calibrated until these sums reconcile. In addition the national series of each
            edition's Table 31 (it prints several years) is compared with the other editions for the years they share. The
            homicide figure is taken by its POSITION in the row (the fifth number); the sums reconcile for any column, so the column is checked
            by GEOMETRY: the header word "Homicide" must lie over the third of the six column pairs. Tier A needs that check confirmed, the
            end-of-year wording, and a later edition printing the same national figure; a mismatch (or a different national figure in a later
            edition) makes the rows tier C; if the header word cannot be placed the rows stay tier B. The text in `validation` is built from these results.
DEFINITION  Homicide cases known to the police (National Police Agency): cases, not victims; attempts and manslaughter are not stated.

TLS         Government sites often serve incomplete certificate chains. Download tries (1) normal verification, (2) the operating-system
            certificate store (verification still ON). Verification is turned OFF only if you pass --insecure, which prints a warning; a
            file downloaded that way is accepted only if it passes the content checks above.

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Taiwan/ ; the one output is
            taiwan_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python taiwan_homicide_rate.py build | inspect (prints the parsed tables)
Options:    --refresh (download the PDFs again)   --insecure (last resort, see TLS)
Needs:      pip install pandas requests pymupdf          (recommended: truststore)
"""
import argparse
import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 10:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")
try:
    import pymupdf
except ImportError:
    sys.exit("[stop] this script needs PyMuPDF:  python -m pip install pymupdf")

P = F.paths(__file__, "Taiwan")          # raw downloads -> Data/Raw/<Region>/Taiwan/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP
UA = "Mozilla/5.0 (research pipeline)"

YEARBOOKS = {   # label -> URL. To renew: add the new edition here.
    "2025": "https://ws.dgbas.gov.tw/Download.ashx?u=LzAwMS9VcGxvYWQvNDY2L3JlbGZpbGUvMTE1MDMvMjM2NzI5L3llYXJib29rMjAyNS5wZGY%3d&n=WWVhcmJvb2syMDI1LnBkZg%3d%3d",
    "2024": "https://ws.dgbas.gov.tw/001/Upload/466/relfile/11503/235329/yearbook2024.pdf",
    "2023": "https://ws.dgbas.gov.tw/001/Upload/466/relfile/11503/233937/yearbook2023.pdf",
}
UNITS = ["New Taipei City", "Taipei City", "Taoyuan City", "Taichung City", "Tainan City", "Kaohsiung City",
         "Yilan County", "Hsinchu County", "Miaoli County", "Changhua County", "Nantou County", "Yunlin County",
         "Chiayi County", "Pingtung County", "Taitung County", "Hualien County", "Penghu County", "Keelung City",
         "Hsinchu City", "Chiayi City", "Kinmen County", "Lienchiang County"]
NPA = "Affiliation with the NPA"
CRIME_CELLS = 12        # Table 31: 6 column groups x 2 numbers
POP_CELLS = 11          # Table 3: Total, Male, Female, 0-14, 15-64, 65+, sex ratio, dependency, households, size, density
HOMICIDE_CELL = 4       # position of "Homicide, cases known to the police" among the 12 numbers (see LIMITATION above)
GAP_GRID = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 5.0, 6.0, 8.0]   # points; thousands-gap candidates
SPACES = "\u00a0\u2009\u202f\u2007\u2002\u2003"


def canon(s):
    return re.sub(r"[^a-z]", "", s.lower())


UNIT_BY_CANON = {canon(u): u for u in UNITS}


# ---------- download: verified, then the operating-system store, then (only on request) unverified ----------
def is_pdf(data: bytes) -> bool:
    try:
        if not data[:5].startswith(b"%PDF"):
            return False
        with pymupdf.open(stream=data, filetype="pdf") as d:
            return len(d) > 20
    except Exception:
        return False


_MODE = {"first": 0}      # the download mode that worked for the previous file is tried first for the next one


def download(label, url, refresh=False, insecure=False):
    """-> (PDF bytes, retrieval date, how). The raw copy is kept date-stamped in the raw folder."""
    attempts = [("verified", dict()), ("operating-system certificate store", dict(os_trust=True))]
    if insecure:
        attempts.append(("verification OFF", dict(os_trust=True, insecure=True)))
    attempts = attempts[_MODE["first"]:] + attempts[:_MODE["first"]]
    last, net_err = None, None
    for how, kw in attempts:
        fetch = F.Fetcher(RAW, user_agent=UA, retries=3, **kw)
        try:
            data = fetch.get(url, f"dgbas_yearbook_{label}", reuse=not refresh, suffix=".pdf", reject_html=True)
        except requests.exceptions.SSLError as e:
            last = e
            print(f"[tls] {label}: '{how}' failed: {str(e)[:120]}")
            continue
        except requests.exceptions.RequestException as e:             # a connection broken mid-download, a timeout, ...
            last = net_err = e
            print(f"[net] {label}: '{how}' failed after retries: {str(e)[:120]}")
            continue
        except RuntimeError as e:
            sys.exit(f"[stop] {label}: download failed: {e}")
        if not is_pdf(data):
            sys.exit(f"[stop] {label}: the downloaded file is not a valid PDF (error page?)")
        if how == "verification OFF":
            print(f"[tls] WARNING {label}: downloaded with certificate verification OFF. It is used only because it passes the table checks below.")
        _MODE["first"] = [h for h, _ in [("verified", 0), ("operating-system certificate store", 0), ("verification OFF", 0)]].index(how)
        return data, fetch.retrieved_on(url), how
    sys.exit(f"[stop] {label}: could not download ({net_err or last}). Run again (the connection may have dropped), or open the URL in a browser, save the PDF in "
             f"{RAW} as dgbas_yearbook_{label}_<YYYYMMDD>.pdf; --insecure turns certificate checks off as a last resort.")


# ---------- generic row reader ----------
def page_lines(page, tol=3.0):
    """Lines of words (x0, x1, text), top to bottom."""
    words = sorted(page.get_text("words"), key=lambda w: (w[1] + w[3]) / 2)
    lines, cur, cy = [], [], None
    for w in words:
        yc = (w[1] + w[3]) / 2
        if cy is None or abs(yc - cy) <= tol:
            cur.append(w)
            cy = yc if cy is None else (cy + yc) / 2
        else:
            lines.append(sorted(cur, key=lambda x: x[0]))
            cur, cy = [w], yc
    if cur:
        lines.append(sorted(cur, key=lambda x: x[0]))
    return [[(w[0], w[2], w[4]) for w in ln] for ln in lines]


NUMERIC = re.compile(r"^(?:\d+(?:\.\d+)?|[-–—])$")


def read_row(line, gap, with_x=False):
    """-> (label, numbers). Numbers are cells; a space-grouped thousand ('38 528') is merged when the
    gap between the two words is below `gap` points. '-' (nil) is 0."""
    toks = []
    for x0, x1, txt in line:
        txt = txt.strip()
        if re.fullmatch(rf"\d{{1,3}}(?:[{SPACES}]\d{{3}})+(?:\.\d+)?", txt):
            txt = re.sub(f"[{SPACES}]", "", txt)
        toks.append([x0, x1, txt])
    i = 0
    label = []
    while i < len(toks) and not NUMERIC.match(toks[i][2]):
        label.append(toks[i][2])
        i += 1
    nums, cur, ctr = [], None, []
    for x0, x1, txt in toks[i:]:
        if not NUMERIC.match(txt):
            return (" ".join(label), None, []) if with_x else (" ".join(label), None)      # stray text inside the numeric part
        if (cur is not None and re.fullmatch(r"\d{1,3}(?:\d{3})*", cur[2])
                and re.fullmatch(r"\d{3}(?:\.\d+)?", txt) and x0 - cur[1] < gap):
            cur = [cur[0], x1, cur[2] + txt]                   # merge "38" + "528"
        else:
            if cur is not None:
                nums.append(cur[2])
                ctr.append((cur[0] + cur[1]) / 2)
            cur = [x0, x1, txt]
    if cur is not None:
        nums.append(cur[2])
        ctr.append((cur[0] + cur[1]) / 2)
    vals = [0.0 if n in "-–—" else float(n) for n in nums]
    return (" ".join(label), vals, ctr) if with_x else (" ".join(label), vals)


def classify(label):
    c = canon(label)
    if "npa" in c or c.startswith("affiliation"):      # the label wraps over two lines; either line may carry the numbers
        return NPA
    return UNIT_BY_CANON.get(c)


def is_year(v):
    return float(v).is_integer() and 1900 <= v <= 2100


# ---------- Table 31 (homicide) ----------
def parse_crime(page, gap):
    """-> (year, {unit: known cases}, npa_known, national_known, {year: national known}). Raises ValueError on any inconsistency."""
    years, units, npa, orphans = {}, {}, None, []
    for line in page_lines(page):
        label, vals = read_row(line, gap)
        if vals is None or not vals:
            continue
        if not label and len(vals) == CRIME_CELLS:
            orphans.append(vals)          # numbers with no label on their line (e.g. the 2-line "Affiliation with the NPA")
            continue
        if not label and is_year(vals[0]):
            if len(vals) != CRIME_CELLS + 1:
                raise ValueError(f"year row has {len(vals)} numbers")
            years[int(vals[0])] = vals[1 + HOMICIDE_CELL]      # homicide, cases known to the police
            continue
        key = classify(label)
        if key is None:
            continue
        if len(vals) != CRIME_CELLS:
            raise ValueError(f"{label!r} has {len(vals)} numbers (expected {CRIME_CELLS})")
        if key == NPA:
            npa = vals[HOMICIDE_CELL]
        else:
            units[key] = vals[HOMICIDE_CELL]
    if npa is None and len(orphans) == 1:
        npa = orphans[0][HOMICIDE_CELL]   # accepted only because the sum check below must then reconcile
    if not years or set(units) != set(UNITS) or npa is None:
        raise ValueError(f"incomplete: {len(years)} year rows, {len(units)} units, NPA {npa}, {len(orphans)} unlabelled 12-number rows")
    y = max(years)
    if sum(units.values()) + npa != years[y]:
        raise ValueError(f"agencies sum to {sum(units.values()) + npa} but national {y} is {years[y]}")
    return y, {u: int(v) for u, v in units.items()}, int(npa), int(years[y]), {k: int(v) for k, v in years.items()}


# ---------- Table 3 (population) ----------
def parse_population(page, gap):
    """-> (year, {unit: persons}, national persons). Total population is the first number (1,000 persons)."""
    if not re.search(r"1,000\s+Persons", page.get_text()):
        raise ValueError("unit '1,000 Persons' not found")
    years, units = {}, {}
    for line in page_lines(page):
        label, vals = read_row(line, gap)
        if vals is None or not vals:
            continue
        if not label and is_year(vals[0]):
            if len(vals) != POP_CELLS + 1:
                raise ValueError(f"year row has {len(vals)} numbers")
            years[int(vals[0])] = vals[1]
            continue
        key = classify(label)
        if key is None or key == NPA:
            continue
        if len(vals) != POP_CELLS:
            raise ValueError(f"{label!r} has {len(vals)} numbers (expected {POP_CELLS})")
        units[key] = vals[0]
    if not years or set(units) != set(UNITS):
        raise ValueError(f"incomplete: {len(years)} year rows, {len(units)} units")
    y = max(years)
    if abs(sum(units.values()) - years[y]) > 3:               # table is rounded to thousands
        raise ValueError(f"districts sum to {sum(units.values())} but national {y} is {years[y]}")
    return y, {u: int(v * 1000) for u, v in units.items()}, int(years[y] * 1000)


def alignment(page, gap):
    """Which of the 6 column pairs of Table 31 lies under the header word 'Homicide'?
    -> (nearest pair index, the pair the script reads, header x-centre, [pair x-centres]) or None if it cannot be told
    (word absent or appearing more than once, no unit row, or the word lying between two pairs)."""
    pairs = None
    for line in page_lines(page):
        label, vals, ctr = read_row(line, gap, with_x=True)
        if vals and len(vals) == CRIME_CELLS and classify(label) in UNITS:
            pairs = [(ctr[2 * g] + ctr[2 * g + 1]) / 2 for g in range(CRIME_CELLS // 2)]
            break
    heads = [(w[0] + w[2]) / 2 for w in page.get_text("words") if re.fullmatch(r"homicide", w[4].strip(), re.I)]
    if pairs is None or len(heads) != 1:
        return None
    hc = heads[0]
    nearest = min(range(len(pairs)), key=lambda g: abs(pairs[g] - hc))
    spacing = min(abs(a - b) for a, b in zip(pairs, pairs[1:]))
    if abs(pairs[nearest] - hc) > spacing / 2:
        return None
    return nearest, HOMICIDE_CELL // 2, hc, pairs


def locate(doc, must, regex):
    out = []
    for i, page in enumerate(doc):
        text = page.get_text()
        if re.search(regex, text, re.I) and all(m in text for m in must):
            out.append(i)
    return out


def parse_with_calibration(doc, pages, fn, what):
    errors = []
    for idx in pages:
        for gap in GAP_GRID:
            try:
                return idx, gap, fn(doc[idx], gap)
            except ValueError as e:
                errors.append(f"p{idx + 1} gap {gap}: {e}")
    sys.exit(f"[stop] {what}: no page/gap setting reconciled. Last errors:\n  " + "\n  ".join(errors[-6:]))


def read_yearbook(label, data, retrieved):
    doc = pymupdf.open(stream=data, filetype="pdf")
    cp = locate(doc, ["Homicide", "Automobile theft", "New Taipei City", "Lienchiang"], r"Table\s+31\.\s+All kinds of illegal cases")
    pp = locate(doc, ["New Taipei City", "Lienchiang", "1,000 Persons"], r"Table\s+3\.\s+General situation of population")
    if not cp or not pp:
        sys.exit(f"[stop] {label}: could not find Table 31 (homicide) or Table 3 (population) in the PDF (candidate pages: crime {cp}, population {pp}).")
    ci, cg, (cy, known, npa, nat_known, series) = parse_with_calibration(doc, cp, parse_crime, f"{label} Table 31")
    pi, pg, (py, pops, nat_pop) = parse_with_calibration(doc, pp, parse_population, f"{label} Table 3")
    if cy != py:
        sys.exit(f"[stop] {label}: homicide table is for {cy} but population table is for {py}.")
    endyear = bool(re.search(r"end\s+of\s+(the\s+)?year|year-?end|end-of-year|at\s+the\s+end\s+of", doc[pi].get_text(), re.I))
    al = alignment(doc[ci], cg)
    if al is None:
        print(f"[alignment] {label}: the header word 'Homicide' could not be placed over a column pair (absent, repeated, or between two pairs): "
              f"the column stays identified by position only")
        aligned = None
    else:
        aligned = al[0] == al[1]
        print(f"[alignment] {label}: the header word 'Homicide' (x = {al[2]:.0f}) lies over column pair {al[0] + 1} of {CRIME_CELLS // 2} "
              f"(pair centres {[round(c) for c in al[3]]}); the script reads pair {al[1] + 1}: {'CONFIRMED' if aligned else 'MISMATCH'}")
    print(f"[parse] {label}: year {cy} | Table 31 on PDF p{ci + 1}, Table 3 on PDF p{pi + 1} | "
          f"agencies sum to national {nat_known} | districts sum to national {nat_pop:,} | end-of-year wording on the page: {'yes' if endyear else 'NO'}")
    return {"aligned": aligned, "year": cy, "known": known, "npa": npa, "nat_known": nat_known, "series": series, "pop": pops, "nat_pop": nat_pop,
            "endyear": endyear, "retrieved": retrieved}


# ---------- commands ----------
def load_all(refresh, insecure):
    data = {}
    for label, url in YEARBOOKS.items():
        raw, got, how = download(label, url, refresh, insecure)
        d = read_yearbook(label, raw, got)
        d.update(url=url, label=label, how=how)
        if d["year"] in data:
            sys.exit(f"[stop] two yearbooks give year {d['year']}; remove one from YEARBOOKS.")
        data[d["year"]] = d
    return data


def continuity(data: dict) -> dict:
    """For each edition year: {other edition year: its printed national figure for this year} for the years the editions share."""
    out = {}
    for y, d in data.items():
        out[y] = {y2: d2["series"][y] for y2, d2 in data.items() if y2 != y and y in d2["series"]}
    return out


def cmd_build(args):
    data = load_all(args.refresh, args.insecure)
    cont = continuity(data)
    rows = []
    for y, d in sorted(data.items()):
        covered = sum(d["known"].values())
        print(f"[coverage] {y}: city/county police units hold {covered} of {d['nat_known']} national cases "
              f"({covered / d['nat_known']:.1%}); {d['npa']} sit with national police units (not a city).")
        same = [e for e, v in cont[y].items() if v == d["nat_known"]]
        diff = [(e, v) for e, v in cont[y].items() if v != d["nat_known"]]
        if diff:
            print(f"[continuity] {y}: the national figure {d['nat_known']} differs in other editions: {diff}")
        else:
            print(f"[continuity] {y}: the national figure is the same in the editions {sorted(same)}" if same else
                  f"[continuity] {y}: no other edition prints this year")
        cont_text = (f"the national figure of {y} is the same in the {', '.join(str(e) for e in sorted(same))} edition(s)" if same and not diff
                     else (f"the national figure of {y} DIFFERS in other editions ({', '.join(f'{e}: {v}' for e, v in diff)})" if diff
                           else f"no other edition prints the national figure of {y} yet"))
        al_text = ("the header word 'Homicide' lies over the 3rd of the 6 column pairs, the pair the figure is read from" if d["aligned"] is True
                   else "the header word 'Homicide' lies over a DIFFERENT column pair than the one read" if d["aligned"] is False
                   else "the homicide column is identified by its position in the row only (the header word could not be placed)")
        tier = "C" if (diff or d["aligned"] is False) else ("A" if (d["aligned"] is True and same and d["endyear"]) else "B")
        for unit in UNITS:
            pop = d["pop"][unit]
            if pop < MIN_POP:
                print(f"[filter] {y} {unit}: {pop:,} residents < {MIN_POP:,}, dropped")
                continue
            m = d["known"][unit]
            rows.append({
                "country": "Taiwan", "unit": unit, "unit_local": "", "unit_code": "", "admin_level": "admin1",
                "unit_type": "county" if unit.endswith("County") else "city", "parent_unit": "", "year": y, "homicide_cases": m, "population": pop,
                "homicide_rate_per_100k": m / pop * 1e5, "flag_low_count": m < LOW_COUNT, "flag_outlier_year": False,
                "population_age_years": 0.5 if d["endyear"] else float("nan"),
                "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "",
                "validation": f"the 22 city/county agency rows + the NPA row add up to the national homicide figure of {y} ({d['nat_known']}) in Table 31; "
                              f"the 22 populations add up to the national population ({d['nat_pop']:,}) within the table's rounding in Table 3; both tables are for {y}; "
                              f"{cont_text}; {al_text}",
                "indicator": f"Statistical Yearbook of the ROC {d['label']}, Table 31, Homicide: cases known to the police, by agency (original source: National Police Agency)",
                "population_method": "Table 3 'General situation of population', total population by city/county in 1,000 persons"
                                     + (" at the end of the year (the page says so)" if d["endyear"] else "; the end-of-year reference is NOT confirmed by the page text")
                                     + " (original source: Ministry of the Interior)",
                "data_notes": f"city/county police units hold {covered} of the {d['nat_known']} national cases; {d['npa']} sit with national police units and are not in any city; "
                              f"population is published rounded to thousands of persons",
                "source_homicide": d["url"], "source_population": d["url"], "retrieved": d["retrieved"], "yearbook_edition": d["label"]})
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[taiwan] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "taiwan")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    print(df.pivot(index="unit", columns="year", values="homicide_rate_per_100k").round(2).to_string())
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df.unit.nunique()} units, years {sorted(int(y) for y in df.year.unique())})")


def cmd_inspect(args):
    for y, d in sorted(load_all(args.refresh, args.insecure).items()):
        print(f"\n=== {y} ===")
        print(pd.DataFrame({"homicide_cases_known": d["known"], "population": d["pop"]}).to_string())
        print(f"  NPA-affiliated: {d['npa']} | national cases {d['nat_known']} | national population {d['nat_pop']:,}")
        print(f"  national homicide series printed in this edition's Table 31: {d['series']}")
    print("\n[inspect only] no CSV written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "inspect"])
    ap.add_argument("--refresh", action="store_true", help="re-download the PDFs even if saved")
    ap.add_argument("--insecure", action="store_true", help="last resort: download with TLS verification OFF (prints a warning)")
    a = ap.parse_args()
    cmd_build(a) if a.cmd == "build" else cmd_inspect(a)