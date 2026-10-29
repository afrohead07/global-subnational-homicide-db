#!/usr/bin/env python3
"""
South Korea - police-recorded murder (살인) cases per 100,000 residents, by city / county.

NUMERATOR   (official): National Police Agency, "Violent crime occurrence by police station" (data.go.kr dataset 15084592; one
            row per police station, column 살인 = murder). The download link is read from the dataset page. The portal offers
            only the newest annual release, so every release is kept in the raw folder under its own year and all saved years
            are used (copy older files in: korea_police_station_violent_crime_<year>[_<date>].csv).
DENOMINATOR (official): Ministry of the Interior and Safety (MOIS) resident-registration population by city / county / district,
            June of the crime year (mid-year), residents with a clear residence (거주자), requested exactly as the MOIS
            website's own "csv 파일 다운로드" button does (a form POST after a normal page visit).
MATCHING    Station names are <province><local name>서. Stations are grouped into cities from the MOIS list itself:
            metropolitan cities (Seoul, Busan, Daegu, Incheon, Gwangju, Daejeon, Ulsan, Sejong): all stations under the prefix ->
            the whole city; other provinces: the local name is matched to a city/county name; stations named after a district
            (e.g. 분당, 일산, 마산, 진해) are matched through the district names in the MOIS list; Jeju's 동부/서부 stations go
            to Jeju City; anything not matched is reported and dropped. Units under 100,000 residents are dropped.
            Police station areas may not coincide with city boundaries.
NAMES       English names are the Revised Romanization of the official Korean names (the government standard); `unit_local` keeps
            the Korean name so every entry can be checked. `unit_code` is the official 10-digit administrative code that MOIS
            prints next to the name (blank for a unit that MOIS lists only through its districts).
DEFINITION  The police 'murder' series (살인) of the five major crimes. The police's own statistical note (published, for example, by the Gyeonggi Nambu Police Agency, and consistent with the national indicator portal's
            remark that the domestic standard, unlike the international one, includes attempts and conspiracy) says it comprises homicide, infanticide, patricide, request/consent killing, instigating or aiding
            suicide and killing by deceit, force or request, INCLUDING attempts, instigation, aiding and preparation: the flag includes_attempts is set (checked 2026-10-27). The dataset used here (15084592) is
            provided by the same division of the National Police Agency as the five-crimes series; the definition is applied to it by that identity of source.
CHECKS      Per year: every police station is accounted for (in the output + in units under 100,000 residents + unmatched);
            the units in the output hold X of the national murder column; MOIS city totals equal the sum of their districts.
            The text in `validation` is built from these results. Tier B for every row: one source and an approximate station -> city grouping;
            every row names its station-matching rule in `data_notes` (a match by the first two letters of a district is the weakest).

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/South Korea/ ; the one output is
            south_korea_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python south_korea_homicide_rate.py build | inspect (shows the files as read and the station -> unit table)
Options:    --no-download   use only the files already in the raw folder
If the police file ever needs a manual download, save it in the raw folder as korea_police_station_violent_crime_<year>.csv
Needs:      pip install pandas requests korean-romanizer
"""
import argparse
import csv
import datetime as dt
import io
import re
import sys
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 7:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

P = F.paths(__file__, "South Korea")     # raw downloads -> Data/Raw/<Region>/South Korea/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=3)
LOW_COUNT, MIN_POP = F.LOW_COUNT, F.MIN_POP

POLICE_PAGE = "https://www.data.go.kr/data/15084592/fileData.do"
MOIS_PAGE = "https://jumin.mois.go.kr/statMonth.do"
MOIS_DOWNLOAD = "https://jumin.mois.go.kr/downloadCsv.do"
MIN_MOIS_ROWS = 100       # a MOIS file with fewer rows than this is not the full list of cities / counties / districts (the real one has 250+)
POP_MONTH = "06"          # DECISION: mid-year
REGISTRATION = "Y"        # MOIS: Y = residents with a clear residence ('' = all incl. overseas nationals)
POLICE_PREFIX = "korea_police_station_violent_crime_"

