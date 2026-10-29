#!/usr/bin/env python3
"""
Japan - police-recorded homicide (殺人) cases per 100,000 residents, 47 prefectures.

NUMERATOR   (official): National Police Agency (NPA), 犯罪統計 確定値, Table 6 "重要犯罪・重要窃盗犯
            都道府県別 認知・検挙件数・検挙人員", block （殺人）, column 認知件数 (cases recognised by the
            police), one CSV per year on e-Stat. Cases, not victims. Attempts are counted with the completed offence
            (the Statistics Bureau's Japan Statistical Yearbook, ch. 28, describing the police crime statistics:
            未遂罪及び予備罪は、殺人予備罪を除き、それぞれの既遂の罪に含める), hence definition_flags = includes_attempts.
DENOMINATOR (official): Ministry of Internal Affairs (MIC), 住民基本台帳に基づく人口、人口動態及び世帯数,
            [総計] prefecture table, population on 1 January (Japanese + foreign residents).
            Rate for year Y uses the mean of 1-Jan-Y and 1-Jan-(Y+1) (mid-year proxy).
CHECKS      Table-6 total = Table-1 national total = sum of the 47 prefectures; every police-region and Hokkaido sub-area
            total equals the sum of its rows; the NEXT year's file repeats this year's values in its "previous-year" column
            (a mismatch is a revision: those prefecture-years drop to tier B and the note gives both values); population:
            the 47 prefectures sum exactly to the national row, the 1-January label inside the sheet must match the year.
            The text in `validation` is built from these results, not typed.
UNIT CODE   The official 6-digit local-government code of each prefecture is read from the MIC sheet (団体コード).
CROSS-CHECK (--crosscheck) prints police cases against the health ministry's homicide deaths (他殺, vital statistics,
            by residence). It is a diagnostic only, never used for the rates: in Tokyo the health series records ~4x fewer
            deaths than the national police-cases-per-death ratio implies (2023: 6 deaths vs 94 cases).

Folders:    this script sits in <repo>/Pipelines/Asia/ ; downloads go to <repo>/Data/Raw/Asia/Japan/ ; the one output is
            japan_homicide_rate.csv next to the script (format: Pipelines/FORMAT.md, enforced by homicide_format.py).
Commands:   python japan_homicide_rate.py inspect | build
Options:    --years 2022 2023 ... (default: 2022 up to last year)  --refresh (download again instead of reusing saved files)
            --npa-sid 2021=<statInfId>  --mic-url 2025=<url>  --crosscheck
Needs:      pip install pandas requests openpyxl xlrd
"""
from __future__ import annotations
import argparse, csv, datetime as dt, html as htmllib, io, re, sys, unicodedata
from pathlib import Path
from urllib.parse import urljoin
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # output format, folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 6:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version")

# ----------------------------------------------------------------------------- paths / constants
P = F.paths(__file__, "Japan")          # raw downloads -> Data/Raw/<Region>/Japan/ ; the one output -> next to this script
RAW, OUT = P.raw, P.out
FETCH = F.Fetcher(RAW)
MIN_POP, LOW_COUNT = F.MIN_POP, F.LOW_COUNT
ATTEMPTS_SOURCE = "https://www.stat.go.jp/data/nenkan/70nenkan/zenbun/jp70/book/pageindices/index695.html"
FIRST_VERIFIED_YEAR = 2022   # the NPA table layout was verified on the 2022-2025 files; older years can be tried with --years
CAUSE_CODE, CAUSE_LABEL = "20300", "他殺"          # label as printed in the MHLW table
TOTAL_CODE, TOTAL_LABEL = "00000", "総数"

ESTAT = "https://www.e-stat.go.jp"
MHLW_TITLE = "死亡数，死因（死因簡単分類）・性・都道府県（特別区－指定都市再掲）別"
MHLW_LIST = (ESTAT + "/stat-search/files?page=1&layout=datalist&cycle=7&year={y}0&month=0"
             "&toukei=00450011&tstat=000001028897&tclass1=000001053058&tclass2=000001053061"
             "&tclass3=000001053065&result_back=1&tclass4val=0")
MHLW_PINNED = {2023: "000040206180"}      # read from the e-Stat listing page for 2023
CSV_URL = ESTAT + "/stat-search/file-download?statInfId={sid}&fileKind=1"
XLS_URL = ESTAT + "/stat-search/file-download?statInfId={sid}&fileKind=0"

MIC_INDEX = "https://www.soumu.go.jp/main_sosiki/jichi_gyousei/daityo/jinkou_jinkoudoutai-setaisuu.html"
MIC_MANUAL_PREF = {2026: "https://www.soumu.go.jp/main_content/000892948.xlsx"}   # link on the MIC page
MIC_PRESS = ["https://www.soumu.go.jp/menu_news/s-news/01gyosei02_02000389.html",   # 令和7年1月1日現在
             "https://www.soumu.go.jp/menu_news/s-news/01gyosei02_02000428.html"]   # 令和8年1月1日現在
