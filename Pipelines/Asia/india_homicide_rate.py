#!/usr/bin/env python3
"""
India - police-recorded murder cases per 100,000 residents, the 19 metropolitan cities of the NCRB tables, 2016-2024.

NUMERATOR   (official): National Crime Records Bureau (NCRB, Ministry of Home Affairs), "Crime in India" yearbooks 2016-2024,
            TABLE 2B.1 "Murder Cases in Metropolitan Cities": murder cases registered in each city. Each edition prints three
            years; its newest year is used and the two earlier columns serve as a check (below).
DENOMINATOR (official): the city population printed in the same NCRB table (in lakhs, converted to persons). The header text
            of that column is quoted in `population_method`. In several editions that header says (2011): a census base that is NOT
            updated every year, and identical values across editions show the same for the editions whose header names no year. Such
            rows are tier B, with the age of the base in `population_age_years` and the editions sharing the figure in
            `population_unchanged_in_editions`; the rate is on NCRB's own base and is overstated for cities that have grown since.
RATE        recomputed as cases / population x 100,000. NCRB's own published rate (per lakh, one decimal) is kept in the extra
            column `ncrb_published_rate` and must agree with the recomputed rate within RATE_TOL; this also proves that the
            murders, population and rate columns were identified correctly.
CITIES      The 19 cities of the table (the NCRB's metropolitan cities). India has no official code for cities, so the
            parent state/union territory is given in `parent_unit` and no code column is used.
CHECKS      (1) the page is the table: header text and printed footer number must match; (2) every city has exactly the expected
            number of numeric cells for its layout; (3) the 19 cities add up to the printed TOTAL CITIES row (a mismatch makes
            the year tier C); (4) published rate vs recomputed rate (a mismatch makes the row tier C); (5) the same year's
            murders in the NEXT two editions (their earlier-year columns) must equal this edition's value (a difference is a
            revision or a substituted figure: tier B, with both values in the note); (6) footnotes printed under the table
            that mention a city are copied into that city's `data_notes`. The text in `validation` is built from these results.
LAYOUTS     A (2020-2024): 3 yearly murder columns | population | RATE | chargesheet rate ; B (2017-2019): 3 years | % share |
            population | RATE ; C (2016): 3 years | % share | rank | population | RATE | rank. Detected from the page text.

ROBOTS      The NCRB site's robots.txt can disallow automated downloads of the PDFs. The script never overrides it: it prints the
            rules and the files to save by hand (a person saving an official PDF is not a crawler), and uses them from the raw folder.
Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/India/ ; the one output is
            india_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python india_homicide_rate.py inspect | build
Options:    --years 2023 2024   --refresh   --local-dir DIR (PDFs you saved yourself, named 2024.pdf, 2023.pdf, ...; a file saved in the
            raw folder under that name is used automatically)
            --insecure (skip TLS verification: only if a .gov.in certificate fails; prints a warning)
Needs:      pip install pandas requests pdfplumber
"""
from __future__ import annotations
import argparse
import datetime as dt
import io
import logging
import re
import sys
from pathlib import Path

import pandas as pd

try:
    import pdfplumber
except ImportError:
    sys.exit("[stop] this script needs pdfplumber:  python -m pip install pdfplumber")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 6:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

log = logging.getLogger("ncrb")
P = F.paths(__file__, "India")          # raw downloads -> Data/Raw/<Region>/India/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH: F.Fetcher | None = None          # created in main() (needs --insecure)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP
RATE_TOL = 0.1                          # DECISION: |published rate - murders / population (lakh)| allowed (published rate has one decimal)
TOTAL_TOL = 0.5                         # the sum of the cities must equal the printed TOTAL CITIES row (whole numbers)
NCRB_UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/124 Safari/537.36"   # as in the original script, which used a browser-style User-Agent