SIDO = {   # station-name prefix -> acceptable starts of the MOIS province/metro-city name
    "서울": ["서울"], "부산": ["부산"], "대구": ["대구"], "인천": ["인천"], "광주": ["광주"], "대전": ["대전"],
    "울산": ["울산"], "세종": ["세종"], "경기": ["경기"], "강원": ["강원"], "충북": ["충청북", "충북"],
    "충남": ["충청남", "충남"], "전북": ["전북", "전라북"], "전남": ["전남", "전라남"], "경북": ["경상북", "경북"],
    "경남": ["경상남", "경남"], "제주": ["제주"],
}
METRO_ENDINGS = ("특별시", "광역시", "특별자치시")


# ---------- helpers ----------
def decode(raw):
    for enc in ("utf-8-sig", "cp949"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", "replace")


def num(s):
    s = str(s).replace(",", "").strip()
    return int(s) if re.fullmatch(r"\d+", s) else None


# ---------- police file (data.go.kr) ----------
def read_police_text(text, label):
    df = pd.read_csv(io.StringIO(text))
    df.columns = [c.strip() for c in df.columns]
    need = {"발생년도": "year", "경찰서": "station", "살인": "murders"}
    if not set(need) <= set(df.columns):
        sys.exit(f"Police file ({label}): expected columns {list(need)}, found {list(df.columns)}")
    df = df.rename(columns=need)[["year", "station", "murders"]]
    df["station"] = df["station"].astype(str).str.strip()
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype("Int64")
    df["murders"] = pd.to_numeric(df["murders"], errors="coerce")
    if df.isna().any().any():
        sys.exit(f"Police file ({label}): missing or non-numeric values:\n{df[df.isna().any(axis=1)].head()}")
    if df.duplicated(["year", "station"]).any():
        sys.exit(f"Police file ({label}): duplicate station rows.")
    df["murders"] = df["murders"].astype(int)
    return df


def police_files():
    """{year: (date, path)} - the newest saved file of each year (date from its name, else the file's modification date)."""
    best = {}
    for f in RAW.glob(POLICE_PREFIX + "*.csv"):
        m = re.fullmatch(re.escape(POLICE_PREFIX) + r"(20\d\d)(?:_(\d{8}))?\.csv", f.name)
        if not m:
            continue
        d = dt.datetime.strptime(m.group(2), "%Y%m%d").date() if m.group(2) else dt.date.fromtimestamp(f.stat().st_mtime)
        y = int(m.group(1))
        if y not in best or d >= best[y][0]:
            best[y] = (d, f)
    return best


def police_download():
    page = decode(FETCH.get(POLICE_PAGE))                  # the dataset page: listing, never saved
    links = re.findall(r"""["']([^"'\s]*fileDownload\.do\?atchFileId=FILE_\d+[^"'\s]*)["']""", page)
    if not links:
        fid = re.findall(r"(FILE_\d{9,})", page)
        if not fid:
            print("[police] no download link found in the dataset page; use a manually downloaded file if present.")
            return
        links = [f"/cmm/cmm/fileDownload.do?atchFileId={fid[0]}&fileDetailSn=1&insertDataPrcus=N"]
    try:
        data = FETCH.get(urljoin(POLICE_PAGE, links[0]), reject_html=True)
    except RuntimeError as e:
        print(f"[police] the portal did not return the file ({e}); download it by hand and save it in {RAW} as "
              f"{POLICE_PREFIX}<year>.csv")
        return
    df = read_police_text(decode(data), "downloaded file")
    RAW.mkdir(parents=True, exist_ok=True)
    for year, g in df.groupby("year"):
        payload = data if df["year"].nunique() == 1 else g.to_csv(index=False).encode("utf-8-sig")
        saved = police_files().get(int(year))
        if saved and saved[1].read_bytes() == payload:
            print(f"[police] {int(year)}: identical to the saved {saved[1].name}; nothing new")
            continue
        p = RAW / f"{POLICE_PREFIX}{int(year)}_{dt.date.today():%Y%m%d}.csv"
        p.write_bytes(payload)
        print(f"[police] saved {p.name} ({len(g)} stations, national murder column = {int(g['murders'].sum())})")


def police_all():
    files = police_files()
    if not files:
        sys.exit(f"No police file in {RAW} ({POLICE_PREFIX}<year>.csv).")
    frames = [read_police_text(decode(f.read_bytes()), f.name) for _, (_, f) in sorted(files.items())]
    df = pd.concat(frames, ignore_index=True)
    df = df[df["year"].isin(list(files))].copy()           # each file counts only for the year in its name
    return df, {y: d.isoformat() for y, (d, _) in files.items()}


# ---------- MOIS population ----------
def mois_csv(year):
    """The MOIS CSV of June `year`, as the website's own download button requests it; a saved copy is reused."""
    data = {   # the same fields as the page's own download form (formXlsDown)
        "sltOrgType": "1", "sltOrgLvl1": "A", "sltOrgLvl2": "", "gender": "gender", "genderPer": "genderPer",
        "generation": "generation", "sltUndefType": REGISTRATION, "searchYearStart": str(year),
        "searchMonthStart": POP_MONTH, "searchYearEnd": str(year), "searchMonthEnd": POP_MONTH,
        "sltOrderType": "1", "sltOrderValue": "ASC", "category": "month", "state": "2",
    }
    try:
        raw = FETCH.post(f"{MOIS_DOWNLOAD}?searchYearMonth=month&xlsStats=2", data, name=f"korea_mois_population_sigungu_{year}{POP_MONTH}",
                         reuse=True, suffix=".csv", reject_html=True,
                         headers={"Referer": MOIS_PAGE, "Origin": "https://jumin.mois.go.kr"}, warmup=MOIS_PAGE)
    except RuntimeError as e:
        sys.exit(f"[stop] MOIS did not return the population CSV for {year} ({e}). Save it from {MOIS_PAGE} (csv download, June {year}) in {RAW} "
                 f"as korea_mois_population_sigungu_{year}{POP_MONTH}_<YYYYMMDD>.csv")
    return raw, FETCH.last_date


def parse_mois(text, year):
    """-> {name: (population, code or '')}. Real MOIS layout: header '행정구역', '<year>년<mm>월_거주자 인구수', '..._세대수', ...;
    names carry their code in brackets, e.g. '서울특별시  (1100000000)'. Older/other layouts with a
    '행정기관' name column and a '총 인구수' column are accepted too."""
    rows = [[c.strip() for c in r] for r in csv.reader(io.StringIO(text))]
    is_name_hdr = lambda c: ("행정구역" in c or "행정기관" in c) and "코드" not in c
    hi = next((i for i, r in enumerate(rows[:10]) if any(is_name_hdr(c) for c in r)), None)
    if hi is None:
        sys.exit("MOIS CSV: name header ('행정구역') not found. First rows:\n" + "\n".join(str(r)[:140] for r in rows[:5]))
    name_col = next(j for j, c in enumerate(rows[hi]) if is_name_hdr(c))
    pop_col, start = None, None
    for i in range(hi, min(hi + 3, len(rows))):
        for j, c in enumerate(rows[i]):
            if j > name_col and "인구" in c and not any(x in c for x in ("남자", "여자", "세대당", "비율", "세대수")):
                pop_col, start = j, i + 1
                break
        if pop_col is not None:
            break
    if pop_col is None:
        sys.exit("MOIS CSV: population column not found. Header: " + str(rows[hi])[:300])
    period = " ".join(" ".join(r) for r in rows[hi:start])
    if f"{year}년" not in period.replace(" ", ""):
        print(f"[warn] MOIS CSV header does not mention {year}: {period[:140]!r}")
    print(f"[mois] using column {rows[start - 1][pop_col]!r}")
    out = {}
    for r in rows[start:]:
        if len(r) <= max(name_col, pop_col):
            continue
        code = re.search(r"\(\s*(\d{8,10})\s*\)", r[name_col])
        name = re.sub(r"\s+", " ", re.sub(r"\(\s*\d+\s*\)", "", r[name_col])).strip()
        pop = num(r[pop_col])
        if name and pop is not None:
            out[name] = (pop, code.group(1) if code else "")
    if len(out) < MIN_MOIS_ROWS:
        sys.exit(f"MOIS CSV: only {len(out)} rows parsed; expected at least {MIN_MOIS_ROWS} cities/counties/districts.")
    return out


def build_units(pop_by_name):
    """-> (units {name: {sido, pop, code}}, cities {sido: {city: [gu,...]}}, mismatches [..]) from the MOIS names.
    Metropolitan cities are one unit; in provinces each city/county is a unit."""
    l1, l2, l3 = {}, {}, {}
    for name, pc in pop_by_name.items():
        t = name.split()
        if len(t) == 1:
            l1[t[0]] = pc
        elif len(t) == 2:
            l2[(t[0], t[1])] = pc
        elif len(t) == 3:
            l3[(t[0], t[1], t[2])] = pc
    units, cities, mismatches = {}, {}, []
    sidos = set(l1) | {k[0] for k in l2} | {k[0] for k in l3}
    for s in sorted(sidos):
        if s.endswith(METRO_ENDINGS):
            if s in l1:
                units[s] = {"sido": s, "pop": l1[s][0], "code": l1[s][1]}
            else:
                pop = sum(v[0] for k, v in l2.items() if k[0] == s)
                if pop:
                    units[s] = {"sido": s, "pop": pop, "code": ""}
            continue
        cs = {k[1] for k in l2 if k[0] == s} | {k[1] for k in l3 if k[0] == s}
        for c in sorted(cs):
            kids = {k[2]: v[0] for k, v in l3.items() if k[0] == s and k[1] == c}
            own = l2.get((s, c))
            if own is not None and kids and own[0] != sum(kids.values()):
                mismatches.append(f"{s} {c}: total {own[0]:,} != sum of its districts {sum(kids.values()):,}")
                print(f"[warn] MOIS: {mismatches[-1]}")
            pop = own[0] if own is not None else sum(kids.values())
            units[f"{s} {c}"] = {"sido": s, "pop": pop, "code": own[1] if own is not None else ""}
            cities.setdefault(s, {})[c] = list(kids)
    return units, cities, mismatches


# ---------- English names: Revised Romanization of Korean (the government standard) ----------
def _pronounce_liquid(text):
    """Apply the standard rule the romanizer library misses: ㄹ after ㅇ/ㅁ becomes ㄴ (강릉 -> 강능),
    and after ㄱ/ㅂ both change (백리 -> 뱅니)."""
    cs = [ord(c) for c in text]
    for i in range(1, len(cs)):
        a, b = cs[i - 1] - 0xAC00, cs[i] - 0xAC00
        if not (0 <= a < 11172 and 0 <= b < 11172) or b // 588 != 5:      # next initial must be ㄹ
            continue
        jong = a % 28
        if jong in (21, 16):                                              # ㅇ, ㅁ
            cs[i] = 0xAC00 + 2 * 588 + b % 588
        elif jong in (1, 17):                                             # ㄱ, ㅂ
            cs[i - 1] = 0xAC00 + (a - jong) + (21 if jong == 1 else 16)
            cs[i] = 0xAC00 + 2 * 588 + b % 588
    return "".join(chr(c) for c in cs)


def romanize(ko):
    try:
        from korean_romanizer.romanizer import Romanizer
    except ImportError:
        sys.exit("[stop] English names need the romanizer:  python -m pip install korean-romanizer")
    return Romanizer(_pronounce_liquid(ko)).romanize().title().replace(" ", "")


def english_names(unit_ko, sido_ko):
    """-> (unit_en, sido_en, unit_type). Suffixes (특별시/광역시/시/군/도) are removed from the English name."""
    sido_stem = re.sub(r"(특별자치도|특별자치시|특별시|광역시|도)$", "", sido_ko)
    sido_en = romanize(sido_stem)
    if unit_ko == sido_ko and sido_ko.endswith(METRO_ENDINGS):
        return sido_en, sido_en, "metropolitan_city"
    local = unit_ko.split()[-1]
    kind = "county" if local.endswith("군") else "city"
    return romanize(local[:-1] if local[-1] in "시군" else local), sido_en, kind


# ---------- station -> city ----------
def stem(name):
    return name[:-1] if name and name[-1] in "시군구" else name


def station_unit(station, units, cities):
    """-> (unit name or None, how)."""
    n = station[:-1] if station.endswith("서") else station
    abbr = next((a for a in SIDO if n.startswith(a)), None)
    if abbr is None:
        return None, "no province prefix"
    sidos = [s for s in {u["sido"] for u in units.values()} | set(cities)
             if any(s.startswith(p) for p in SIDO[abbr])]
    if len(sidos) != 1:
        return None, f"province '{abbr}' not found uniquely in the MOIS list ({sidos})"
    sido = sidos[0]
    if sido.endswith(METRO_ENDINGS):
        return (sido, "metropolitan city") if sido in units else (None, "metro city missing from MOIS list")
    local = n[len(abbr):]
    cs = cities.get(sido, {})
    best = max((c for c in cs if local.startswith(stem(c))), key=lambda c: len(stem(c)), default=None)
    if best:
        return f"{sido} {best}", "city name"
    hits = {c for c, gus in cs.items() for g in gus if local.startswith(stem(g))}
    if len(hits) == 1:
        return f"{sido} {hits.pop()}", "district name"
    hits = {c for c, gus in cs.items() for g in gus if len(local) >= 2 and stem(g).startswith(local[:2])}
    if len(hits) == 1:
        return f"{sido} {hits.pop()}", "district name (first 2 letters)"
    same = [c for c in cs if stem(c) == abbr]
    if len(same) == 1:
        return f"{sido} {same[0]}", "province-named city"
    return None, "no city/county matched"


# ---------- commands ----------
def load(args):
    if not args.no_download:
        police_download()
    police, police_dates = police_all()
    pops, pop_dates = {}, {}
    for y in sorted(police["year"].unique()):
        raw, d = mois_csv(int(y))
        pops[int(y)] = parse_mois(decode(raw), int(y))
        pop_dates[int(y)] = d
    return police, police_dates, pops, pop_dates


def cmd_build(args):
    police, police_dates, pops, pop_dates = load(args)
    rows, dropped = [], []
    for year, g in police.groupby("year"):
        year = int(year)
        units, cities, mismatches = build_units(pops[year])
        g = g.copy()
        res = [station_unit(s, units, cities) for s in g["station"]]
        g["unit"], g["how"] = [r[0] for r in res], [r[1] for r in res]
        bad = g[g["unit"].isna()]
        for _, r in bad.iterrows():
            dropped.append((year, r["station"], int(r["murders"]), r["how"]))
        n_small = 0
        agg = g.dropna(subset=["unit"]).groupby("unit").agg(murders=("murders", "sum"), n_stations=("station", "size"),
                                                           how=("how", lambda s: "; ".join(sorted(set(s)))))
        year_rows = []
        for unit, a in agg.iterrows():
            pop = units[unit]["pop"]
            if pop < MIN_POP:
                dropped.append((year, unit, int(a.murders), f"population {pop:,} < {MIN_POP:,}"))
                n_small += int(a.n_stations)
                continue
            unit_en, sido_en, kind = english_names(unit, units[unit]["sido"])
            metro = kind == "metropolitan_city"
            year_rows.append({
                "country": "South Korea", "unit": unit_en, "unit_local": unit, "unit_code": units[unit]["code"],
                "admin_level": "admin1" if metro else "admin2", "unit_type": kind, "parent_unit": "" if metro else sido_en,
                "year": year, "homicide_cases": int(a.murders), "population": int(pop),
                "homicide_rate_per_100k": int(a.murders) / int(pop) * 1e5, "flag_low_count": int(a.murders) < LOW_COUNT,
                "flag_outlier_year": False, "population_age_years": 0.0, "indicator_type": "police_recorded_cases",
                "reliability_tier": "B", "definition_flags": "includes_attempts",
                "n_stations": int(a.n_stations), "match_type": a.how})
        total = int(g["murders"].sum())
        kept = sum(r["homicide_cases"] for r in year_rows)
        n_out = len(g) - len(bad) - n_small
        acct = (f"{len(g)} police stations = {n_out} in the output + {n_small} in units under {MIN_POP:,} residents + {len(bad)} unmatched")
        cover = f"the units in the output hold {kept} of the national murder column's {total} ({kept / total:.1%})" if total else "no murders in the file"
        mois = ("MOIS city totals equal the sum of their districts in every city" if not mismatches
                else f"MOIS city totals differ from the sum of their districts in {len(mismatches)} cities")
        print(f"[{year}] {len(g)} stations, national murder column {total}")
        print(f"[accounting] {year}: {acct}\n[coverage] {year}: {cover}")
        if len(bad):
            print(f"[UNMATCHED] {year}: " + "; ".join(f"{r['station']} ({r['how']})" for _, r in bad.iterrows()))
        d_pol, d_pop = police_dates[year], pop_dates[year]
        for r in year_rows:
            r.update({
                "validation": f"{acct}; {cover}; {mois}",
                "indicator": "National Police Agency homicide (살인) cases by police station (data.go.kr 15084592), summed over the stations of the unit; the police definition includes infanticide, patricide, consent killing, aiding suicide, and attempts, instigation and preparation",
                "population_method": f"MOIS resident-registration population of June {year} (mid-year), residents with a clear residence (거주자)",
                "data_notes": f"stations are grouped into the unit by name ({r['match_type']}); police station areas may not coincide with the unit's boundary; "
                              f"the police definition of 살인 includes attempts, instigation, aiding and preparation (flag includes_attempts)",
                "source_homicide": POLICE_PAGE, "source_population": f"{MOIS_PAGE} (CSV via {MOIS_DOWNLOAD}, June {year})",
                "retrieved": min(d_pol, d_pop)})
        rows.extend(year_rows)
    df = pd.DataFrame(rows)
    if df.empty:
        sys.exit("[stop] no unit could be built")
    if dropped:
        print(f"\n[dropped] {len(dropped)} stations/units (year, name, murders, reason):")
        for d in sorted(dropped, key=lambda x: -x[2])[:25]:
            print("   ", d)
        if len(dropped) > 25:
            print(f"    ... and {len(dropped) - 25} more (mostly counties under {MIN_POP:,} residents)")
    df = F.add_outlier_flags(df)
    for _, r in df[df.flag_outlier_year].iterrows():
        print(f"[korea] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
    if df["robust_z"].isna().all():
        df = df.drop(columns="robust_z")
    df = F.finalize(df)
    F.require_valid(df, "korea")
    print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    print(df[["unit", "unit_local", "parent_unit", "year", "homicide_cases", "population", "homicide_rate_per_100k"]].round(2).to_string(index=False))
    F.write_csv(df, OUT)
    print(f"\n[ok] wrote {OUT}  ({len(df)} rows, {df.groupby(['parent_unit', 'unit']).ngroups} units, years {sorted(df.year.unique())})")


def cmd_inspect(args):
    police, _, pops, _ = load(args)
    print("\nPolice file head:\n", police.head(8).to_string(index=False))
    for y, p in pops.items():
        print(f"\nMOIS {y}-{POP_MONTH}: {len(p)} rows; first rows:")
        for k, (v, c) in list(p.items())[:8]:
            print(f"   {k} [{c}]: {v:,}")
        units, cities, _ = build_units(p)
        print(f"   units: {len(units)} (metropolitan cities: {sorted(u for u in units if u.endswith(METRO_ENDINGS))})")
        print(f"   station -> unit table ({y}):")
        for _, r in police[police.year == y].iterrows():
            u, how = station_unit(r["station"], units, cities)
            print(f"      {r['station']:14s} -> {u or 'UNMATCHED':26s} [{how}]")
    print("\n[inspect only] no CSV written")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="build", choices=["build", "inspect"])
    ap.add_argument("--no-download", action="store_true", help="use only the files already in the raw folder")
    a = ap.parse_args()
    cmd_build(a) if a.cmd == "build" else cmd_inspect(a)