MIC_LISTS = [ESTAT + "/stat-search/files?page=1&layout=datalist&toukei=00200241&tstat=000001039591&cycle=7&year={y}0&month=0&result_back=1",
             ESTAT + "/stat-search/files?layout=dataset&toukei=00200241&tstat=000001039591&cycle=7&year={y}0&month=0",
             ESTAT + "/stat-search/files?toukei=00200241&tstat=000001039591&cycle=7&year={y}0"]

NPA_LIST = "https://www.e-stat.go.jp/stat-search/files?toukei=00130001&page={p}"
NPA_TSTAT = ("https://www.e-stat.go.jp/stat-search/files?page=1&layout=datalist&toukei=00130001"
             "&tstat={t}&cycle=0&tclass1val=0")          # per-dataset page that shows the CSV link
NPA_PINNED = {2022: "000040015380"}       # statInfId read from the e-Stat page for 令和4年 確定値
# dataset ids (tstat) of annual final-value releases seen on e-Stat listings; others are discovered
NPA_TSTAT_PINNED = {2015: "000001079595", 2016: "000001095455", 2017: "000001112156",
                    2022: "000001201280", 2023: "000001214060", 2024: "000001225741"}

PREFS = [("北海道", "Hokkaido"), ("青森県", "Aomori"), ("岩手県", "Iwate"), ("宮城県", "Miyagi"), ("秋田県", "Akita"),
         ("山形県", "Yamagata"), ("福島県", "Fukushima"), ("茨城県", "Ibaraki"), ("栃木県", "Tochigi"), ("群馬県", "Gunma"),
         ("埼玉県", "Saitama"), ("千葉県", "Chiba"), ("東京都", "Tokyo"), ("神奈川県", "Kanagawa"), ("新潟県", "Niigata"),
         ("富山県", "Toyama"), ("石川県", "Ishikawa"), ("福井県", "Fukui"), ("山梨県", "Yamanashi"), ("長野県", "Nagano"),
         ("岐阜県", "Gifu"), ("静岡県", "Shizuoka"), ("愛知県", "Aichi"), ("三重県", "Mie"), ("滋賀県", "Shiga"),
         ("京都府", "Kyoto"), ("大阪府", "Osaka"), ("兵庫県", "Hyogo"), ("奈良県", "Nara"), ("和歌山県", "Wakayama"),
         ("鳥取県", "Tottori"), ("島根県", "Shimane"), ("岡山県", "Okayama"), ("広島県", "Hiroshima"), ("山口県", "Yamaguchi"),
         ("徳島県", "Tokushima"), ("香川県", "Kagawa"), ("愛媛県", "Ehime"), ("高知県", "Kochi"), ("福岡県", "Fukuoka"),
         ("佐賀県", "Saga"), ("長崎県", "Nagasaki"), ("熊本県", "Kumamoto"), ("大分県", "Oita"), ("宮崎県", "Miyazaki"),
         ("鹿児島県", "Kagoshima"), ("沖縄県", "Okinawa")]
EN = dict(PREFS)
KEY: dict[str, str] = {}                      # name as printed in a file -> canonical ja name
for ja, _ in PREFS:
    KEY[ja] = ja
    KEY.setdefault(ja if ja == "北海道" else ja[:-1], ja)


# ----------------------------------------------------------------------------- helpers
def norm(s) -> str:
    """NFKC + strip every kind of whitespace (full-width spaces are used as padding in the files)."""
    if s is None or (isinstance(s, float) and pd.isna(s)):
        return ""
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", str(s)))


def get(url: str, name: str | None = None, refresh=False, kind="bin", suffix: str | None = None) -> bytes:
    """kind='html' (listing pages): downloaded every run, never saved. Data files: saved date-stamped in the raw folder and reused
    on later runs unless --refresh; an HTML page where a data file is expected is refused."""
    if kind == "html":
        return FETCH.get(url)
    return FETCH.get(url, name, reuse=not refresh, suffix=suffix, reject_html=True)


def find_anchor_id(html: str, title: str) -> str | None:
    """Return the e-Stat statInfId of the listing row whose title contains `title`."""
    want = norm(title)
    for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, inner = m.groups()
        if want in norm(re.sub(r"<[^>]+>", "", inner)):
            mm = re.search(r"stat_infid=(\d+)", href, re.I) or re.search(r"statInfId=(\d+)", href)
            if mm:
                return mm.group(1)
    return None


def era_year(text: str) -> int | None:
    m = re.search(r"(令和|平成)(元|\d+)年", norm(text))
    if not m:
        return None
    n = 1 if m.group(2) == "元" else int(m.group(2))
    return (2018 if m.group(1) == "令和" else 1988) + n


def to_int(x):
    t = norm(x).replace(",", "")
    if t in ("-", "－", "―"):
        return 0                                # "-" = no deaths in this cell
    return int(t) if re.fullmatch(r"\d+", t) else None