# year -> (printed page number at the bottom of the yearbook page, URL)
SOURCES = {
    2024: (243, "https://www.ncrb.gov.in/uploads/files/11CrimeinIndia2024-VolumeI.pdf"),
    2023: (173, "https://www.ncrb.mha.gov.in/uploads/files/1CrimeinIndia2023PartI1.pdf"),
    2022: (173, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/custom/1701607577CrimeinIndia2022Book1.pdf"),
    2021: (173, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/custom/1696831798CII2021Volume1.pdf"),
    2020: (173, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/post/16959885631653645869CII2020Volume1.pdf"),
    2019: (169, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/custom/1653730573_CII%202019%20Volume%201.pdf"),
    2018: (169, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/custom/1653734481_Crime%20in%20India%202018%20-%20Volume%201_3_0_0.pdf"),
    2017: (169, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/post/16959893381653885627CrimeinIndia2017-Volume100.pdf"),
    2016: (100, "https://www.ncrb.mha.gov.in/uploads/nationalcrimerecordsbureau/custom/1653886924_Crime%20in%20India%20-%202016%20Complete%20PDF%20291117.pdf"),
}

# Layout -> (numeric tokens per row, index of year-N murders, index of population, index of RATE)
LAYOUTS = {
    "A": dict(n=6, murders=2, pop=3, rate=4),   # 2020-2024
    "B": dict(n=6, murders=2, pop=4, rate=5),   # 2017-2019
    "C": dict(n=8, murders=2, pop=5, rate=6),   # 2016
}


def expected_layout(year):
    return "A" if year >= 2020 else ("B" if year >= 2017 else "C")


# canonical city -> (state / union territory, accepted first-word spellings)
CITIES = {
    "Ahmedabad":  ("Gujarat", {"ahmedabad", "ahmadabad"}),
    "Bengaluru":  ("Karnataka", {"bengaluru", "bangalore", "bengalore"}),
    "Chennai":    ("Tamil Nadu", {"chennai"}),
    "Coimbatore": ("Tamil Nadu", {"coimbatore"}),
    "Delhi":      ("Delhi", {"delhi"}),
    "Ghaziabad":  ("Uttar Pradesh", {"ghaziabad"}),
    "Hyderabad":  ("Telangana", {"hyderabad"}),
    "Indore":     ("Madhya Pradesh", {"indore"}),
    "Jaipur":     ("Rajasthan", {"jaipur"}),
    "Kanpur":     ("Uttar Pradesh", {"kanpur"}),
    "Kochi":      ("Kerala", {"kochi", "cochin"}),
    "Kolkata":    ("West Bengal", {"kolkata"}),
    "Kozhikode":  ("Kerala", {"kozhikode", "calicut"}),
    "Lucknow":    ("Uttar Pradesh", {"lucknow"}),
    "Mumbai":     ("Maharashtra", {"mumbai"}),
    "Nagpur":     ("Maharashtra", {"nagpur"}),
    "Patna":      ("Bihar", {"patna"}),
    "Pune":       ("Maharashtra", {"pune"}),
    "Surat":      ("Gujarat", {"surat"}),
}
ALIAS_TO_CANON = {a: c for c, (_, al) in CITIES.items() for a in al}
NUM_RE = re.compile(r"^\d+(\.\d+)?$")


class ParseError(RuntimeError):
    pass


# ----------------------------------------------------------------------------- download
def get_pdf(year, url, local_dir=None, refresh=False) -> tuple[bytes, str]:
    """-> (PDF bytes, retrieval date). Order: a file in --local-dir; a file you saved in the raw folder as <year>.pdf; the download
    (only if the site's robots.txt allows automated downloads: otherwise F.RobotsDisallowed is raised and the file must be saved by hand)."""
    for folder in ([Path(local_dir)] if local_dir else []) + [RAW]:
        p = folder / f"{year}.pdf"
        if p.exists():
            data = p.read_bytes()
            if data[:5] != b"%PDF-":
                raise RuntimeError(f"{p} is not a PDF")
            print(f"[manual file] {p}  {len(data):,} bytes")
            return data, dt.date.fromtimestamp(p.stat().st_mtime).isoformat()
    if local_dir:
        raise FileNotFoundError(f"{Path(local_dir) / f'{year}.pdf'} not found (expected {year}.pdf in --local-dir)")
    try:
        data = FETCH.get(url, f"ncrb_crime_in_india_{year}", reuse=not refresh, suffix=".pdf", reject_html=True)
    except RuntimeError as e:
        raise RuntimeError(f"{year}: {e}. Download the PDF in your browser and save it as {RAW / f'{year}.pdf'}") from e
    if not data[:5] == b"%PDF-":
        raise RuntimeError(f"{year}: the download is not a PDF ({url})")
    return data, FETCH.retrieved_on(url)


# ----------------------------------------------------------------------------- page search
def _text(pdf, i):
    return pdf.pages[i].extract_text() or ""


def _is_table_page(text):
    t = text.lower()
    return "2b.1" in t and "murder" in t and "metropolitan" in t and "total cities" in t


def _printed_number(text):
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    for l in reversed(lines[-4:]):
        if re.fullmatch(r"\d{1,4}", l):
            return int(l)
    return None


def find_table_page(pdf, printed_page, window=80):
    """Return (0-based PDF page index of Table 2B.1, whether its printed footer == printed_page)."""
    n = len(pdf.pages)
    first = max(0, printed_page - 1)
    near = list(range(first, min(n, printed_page + window)))
    rest = [i for i in range(n) if i not in set(near)]
    candidates = []
    for phase, idxs in (("window", near), ("full scan", rest)):
        for i in idxs:
            txt = _text(pdf, i)
            if not _is_table_page(txt):
                continue
            if _printed_number(txt) == printed_page:
                log.info("   table page: PDF index %d (printed %d)", i, printed_page)
                return i, True
            candidates.append(i)
        if candidates and phase == "window":
            break
    if candidates:
        log.warning("   printed page %d not confirmed; using PDF index %d (candidates %s)", printed_page, candidates[0], candidates)
        return candidates[0], False
    raise ParseError(f"Table 2B.1 page not found (printed page {printed_page}).")


# ----------------------------------------------------------------------------- layout
def detect_layout(page_text, year):
    t = page_text.lower()
    if "chargesheet" in t:
        det = "A"
    elif "rank" in t:
        det = "C"
    else:
        det = "B"
    exp = expected_layout(year)
    if det != exp:
        log.warning("%s: detected layout %s but expected %s; using detected", year, det, exp)
    return det


# ----------------------------------------------------------------------------- parsing
def _norm(w):
    return re.sub(r"[^a-z]", "", w.lower())


def page_notes(text):
    """Header lines about the population column, and the footnote lines printed under the table."""
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    head = [l for l in lines[:18] if re.search(r"popul|lakh", l, re.I)]
    ti = next((i for i, l in enumerate(lines) if re.search(r"total\s+cities", l, re.I)), None)
    foot = [l for l in (lines[ti + 1:] if ti is not None else []) if len(l) > 12 and not re.fullmatch(r"\d{1,4}", l)]
    return " | ".join(dict.fromkeys(head))[:260], foot[:8]


def header_reference_year(pop_header: str):
    """The year printed after '(in Lakhs)' in the population column header, e.g. 'Population (in Lakhs) (2011)+' -> 2011; None if absent."""
    m = re.search(r"lakhs?\s*\)?\s*\(\s*(\d{4})\s*\)", pop_header.replace("|", " "), re.I)
    return int(m.group(1)) if m else None


def parse_page(page, year):
    text = page.extract_text() or ""
    layout = detect_layout(text, year)
    spec = LAYOUTS[layout]
    words = page.extract_words(x_tolerance=2, y_tolerance=2, keep_blank_chars=False)
    if not words:
        raise ParseError("no text layer on page (scanned PDF?). OCR would be required.")
    for w in words:
        w["cy"] = (w["top"] + w["bottom"]) / 2

    # --- TOTAL CITIES row position
    total_top = None
    for w in words:
        if w["text"].upper() == "TOTAL":
            if any(v["text"].upper() == "CITIES" and abs(v["cy"] - w["cy"]) < 3 for v in words):
                total_top = w["top"]
                total_cy = w["cy"]
                break
    if total_top is None:
        raise ParseError("TOTAL CITIES row not found")

    # --- city anchors (first word of the name, above the total row)
    anchors = {}
    for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
        if w["top"] >= total_top - 1:
            continue
        canon = ALIAS_TO_CANON.get(_norm(w["text"]))
        if canon and canon not in anchors and not w["text"].startswith("("):
            anchors[canon] = w
    missing = set(CITIES) - set(anchors)
    if missing:
        raise ParseError(f"cities not found on page: {sorted(missing)}")

    city_x0 = sorted(a["x0"] for a in anchors.values())[len(anchors) // 2]

    # --- row block centre = mean of name line and "(State)" line (if any)
    blocks = {}
    for canon, a in anchors.items():
        ys = [a["cy"]]
        for w in words:
            if (w["text"].startswith("(") and abs(w["x0"] - a["x0"]) < 6
                    and 0 < w["top"] - a["top"] < 20):
                ys.append(w["cy"])
                break
        blocks[canon] = sum(ys) / len(ys)

    first_block = min(blocks.values())
    body_top = first_block - 14          # excludes header + the "1 2 3 ..." index row
    body = [w for w in words if body_top <= w["cy"] < total_top - 1]

    # --- city column's right edge = rightmost non-numeric body word
    text_words = [w for w in body if not NUM_RE.match(w["text"].replace(",", ""))]
    city_right = max(w["x1"] for w in text_words)

    # --- numeric tokens -> nearest row block
    rows = {c: [] for c in CITIES}
    for w in body:
        s = w["text"].replace(",", "")
        if not NUM_RE.match(s) or w["x0"] <= max(city_right, city_x0) - 1:
            continue
        canon = min(blocks, key=lambda c: abs(blocks[c] - w["cy"]))
        rows[canon].append((w["x0"], float(s)))

    results = {}
    for canon, toks in rows.items():
        toks.sort()
        vals = [v for _, v in toks]
        if len(vals) != spec["n"]:
            raise ParseError(f"{canon}: expected {spec['n']} numeric cells for layout {layout}, got {vals}")
        results[canon] = dict(rate=vals[spec["rate"]], murders=vals[spec["murders"]], pop=vals[spec["pop"]],
                              earlier=(vals[0], vals[1]))           # murders of the two years before this edition's year

    # --- total-row cross-check (sum of last-year murders)
    tot_vals = sorted((w["x0"], float(w["text"].replace(",", ""))) for w in words
                      if abs(w["cy"] - total_cy) < 4 and w["x0"] > city_right
                      and NUM_RE.match(w["text"].replace(",", "")))
    printed_total, total_ok = None, None
    if len(tot_vals) >= 3:
        printed_total = tot_vals[spec["murders"]][1]
        total_ok = abs(sum(r["murders"] for r in results.values()) - printed_total) < TOTAL_TOL
        if not total_ok:
            log.warning("%s: sum of cities %s != printed TOTAL CITIES %s", year, sum(r["murders"] for r in results.values()), printed_total)
    pop_header, foot = page_notes(text)
    return {"pop_ref_year": header_reference_year(pop_header), "layout": layout, "results": results, "total_ok": total_ok, "printed_total": printed_total,
            "sum_cities": sum(r["murders"] for r in results.values()), "pop_header": pop_header, "footnotes": foot}


def process_year(year, pdf_bytes):
    printed, _ = SOURCES[year]
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        idx, confirmed = find_table_page(pdf, printed)
        info = parse_page(pdf.pages[idx], year)
    info.update(printed=printed, pdf_index=idx + 1, page_confirmed=confirmed)
    return info


# ----------------------------------------------------------------------------- assembling rows
def build_rows(editions: dict[int, dict], urls: dict[int, str], retrieved: dict[int, str]) -> list[dict]:
    rows = []
    for year in sorted(editions):
        ed = editions[year]
        for canon, r in ed["results"].items():
            murders, lakhs = r["murders"], r["pop"]
            pop = round(lakhs * 100_000)                     # whole persons; the rate below uses exactly this figure
            stated = ed["pop_ref_year"]                      # reference year this edition's header states for its population column
            same_pop = sorted(y2 for y2, e2 in editions.items() if y2 != year and e2["results"][canon]["pop"] == lakhs)
            # an identical figure printed in other editions is ONE base: its year is the earliest one any of those headers states
            stated_by_sharers = [editions[y2]["pop_ref_year"] for y2 in same_pop if editions[y2]["pop_ref_year"] is not None]
            ref = min(stated_by_sharers + ([stated] if stated is not None else [])) if (same_pop or stated is not None) else None
            ref_basis = ("" if ref is None else "stated in this edition's header" if (ref == stated and not same_pop)
                         else "stated in this edition's header and in the editions printing the same figure" if ref == stated
                         else "taken from the headers of the editions that print the identical figure")
            age = (year - ref) if ref is not None else None
            stale = bool(same_pop) or (age is not None and age > F.MAX_DENOMINATOR_AGE)
            recomputed = murders / lakhs
            rate_ok = abs(recomputed - r["rate"]) <= RATE_TOL
            # the same year as printed in the next two editions' earlier-year columns
            later = []
            if year + 1 in editions:
                later.append((year + 1, editions[year + 1]["results"][canon]["earlier"][1]))
            if year + 2 in editions:
                later.append((year + 2, editions[year + 2]["results"][canon]["earlier"][0]))
            same = [e for e, v in later if v == murders]
            diff = [(e, v) for e, v in later if v != murders]
            checks = []
            if ed["total_ok"] is True:
                checks.append(f"the {len(ed['results'])} cities add up to the printed TOTAL CITIES row ({ed['printed_total']:,.0f})")
            elif ed["total_ok"] is False:
                checks.append(f"MISMATCH: the cities add up to {ed['sum_cities']:,.0f} but the printed TOTAL CITIES row says {ed['printed_total']:,.0f}")
            else:
                checks.append("the printed TOTAL CITIES row could not be read, so the sum of the cities is not reconciled")
            checks.append(f"recomputed rate {recomputed:.2f} {'agrees with' if rate_ok else 'DIFFERS from'} the published NCRB rate {r['rate']} (tolerance {RATE_TOL})")
            if same and not diff:
                checks.append("the same value is printed in the " + " and ".join(f"{e}" for e in same) + " edition" + ("s" if len(same) > 1 else ""))
            elif diff:
                checks.append("later editions differ: " + "; ".join(f"the {e} edition prints {int(v)}" for e, v in diff))
            else:
                checks.append("no later edition yet to confirm this year's value")
            checks.append("the table page was found by its printed page number" if ed["page_confirmed"] else "the table page was found by its text only (printed page number not confirmed)")
            tier = "A"
            if ed["total_ok"] is False or not rate_ok:
                tier = "C"
            elif ed["total_ok"] is None or diff or not ed["page_confirmed"] or stale:
                tier = "B"
            notes = [f"NCRB table note: {n[:200]}" for n in ed["footnotes"] if any(a in re.sub(r"[^a-z ]", " ", n.lower()).split() for a in CITIES[canon][1])]
            if stale:
                why = []
                if age is not None and age > F.MAX_DENOMINATOR_AGE:
                    why.append(f"the base year is {ref} ({ref_basis}), {age} years before {year}")
                if stated is not None and ref is not None and stated != ref:
                    why.append(f"this edition's own header says {stated}, but the figure is identical to the one printed under {ref}")
                if same_pop:
                    why.append("the same population figure is printed in the " + ", ".join(str(y2) for y2 in same_pop) + " edition" + ("s" if len(same_pop) > 1 else ""))
                notes.append("the population is a fixed base that is not updated every year (" + "; ".join(why) + "): the rate is on that base, as NCRB's own "
                             "published rate is, and is overstated for a city that has grown since")
            if diff:
                notes.append(f"the {year} edition prints {int(murders)}; " + "; ".join(f"the {e} edition prints {int(v)} for {year}" for e, v in diff))
            url = urls[year]
            rows.append({
                "country": "India", "unit": canon, "unit_local": "", "unit_code": "", "admin_level": "city",
                "unit_type": "metropolitan_city", "parent_unit": CITIES[canon][0], "year": year,
                "homicide_cases": int(murders), "population": pop, "homicide_rate_per_100k": int(murders) / pop * 1e5,
                "flag_low_count": int(murders) < LOW_COUNT, "flag_outlier_year": False,
                "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "",
                "validation": "; ".join(checks),
                "indicator": f"NCRB Crime in India {year}, Table 2B.1 'Murder Cases in Metropolitan Cities': murder cases registered in the city",
                "population_method": f"population of the city as printed in the same NCRB table (lakhs, converted to persons); the table's header text: "
                                     f"'{ed['pop_header'] or 'not found in the page text'}'",
                "data_notes": "; ".join(notes),
                "source_homicide": f"{url} (printed page {ed['printed']}, PDF page {ed['pdf_index']})",
                "source_population": f"{url} (printed page {ed['printed']}, PDF page {ed['pdf_index']}, same table)",
                "retrieved": retrieved[year],
                "ncrb_published_rate": r["rate"], "table_layout": ed["layout"], "printed_page": ed["printed"],
                "population_reference_year": "" if ref is None else ref, "population_reference_basis": ref_basis,
                "population_age_years": "" if age is None else age,
                "population_unchanged_in_editions": ";".join(str(y2) for y2 in same_pop),
            })
    return rows


# ----------------------------------------------------------------------------- main
def main(argv=None):
    global FETCH
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--years", nargs="*", type=int, default=sorted(SOURCES, reverse=True))
    ap.add_argument("--local-dir", help="folder with 2024.pdf, 2023.pdf, ... (skips the download)")
    ap.add_argument("--refresh", action="store_true", help="download again instead of reusing the saved PDFs")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification (only if a .gov.in certificate fails)")
    ap.add_argument("-v", "--verbose", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if a.verbose else logging.INFO, format="%(message)s")
    FETCH = F.Fetcher(RAW, user_agent=NCRB_UA, insecure=a.insecure, retries=4, timeout=(15, 180))

    editions, urls, retrieved, failures, manual = {}, {}, {}, [], []
    for year in sorted(a.years):
        if year not in SOURCES:
            log.error("no source configured for %s", year)
            continue
        try:
            data, got = get_pdf(year, SOURCES[year][1], a.local_dir, a.refresh)
            editions[year] = process_year(year, data)
            urls[year], retrieved[year] = SOURCES[year][1], got
            log.info("%s: OK (%d cities, layout %s)", year, len(editions[year]["results"]), editions[year]["layout"])
        except F.RobotsDisallowed as e:
            log.error("%s: not downloaded (robots.txt)", year)
            manual.append((year, e.url))
            failures.append(year)
        except Exception as e:  # noqa: BLE001
            log.error("%s: FAILED - %s", year, e)
            failures.append(year)
    if manual:
        print(f"\n[manual download needed] the site's robots.txt does not allow automated downloads of these files. A person may save them in a browser;"
              f"\nsave each one under the file name shown, in {RAW}, then run the script again:")
        for y, u in manual:
            print(f"   {y}.pdf   <-   {u}")
    if not editions:
        sys.exit("[stop] no edition could be read" + (" - save the PDFs listed above first" if manual else ""))

    rows = build_rows(editions, urls, retrieved)
    df = pd.DataFrame(rows)
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        log.warning("[india] statistical outlier: %s %s = %s cases (robust z = %.1f)", r.unit, int(r.year), int(r.homicide_cases), r.robust_z)
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "india")
    print("\nPopulation column header as printed, per edition:")
    for y in sorted(editions):
        print(f"  {y}: {editions[y]['pop_header'] or '(not found)'}")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    below = df[df.reliability_tier != "A"]
    if len(below):
        print(f"\nRows below tier A: {len(below)}. By reason (the first lines of each row's data_notes / validation):")
        for _, r in below.sort_values(["unit", "year"]).head(12).iterrows():
            print(f"   {r.unit} {int(r.year)} tier {r.reliability_tier}: {(r.data_notes or r.validation)[:170]}")
        if len(below) > 12:
            print(f"   ... and {len(below) - 12} more")
    pops = {y: {c: e["results"][c]["pop"] for c in CITIES} for y, e in editions.items()}
    ys = sorted(pops)
    print("\nPopulation base: cities whose population figure is identical to the previous edition's:")
    for a_, b_ in zip(ys, ys[1:]):
        print(f"   {b_} vs {a_}: {sum(pops[b_][c] == pops[a_][c] for c in CITIES)}/{len(CITIES)}")
    last = df[df.year == df.year.max()].sort_values("homicide_rate_per_100k", ascending=False)
    print(f"\nRate per 100k in {int(df.year.max())} (all cities):")
    print(last[["unit", "parent_unit", "homicide_cases", "population", "homicide_rate_per_100k", "ncrb_published_rate"]].round(3).to_string(index=False))
    if failures:
        print(f"\n[warning] these years could not be read and are missing from the output: {sorted(failures)}")
    if a.cmd == "build":
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows)")
    else:
        print("\n[inspect only] no CSV written")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())