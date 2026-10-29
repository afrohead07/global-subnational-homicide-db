#!/usr/bin/env python3
"""
China - police-recorded homicide cases per 100,000 residents, by unit (registry).

UNITS IMPLEMENTED
  hk   Hong Kong SAR
         NUMERATOR   Hong Kong Police Force (HKPF) 'Crime Statistics in Detail' (data.gov.hk), column 'Homicide'
                     (murder + manslaughter as recorded by HKPF; HKPF's own annual reviews note that this can include
                     deaths from e.g. dangerous driving and industrial accidents, and a single multi-fatality event
                     can raise a year's count).
         DENOMINATOR Census & Statistics Department (C&SD) table 110-01001 'Population by sex and age group':
                     mid-year (June) resident population, thousand persons.
         CHECKS      * 'Homicide' must be found in the file's own English column header (page titles are not trusted);
                     * every year that the HKPF 'Crime Statistics Comparison' file also reports must equal the detail file;
                     * the HKPF's published 'Crime Rate' (cases per 100,000 population) implies a population:
                       overall cases / rate. It must agree with the C&SD mid-year population within RATE_TOL;
                     * C&SD: total = male + female and total = sum of the age groups (rounding tolerances).
  sh   Shanghai (municipality)
         NUMERATOR   Shanghai Statistical Yearbook, table 23.3 'Criminal cases recorded by the public security organs
                     (main years)', row 杀人 (homicide). Each edition shows four selected years, so years are assembled
                     across editions (newest edition wins).
         DENOMINATOR Shanghai Statistical Yearbook, table 2.1 (annual series), year-end resident population;
                     rate uses the mean of year-end Y-1 and Y.
         CHECKS      * the seven categories must add up to the table's own total in every year column;
                     * every year that appears in two editions must carry identical values (all categories);
                     * population: the column is identified from the table's own header text; if the layout is not
                       recognised the script prints the table and stops this unit (other units still run).
  bj   Beijing (municipality)
         NUMERATOR   Beijing Statistical Yearbook, table 23-4 'Criminal cases recorded by the public security
                     organs'. The yearbook publishes this table ONLY AS AN IMAGE (two years per edition), so it is read
                     with OCR (pip install rapidocr-onnxruntime) under hard safeguards: every OCR box must have
                     confidence >= OCR_MIN_CONF, the seven categories must add up to the total, and every year that
                     appears in two editions (consecutive editions overlap by one year) must be identical in all
                     categories. The newest year is read from one image only (arithmetically verified).
         DENOMINATOR year-end resident population from the Beijing statistical communiqué (HTML text);
                     rate uses the mean of year-end Y-1 and Y.
  js   Jiangsu (province)
         NUMERATOR   Jiangsu Statistical Yearbook, table 17-13 (HTML, bilingual): 合计 must equal the sum of all 13
                     categories; every year in two editions must be identical.
         DENOMINATOR Jiangsu Statistical Yearbook table 3-1 (year-end resident population); layout recognised from
                     header text, otherwise the table is printed and this unit stops.
  (more mainland units are added here once their table layouts are confirmed)

Commands:   python china_homicide_rate.py inspect | build        Options: --units hk sh bj js
Needs:      pip install pandas requests   (Beijing images also need  rapidocr-onnxruntime)
"""
from __future__ import annotations
import argparse, csv, datetime as dt, html as htmllib, io, json, re, sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 6:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

HERE = Path(__file__).resolve().parent
P = F.paths(__file__, "China")         # raw downloads -> Data/Raw/<Region>/China/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW)
RATE_TOL = 0.02            # DECISION: police-rate-implied population vs C&SD mid-year population (relative)
SUM_TOL_SEX = 0.25         # thousand persons: total vs male + female (each figure rounded to 0.1)
SUM_TOL_AGE = 1.5          # thousand persons: total vs sum of 18 age groups (rounding)
OCR_MIN_CONF = 0.95        # DECISION: every OCR box used must be at least this confident

HK_PAGES = ["https://data.gov.hk/en-data/dataset/hk-hkpf-stat-crm-stat-detail"]
HK_COMPARE_PAGES = ["https://data.gov.hk/en-data/dataset/hk-hkpf-stat-crm-stat-compar"]
HK_DETAIL_PINNED = "https://www.police.gov.hk/info/doc/crime_details.csv"
HK_COMPARE_PINNED = "https://www.police.gov.hk/info/doc/crime_situation_comparison_en.csv"
HK_POP_API = "https://www.censtatd.gov.hk/api/get.php?id=110-01001&lang=en&full_series=1"


TAGS = {"Hong Kong": "hk", "Shanghai": "sh", "Beijing": "bj", "Jiangsu": "js"}
def get(url: str, name: str | None = None) -> bytes:
    """Download through the shared routine (robots.txt, dated copy in the raw folder, sha256 log)."""
    return FETCH.get(url, name)