# ----------------------------------------------------------------------------- health ministry deaths (cross-check only)
def mhlw_statinfid(year: int, refresh=False) -> str | None:
    if year in MHLW_PINNED:
        return MHLW_PINNED[year]
    try:
        html = get(MHLW_LIST.format(y=year), kind="html").decode("utf-8", "replace")
    except Exception as e:
        print(f"[mhlw {year}] listing page failed: {e}")
        return None
    return find_anchor_id(html, MHLW_TITLE)


def decode_csv(b: bytes) -> str:
    for enc in ("cp932", "utf-8-sig"):
        try:
            s = b.decode(enc)
        except UnicodeDecodeError:
            continue
        if CAUSE_LABEL in norm(s):
            return s
    raise ValueError("cannot decode MHLW CSV (neither Shift-JIS nor UTF-8 shows 他殺)")


def show_head(raw: bytes, n=6, width=10):
    """Print the first rows of a file so a layout problem can be diagnosed from the console output."""
    try:
        rows = list(csv.reader(io.StringIO(decode_csv(raw))))
    except Exception:
        rows = list(csv.reader(io.StringIO(raw.decode("cp932", "replace"))))
    print(f"  [debug] file has {len(rows)} rows; first {n}:")
    for r in rows[:n]:
        print("   ", [norm(c)[:14] for c in r[:width]])


def parse_mhlw(raw: bytes, year: int) -> dict:
    """Return {'national':int, 'prefectures':{ja:int}, 'checks':[...]} for homicide deaths (他殺); raises on any inconsistency."""
    rows = list(csv.reader(io.StringIO(decode_csv(raw))))
    # --- reference year printed in the title row must match
    title_year = next((era_year(c) for r in rows[:3] for c in r if era_year(c)), None)
    if title_year != year:
        raise ValueError(f"file says year {title_year}, expected {year}")
    # --- header row: area names across columns
    hi = next((i for i, r in enumerate(rows)
               if "全国" in [norm(c) for c in r] and any(norm(c).endswith("札幌市") for c in r)), None)
    if hi is None:
        raise ValueError("header row with 全国 + 札幌市 not found - this year uses a different table layout")
    cols: dict[str, int] = {}
    order: list[str] = []
    for j, c in enumerate(rows[hi]):
        n = norm(c)
        if j < 2 or not n:
            continue
        name = n if n in ("全国", "外国", "不詳") else re.sub(r"^\d{2}", "", n)
        cols[name] = j
        order.append(name)
    pref_names = order[order.index("全国") + 1: order.index("外国")]
    if len(pref_names) != 47:
        raise ValueError(f"expected 47 prefecture columns, found {len(pref_names)}")

    def block(code, label):
        i = next((k for k, r in enumerate(rows)
                  if r and ((norm(r[0]).startswith(code) and label in norm(r[0]))
                            or (code == TOTAL_CODE and norm(r[0]) == TOTAL_LABEL and len(r) > 1
                                and norm(r[1]).startswith("総数")))), None)   # real file: total row has no code
        if i is None:
            raise ValueError(f"row {code} {label} not found")
        sexes = [norm(rows[i + k][1]) for k in (1, 2)]
        if not (sexes[0].startswith("男") and sexes[1].startswith("女")):
            raise ValueError(f"rows after {code} are not male/female: {sexes}")
        return [rows[i], rows[i + 1], rows[i + 2]]

    checks = []
    out = {}
    for code, label in ((TOTAL_CODE, TOTAL_LABEL), (CAUSE_CODE, CAUSE_LABEL)):
        tot, male, fem = block(code, label)
        v = lambda r, n: to_int(r[cols[n]])
        for n in order:
            a, b, c = v(tot, n), v(male, n), v(fem, n)
            if None in (a, b, c) or a != b + c:
                raise ValueError(f"{code} {n}: total {a} != male {b} + female {c}")
        nat = v(tot, "全国")
        s = sum(v(tot, n) for n in pref_names) + v(tot, "外国") + v(tot, "不詳")
        if s != nat:
            raise ValueError(f"{code}: national {nat} != prefectures+abroad+unknown {s}")
        checks.append(f"{label}: national={nat:,} = sum of 47 prefectures + 外国 + 不詳 ; total = male + female (all {len(order)} columns)")
        out[code] = {n: v(tot, n) for n in order}
    return {"national": out[CAUSE_CODE]["全国"],
            "prefectures": {n: out[CAUSE_CODE][n] for n in pref_names}, "checks": checks}


def load_deaths(years, refresh):
    res = {}
    for y in years:
        sid = mhlw_statinfid(y, refresh)
        if not sid:
            print(f"[mhlw {y}] table not found in e-Stat listing (not published yet / layout changed) - skipped")
            continue
        raw = get(CSV_URL.format(sid=sid), f"mhlw_deaths_cause_area_{y}_{sid}", refresh, suffix=".csv")
        try:
            res[y] = parse_mhlw(raw, y)
        except Exception as e:
            show_head(raw)
            print(f"[mhlw {y}] statInfId {sid}: {type(e).__name__}: {e}  - year skipped (older/different layout)")
            continue
        res[y]["sid"] = sid
        print(f"[mhlw {y}] statInfId={sid}  national homicide deaths={res[y]['national']:,}")
        for c in res[y]["checks"]:
            print("    OK  " + c)
    return res

# ----------------------------------------------------------------------------- MIC population discovery
def is_mic_title(t: str, word: str) -> bool:
    """Both title styles: '人口、世帯数、人口動態（都道府県別）【総計】' and '【総計】都道府県別人口、人口動態及び世帯数'."""
    return "【総計】" in t and word in t and "人口" in t and "年齢" not in t


def scan_mic_xlsx(url: str, word: str, found: dict[int, str]):
    try:
        html = htmllib.unescape(get(url, kind="html").decode("utf-8", "replace"))
    except Exception as e:
        print(f"[mic] {url}: {e}")
        return
    links = list(re.finditer(r'<a\b[^>]*href="([^"]+\.xlsx?)"[^>]*>(.*?)</a>', html, re.S | re.I))
    got = []
    for m in links:
        t = norm(re.sub(r"<[^>]+>", "", m.group(2)))
        if is_mic_title(t, word) and "人口・世帯数" in t:
            y = era_year(t)
            if y:
                found.setdefault(y, urljoin(url, m.group(1)))
                got.append(y)
    print(f"[mic] {url.rsplit('/', 1)[-1]}: {len(links)} Excel links, {word} total-population files for 1-Jan of {sorted(set(got))}")


def mic_urls(extra: dict[int, str], years: list[int], refresh=False) -> dict[int, str]:
    """1-Jan-Y prefecture population file URLs: manual > MIC pages (index + press releases) > e-Stat listing."""
    word = "都道府県別"
    found = dict(MIC_MANUAL_PREF)
    for u in [MIC_INDEX] + MIC_PRESS:
        scan_mic_xlsx(u, word, found)
    for y in years:
        if y in found or y in extra:
            continue
        seen = []
        for tpl in MIC_LISTS:
            try:
                html = htmllib.unescape(get(tpl.format(y=y), kind="html").decode("utf-8", "replace"))
            except Exception as e:
                print(f"[mic {y}] e-Stat listing failed: {e}")
                continue
            for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', html, re.S | re.I):
                t = norm(re.sub(r"<[^>]+>", "", m.group(2)))
                if "人口" in t or "総計" in t:
                    seen.append(t[:60])
                if is_mic_title(t, word):
                    sid = re.search(r"stat_infid=(\d+)", m.group(1), re.I) or re.search(r"statInfId=(\d+)", m.group(1))
                    if sid:
                        found[y] = XLS_URL.format(sid=sid.group(1))
                        break
            if y in found:
                break
        if y not in found:
            print(f"[mic {y}] e-Stat listing gave no usable {word} file; anchors seen: {list(dict.fromkeys(seen))[:8]}")
    found.update(extra)
    return found


# ----------------------------------------------------------------------------- NPA police cases
def era_labels(y: int) -> list[str]:
    if y >= 2020:
        return [f"令和{y - 2018}年"]
    if y == 2019:
        return ["令和元年", "平成31年"]
    return [f"平成{y - 1988}年"]


def _csv_link(t: str) -> str | None:
    h = htmllib.unescape(get(NPA_TSTAT.format(t=t), kind="html").decode("utf-8", "replace"))
    m = re.search(r"file-download\?statInfId=(\d+)&fileKind=1", h)
    return m.group(1) if m else None


def npa_statinfid(year: int, manual: dict[int, str]) -> str | None:
    if year in manual:
        return manual[year]
    if year in NPA_PINNED:
        return NPA_PINNED[year]
    tstat = NPA_TSTAT_PINNED.get(year)
    if not tstat:
        pat = [re.compile(rf"^{re.escape(l)}1月?[~〜]12月犯罪統計") for l in era_labels(year)]
        best = None                                   # (is_corrected, tstat)
        for p in range(1, 12):
            try:
                h = get(NPA_LIST.format(p=p), kind="html").decode("utf-8", "replace")
            except Exception as e:
                print(f"[npa {year}] listing page {p}: {e}")
                break
            n_anchor = 0
            for m in re.finditer(r'<a\b[^>]*href="([^"]*)"[^>]*>(.*?)</a>', h, re.S | re.I):
                href = htmllib.unescape(m.group(1))
                t = norm(htmllib.unescape(re.sub(r"<[^>]+>", "", m.group(2))))
                ts = re.search(r"tstat=(\d+)", href)
                if ts and "確定値" in t:
                    n_anchor += 1
                    if any(q.match(t) for q in pat):
                        cand = ("訂正版" in t, ts.group(1))
                        best = max(best, cand) if best else cand
            if best or n_anchor == 0 and p > 1:
                break
        if not best:
            return None
        tstat = best[1]
    sid = _csv_link(tstat)
    if not sid:
        print(f"[npa {year}] dataset {tstat} found but no CSV link on its page")
    return sid