def decode_hk(raw: bytes) -> str:
    """HKPF files are Big5-HKSCS (Chinese) with English labels; try UTF-8 first, strictly."""
    for enc in ("utf-8-sig", "big5hkscs", "gb18030"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


def english(cell: str) -> str:
    """Trailing ASCII phrase of a bilingual header cell: '羆砰竜 / Overall Crime' -> 'Overall Crime'."""
    m = re.search(r"([A-Za-z][A-Za-z ,()&'-]*)\s*$", cell.strip())
    return re.sub(r"\s+", " ", m.group(1)).strip() if m else ""


def to_num(x) -> float | None:
    s = str(x).replace(",", "").strip().rstrip("p").strip()
    try:
        return float(s)
    except ValueError:
        return None


# ----------------------------------------------------------------------------- Hong Kong: police files
def parse_hk_detail(text: str) -> pd.DataFrame:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise ValueError("empty file")
    eng = [english(c) for c in rows[0]]
    low = [e.lower() for e in eng]

    def one(name):
        idx = [i for i, e in enumerate(low) if e == name.lower()]
        if len(idx) != 1:
            raise ValueError(f"expected exactly one '{name}' column, found {len(idx)}; English headers: {eng[:12]}")
        return idx[0]
    iy, io_, iv, ih = one("Year"), one("Overall Crime"), one("Violent Crime"), one("Homicide")
    if low[io_ + 1:io_ + 2] != ["crime rate"] or low[iv + 1:iv + 2] != ["crime rate"]:
        raise ValueError("a 'Crime Rate' column does not follow 'Overall Crime' / 'Violent Crime'")
    out = []
    for r in rows[1:]:
        if not r or not re.fullmatch(r"\s*(19|20)\d\d\s*", r[iy] if len(r) > iy else ""):
            continue
        vals = {k: to_num(r[i]) if len(r) > i else None for k, i in
                (("overall", io_), ("overall_rate", io_ + 1), ("violent", iv), ("violent_rate", iv + 1), ("homicide", ih))}
        bad = [k for k, v in vals.items() if v is None]
        if bad:
            raise ValueError(f"year {r[iy].strip()}: non-numeric value in {bad}: {[r[i] for i in (io_, io_+1, iv, iv+1, ih)]}")
        out.append({"year": int(r[iy]), **vals})
    df = pd.DataFrame(out)
    if df.empty or df.year.duplicated().any():
        raise ValueError("no data rows, or duplicated years")
    return df.sort_values("year").reset_index(drop=True)


def parse_hk_compare(text: str) -> dict[int, float]:
    rows = list(csv.reader(io.StringIO(text)))
    hdr = next((r for r in rows if any(re.fullmatch(r"(19|20)\d\d", c.strip()) for c in r)), None)
    if hdr is None:
        raise ValueError("no year header in the comparison file")
    cols = {i: int(c) for i, c in enumerate(hdr) if re.fullmatch(r"(19|20)\d\d", c.strip())}
    row = next((r for r in rows if len(r) > 1 and re.match(r"\s*Homicide", r[1])), None)
    if row is None:
        raise ValueError("no 'Homicide' row in the comparison file")
    return {y: float(row[i].replace(",", "")) for i, y in cols.items()}


def discover_csvs(pages: list[str]) -> list[str]:
    found = []
    for pg in pages:
        try:
            html = htmllib.unescape(get(pg).decode("utf-8", "replace"))
        except Exception as e:
            print(f"[hk] data.gov.hk page failed: {e}")
            continue
        for h in re.findall(r'href="([^"]*?/resource/[^"]+)"', html):
            try:
                t = htmllib.unescape(get(urljoin(pg, h)).decode("utf-8", "replace"))
            except Exception:
                continue
            found += [urljoin(pg, u) for u in re.findall(r'href="([^"]+\.csv)"', t)]
    return list(dict.fromkeys(found))


# ----------------------------------------------------------------------------- Hong Kong: population
def parse_hk_pop(text: str) -> tuple[dict[int, tuple[float, bool]], list[str]]:
    """Mid-year (June) total population, thousand persons, with sex and age-group consistency checks."""
    obj = json.loads(text)
    tot, male, female, groups = {}, {}, {}, {}
    for r in obj["dataSet"]:
        if r.get("sv") != "POP" or not str(r.get("svDesc", "")).startswith("Number"):
            continue
        per = str(r.get("period", ""))
        if not re.fullmatch(r"\d{4}06", per):
            continue
        fig = to_num(r.get("figure"))
        if fig is None:
            continue
        y, sex, age = int(per[:4]), str(r.get("SEX", "")), str(r.get("AGE", ""))
        if age == "" and sex == "":
            tot[y] = (fig, str(r.get("sd_value", "")).strip().lower() == "p")
        elif age == "" and sex == "M":
            male[y] = fig
        elif age == "" and sex == "F":
            female[y] = fig
        elif age != "" and sex == "":
            groups.setdefault(y, []).append(fig)
    if not tot:
        raise ValueError("no mid-year total-population records found")
    notes, n_sex, n_age = [], 0, 0
    for y, (t, _) in tot.items():
        if y in male and y in female:
            n_sex += 1
            if abs(t - (male[y] + female[y])) > SUM_TOL_SEX:
                raise ValueError(f"C&SD {y}: total {t} != male {male[y]} + female {female[y]}")
        if y in groups:
            n_age += 1
            if abs(t - sum(groups[y])) > SUM_TOL_AGE:
                raise ValueError(f"C&SD {y}: total {t} != sum of {len(groups[y])} age groups {sum(groups[y]):.1f}")
    notes.append(f"C&SD total = male + female in {n_sex} years and = sum of age groups in {n_age} years")
    return tot, notes


# ----------------------------------------------------------------------------- Hong Kong: build
def build_hk() -> pd.DataFrame:
    print("\n=== Hong Kong SAR ===")
    cands = [HK_DETAIL_PINNED] + [u for u in discover_csvs(HK_PAGES) if u != HK_DETAIL_PINNED]
    detail, used = None, None
    for u in cands:
        try:
            raw = get(u, "china_hk_detail")
            detail = parse_hk_detail(decode_hk(raw))
            used = u
            break
        except Exception as e:
            print(f"[hk] {u}: {type(e).__name__}: {e}")
    if detail is None:
        sys.exit("[stop] no HKPF CSV with a Homicide column found")
    print(f"[hk] detail file {used}: years {detail.year.min()}-{detail.year.max()} ({len(detail)} rows)")

    # independent police file: must agree wherever it overlaps
    cmp_vals, cmp_used = {}, None
    for u in [HK_COMPARE_PINNED] + [x for x in discover_csvs(HK_COMPARE_PAGES) if "_en" in x and x != HK_COMPARE_PINNED]:
        try:
            cmp_vals = parse_hk_compare(decode_hk(get(u, "china_hk_compare")))
            cmp_used = u
            break
        except Exception as e:
            print(f"[hk] comparison file {u}: {type(e).__name__}: {e}")
    n_cmp = 0
    for y, v in cmp_vals.items():
        d = detail.loc[detail.year == y, "homicide"]
        if len(d):
            n_cmp += 1
            if float(d.iloc[0]) != v:
                sys.exit(f"[stop] Homicide {y}: detail file {d.iloc[0]:.0f} != comparison file {v:.0f}")
    print(f"[hk] comparison file agrees with the detail file for {n_cmp} year(s): {sorted(cmp_vals)}")

    try:
        tot, notes = parse_hk_pop(get(HK_POP_API, "china_hk_population").decode("utf-8-sig"))
    except (ValueError, KeyError) as e:
        sys.exit(f"[stop] C&SD population file: {type(e).__name__}: {e}")
    print("[hk]", notes[0])

    # police published crime rate -> implied population vs C&SD
    devs = []
    for _, r in detail.iterrows():
        y = int(r.year)
        if y not in tot:
            continue
        for col, rate in (("overall", "overall_rate"), ("violent", "violent_rate")):
            implied = r[col] / r[rate] * 1e5
            dev = implied / (tot[y][0] * 1000) - 1
            devs.append((y, col, dev))
            if abs(dev) > RATE_TOL:
                sys.exit(f"[stop] {y}: HKPF {col} rate implies population {implied:,.0f} vs C&SD mid-year {tot[y][0]*1000:,.0f} ({dev:+.1%})")
    mx = max(abs(d) for _, _, d in devs)
    print(f"[hk] HKPF crime rates imply the C&SD mid-year population within {mx:.2%} (largest deviation, {len(devs)} checks; limit {RATE_TOL:.0%})")

    rows = []
    for _, r in detail.iterrows():
        y = int(r.year)
        if y not in tot:
            print(f"[skip] {y}: no C&SD mid-year population")
            continue
        pop = tot[y][0] * 1000
        if pop < MIN_POP:
            continue
        n = int(r.homicide)
        rows.append({
            "country": "China", "unit": "Hong Kong", "admin_level": "admin1", "unit_type": "special_administrative_region",
            "year": y, "homicide_cases": n, "population": round(pop), "homicide_rate_per_100k": n / pop * 1e5,
            "flag_low_count": n < LOW_COUNT, "population_provisional": tot[y][1],
            "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": "A", "definition_flags": "includes_manslaughter",
            "validation": f"HKPF rates imply C&SD population within {mx:.2%}; {n_cmp} year(s) equal to the HKPF comparison file; "
                          f"C&SD sex/age sums consistent",
            "indicator": "HKPF homicide (murder + manslaughter) cases recorded in the year",
            "population_method": "C&SD mid-year (June) resident population",
            "data_notes": "HKPF 'homicide' = murder + manslaughter (HKPF reviews cite e.g. dangerous-driving and industrial-accident deaths); a multi-fatality event charged as manslaughter is registered as one case per victim (HKPF reports to LegCo)",
            "source_homicide": used, "source_homicide_check": cmp_used, "source_population": HK_POP_API,
            "retrieved": dt.date.today().isoformat()})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- web helpers (yearbook sites)
def decode_web(raw: bytes) -> str:
    """Declared charset first (gb2312/gbk -> gb18030), then utf-8, gb18030, big5hkscs; strict, never latin-1."""
    sniff = raw[:4000].decode("ascii", "ignore")
    m = re.search(r"charset\s*=\s*[\"']?([\w-]+)", sniff, re.I)
    cands = []
    if m:
        d = m.group(1).lower()
        cands.append("gb18030" if d in ("gb2312", "gbk") else d)
    for enc in cands + ["utf-8-sig", "gb18030", "big5hkscs"]:
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", "replace")


def anchors(text: str, base: str) -> list[tuple[str, str]]:
    out = []
    for m in re.finditer(r'<a\b[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', text, re.S | re.I):
        label = re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", m.group(2)))).strip()
        out.append((urljoin(base, htmllib.unescape(m.group(1))), label))
    return out


def frames(text: str, base: str) -> list[str]:
    return [urljoin(base, htmllib.unescape(u)) for u in re.findall(r'<i?frame\b[^>]*\bsrc\s*=\s*["\']([^"\']+)', text, re.I)]


def squash(s: str) -> str:
    """Remove every kind of whitespace and invisible character (the yearbooks write '杀 人' and '119 691')."""
    return re.sub(r"[\s\u00a0\u3000\u200b-\u200f\u2060\ufeff]+", "", str(s))


def num(s) -> float | None:
    t = squash(s).replace(",", "")
    return float(t) if re.fullmatch(r"-?\d+(\.\d+)?", t) else None


class _TableParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables, self.cur, self.row, self.cell, self.attrs, self.depth = [], None, None, None, {}, 0

    def handle_starttag(self, tag, attrs):
        t = tag.lower()
        if t == "table":
            self.depth += 1
            if self.depth == 1:
                self.cur = []
        elif t == "tr" and self.cur is not None and self.depth == 1:
            self.row = []
        elif t in ("td", "th") and self.row is not None and self.depth == 1:
            self.cell, self.attrs = [], dict(attrs)
        elif t == "br" and self.cell is not None:
            self.cell.append(" ")

    def handle_data(self, d):
        if self.cell is not None:
            self.cell.append(d)

    def handle_endtag(self, tag):
        t = tag.lower()
        if t in ("td", "th") and self.cell is not None:
            def n(k):
                try:
                    return max(1, int(re.sub(r"\D", "", self.attrs.get(k, "1")) or 1))
                except ValueError:
                    return 1
            self.row.append((" ".join("".join(self.cell).split()), n("colspan"), n("rowspan")))
            self.cell = None
        elif t == "tr" and self.row is not None:
            self.cur.append(self.row)
            self.row = None
        elif t == "table":
            self.depth -= 1
            if self.depth == 0 and self.cur is not None:
                self.tables.append(self.cur)
                self.cur = None


def html_grids(text: str) -> list[list[list[str]]]:
    """Every outermost <table> as a rectangular grid (colspan/rowspan expanded)."""
    tp = _TableParser()
    tp.feed(text)
    grids = []
    for rows in tp.tables:
        grid, pend = [], {}
        for r in rows:
            out, c = [], 0

            def take_pending():
                nonlocal c
                while c in pend:
                    txt, rem = pend[c]
                    out.append(txt)
                    if rem > 1:
                        pend[c] = (txt, rem - 1)
                    else:
                        del pend[c]
                    c += 1
            take_pending()
            for txt, cs, rs in r:
                for _ in range(cs):
                    out.append(txt)
                    if rs > 1:
                        pend[c] = (txt, rs - 1)
                    c += 1
                    take_pending()
            grid.append(out)
        grids.append(grid)
    return grids


# ----------------------------------------------------------------------------- Shanghai
SH_INDEX = "https://tjj.sh.gov.cn/tjnj/index.html"
SH_CRIME_TITLE = "公安机关立案刑事案件"
SH_POP_TITLE = "户数、人口、人口密度"


def parse_sh_crime(text: str) -> dict[int, dict]:
    """-> {year: {'total':n, 'homicide':n, 'cats':{label:n}}}; raises if the table or its arithmetic is wrong."""
    for grid in html_grids(text):
        flat = "".join(squash(c) for r in grid for c in r)
        if SH_CRIME_TITLE not in flat:
            continue
        hdr, years = None, []
        for i, r in enumerate(grid):
            ys = []
            for c in r:
                if re.fullmatch(r"(19|20)\d\d", squash(c)) and int(squash(c)) not in ys:
                    ys.append(int(squash(c)))
            if len(ys) >= 2:
                hdr, years = i, ys
                break
        if hdr is None:
            raise ValueError("crime table found but no row of year headings")
        rows = {}
        for r in grid[hdr + 1:]:
            cells = [c for c in r if squash(c) != ""]
            if len(cells) < 2:
                continue
            label, vals = squash(cells[0]), [num(c) for c in cells[1:]]
            if not re.search(r"[\u4e00-\u9fff]", label) or len(vals) != len(years) or label in rows:
                continue
            if vals == [float(y) for y in years] or label in ("类别", "项目"):         # heading row repeated by a rowspan
                continue
            rows[label] = vals
        if "总计" not in rows or "杀人" not in rows:
            raise ValueError(f"rows found: {list(rows)}; need 总计 and 杀人")
        cats = {k: v for k, v in rows.items() if k != "总计"}
        out = {}
        for j, y in enumerate(years):
            col = [v[j] for v in cats.values()]
            tot = rows["总计"][j]
            if tot is None or None in col or rows["杀人"][j] is None:
                print(f"    [sh] {y}: missing cell(s) in the crime table - year skipped")
                continue
            if abs(sum(col) - tot) > 0.5:
                print(f"    [sh] {y}: categories add up to {sum(col):,.0f} but the table's total is {tot:,.0f} - year skipped")
                continue
            out[y] = {"total": int(tot), "homicide": int(rows["杀人"][j]), "cats": {k: int(v[j]) for k, v in cats.items()}}
        if not out:
            raise ValueError("no year column passed the arithmetic check (categories must add up to the total)")
        return out
    raise ValueError("no table titled '公安机关立案刑事案件' on the page")


def parse_sh_pop(texts) -> tuple[dict[int, float], str]:
    """Year-end resident population (persons) from table 2.1. `texts` = the page and its frames: the headings and the
    year rows may sit in different frame pages (frozen-header Excel export); they are joined column by column."""
    texts = [texts] if isinstance(texts, str) else texts
    grids = [g for t in texts for g in html_grids(t)]
    is_year = lambda r: bool(r) and re.fullmatch(r"(19|20)\d\d年?", squash(r[0])) is not None
    head = None
    for g in grids:
        flat = "".join(squash(c) for r in g for c in r)
        if "常住人口" in flat and SH_POP_TITLE in flat:
            head = g
            break
    if head is None:
        raise ValueError("no population table (户数、人口、人口密度) on the page")
    first = next((i for i, r in enumerate(head) if is_year(r)), None)
    if first is None:
        hdr_rows = head
        data_rows = [r for g in grids if g is not head for r in g if is_year(r)]
        if not data_rows:
            raise ValueError("population headings found but no row starting with a year in the page or its frames")
    else:
        hdr_rows = head[:first]
        data_rows = [r for r in head[first:] if is_year(r)]
    hdr_rows = [r for r in hdr_rows if len({squash(c) for c in r if squash(c)}) > 1]       # drop merged full-width banners
    ncol = max(len(r) for r in hdr_rows)
    if any(len(r) < ncol for r in data_rows[:3]):
        raise ValueError(f"year rows have fewer columns ({len(data_rows[0])}) than the headings ({ncol}): columns cannot be aligned")
    heads = ["|".join(dict.fromkeys(squash(r[j]) for r in hdr_rows if j < len(r) and squash(r[j]))) for j in range(ncol)]
    bad = r"户籍|外来|密度|比|增|率|性别|城镇|乡村|指数|户数|每户"
    cand = [j for j, h in enumerate(heads) if "常住人口" in h and not re.search(bad, h)]
    if len(cand) != 1:
        raise ValueError("cannot identify the year-end resident population column; headers: "
                         + " || ".join(f"[{j}] {h}" for j, h in enumerate(heads)))
    j = cand[0]
    factor = 1e4 if re.search(r"万", heads[j]) else None
    if factor is None:
        raise ValueError(f"unit of the population column not recognised: header '{heads[j]}'")
    pop = {int(squash(r[0])[:4]): num(r[j]) * factor for r in data_rows if num(r[j]) is not None}
    recent = [v for y, v in pop.items() if y >= 2000]
    if not recent or not all(5e6 < v < 5e7 for v in recent):
        raise ValueError(f"population values outside the plausible range for a municipality of this size: {recent[:3]}")
    note = f"column '{heads[j]}' (unit factor {factor:,.0f})"
    # alignment identity: registered population = male + female (proves headings and year rows line up)
    hj = [k for k, h in enumerate(heads) if "户籍人口" in h and "性别" not in h]
    ml = [k for k, h in enumerate(heads) if "男" in h]
    fm = [k for k, h in enumerate(heads) if "女" in h]
    if len(hj) == 1 and len(ml) == 1 and len(fm) == 1:
        n = 0
        for r in data_rows:
            a_, m_, f_ = num(r[hj[0]]), num(r[ml[0]]), num(r[fm[0]])
            if None not in (a_, m_, f_):
                n += 1
                if abs(a_ - (m_ + f_)) > 0.03:
                    raise ValueError(f"{squash(r[0])}: registered population {a_} != male {m_} + female {f_}: columns misaligned")
        note += f"; registered = male + female in {n} year(s) (columns aligned)"
    if len(hj) == 1 and len(cand) == 1:
        wl = [k for k, h in enumerate(heads) if "外来" in h and "常住" in h]
        if len(wl) == 1:
            n = 0
            for r in data_rows:
                a_, b_, c_ = num(r[j]), num(r[hj[0]]), num(r[wl[0]])
                if None not in (a_, b_, c_):
                    n += 1
                    if abs(a_ - (b_ + c_)) > 0.02:
                        raise ValueError(f"{squash(r[0])}: resident {a_} != registered {b_} + migrant {c_}")
            note += f"; resident = registered + migrant in {n} year(s)"
    return pop, note


def sh_editions() -> list[tuple[int, str, str]]:
    """[(edition_year, url, local_name)] newest first, statistical yearbooks only (no census editions)."""
    html = decode_web(get(SH_INDEX))
    out, seen = [], set()
    for h, t in anchors(html, SH_INDEX):
        m = re.search(r"(20\d\d)\s*年\s*(.{1,6}?)统计年鉴", t)
        if m and not re.search(r"普查|经济|英文", t) and int(m.group(1)) not in seen:
            seen.add(int(m.group(1)))
            out.append((int(m.group(1)), h, m.group(2)))
    return sorted(out, reverse=True)


def sh_table_urls(edition_url: str) -> dict[str, str]:
    """Direct table pages derived from the edition's table of contents (viewer links carry d1=<year>tjnj/<code>.htm)."""
    page = decode_web(get(edition_url))
    pages = [(edition_url, page)]
    for fu in frames(page, edition_url)[:4]:                  # the contents list sits in a frame page (tjnj2025.htm)
        try:
            pages.append((fu, decode_web(get(fu))))
        except Exception as e:
            print(f"    [sh] frame {fu}: {type(e).__name__}: {e}")
    found = {}
    for base_url, html in pages:
        for h, t in anchors(html, base_url):
            d1 = parse_qs(urlparse(h).query).get("d1")
            if not d1:
                continue
            for key, title in (("crime", SH_CRIME_TITLE), ("pop", SH_POP_TITLE)):
                if title in squash(t) and key not in found:
                    found[key] = urljoin(h.split("?")[0], d1[0])
    return found


def sh_pop_from(url: str) -> tuple[dict[int, float], str]:
    """Table 2.1 is an Excel 'web page' export (frameset); gather the page and its frames and parse them together."""
    main = decode_web(get(url, "china_sh_pop"))
    texts = [main]
    for fu in frames(main, url):
        try:
            texts.append(decode_web(get(fu)))
        except Exception as e:
            print(f"    [sh] frame {fu}: {type(e).__name__}: {e}")
    try:
        return parse_sh_pop(texts)
    except ValueError:
        print(f"[sh] table 2.1: {len(texts)} page(s) fetched (main page + frames {frames(main, url)})")
        for i, t in enumerate(texts):
            for g in html_grids(t)[:1]:
                print(f"[sh]   page {i}: first rows of its table ({len(g)} rows):")
                for r in g[:4]:
                    print("        ", [c[:14] for c in r][:10])
        raise


def build_sh() -> pd.DataFrame:
    print("\n=== Shanghai ===")
    eds = sh_editions()
    if not eds:
        sys.exit("[stop] no Shanghai statistical-yearbook editions found on the index page")
    print(f"[sh] editions on the index page: {[e for e, _, _ in eds]}")
    series, pops, pop_urls, local = {}, {}, {}, ""
    for ey, eurl, loc in eds:
        local = local or loc
        urls = sh_table_urls(eurl)
        if "crime" in urls:
            try:
                tab = parse_sh_crime(decode_web(get(urls["crime"], f"china_sh_crime_{ey}")))
            except (ValueError, RuntimeError, requests.RequestException) as e:
                print(f"[sh] {ey} edition crime table: {type(e).__name__}: {e}")
                continue
            series[ey] = (tab, urls["crime"])
            print(f"[sh] {ey} edition: crime table years {sorted(tab)}; homicide {[tab[y]['homicide'] for y in sorted(tab)]}")
        else:
            print(f"[sh] {ey} edition: no table '{SH_CRIME_TITLE}' in its contents")
        if "pop" in urls and len(pops) < 2:
            try:
                pops[ey] = sh_pop_from(urls["pop"])
                pop_urls[ey] = urls["pop"]
            except (ValueError, RuntimeError, requests.RequestException) as e:
                print(f"[sh] {ey} edition population table: {type(e).__name__}: {e}")
                if not pops:
                    sys.exit("[stop] Shanghai population table layout not recognised - paste this output")
    if not series:
        sys.exit("[stop] no Shanghai edition has the criminal-case table")
    if not pops:
        sys.exit("[stop] no Shanghai population table found")
    best, pairs = merge_editions(series, "Shanghai")
    print(f"[sh] {len(best)} years from {len(series)} editions; {pairs} overlapping year(s) identical (total, homicide, shared categories)")
    newest = max(pops)
    pop, pnote = pops[newest]
    print(f"[sh] population: {newest} edition table 2.1, {pnote}")
    if len(pops) > 1:
        older = sorted(pops)[0]
        diffs = [y for y in pops[older][0] if y in pop and abs(pops[older][0][y] - pop[y]) > 150]
        print(f"[sh] population series of the {older} and {newest} editions differ in {len(diffs)} year(s)"
              + (f" (revisions, newest used): {sorted(diffs)[:8]}" if diffs else ""))
    unit = {"unit": "Shanghai", "local": local, "type": "municipality", "pop_source": f"{pop_urls[newest]} (Shanghai Statistical Yearbook {newest}, table 2.1)",
            "notes": "yearbook publishes selected years only; years assembled across editions"}
    return rate_rows(unit, best, pop, pairs, f"population: {pnote}", len(series), "A",
                     "mean of year-end resident population of Y-1 and Y (yearbook table 2.1)")


# ----------------------------------------------------------------------------- shared: link finder, rate rows
def find_link(start: str, pattern: str, root: str, max_pages: int = 18) -> tuple[str, str] | None:
    """Breadth-first search (frames, links, file names written in scripts) inside `root` for an anchor whose label matches."""
    host = urlparse(start).netloc
    queue, seen = [start], set()
    while queue and len(seen) < max_pages:
        url = queue.pop(0)
        if url in seen:
            continue
        seen.add(url)
        try:
            html = decode_web(get(url))
        except Exception:
            continue
        nxt = frames(html, url)
        for h, t in anchors(html, url):
            if re.search(pattern, squash(t)):
                return h, t
            nxt.append(h)
        nxt += [urljoin(url, u) for u in re.findall(r"""['"]([^'"\s<>]+\.html?)['"]""", html)]
        for u in nxt:
            q = urlparse(u)
            if q.netloc == host and q.path.startswith(root) and re.search(r"\.(htm|html)$", q.path, re.I) and u not in seen:
                queue.append(u)
    return None


def same_year(a: dict, b: dict) -> bool:
    """Same total, same homicide, same value in every category the two editions share (category lists may differ)."""
    if a["total"] != b["total"] or a["homicide"] != b["homicide"]:
        return False
    common = set(a["cats"]) & set(b["cats"])
    return all(a["cats"][k] == b["cats"][k] for k in common)


def merge_editions(series: dict[int, tuple[dict, str]], label: str) -> tuple[dict[int, tuple[dict, str, int]], int]:
    """{edition: ({year: values}, url)} -> {year: (values, url, edition)}; identical values required wherever a year repeats."""
    best, pairs, label_diffs = {}, 0, set()
    for ey in sorted(series, reverse=True):
        for y, d in series[ey][0].items():
            if y in best:
                pairs += 1
                if not same_year(best[y][0], d):
                    sys.exit(f"[stop] {label} {y}: editions {best[y][2]} and {ey} disagree: homicide {best[y][0]['homicide']} vs {d['homicide']}, "
                             f"totals {best[y][0]['total']} vs {d['total']}, or a shared category differs")
                if set(best[y][0]["cats"]) != set(d["cats"]):
                    label_diffs.add((best[y][2], ey))
            else:
                best[y] = (d, series[ey][1], ey)
    if label_diffs:
        print(f"[{TAGS.get(label, label.lower()[:2])}] note: the category list differs between editions {sorted(label_diffs)}; "
              f"total, homicide and all shared categories are identical")
    return best, pairs


def rate_rows(unit: dict, best: dict, pop: dict[int, float], pairs: int, pnote: str, n_editions: int, tier: str,
              method_note: str, single_read_note: str = "") -> pd.DataFrame:
    rows = []
    for y in sorted(best):
        d, url, ey = best[y]
        if y not in pop or y - 1 not in pop:
            print(f"[skip] {unit['unit']} {y}: needs year-end population for {y - 1} and {y}")
            continue
        p_mid = (pop[y - 1] + pop[y]) / 2
        n = d["homicide"]
        rows.append({
            "country": "China", "unit": unit["unit"], "unit_local": unit.get("local", ""), "admin_level": "admin1",
            "unit_type": unit["type"], "year": y, "homicide_cases": n, "population": round(p_mid),
            "homicide_rate_per_100k": n / p_mid * 1e5, "flag_low_count": n < LOW_COUNT, "flag_outlier_year": False,
            "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": tier,
            "validation": f"categories sum to the table total in every year column; {pairs} overlapping year(s) identical across "
                          f"{n_editions} editions; {pnote}" + (f"; {single_read_note}" if d.get("single_read") else "") + (f"; {d['note']}" if d.get("note") else ""),
            "indicator": f"{unit['unit']} yearbook: criminal cases recorded by the public security organs, category 杀人 (homicide)",
            "population_method": method_note, "data_notes": unit.get("notes", ""),
            "source_homicide": url, "source_population": unit.get("pop_source_by_year", {}).get(y, unit.get("pop_source", "")), "homicide_edition": ey,
            "retrieved": dt.date.today().isoformat()})
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------------- Beijing (image tables read with OCR)
BJ_EDITION = "https://nj.tjj.beijing.gov.cn/nj/main/{e}-tjnj/zk/indexch.htm"
BJ_TITLE = "公安机关刑事案件立案情况"
BJ_LINK = r"^(?!.*(?:法院|检察|审理|收、结|结案)).*刑事案件(?:立案)?情况"      # 2025-2023 editions: 公安机关刑事案件立案情况; 2022: 刑事案件情况
BJ_IMG_TITLE = r"刑事案件(?:立案)?情况"
BJ_COMMUNIQUE_LISTS = ["https://www.beijing.gov.cn/gongkai/shuju/tjgb/"]
_OCR = None


DLL_HINT = ("  Hint: 'DLL load failed' means Windows cannot load the OCR engine's library; the usual cause is the missing Microsoft "
            "Visual C++ Runtime. Install it with:  winget install -e --id Microsoft.VCRedist.2015+.x64  (then open a new PowerShell) and test "
            "with:  python -c \"import onnxruntime; print('ok')\"")


def ocr_boxes(img: bytes) -> list[tuple[float, float, float, float, str, float]]:
    """OCR boxes (x0, y0, x1, y1, text, confidence) of a table image, read in-process with rapidocr-onnxruntime."""
    global _OCR
    try:
        from rapidocr_onnxruntime import RapidOCR
    except ImportError as imp:
        sys.exit("[stop] the Beijing tables are images and need an OCR engine: pip install rapidocr-onnxruntime (a Python that onnxruntime "
                 "supports, e.g. 3.12/3.13). Import error: " + str(imp)[:160] + (DLL_HINT if "DLL" in str(imp) else ""))
    _OCR = _OCR or RapidOCR()
    res, _ = _OCR(img)
    out = []
    for box, txt, conf in (res or []):
        xs, ys = [p[0] for p in box], [p[1] for p in box]
        out.append((min(xs), min(ys), max(xs), max(ys), str(txt), float(conf)))
    return out


class NoHomicideRows(ValueError):
    """The older Beijing table (editions up to 2022) lists only cases registered (立案) and solved (破案), no categories."""
    def __init__(self, totals: dict[int, int]):
        super().__init__("table 23-4 has only total cases registered/solved (立案/破案) and no homicide row")
        self.totals = totals


def parse_bj_boxes(boxes: list) -> dict[int, dict]:
    if not re.search(BJ_IMG_TITLE, squash("".join(b[4] for b in boxes))):
        raise ValueError("title '(公安机关)刑事案件(立案)情况' not found in the image")
    mid = lambda b: (b[1] + b[3]) / 2
    total_lab = [b for b in boxes if squash(b[4]) == "刑事案件" or (squash(b[4]).startswith("刑事案件") and not re.search(BJ_IMG_TITLE, squash(b[4])))]
    if not total_lab:
        raise ValueError("row label 刑事案件 (the total) not found")
    y0 = mid(total_lab[0]) - 12
    years = sorted([b for b in boxes if re.fullmatch(r"(19|20)\d\d", b[4]) and mid(b) < y0], key=lambda b: (b[0] + b[2]) / 2)
    yrs = [int(b[4]) for b in years]
    if len(yrs) < 1 or len(set(yrs)) != len(yrs):
        raise ValueError(f"year headings not recognised: {yrs}")
    body = [b for b in boxes if mid(b) >= y0]
    nums = [b for b in body if re.fullmatch(r"\d[\d,]*", b[4])]
    if not nums:
        raise ValueError("no numbers in the table body")
    low = [b for b in nums if b[5] < OCR_MIN_CONF]
    if low:
        raise ValueError(f"OCR confidence below {OCR_MIN_CONF} for {[(b[4], round(b[5], 3)) for b in low]}")
    num_left = min(b[0] for b in nums)
    lines = []
    for b in sorted(body, key=mid):
        if lines and abs(mid(b) - lines[-1]["y"]) <= 8:
            lines[-1]["boxes"].append(b)
        else:
            lines.append({"y": mid(b), "boxes": [b]})
    rows = {}
    for ln in lines:
        vals = sorted([b for b in ln["boxes"] if re.fullmatch(r"\d[\d,]*", b[4])], key=lambda b: b[0])
        labs = sorted([b for b in ln["boxes"] if re.search(r"[\u4e00-\u9fff]", b[4]) and b[2] < num_left + 2], key=lambda b: b[0])
        label = squash("".join(b[4] for b in labs))
        if label and len(vals) == len(yrs) and label not in rows:
            rows[label] = [int(b[4].replace(",", "")) for b in vals]
    if "杀人" not in rows and "立案" in rows:
        raise NoHomicideRows({y: rows["立案"][j] for j, y in enumerate(yrs)})
    if "刑事案件" not in rows or "杀人" not in rows:
        raise ValueError(f"rows read: {list(rows)}; need 刑事案件 and 杀人")
    cats = {k: v for k, v in rows.items() if k != "刑事案件"}
    out = {}
    for j, y in enumerate(yrs):
        tot = rows["刑事案件"][j]
        sm = sum(v[j] for v in cats.values())
        if sm != tot:
            print(f"    [bj] {y}: categories add up to {sm:,} but the total reads {tot:,} - year skipped")
            continue
        out[y] = {"total": tot, "homicide": rows["杀人"][j], "cats": {k: v[j] for k, v in cats.items()}}
    if not out:
        raise ValueError("no year passed the arithmetic check")
    return out


def bj_communiqués() -> dict[int, str]:
    found = {}
    for lst in BJ_COMMUNIQUE_LISTS:
        try:
            html = decode_web(get(lst))
        except Exception as e:
            print(f"[bj] communiqué list {lst}: {type(e).__name__}: {e}")
            continue
        for h, t in anchors(html, lst):
            m = re.search(r"北京市\s*(20\d\d)\s*年国民经济和社会发展统计公报", t)
            if m and "解读" not in t:
                found.setdefault(int(m.group(1)), h)
    return found


def parse_bj_communiqué(text: str) -> float:
    """Year-end resident population (persons) from the statistical communiqué's text."""
    flat = squash(strip_tags_text(text))
    note = r"(?:\[\d+\]|［\d+］|【\d+】|（\d+）|\(\d+\))?"                       # footnote marker such as [3]
    vals = [float(x) for x in re.findall(r"常住人口" + note + r"[^0-9。；\[\]（）()]{0,15}?(\d{3,5}(?:\.\d+)?)万人", flat)]
    if not vals:                                                    # figure in a table cell without the unit; a decimal point excludes densities
        vals = [float(x) for x in re.findall(r"常住人口" + note + r"[^0-9。；\[\]（）()]{0,15}?(\d{4}\.\d{1,2})", flat)]
    vals = [v for v in vals if 1000 <= v <= 4000]
    if not vals:
        snips = [flat[max(0, m.start() - 8): m.start() + 45] for m in re.finditer("常住人口", flat)][:4]
        if not snips:
            snips = [f"(no '常住人口' in {len(flat):,} characters of text)"] + \
                    [flat[max(0, m.start() - 12): m.start() + 40] for m in re.finditer("常住|人口", flat)][:4]
        raise ValueError(f"no resident-population figure found; text around it: {snips}")
    if len(set(vals[:3])) > 1:
        raise ValueError(f"several different resident-population figures in the first statements: {vals[:3]}")
    return vals[0] * 1e4


def strip_tags_text(t: str) -> str:
    return re.sub(r"\s+", " ", htmllib.unescape(re.sub(r"<[^>]+>", " ", t)))


def check_bj_totals(best: dict, old_totals: dict[int, int]) -> int:
    """Totals of the older-layout table (cases registered) must equal the total read from the newer table, year by year."""
    n = 0
    for y, tot in sorted(old_totals.items()):
        if y in best:
            n += 1
            if best[y][0]["total"] != tot:
                sys.exit(f"[stop] Beijing {y}: total criminal cases {best[y][0]['total']:,} in the {best[y][2]} edition "
                         f"but {tot:,} cases registered in the older-layout table")
            best[y][0]["note"] = "total cases confirmed by a second (older-layout) table"
    return n


def bj_communiqué_value(url: str, year: int) -> float:
    """Resident population from a communiqué that may be split over several pages (…_2.html, …_3.html)."""
    html = decode_web(get(url, f"china_bj_communique_{year}"))
    try:
        return parse_bj_communiqué(html)
    except ValueError as first:
        stem = re.sub(r"(?:_\d+)?\.html?$", "", url)
        pages = [h for h, _ in anchors(html, url) if h.startswith(stem) and re.search(r"_\d+\.html?$", h) and h != url]
        pages += [f"{stem}_{n}.html" for n in range(2, 6) if f"{stem}_{n}.html" not in pages]
        tried = []
        for pu in dict.fromkeys(pages):
            try:
                t = decode_web(get(pu, f"china_bj_communique_{year}_p"))
            except Exception:
                continue
            tried.append(pu.rsplit("/", 1)[-1])
            try:
                return parse_bj_communiqué(t)
            except ValueError:
                continue
        raise ValueError(f"{first} | further pages tried: {tried or 'none found'}")


def build_bj() -> pd.DataFrame:
    print("\n=== Beijing ===")
    series, misses, old_totals = {}, 0, {}
    for e in range(dt.date.today().year + 1, 2017, -1):
        start = BJ_EDITION.format(e=e)
        try:
            get(start)
        except Exception:
            continue
        hit = find_link(start, BJ_LINK, f"/nj/main/{e}-tjnj/")
        if not hit:
            misses += 1
            print(f"[bj] {e} edition: contents link for table 23-4 not found")
            if misses >= 2:
                print("[bj] two editions in a row without the table link - older editions not tried (see china_probe.py to inspect them)")
                break
            continue
        misses = 0
        try:
            tab = parse_bj_boxes(ocr_boxes(get(hit[0], f"china_bj_{e}")))
        except NoHomicideRows as ex:
            old_totals.update({y: v for y, v in ex.totals.items() if y not in old_totals})
            print(f"[bj] {e} edition: {ex} (years {sorted(ex.totals)}); earlier editions use this layout, so they are not read")
            break
        except (ValueError, RuntimeError, requests.RequestException) as ex:
            print(f"[bj] {e} edition: {type(ex).__name__}: {ex}")
            continue
        series[e] = (tab, hit[0])
        print(f"[bj] {e} edition: years {sorted(tab)}; homicide {[tab[y]['homicide'] for y in sorted(tab)]}  (image {hit[0].rsplit('/', 1)[-1]})")
    if not series:
        sys.exit("[stop] no Beijing edition could be read")
    best, pairs = merge_editions(series, "Beijing")
    for y, (d, _, ey) in best.items():
        d["single_read"] = sum(1 for e in series if y in series[e][0]) == 1
    print(f"[bj] {len(best)} years from {len(series)} editions; {pairs} overlapping year(s) identical in every category")
    if old_totals:
        n_chk = check_bj_totals(best, old_totals)
        print(f"[bj] older-layout table (totals only, years {sorted(old_totals)}): {n_chk} year(s) overlap with the newer tables and agree")

    comm = bj_communiqués()
    need = sorted({y for y in best} | {y - 1 for y in best})
    pop = {}
    for y in need:
        if y in comm:
            try:
                pop[y] = bj_communiqué_value(comm[y], y)
            except ValueError as ex:
                print(f"[bj] communiqué {y}: {ex}")
    print(f"[bj] year-end resident population found for {sorted(pop)} (communiqués listed: {len(comm)})")
    if not pop:
        sys.exit("[stop] no Beijing population figure could be read from the communiqués")
    unit = {"unit": "Beijing", "local": "北京", "type": "municipality", "pop_source": BJ_COMMUNIQUE_LISTS[0],
            "pop_source_by_year": {y: f"{comm[y - 1]}; {comm[y]}" for y in best if y in comm and y - 1 in comm},
            "notes": "yearbook table is an image read by OCR with arithmetic and cross-edition checks; population has 0.1 万 resolution"}
    return rate_rows(unit, best, pop, pairs, "population = year-end resident population in the statistical communiqué", len(series), "B",
                     "mean of year-end resident population of Y-1 and Y (statistical communiqués)",
                     "newest year read from one edition only (arithmetic check)")


# ----------------------------------------------------------------------------- Jiangsu
JS_BASE = "https://tj.jiangsu.gov.cn/{e}/nj{ch}/nj{ch}{n:02d}.htm"
JS_CRIME_TITLE = "公安机关立案的刑事案件情况"
JS_POP_TITLE = "全省人口数、户数"


def parse_js_crime(text: str) -> dict[int, dict]:
    for grid in html_grids(text):
        flat = "".join(squash(c) for r in grid for c in r)
        if JS_CRIME_TITLE not in flat:
            continue
        hdr, years = None, []
        for i, r in enumerate(grid):
            ys = []
            for c in r:
                if re.fullmatch(r"(19|20)\d\d", squash(c)) and int(squash(c)) not in ys:
                    ys.append(int(squash(c)))
            if len(ys) >= 2:
                hdr, years = i, ys
                break
        if hdr is None:
            raise ValueError("no row of year headings")
        rows = {}
        for r in grid[hdr + 1:]:
            cells = [c for c in r if squash(c) != ""]
            if len(cells) < 3 or not re.search(r"[\u4e00-\u9fff]", cells[0]):
                continue
            label = squash(re.sub(r"[A-Za-z].*$", "", cells[0]))      # Chinese part of a bilingual label
            vals = []
            for c in cells[1:]:
                if re.search(r"[A-Za-z]{3}", c):                      # English label cell
                    continue
                n = num(c)
                if n is not None:
                    vals.append(n)
                elif squash(c) in ("…", "—", "-", "－"):
                    vals.append(None)
            cnt = vals[:len(years)]
            if cnt == [float(y) for y in years] or label in ("案件类别", "类别"):
                continue                                                  # heading row repeated by a rowspan
            if len(cnt) == len(years) and label not in rows:
                rows[label] = cnt
        tot_lab = next((k for k in rows if k in ("合计", "总计")), None)
        if tot_lab is None or "杀人" not in rows:
            raise ValueError(f"rows read: {list(rows)}; need 合计 and 杀人")
        cats = {k: v for k, v in rows.items() if k != tot_lab}
        out = {}
        for j, y in enumerate(years[:len(rows[tot_lab])]):
            col = [v[j] for v in cats.values()]
            tot = rows[tot_lab][j]
            if tot is None or None in col:
                print(f"    [js] {y}: missing cell(s) - year skipped")
                continue
            if abs(sum(col) - tot) > 0.5:
                print(f"    [js] {y}: categories add up to {sum(col):,.0f} but the total is {tot:,.0f} - year skipped")
                continue
            out[y] = {"total": int(tot), "homicide": int(rows["杀人"][j]), "cats": {k: int(v[j]) for k, v in cats.items()}}
        if not out:
            raise ValueError("no year passed the arithmetic check")
        return out
    raise ValueError(f"no table titled '{JS_CRIME_TITLE}' on the page")


def parse_js_pop(text: str) -> tuple[dict[int, float], str]:
    """Year-end resident population (persons) from table 3-1 '全省人口数、户数(常住)': column 总人口 (万人)."""
    for grid in html_grids(text):
        flat = "".join(squash(c) for r in grid for c in r)
        if JS_POP_TITLE not in flat or "常住" not in flat:
            continue
        first = next((i for i, r in enumerate(grid) if r and re.fullmatch(r"(19|20)\d\d年?", squash(r[0]))), None)
        if first is None:
            raise ValueError("population table found but no data row starting with a year")
        ncol = max(len(r) for r in grid)
        hdr_rows = [r for r in grid[:first] if len({squash(c) for c in r if squash(c)}) > 1]
        heads = ["|".join(dict.fromkeys(squash(r[j]) for r in hdr_rows if j < len(r) and squash(r[j]))) for j in range(ncol)]
        bad = r"户|男|女|比重|密度|平均|性别|城镇|乡村|指数|增|率"
        cand = [j for j, h in enumerate(heads) if re.search(r"常住人口|总人口", h) and not re.search(bad, h)]
        if len(cand) != 1:
            raise ValueError("cannot identify the year-end resident population column; headers: "
                             + " || ".join(f"[{j}] {h}" for j, h in enumerate(heads)))
        j = cand[0]
        factor = 1e4 if re.search(r"万|10000", heads[j]) or "万人" in flat else None
        if factor is None:
            raise ValueError(f"unit of the population column not recognised: '{heads[j]}'")
        rows = [r for r in grid[first:] if r and re.fullmatch(r"(19|20)\d\d年?", squash(r[0]))]
        pop = {int(squash(r[0])[:4]): num(r[j]) * factor for r in rows if j < len(r) and num(r[j]) is not None}
        recent = [v for y, v in pop.items() if y >= 2000]
        if not recent or not all(1e7 < v < 2e8 for v in recent):
            raise ValueError(f"population values outside the plausible range: {recent[:3]}")
        note = f"column '{heads[j]}' (unit factor {factor:,.0f})"
        av = [k for k, h in enumerate(heads) if "年平均人口" in h]                # official annual average population
        if len(av) == 1:
            devs = []
            for r in rows:
                y = int(squash(r[0])[:4])
                a = num(r[av[0]]) if av[0] < len(r) else None
                if a is not None and y in pop and y - 1 in pop:
                    devs.append(abs(a * factor - (pop[y - 1] + pop[y]) / 2))
            if devs:
                note += (f"; official 年平均人口 agrees with the mean of year-end totals within {max(devs) / 1e4:.2f} 万 "
                         f"(median {sorted(devs)[len(devs) // 2] / 1e4:.2f}) over {len(devs)} years")
        return pop, note
    raise ValueError(f"no resident-population table with '{JS_POP_TITLE}' on the page")


def js_find(e: int, ch: str, rng: range, title: str) -> tuple[str, str] | None:
    for n in rng:
        u = JS_BASE.format(e=e, ch=ch, n=n)
        try:
            t = decode_web(get(u))
        except Exception:
            continue
        if title in "".join(squash(c) for g in html_grids(t) for r in g for c in r):
            return u, t
    return None


def build_js() -> pd.DataFrame:
    print("\n=== Jiangsu ===")
    series, pops, pop_urls = {}, {}, {}
    for e in range(dt.date.today().year, 2015, -1):
        hit = js_find(e, "17", [13] + [n for n in range(8, 22) if n != 13], JS_CRIME_TITLE)
        if not hit:
            continue
        try:
            tab = parse_js_crime(hit[1])
        except ValueError as ex:
            print(f"[js] {e} edition: {ex}")
            continue
        series[e] = (tab, hit[0])
        print(f"[js] {e} edition: years {sorted(tab)}; homicide {[tab[y]['homicide'] for y in sorted(tab)]}")
        if len(pops) < 2:
            ph = js_find(e, "03", [1] + list(range(2, 8)), JS_POP_TITLE)
            if ph:
                try:
                    pops[e] = parse_js_pop(ph[1])
                    pop_urls[e] = ph[0]
                except ValueError as ex:
                    print(f"[js] {e} edition population table: {ex}")
                    if not pops:
                        g = html_grids(ph[1])
                        if g:
                            print("[js] first rows of the table (for the layout):")
                            for r in g[0][:8]:
                                print("      ", [c[:16] for c in r][:12])
                        sys.exit("[stop] Jiangsu population table layout not recognised - paste this output")
    if not series:
        sys.exit("[stop] no Jiangsu edition with the criminal-case table was found")
    best, pairs = merge_editions(series, "Jiangsu")
    print(f"[js] {len(best)} years from {len(series)} editions; {pairs} overlapping year(s) identical in every category")
    if not pops:
        sys.exit("[stop] no Jiangsu population table found")
    newest = max(pops)
    pop, pnote = pops[newest]
    print(f"[js] population: {newest} edition table 3-1, {pnote}")
    unit = {"unit": "Jiangsu", "local": "江苏", "type": "province", "pop_source": f"{pop_urls[newest]} (Jiangsu Statistical Yearbook {newest}, table 3-1)",
            "notes": "13 categories incl. drug offences, snatching and credit-card fraud; 杀人 as published"}
    return rate_rows(unit, best, pop, pairs, f"population = {pnote}", len(series), "A",
                     "mean of year-end resident population of Y-1 and Y (yearbook table 3-1)")


UNITS = {"hk": build_hk, "sh": build_sh, "bj": build_bj, "js": build_js}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--units", nargs="*", default=list(UNITS), choices=list(UNITS))
    a = ap.parse_args()
    parts, failed = [], []
    for u in a.units:
        try:
            parts.append(UNITS[u]())
        except SystemExit as e:
            print(f"\n[unit {u}] STOPPED: {e}")
            failed.append(u)
        except Exception as e:                                       # unexpected: report, keep the other units
            print(f"\n[unit {u}] FAILED unexpectedly: {type(e).__name__}: {e}")
            failed.append(u)
    parts = [p for p in parts if not p.empty]
    if not parts:
        sys.exit("[stop] no unit produced data")
    df = F.add_outlier_flags(pd.concat(parts, ignore_index=True))
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[{TAGS.get(r.unit, r.unit.lower()[:2])}] statistical outlier: {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    df = F.finalize(df)
    F.require_valid(df, "china")
    show = df[["unit", "year", "homicide_cases", "population", "homicide_rate_per_100k", "flag_low_count"]].copy()
    show["homicide_rate_per_100k"] = show["homicide_rate_per_100k"].round(3)
    print("\n" + show.to_string(index=False))
    if failed:
        print(f"\nUnits that stopped (not in the output): {failed}")
    print("\nNote: more mainland units are being added as their table layouts are confirmed.")
    if a.cmd == "build":
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows)")
    else:
        print("\n[inspect only] no CSV written")


if __name__ == "__main__":
    main()