def parse_npa(raw: bytes, year: int) -> dict:
    """Return {'cases':{pref:int},'prev':{pref:int},'total':int,'checks':[...]} for Table 6 (殺人).

    Real layout (verified on the 2022-2024 files): col0 = police region (北海道 / 東北 / 関東 / 中部 / 近畿 /
    中国 / 四国 / 九州) or 東京都 (own row, col1 empty); col1 = '計' for a region total, a prefecture name for
    prefectures inside a region, or a sub-area name (札幌方面 ...) for Hokkaido, whose '計' row IS the prefecture.
    """
    text = None
    for enc in ("cp932", "utf-8-sig"):
        try:
            t = raw.decode(enc)
        except UnicodeDecodeError:
            continue
        if "殺人" in t:
            text = t
            break
    if text is None:
        raise ValueError("cannot decode NPA CSV (no 殺人 found in Shift-JIS or UTF-8)")
    rows = list(csv.reader(io.StringIO(text)))
    cells = [[norm(c) for c in r] for r in rows]
    starts = [i for i, r in enumerate(cells)
              if any("第6表" in c for c in r) and any("殺人" in c for c in r)]
    if not starts:
        hits = [i for i, r in enumerate(cells) if any("殺人" in c for c in r)]
        raise ValueError(f"Table 6 (殺人) block not found; rows mentioning 殺人: {hits[:15]}")
    s0 = starts[0]
    gi = next((i for i in range(s0, min(s0 + 12, len(cells))) if "認知件数" in cells[i]), None)
    if gi is None:
        raise ValueError("header row with 認知件数 not found under the Table 6 (殺人) title")
    c_cur = cells[gi].index("認知件数")
    sub = cells[gi + 1]
    yrs = [re.search(r"(\d{4})年1月?[~〜-]12月", sub[c_cur + k]) for k in (0, 1)]
    if not all(yrs) or int(yrs[0].group(1)) != year or int(yrs[1].group(1)) != year - 1:
        raise ValueError(f"column years {[y.group(1) if y else None for y in yrs]} != ({year}, {year - 1})")

    cur, prev, regions, labels = {}, {}, {}, []
    total = None

    def dump():
        return "\n    block rows (row, col0, col1, cases): " + "; ".join(f"{i}:{n}|{c1}|{v}" for i, n, c1, v in labels[:90])

    def put(ja, v):
        if None in v:
            raise ValueError(f"{ja}: non-numeric value" + dump())
        if ja in cur:
            raise ValueError(f"{ja}: appears twice in the block" + dump())
        cur[ja], prev[ja] = v

    for i in range(gi + 2, len(cells)):
        r = cells[i]
        if any(re.match(r"^第\d+表", c) for c in r):
            break
        c0 = r[0] if r else ""
        c1 = r[1] if len(r) > 1 else ""
        labels.append((i, c0, c1, rows[i][c_cur] if len(rows[i]) > c_cur else ""))
        if not c0 and not c1:
            continue
        v = (to_int(rows[i][c_cur]), to_int(rows[i][c_cur + 1]))
        if c0 == "総数" and total is None:
            total = v
        elif c1 == "計":                                   # region total (北海道 計 is also the prefecture)
            if None in v:
                raise ValueError(f"{c0}: non-numeric region total" + dump())
            regions[c0] = [v[0], v[1], 0, 0]
            if c0 == "北海道":
                put("北海道", v)
        elif c0 == "北海道" and c1 not in KEY:             # Hokkaido sub-areas (札幌方面, ...)
            if None in v or "北海道" not in regions:
                raise ValueError("Hokkaido sub-area row without a 計 row above it" + dump())
            regions["北海道"][2] += v[0]
            regions["北海道"][3] += v[1]
        elif c0 in KEY and c1 == "":                       # 東京都 has its own row
            put(KEY[c0], v)
        elif c1 in KEY:                                    # prefecture inside a police region
            put(KEY[c1], v)
            if c0 in regions and None not in v:
                regions[c0][2] += v[0]
                regions[c0][3] += v[1]
    if total is None or None in total:
        raise ValueError("総数 row not found in the block" + dump())
    if len(cur) != 47:
        raise ValueError(f"found {len(cur)} prefectures, expected 47: missing {[p for p, _ in PREFS if p not in cur]}" + dump())
    for name, (ta, tb, aa, ab) in regions.items():
        if (ta, tb) != (aa, ab):
            raise ValueError(f"region {name}: 計 row ({ta},{tb}) != sum of its rows ({aa},{ab})" + dump())
    if sum(cur.values()) != total[0] or sum(prev.values()) != total[1]:
        raise ValueError(f"sum of prefectures ({sum(cur.values())}, {sum(prev.values())}) != 総数 {total}" + dump())
    checks = [f"総数 {total[0]:,} = sum of 47 prefectures (previous-year column: {total[1]:,})",
              f"{len(regions)} region/sub-area totals (計) equal the sum of their rows, in both columns"]
    t1 = next((to_int(rows[i][2]) for i, r in enumerate(cells) if len(r) > 2 and r[0] == "凶悪犯" and r[1] == "殺人"), None)
    if t1 is None:
        raise ValueError("Table 1 national row (凶悪犯 / 殺人) not found")
    if t1 != total[0]:
        raise ValueError(f"Table 1 national 殺人 {t1} != Table 6 総数 {total[0]}")
    checks.append(f"Table 1 national 殺人 = {t1:,} = Table 6 総数")
    return {"cases": cur, "prev": prev, "total": total[0], "checks": checks}


# ----------------------------------------------------------------------------- MIC prefecture population
def show_xlsx_head(df: pd.DataFrame, n=12, width=9):
    print(f"  [debug] sheet has {len(df)} rows x {df.shape[1]} columns; first {n} rows:")
    for i in range(min(n, len(df))):
        print("   ", i, [norm(c)[:12] for c in df.iloc[i].tolist()[:width]])


def read_mic_pref(raw: bytes, year: int, label="") -> tuple[dict[str, int], dict]:
    """Population of the 47 prefectures on 1 January `year` (total residents), and what was verified about it.

    The real MIC sheet keeps its group labels above the header row, so the population column is found from
    the data: the first block of three adjacent columns (男, 女, 計) where 計 = 男 + 女 (+ a tiny remainder) for all 47
    prefectures and every 計 is of population scale. Year: checked against a '令和N年1月1日' label if the sheet has one.
    The 6-digit local-government code (団体コード) of each prefecture is read from the column left of the names.
    Returns (population by prefecture, info) with info = {'national': int|None, 'label': int|None, 'codes': {ja: code}}.
    """
    df = pd.read_excel(io.BytesIO(raw), header=None, dtype=object)
    first = name_c = None
    for i in range(min(80, len(df))):
        for j in range(min(6, df.shape[1])):
            if norm(df.iat[i, j]) in KEY:
                first, name_c = i, j
                break
        if first is not None:
            break
    if first is None:
        show_xlsx_head(df)
        raise ValueError("no prefecture rows found in the MIC prefecture table")
    pref_rows = {}
    for i in range(first, len(df)):
        n = norm(df.iat[i, name_c])
        if n in KEY and KEY[n] not in pref_rows:
            pref_rows[KEY[n]] = i
    if len(pref_rows) != 47:
        show_xlsx_head(df)
        raise ValueError(f"found {len(pref_rows)} prefectures in the MIC table, expected 47")
    nat_row = next((i for i in range(max(0, first - 3), first)
                    if norm(df.iat[i, name_c]) in ("全国", "合計", "総数", "計")), None)
    order = [pref_rows[ja] for ja, _ in PREFS]

    def col(j, rows):
        return [to_int(df.iat[i, j]) for i in rows]
    pop_c = None
    for j in range(name_c + 1, df.shape[1] - 2):
        a_, b_, c_ = col(j, order), col(j + 1, order), col(j + 2, order)
        if None in a_ + b_ + c_:
            continue
        rem = [c - (x + y) for x, y, c in zip(a_, b_, c_)]
        # since 2025 the register has residents with no male/female entry: 計 = 男 + 女 + a small remainder
        if min(rem) >= 0 and all(r <= max(100, 0.0005 * c) for r, c in zip(rem, c_)) and min(c_) >= 100_000:
            pop_c = j + 2
            max_rem = max(rem)
            break
    if pop_c is None:
        show_xlsx_head(df)
        raise ValueError("no (男, 女, 計) population block found where 計 = 男 + 女 (+ a tiny remainder) for all 47 prefectures")
    # year label, if the sheet carries one
    lab = None
    for i in range(min(first + 1, 25)):
        for c in df.iloc[i].tolist():
            m = re.search(r"令和(\d+)年1月1日", norm(c))
            if m:
                lab = int(m.group(1)) + 2018
                break
        if lab:
            break
    if lab is not None and lab != year:
        raise ValueError(f"this file is for 1-Jan-{lab}, not 1-Jan-{year}")
    note = f"label confirms 1-Jan-{lab}" if lab else "no 令和N年1月1日 label in the sheet: year taken from the source link"
    out = {ja: to_int(df.iat[pref_rows[ja], pop_c]) for ja, _ in PREFS}
    print(f"  [mic-pref {year}] total-population column = {pop_c} (計 = 男 + 女 + remainder <= {max_rem} persons, 47/47 prefectures); {note}")
    nat = None
    if nat_row is not None:
        nat = to_int(df.iat[nat_row, pop_c])
        if nat != sum(out.values()):
            raise ValueError(f"MIC national {nat:,} != sum of 47 prefectures {sum(out.values()):,}")
        print(f"    OK  national row {nat:,} = sum of 47 prefectures")
    codes = {}
    if name_c >= 1:
        for ja, _ in PREFS:
            raw_code = norm(df.iat[pref_rows[ja], name_c - 1]).split(".")[0]
            if re.fullmatch(r"\d{5,6}", raw_code):
                codes[ja] = raw_code.zfill(6)
        if len(codes) != 47 or len(set(codes.values())) != 47:
            codes = {}
    return out, {"national": nat, "label": lab, "codes": codes}


# ----------------------------------------------------------------------------- cross-check
def crosscheck(police: dict[int, dict], refresh: bool):
    print("\n=== cross-check: police cases (NPA) vs homicide deaths (health ministry, 他殺) ===")
    try:
        yrs = sorted(y for y in police if y >= 2023)[:2] or [2023]      # table layout verified from 2023
        deaths = load_deaths(yrs, refresh)
    except SystemExit as e:
        print("  [skip] health series could not be loaded:", e)
        return
    if not deaths:
        print("  [skip] no health year available")
        return
    hy = sorted(deaths)[0]
    py = hy if hy in police else max(police, key=lambda y: -abs(y - hy))
    note = "same year" if py == hy else f"police {py} vs health {hy} (adjacent years - rough)"
    pol, hea = police[py]["cases"], deaths[hy]["prefectures"]
    df = pd.DataFrame({"police_cases": pd.Series(pol), "health_deaths": pd.Series(hea)})
    df["cases_per_death"] = (df.police_cases / df.health_deaths.where(df.health_deaths > 0)).round(1)
    nat = police[py]["total"] / deaths[hy]["national"]
    med = df["cases_per_death"].median()
    print(f"  {note}. National: {police[py]['total']:,} police cases vs {deaths[hy]['national']:,} deaths "
          f"= {nat:.1f} cases per death (attempts and non-fatal cases explain a ratio above 1).")
    tk = df.loc["東京都"]
    print(f"  Tokyo: {int(tk.police_cases)} cases vs {int(tk.health_deaths)} deaths = {tk.cases_per_death} per death; "
          f"median prefecture = {med:.1f}")
    show = df.sort_values("cases_per_death", ascending=False).head(6)
    print("  most under-counted by the health series (highest cases per death):")
    print(show.to_string())
    rank = int(df["cases_per_death"].rank(ascending=False)["東京都"])
    n_rank = int(df["cases_per_death"].notna().sum())
    print(f"  => Tokyo's cases-per-death is {tk.cases_per_death / nat:.1f}x the national ratio and ranks {rank} of {n_rank} "
          f"(1 = most under-counted by the health series). Judge from the table, not from a threshold.")


# ----------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["inspect", "build"])
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--npa-sid", action="append", default=[], help="YEAR=statInfId of the NPA 確定値 CSV")
    ap.add_argument("--mic-url", action="append", default=[], help="YEAR=URL of the 1-Jan-YEAR [総計] prefecture Excel")
    ap.add_argument("--crosscheck", action="store_true")
    a = ap.parse_args()
    manual = {int(k): v for k, v in (s.split("=", 1) for s in a.npa_sid)}
    extra = {int(k): v for k, v in (s.split("=", 1) for s in a.mic_url)}
    years = sorted(a.years or range(FIRST_VERIFIED_YEAR, dt.date.today().year))

    police = {}
    for y in years:
        sid = npa_statinfid(y, manual)
        if not sid:
            print(f"[npa {y}] dataset not found on e-Stat (not published yet / listing changed) - skipped")
            continue
        raw = get(CSV_URL.format(sid=sid), f"npa_crime_stats_{y}_{sid}", a.refresh, suffix=".csv")
        try:
            police[y] = parse_npa(raw, y)
        except Exception as e:
            show_head(raw, n=4)
            print(f"[npa {y}] statInfId {sid}: {type(e).__name__}: {e}  - skipped")
            continue
        police[y]["sid"] = sid
        print(f"[npa {y}] statInfId={sid}  national 殺人 cases={police[y]['total']:,}")
        for c in police[y]["checks"]:
            print("    OK  " + c)
    if not police:
        sys.exit("[stop] no NPA year could be parsed")

    # column-identity guard: the NEXT year's file repeats this year's values in its previous-year column
    rev: dict[int, dict | None] = {}
    for y in sorted(police):
        if y + 1 in police:
            rev[y] = {p: (police[y]["cases"][p], police[y + 1]["prev"][p]) for p, _ in PREFS
                      if police[y + 1]["prev"][p] != police[y]["cases"][p]}
            if rev[y]:
                print(f"[continuity {y}] the {y + 1} file's previous-year column differs from the {y} file for {len(rev[y])} prefectures "
                      f"(a revision, or a misread column): {[EN[p] for p in rev[y]][:8]}")
            else:
                print(f"[continuity {y}] the {y + 1} file's previous-year column == the {y} file for 47/47 prefectures")
        else:
            rev[y] = None

    need = {y for d in police for y in (d, d + 1)}
    urls = mic_urls(extra, sorted(need), a.refresh)
    pops = {}
    for yr in sorted(urls):                      # each MIC file holds one 1-January only
        if yr not in need:
            continue
        raw = get(urls[yr], f"mic_pref_pop_{yr}0101", a.refresh, suffix=".xlsx")
        try:
            pop_by_pref, info = read_mic_pref(raw, yr, f"1-Jan-{yr}")
            pops[yr] = (pop_by_pref, urls[yr], info)
        except Exception as e:
            print(f"[mic-pref {yr}] {urls[yr]}: {type(e).__name__}: {e}")
    print("\nPopulation found for 1-Jan of:", sorted(pops), "| needed:", sorted(need))

    codes: dict[str, str] = {}                   # official prefecture codes, which must agree across every file used
    for yr in sorted(pops):
        for ja, c in pops[yr][2]["codes"].items():
            if codes.setdefault(ja, c) != c:
                sys.exit(f"[stop] the MIC code of {EN[ja]} differs between files ({codes[ja]} vs {c} in 1-Jan-{yr})")

    rows = []
    for y, d in sorted(police.items()):
        if y not in pops or y + 1 not in pops:
            print(f"[skip] {y}: needs MIC 1-Jan-{y} and 1-Jan-{y + 1}")
            continue
        infos = [pops[y][2], pops[y + 1][2]]
        pop_sum = all(i["national"] is not None for i in infos)
        pop_lab = all(i["label"] is not None for i in infos)
        pop_text = (f"MIC 1-Jan-{y} and 1-Jan-{y + 1}: " + ("47 prefectures sum to the national row" if pop_sum else "national row NOT found, sum not reconciled")
                    + ("; sheet year labels confirmed" if pop_lab else "; year taken from the source link (no label in a sheet)"))
        if rev[y] is None:
            cont_text = f"no {y + 1} NPA file yet to confirm these values (Table 1 vs Table 6 is the second check)"
        elif not rev[y]:
            cont_text = f"the {y + 1} file's previous-year column equals this file for 47/47 prefectures"
        else:
            cont_text = f"the {y + 1} file's previous-year column equals this file for {47 - len(rev[y])}/47 prefectures"
        validation = "; ".join(d["checks"] + [cont_text, pop_text])
        for ja, en in PREFS:
            pop = round((pops[y][0][ja] + pops[y + 1][0][ja]) / 2)        # whole persons, and the rate below uses exactly this figure
            n = d["cases"][ja]
            notes = [f"attempts are counted with the completed offence, except preparation for murder (Statistics Bureau of Japan: {ATTEMPTS_SOURCE})"]
            tier = "A"
            if rev[y] and ja in rev[y]:
                tier = "B"
                notes.append(f"revision: this file gives {rev[y][ja][0]}, the {y + 1} NPA file gives {rev[y][ja][1]} for {y}")
            if not pop_sum:
                tier = "B"
            url_h, url_p = CSV_URL.format(sid=d["sid"]), (pops[y][1], pops[y + 1][1])
            rows.append({
                "country": "Japan", "unit": en, "unit_local": ja, "unit_code": codes.get(ja, ""), "admin_level": "admin1",
                "unit_type": "prefecture", "year": y, "homicide_cases": n, "population": pop,
                "homicide_rate_per_100k": n / pop * 1e5, "flag_low_count": n < LOW_COUNT, "flag_outlier_year": False,
                "population_age_years": 0.0, "indicator_type": "police_recorded_cases", "reliability_tier": tier, "definition_flags": "includes_attempts",
                "validation": validation,
                "indicator": "NPA 殺人 cases recognised by the police (認知件数), final-value (確定値) crime statistics on e-Stat; cases, not victims",
                "population_method": "mean of the MIC resident-register total population on 1 January Y and 1 January Y+1 (Japanese and foreign residents)",
                "data_notes": "; ".join(notes),
                "source_homicide": url_h, "source_population": f"{url_p[0]} ; {url_p[1]}",
                "retrieved": FETCH.retrieved_on(url_h, *url_p)})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df[df["population"] >= MIN_POP]
        df = F.add_outlier_flags(df)
        for _, r in df[df.flag_outlier_year].iterrows():
            print(f"[japan] statistical outlier: {r.unit} {int(r.year)} = {int(r.homicide_cases)} cases (robust z = {r.robust_z:.1f})")
        if df["robust_z"].isna().all():
            df = df.drop(columns="robust_z")
        df = F.finalize(df)
        F.require_valid(df, "japan")
        cols = ["unit", "year", "homicide_cases", "population", "homicide_rate_per_100k"]
        print("\nRate per 100k (top 8 / bottom 3 in the latest year):")
        last = df[df.year == df.year.max()].sort_values("homicide_rate_per_100k", ascending=False)
        print(last[cols].head(8).round(3).to_string(index=False))
        print(last[cols].tail(3).round(3).to_string(index=False))
        g = df.groupby("year")[["homicide_cases", "population"]].sum()
        print("\nNational rate per 100k implied by the 47 prefectures:\n" + (g.homicide_cases / g.population * 1e5).round(3).to_string())
        print(f"\nReliability tiers: {df.reliability_tier.value_counts().to_dict()}")
    else:
        print("\n[note] nothing to compute yet (population files missing) - numerator results above are still valid")
    if a.crosscheck:
        crosscheck(police, a.refresh)
    if a.cmd == "build" and not df.empty:
        F.write_csv(df, OUT)
        print(f"\n[ok] wrote {OUT}  ({len(df)} rows)")
    else:
        print("\n[no CSV written]" if a.cmd == "inspect" else "\n[no CSV written - population missing]")


if __name__ == "__main__":
    main()