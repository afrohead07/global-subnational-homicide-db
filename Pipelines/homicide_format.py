#!/usr/bin/env python3
"""
homicide_format.py - the output format, folder layout and download routine every country pipeline follows (version 1.1).

Folder layout (one copy of this file, in Pipelines/):
    <repo>/Pipelines/homicide_format.py
    <repo>/Pipelines/<Region>/<country>_homicide_rate.py   and its single output  <country>_homicide_rate.csv
    <repo>/Data/Raw/<Region>/<Country>/                    every download of that country, date-stamped

Each pipeline starts with:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]));  import homicide_format as F
    P = F.paths(__file__, "Japan")          # P.raw (download folder), P.out (the one CSV), P.region
    FETCH = F.Fetcher(P.raw)                # robots.txt, dated copies, sha256, TLS verified
and ends with:
    df = F.finalize(df);  F.require_valid(df, "japan");  F.write_csv(df, P.out)

Command line:
    python homicide_format.py check  china_homicide_rate.csv [more.csv ...]   validate files (exit code 1 on errors)
    python homicide_format.py spec   > FORMAT.md                              print the specification as markdown
    python homicide_format.py template  [template.csv]                        write an empty template with one example row
Needs: pip install pandas
"""
from __future__ import annotations
import argparse, datetime as dt, hashlib, re, ssl, sys, time
from pathlib import Path
from types import SimpleNamespace
from urllib import robotparser
from urllib.parse import urlparse
import numpy as np
import pandas as pd
import requests
from requests.adapters import HTTPAdapter

FORMAT_VERSION = "1.2"
REVISION = 14          # bumped when the module gains something scripts rely on: 2 = Fetcher suffix/reject_html, 3 = Fetcher retries, 4 = RobotsDisallowed, 5 = MAX_DENOMINATOR_AGE, 6 = population_age_years, 7 = Fetcher.post and cookie session, 8 = get(headers=...), 9 = Fetcher(os_trust=...), 10 = certificate errors are not retried, 11 = exact null-word check, 12 = finalize leaves numeric and boolean extras alone, 13 = a 5xx robots.txt disallows everything (RFC 9309), 14 = a missing pandas NA / NaT is an empty cell (not the text '<NA>')

# ----------------------------------------------------------------------------- project-wide constants (one place only)
LOW_COUNT = 10             # flag_low_count: fewer cases than this
MIN_POP = 100_000          # units below this population are not published
OUTLIER_Z = 3.5            # flag_outlier_year: robust z-score threshold (median/MAD, Iglewicz-Hoaglin)
OUTLIER_MIN_YEARS = 8      # the outlier test is only run on series at least this long
RATE_REL_TOL = 1e-9        # homicide_rate_per_100k must equal cases / population x 100,000 within this relative tolerance
MAX_DENOMINATOR_AGE = 3.5  # years: a population older than this (from its own reference date) is a documented weakness (tier B at best), or no rate is made
YOY_POP_WARN = 0.25        # warn when a unit's population changes by more than this between consecutive years
RATE_WARN = 50.0           # warn when a rate per 100,000 exceeds this

ADMIN_LEVELS = ["admin1", "admin2", "city", "police_unit"]
INDICATOR_TYPES = ["police_recorded_cases", "health_registry_deaths", "court_convictions"]
TIERS = ["A", "B", "C"]
DEFINITION_FLAGS = ["includes_attempts", "includes_manslaughter", "counts_victims"]

# (name, kind, required, description)
COLUMNS = [
    ("country", "text", True, "Country name in English, e.g. Japan."),
    ("unit", "text", True, "Area name in English as the source gives it (else a standard transliteration). Unique within (country, parent_unit)."),
    ("unit_local", "text", False, "Name in the local script, only when the source provides it."),
    ("unit_code", "text", False, "The country's own official code for the area, kept as text (leading zeros preserved). Never ISO codes."),
    ("admin_level", "vocab", True, "admin1 = first-level division (province, prefecture, region, municipality, SAR); admin2 = second level (district, county); "
                                  "city = a city-level unit; police_unit = a police administrative unit that does not follow admin boundaries."),
    ("unit_type", "text", True, "The source's own term in lower snake_case: province, prefecture, region, municipality, special_administrative_region, district, ..."),
    ("parent_unit", "text", False, "Enclosing first-level area for admin2/city units (e.g. the state of a Malaysian district); blank otherwise."),
    ("year", "int", True, "Calendar year the count refers to."),
    ("homicide_cases", "int", True, "The count (>= 0) in the unit defined by indicator_type and definition_flags: recorded cases, deaths or convictions."),
    ("population", "int", True, "Denominator actually used, in persons (>= 100,000); how it was built is in population_method."),
    ("homicide_rate_per_100k", "float", True, "homicide_cases / population x 100,000, not rounded."),
    ("flag_low_count", "bool", True, "True when homicide_cases < 10."),
    ("flag_outlier_year", "bool", True, "True when the year's robust z-score within the unit's own series exceeds 3.5; only tested for series of >= 8 years, otherwise False."),
    ("indicator_type", "vocab", True, "police_recorded_cases | health_registry_deaths | court_convictions."),
    ("reliability_tier", "vocab", True, "A | B | C - how strongly the numbers were verified (definitions below), not how close they are to a perfect homicide measure."),
    ("definition_flags", "flags", False, "Semicolon-separated, only what the SOURCE states: includes_attempts | includes_manslaughter | counts_victims. "
                                         "Blank means 'nothing stated', not 'no'."),
    ("validation", "text", True, "The checks this row passed, written by the script from computed values."),
    ("indicator", "text", True, "What the numerator is, in the source's own terms."),
    ("population_method", "text", True, "Source, reference date and averaging used to build the denominator."),
    ("population_age_years", "float", False, "How old the denominator is: years between the date the population refers to and the middle of `year` (1 July). "
                                             "0 for a population of the same period (a mid-year estimate, the mean of two year-ends or of two 1 Januaries); "
                                             "3.0 for a census taken three years before the count; blank only if the source gives no reference date. "
                                             "Tier A needs a value here that is at most 3.5."),
    ("data_notes", "text", False, "Caveats specific to the unit or year."),
    ("source_homicide", "text", True, "URL(s) of the numerator source, semicolon-separated."),
    ("source_population", "text", True, "URL(s) or table identifier of the denominator source."),
    ("retrieved", "date", True, "YYYY-MM-DD on which the data was downloaded."),
]
CORE_COLUMNS = [c[0] for c in COLUMNS]
REQUIRED = [c[0] for c in COLUMNS if c[2]]
BOOL_COLS = [c[0] for c in COLUMNS if c[1] == "bool"]
NULL_WORDS = {"nan", "NaN", "None", "null", "NULL", "NA", "N/A", "<NA>", "NaT"}      # EXACT strings a script writes for a missing value; "Nan" (a Thai province) is a name
KEY = ["country", "parent_unit", "unit", "year"]

TIER_TEXT = {
    "A": "Every count reconciles to the source's own totals (or an equivalent identity) AND is confirmed by at least one independent check "
         "(a second edition, table or file, or an identity linking the denominator to another official figure), AND the denominator is no older "
         "than 3.5 years (population_age_years).",
    "B": "Reconciled, with a documented weakness: read by OCR, confirmed by one source only, an unallocated remainder, a rounded or provisional "
         "denominator, a denominator older than 3.5 years, or a newest year read once.",
    "C": "A check failed or could not be run, or the indicator is a proxy (health deaths, convictions). Not for headline use.",
}


# ----------------------------------------------------------------------------- helpers for pipelines
def robust_z(values: list[float]) -> list[float | None]:
    """Median/MAD z-scores (0.6745 scaling). None when the series is too short or its MAD is zero."""
    s = pd.Series(values, dtype=float)
    if len(s) < OUTLIER_MIN_YEARS:
        return [None] * len(s)
    med = s.median()
    mad = (s - med).abs().median()
    if mad == 0:
        return [None] * len(s)
    return [float(0.6745 * (v - med) / mad) for v in s]


def add_outlier_flags(df: pd.DataFrame, keep_z: bool = True) -> pd.DataFrame:
    """Sets flag_outlier_year (and an extra robust_z column) per unit series."""
    d = df.copy()
    d["robust_z"] = None
    d["flag_outlier_year"] = False
    for _, idx in d.groupby(["country", d["parent_unit"].fillna("") if "parent_unit" in d else "country", "unit"], sort=False).groups.items():
        sub = d.loc[idx].sort_values("year")
        z = robust_z(sub["homicide_cases"].astype(float).tolist())
        d.loc[sub.index, "robust_z"] = z
        d.loc[sub.index, "flag_outlier_year"] = [abs(v) > OUTLIER_Z if v is not None else False for v in z]
    if not keep_z:
        d = d.drop(columns="robust_z")
    return d


def to_core(df: pd.DataFrame) -> pd.DataFrame:
    """Core columns first, in the canonical order (missing optional ones blank, missing flags derived); extras follow."""
    d = df.copy()
    for c in CORE_COLUMNS:
        if c not in d.columns:
            d[c] = "" if c not in BOOL_COLS else False
    extras = [c for c in d.columns if c not in CORE_COLUMNS]
    return d[CORE_COLUMNS + extras]


def finalize(df: pd.DataFrame) -> pd.DataFrame:
    """Canonical frame: derived values filled, text cleaned, types fixed, rows sorted. Does not hide errors: run require_valid after."""
    d = df.copy()
    if "homicide_rate_per_100k" not in d.columns and {"homicide_cases", "population"} <= set(d.columns):
        d["homicide_rate_per_100k"] = d["homicide_cases"].astype(float) / d["population"].astype(float) * 1e5
    if "flag_low_count" not in d.columns and "homicide_cases" in d.columns:
        d["flag_low_count"] = d["homicide_cases"].astype(float) < LOW_COUNT
    d = to_core(d)
    text_cols = [c for c in d.columns if c not in ("year", "homicide_cases", "population", "homicide_rate_per_100k", "population_age_years") and c not in BOOL_COLS]
    for c in text_cols:
        if pd.api.types.is_numeric_dtype(d[c]) or pd.api.types.is_bool_dtype(d[c]):
            continue                                   # a numeric or boolean extra keeps its type (only text is cleaned)
        d[c] = [("" if _missing(v) else re.sub(r"\s+", " ", str(v)).strip()) for v in d[c].tolist()]
    for c in ("year", "homicide_cases", "population"):
        d[c] = pd.to_numeric(d[c]).round().astype("int64")
    d["homicide_rate_per_100k"] = pd.to_numeric(d["homicide_rate_per_100k"]).astype(float)
    d["population_age_years"] = pd.to_numeric(d["population_age_years"], errors="coerce").round(1)      # blank stays blank
    for c in BOOL_COLS:
        d[c] = d[c].astype(bool)
    return d.sort_values(KEY, kind="stable").reset_index(drop=True)


def write_csv(df: pd.DataFrame, path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig", lineterminator="\n")



# ----------------------------------------------------------------------------- folder layout
def slug(country: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", country.lower()).strip("_")


def paths(script_file: str, country: str) -> SimpleNamespace:
    """<repo>/Pipelines/<Region>/<script>.py  ->  raw downloads in <repo>/Data/Raw/<Region>/<Country>/, one CSV next to the script."""
    here = Path(script_file).resolve().parent
    if here.parent.name != "Pipelines":
        sys.exit(f"[stop] this script must live in <repo>/Pipelines/<Region>/ (it is in {here}); the Region folder name decides where "
                 f"downloads go (Data/Raw/<Region>/{country}/)")
    root = here.parents[1]
    return SimpleNamespace(region=here.name, root=root, raw=root / "Data" / "Raw" / here.name / country,
                           out=here / f"{slug(country)}_homicide_rate.csv", country=country)


# ----------------------------------------------------------------------------- downloads
DEFAULT_UA = "global-subnational-homicide-db research pipeline"


class _ContextAdapter(HTTPAdapter):
    """Mounts a prepared SSL context on a requests session."""
    def __init__(self, ctx, *a, **k):
        self._ctx = ctx
        super().__init__(*a, **k)

    def init_poolmanager(self, *a, **k):
        k["ssl_context"] = self._ctx
        super().init_poolmanager(*a, **k)


class RobotsDisallowed(SystemExit):
    """The site's robots.txt does not allow an automated download of this URL. It is a SystemExit (so a script that does not catch it
    stops with the message) but a script can catch it by class to carry on with other files and ask for a manual download."""
    def __init__(self, url: str, rules: list[str]):
        self.url, self.rules = url, rules
        super().__init__(f"[stop] robots.txt disallows an automated download of {url}")


def _rules_for_everyone(robots_text: str) -> list[str]:
    """The Allow/Disallow lines of the 'User-agent: *' group (what applies to this pipeline), for display."""
    out, active = [], False
    for line in robots_text.splitlines():
        t = line.split("#", 1)[0].strip()
        if not t:
            continue
        k, _, v = t.partition(":")
        k, v = k.strip().lower(), v.strip()
        if k == "user-agent":
            active = v == "*"
        elif active and k in ("allow", "disallow"):
            out.append(f"{k.capitalize()}: {v}")
    return out


class Fetcher:
    """One download routine for every pipeline: robots.txt respected (RFC 9309: a 4xx robots.txt means no rules), every download saved
    date-stamped in the country's raw folder and logged with its sha256, certificates verified unless insecure=True is passed on purpose."""

    def __init__(self, raw_dir, user_agent: str = DEFAULT_UA, insecure: bool = False, timeout: int = 180, retries: int = 1,
                 os_trust: bool = False):
        """os_trust=True verifies certificates against the operating system's store (it can fetch the intermediate certificates that some
        government sites omit; needs `pip install truststore`, else Python's default store). insecure=True turns verification OFF."""
        self.raw, self.ua, self.insecure, self.timeout, self.retries = Path(raw_dir), user_agent, insecure, timeout, max(1, retries)
        self.os_trust = os_trust
        self._robots: dict[str, robotparser.RobotFileParser] = {}
        self._robots_text: dict[str, str] = {}
        self._told: set[str] = set()                      # hosts whose robots rules were already printed
        self.session = requests.Session()                  # keeps cookies between requests (some portals need a prior page visit)
        if os_trust:
            try:
                import truststore
                ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            except Exception:
                ctx = ssl.create_default_context()
            if hasattr(ssl, "VERIFY_X509_STRICT"):         # Python 3.13 rejects some certificates that browsers accept
                try:
                    ctx.verify_flags &= ~ssl.VERIFY_X509_STRICT
                except Exception:
                    pass
            self.session.mount("https://", _ContextAdapter(ctx))
        self.last_date = dt.date.today().isoformat()       # retrieval date of the most recent get/post
        self._memo: dict[str, bytes] = {}
        self.retrieved: dict[str, str] = {}            # url -> YYYY-MM-DD the content was obtained (today, or the cached copy's date)
        if insecure:
            print("[warning] TLS certificate checks are OFF for this run (insecure=True)")
            try:
                import urllib3
                urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            except Exception:
                pass

    def _allowed(self, url: str) -> bool:
        p = urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = robotparser.RobotFileParser()
            try:
                r = self.session.get(host + "/robots.txt", headers={"User-Agent": self.ua}, timeout=30, verify=not self.insecure)
                rp.parse(r.text.splitlines() if r.status_code == 200 else [])
                self._robots_text[host] = r.text if r.status_code == 200 else ''
                print(f"[robots] {host}: HTTP {r.status_code}")
                if r.status_code >= 500:                       # RFC 9309: an UNREACHABLE robots.txt (5xx) means "assume everything is disallowed"; a 4xx means no rules
                    rp.disallow_all, rp.allow_all = True, False
                    self._robots_text[host] = f"# robots.txt answered HTTP {r.status_code}: unreachable, so everything is treated as disallowed (RFC 9309)\nUser-agent: *\nDisallow: /"
            except Exception as e:
                rp.parse([])
                print(f"[robots] {host}: could not read ({type(e).__name__}); proceeding")
            self._robots[host] = rp
        return self._robots[host].can_fetch(self.ua, url)

    def _cached(self, name: str, suffix: str) -> Path | None:
        if not self.raw.exists():
            return None
        pat = re.compile(re.escape(name) + r"_\d{8}" + re.escape(suffix))
        found = sorted(f for f in self.raw.glob(f"{name}_*{suffix}") if pat.fullmatch(f.name))
        return found[-1] if found else None

    @staticmethod
    def _is_html(data: bytes) -> bool:
        return data[:200].lstrip().lower().startswith((b"<!doctype", b"<html"))

    def get(self, url: str, name: str | None = None, reuse: bool = False, suffix: str | None = None, reject_html: bool = False,
            headers: dict | None = None) -> bytes:
        """Bytes of `url`. With `name`, a copy is saved as <raw>/<name>_<YYYYMMDD><suffix> (suffix defaults to the URL's extension; pass it
        when the URL has none). reuse=True uses the newest saved copy instead of downloading (its date becomes the retrieval date).
        reject_html=True refuses an HTML page where a data file is expected: it is neither saved nor reused."""
        return self._fetch("GET", url, name, reuse, suffix, reject_html, None, headers, None)

    def post(self, url: str, data: dict, name: str | None = None, reuse: bool = False, suffix: str | None = None,
             reject_html: bool = False, headers: dict | None = None, warmup: str | None = None) -> bytes:
        """Like get() for a form POST (what a site's own download button sends). `warmup` is a page fetched first, only when a real
        download is needed, so that the session holds the cookies a browser visit would have set."""
        return self._fetch("POST", url, name, reuse, suffix, reject_html, data, headers, warmup)

    def _fetch(self, method, url, name, reuse, suffix, reject_html, data, headers, warmup) -> bytes:
        key = url if method == "GET" else url + "#" + "&".join(f"{k}={v}" for k, v in sorted((data or {}).items()))
        if key in self._memo:
            return self._memo[key]
        suffix = suffix or Path(urlparse(url).path).suffix or ".dat"
        if reuse and name:
            c = self._cached(name, suffix)
            if c is not None:
                cached = c.read_bytes()
                if not (reject_html and self._is_html(cached)):
                    self.retrieved[key] = self.last_date = dt.datetime.strptime(c.stem[-8:], "%Y%m%d").date().isoformat()
                    print(f"[cache] {c.name}  {len(cached):,} bytes  sha256={hashlib.sha256(cached).hexdigest()[:12]}")
                    self._memo[key] = cached
                    return cached
        if not self._allowed(url):
            p = urlparse(url)
            rules = _rules_for_everyone(self._robots_text.get(f"{p.scheme}://{p.netloc}", ""))
            if p.netloc not in self._told:
                self._told.add(p.netloc)
                print(f"[robots] {p.netloc} does not allow automated downloads. Rules for all robots: "
                      + ("; ".join(rules[:8]) if rules else "(could not be summarised)"))
            raise RobotsDisallowed(url, rules)
        if warmup:
            self.get(warmup)
        r, last = None, None
        for attempt in range(1, self.retries + 1):                 # connection errors and HTTP 5xx are retried; 4xx is final
            try:
                r = self.session.request(method, url, data=data, headers={"User-Agent": self.ua, **(headers or {})},
                                         timeout=self.timeout, verify=not self.insecure)
                if r.status_code < 500:
                    break
                last = RuntimeError(f"HTTP {r.status_code} for {url}")
            except requests.exceptions.SSLError:
                raise                                       # a certificate problem is not transient: retrying only wastes time
            except requests.RequestException as e:
                last = e
            if attempt < self.retries:
                print(f"[retry] {url}: {last} (attempt {attempt} of {self.retries})")
                time.sleep(2 * attempt)
        if r is None or r.status_code >= 500:
            raise last if isinstance(last, Exception) else RuntimeError(f"could not download {url}")
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        content = r.content
        if reject_html and self._is_html(content):
            raise RuntimeError(f"got an HTML page instead of a data file: {url}")
        if name:
            self.raw.mkdir(parents=True, exist_ok=True)
            (self.raw / f"{name}_{dt.date.today():%Y%m%d}{suffix}").write_bytes(content)
        print(f"[download] {url}  {len(content):,} bytes  sha256={hashlib.sha256(content).hexdigest()[:12]}")
        self._memo[key] = content
        self.retrieved[key] = self.last_date = dt.date.today().isoformat()
        return content

    def retrieved_on(self, *urls: str) -> str:
        """The oldest retrieval date among the given URLs (what a row built from them should report)."""
        dates = [self.retrieved[u] for u in urls if u in self.retrieved]
        return min(dates) if dates else dt.date.today().isoformat()


# ----------------------------------------------------------------------------- validator
def _missing(v) -> bool:
    """True for every kind of missing cell: None, float NaN, numpy NaN, pandas NA / NaT (a nullable-integer column holds pd.NA, which is not a float)."""
    if v is None or v is pd.NA or v is pd.NaT:
        return True
    return isinstance(v, (float, np.floating)) and bool(pd.isna(v))


def _strings(df: pd.DataFrame) -> pd.DataFrame:
    out = pd.DataFrame(index=df.index)
    for c in df.columns:
        out[c] = [("" if _missing(v) else str(v)) for v in df[c].tolist()]
    return out


def check_frame(df_in: pd.DataFrame) -> tuple[list[str], list[str]]:
    """-> (errors, warnings). Errors mean the file does not follow the format."""
    errs: list[str] = []
    warns: list[str] = []
    df = _strings(df_in)
    cols = list(df.columns)
    missing = [c for c in CORE_COLUMNS if c not in cols]
    if missing:
        return [f"missing core columns: {missing}"], warns
    if cols[:len(CORE_COLUMNS)] != CORE_COLUMNS:
        errs.append("core columns are not first and in the canonical order")
    iso = [c for c in cols if re.search(r"iso", c, re.I)]
    if iso:
        errs.append(f"ISO-code columns are not allowed: {iso}")
    for c in cols[len(CORE_COLUMNS):]:
        if not re.fullmatch(r"[a-z][a-z0-9_]*", c):
            warns.append(f"extra column '{c}' is not lower snake_case")
    n = len(df)
    if n == 0:
        return ["no rows"], warns

    for c in REQUIRED:
        k = int((df[c].str.strip() == "").sum())
        if k:
            errs.append(f"required column '{c}' is empty in {k} row(s)")
    for c in cols:                                             # text hygiene
        s = df[c]
        k = int((s != s.str.strip()).sum())
        if k:
            errs.append(f"'{c}': {k} cell(s) with leading/trailing spaces")
        k = int(s.str.contains(r"[\r\n]", regex=True).sum())
        if k:
            errs.append(f"'{c}': {k} cell(s) containing a line break")
        k = int(s.isin(NULL_WORDS).sum())
        if k:
            errs.append(f"'{c}': {k} cell(s) holding a null word such as 'nan'/'None'/'NA' (leave the cell empty instead)")

    num = {}
    for c, lo in (("year", 1900), ("homicide_cases", 0), ("population", MIN_POP)):
        v = pd.to_numeric(df[c], errors="coerce")
        bad = v.isna() | (v != v.round())
        if bad.any():
            errs.append(f"'{c}': {int(bad.sum())} value(s) are not whole numbers (first: {df.loc[bad, c].iloc[0]!r})")
        if (v < lo).any():
            errs.append(f"'{c}': {int((v < lo).sum())} value(s) below {lo:,}")
        num[c] = v
    if (num["year"] > dt.date.today().year + 1).any():
        errs.append("'year': a year in the future")
    rate = pd.to_numeric(df["homicide_rate_per_100k"], errors="coerce")
    if rate.isna().any() or (rate < 0).any():
        errs.append("'homicide_rate_per_100k': non-numeric or negative values")
    else:
        calc = num["homicide_cases"] / num["population"] * 1e5
        dev = (calc - rate).abs() / calc.abs().clip(lower=1.0)
        if (dev > RATE_REL_TOL).any():
            errs.append(f"'homicide_rate_per_100k' is not cases / population x 100,000 in {int((dev > RATE_REL_TOL).sum())} row(s)")
        if (rate > RATE_WARN).any():
            warns.append(f"{int((rate > RATE_WARN).sum())} row(s) with a rate above {RATE_WARN:g} per 100,000")

    for c in BOOL_COLS:
        bad = ~df[c].isin(["True", "False"])
        if bad.any():
            errs.append(f"'{c}': {int(bad.sum())} value(s) other than True/False (first: {df.loc[bad, c].iloc[0]!r})")
    if not df["flag_low_count"].isin(["True", "False"]).all():
        pass
    else:
        want = (num["homicide_cases"] < LOW_COUNT).map({True: "True", False: "False"})
        k = int((df["flag_low_count"] != want).sum())
        if k:
            errs.append(f"'flag_low_count' disagrees with homicide_cases < {LOW_COUNT} in {k} row(s)")

    age_blank = df["population_age_years"].str.strip() == ""
    age = pd.to_numeric(df["population_age_years"], errors="coerce")
    if (~age_blank & age.isna()).any():
        errs.append(f"'population_age_years': {int((~age_blank & age.isna()).sum())} value(s) are not numbers")
    elif (age < 0).any():
        errs.append("'population_age_years': negative values (it is a distance in years, never below 0)")
    tier_a = df["reliability_tier"] == "A"
    if (tier_a & age_blank).any():
        errs.append(f"{int((tier_a & age_blank).sum())} tier-A row(s) have no population_age_years: an unknown denominator age cannot be tier A")
    if (tier_a & (age > MAX_DENOMINATOR_AGE)).any():
        errs.append(f"{int((tier_a & (age > MAX_DENOMINATOR_AGE)).sum())} tier-A row(s) have a denominator older than {MAX_DENOMINATOR_AGE:g} years "
                    f"(population_age_years): that is tier B at best")
    for c, allowed in (("admin_level", ADMIN_LEVELS), ("indicator_type", INDICATOR_TYPES), ("reliability_tier", TIERS)):
        bad = ~df[c].isin(allowed)
        if bad.any():
            errs.append(f"'{c}': {int(bad.sum())} value(s) outside {allowed} (first: {df.loc[bad, c].iloc[0]!r})")
    toks = df["definition_flags"].apply(lambda v: [t.strip() for t in v.split(";") if t.strip()])
    badtok = sorted({t for ts in toks for t in ts if t not in DEFINITION_FLAGS})
    if badtok:
        errs.append(f"'definition_flags': unknown token(s) {badtok}; allowed {DEFINITION_FLAGS}")
    bad = ~df["retrieved"].str.fullmatch(r"\d{4}-\d{2}-\d{2}")
    if bad.any():
        errs.append(f"'retrieved': {int(bad.sum())} value(s) not in YYYY-MM-DD form")
    for c in ("source_homicide", "source_population"):
        if not df[c].str.contains(r"http|table|tbl", case=False, regex=True).all():
            warns.append(f"'{c}': some rows carry neither a URL nor a table identifier")

    key = df[["country", "parent_unit", "unit"]].assign(year=num["year"])
    k = int(key.duplicated(keep=False).sum())
    if k:
        errs.append(f"{k} row(s) share the same (country, parent_unit, unit, year)")
    srt = key.assign(_y=num["year"]).sort_values(["country", "parent_unit", "unit", "_y"], kind="stable")
    if not srt.index.equals(key.index):
        warns.append("rows are not sorted by (country, parent_unit, unit, year)")

    work = key.assign(pop=num["population"])
    gaps = 0
    jumps = []
    for (ctry, par, unit), g in work.groupby(["country", "parent_unit", "unit"], sort=False):
        g = g.sort_values("year")
        ys = g["year"].astype(int).tolist()
        if any(b - a > 1 for a, b in zip(ys, ys[1:])):
            gaps += 1
        ch = g["pop"].pct_change().abs()
        for yv, cv in zip(g["year"], ch):
            if pd.notna(cv) and cv > YOY_POP_WARN:
                jumps.append(f"{unit} {int(yv)} ({cv:+.0%})")
    if gaps:
        warns.append(f"{gaps} unit(s) have gaps in their years (allowed, but check they are real)")
    if jumps:
        warns.append(f"population moves by more than {YOY_POP_WARN:.0%} year to year: {', '.join(jumps[:6])}{' ...' if len(jumps) > 6 else ''}")
    return errs, warns


def require_valid(df: pd.DataFrame, tag: str = "schema") -> None:
    """For pipelines: print warnings, stop the run on errors, otherwise one summary line."""
    errs, warns = check_frame(df)
    for w in warns:
        print(f"[{tag}] warning: {w}")
    if errs:
        for e in errs:
            print(f"[{tag}] ERROR: {e}")
        sys.exit(f"[stop] the output does not follow homicide_format {FORMAT_VERSION} ({len(errs)} problem(s) above)")
    print(f"[{tag}] OK (homicide_format {FORMAT_VERSION}): {len(df)} rows, {df.groupby(['country', 'parent_unit', 'unit']).ngroups} unit(s), "
          f"years {int(df.year.min())}-{int(df.year.max())}")


def check_file(path: Path) -> bool:
    if not path.exists():
        print(f"FAIL {path}\n   file not found")
        return False
    raw = path.read_bytes()
    problems: list[str] = []
    warns: list[str] = []
    try:
        raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        print(f"FAIL {path.name}\n   not valid UTF-8")
        return False
    if not raw.startswith(b"\xef\xbb\xbf"):
        warns.append("no UTF-8 BOM (Excel on Windows may show wrong characters)")
    df = pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False)
    errs, w2 = check_frame(df)
    problems += errs
    warns += w2
    status = "FAIL" if problems else "PASS"
    print(f"{status} {path.name}  ({len(df)} rows, {df.shape[1]} columns)")
    for p in problems:
        print(f"   ERROR   {p}")
    for w in warns:
        print(f"   warning {w}")
    return not problems


# ----------------------------------------------------------------------------- specification text
def spec_markdown() -> str:
    L = [f"# Output format for all country pipelines (homicide_format {FORMAT_VERSION})", "",
         "Generated by `python homicide_format.py spec`; the validator enforces exactly this.", "",
         "## Folders", "",
         "```", "<repo>/Pipelines/homicide_format.py            (this module: format, folder layout, downloads, validator)",
         "<repo>/Pipelines/<Region>/<country>_homicide_rate.py  the pipeline",
         "<repo>/Pipelines/<Region>/<country>_homicide_rate.csv its ONE output",
         "<repo>/Data/Raw/<Region>/<Country>/                   every download of that country, date-stamped", "```", "",
         "- `<Region>` is Asia, Americas or Europe; the folder the script sits in decides where its downloads go.",
         "- **One output per script**: exactly one CSV. Diagnostics are printed, never written; anything else a script keeps (cached downloads) lives in its country's raw folder. "
         "No probe, helper or comparison scripts or files stay in `Pipelines/`.", "",
         "## Files", "",
         "- Script and output named `<country>_homicide_rate.py` / `<country>_homicide_rate.csv`, lower case with underscores (`south_korea_homicide_rate.csv`). "
         "A source that covers several countries is named after the source (`eurostat_homicide_rate.py`, raw files in `Data/Raw/Europe/Eurostat/`) and its `country` column carries the country.",
         "- CSV: UTF-8 **with BOM**, comma separated, one header row, `.` as decimal separator, no thousands separators, booleans `True`/`False`, "
         "empty cells instead of `NA`/`nan`/`None`, no line breaks inside cells, rows sorted by (country, parent_unit, unit, year).",
         "- Downloads go through `F.Fetcher`: robots.txt respected, each file saved as `<name>_<YYYYMMDD>.<ext>` in the country's raw folder and logged with its sha256, "
         "TLS certificates verified (turning that off needs an explicit `insecure=True` and prints a warning). `retrieved` is the date of the data actually used.",
         "- Nothing is typed in by hand: every number comes from an official file read by the script.", "",
         "## Columns (fixed order; country-specific extras go after them, in lower snake_case)", "",
         "| # | column | type | required | meaning |", "|---|---|---|---|---|"]
    for i, (n, k, r, d) in enumerate(COLUMNS, 1):
        L.append(f"| {i} | `{n}` | {k} | {'yes' if r else 'no'} | {d} |")
    L += ["", "## Vocabularies", "",
          f"- `admin_level`: {', '.join(ADMIN_LEVELS)}", f"- `indicator_type`: {', '.join(INDICATOR_TYPES)}",
          f"- `reliability_tier`: {', '.join(TIERS)}", f"- `definition_flags`: {', '.join(DEFINITION_FLAGS)}", "",
          "## Reliability tiers (verification strength)", ""]
    for t in TIERS:
        L.append(f"- **{t}** - {TIER_TEXT[t]}")
    L += ["", "## Rules the validator enforces", "",
          "- All core columns present, first, in order; no ISO-code columns.",
          f"- `year` whole number; `homicide_cases` whole number >= 0; `population` whole number >= {MIN_POP:,}.",
          f"- `homicide_rate_per_100k` = cases / population x 100,000 (relative tolerance {RATE_REL_TOL:g}).",
          f"- `flag_low_count` = (cases < {LOW_COUNT}); flags are `True`/`False`; vocabularies respected; `retrieved` is `YYYY-MM-DD`.",
          "- Required columns never empty; no leading/trailing spaces, line breaks or null words in any cell.",
          "- `(country, parent_unit, unit, year)` is unique.",
          f"- `population_age_years` is a number >= 0 or blank; tier A needs it present and at most {MAX_DENOMINATOR_AGE:g} (an unknown or older denominator is tier B at best).",
          f"- Warnings (not errors): unsorted rows, year gaps, population moving more than {YOY_POP_WARN:.0%} in a year, rates above {RATE_WARN:g}.", "",
          "## Conventions for every script", "",
          "- Commands `inspect` (checks, no file written) and `build` (writes the one CSV).",
          "- Every table is reconciled against its own totals or an equivalent identity; a failure stops the unit (or skips the year, with a warning, "
          "where the source's own table does not add up).",
          "- Decisions are named constants marked `# DECISION`; no statistic is ever typed into code or into a message.",
          f"- Shared constants (low count {LOW_COUNT}, minimum population {MIN_POP:,}, outlier z {OUTLIER_Z}, minimum series {OUTLIER_MIN_YEARS}) live only in `homicide_format.py`.",
          "- Text columns are in English; local-script names go in `unit_local` only.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("check")
    c.add_argument("files", nargs="+")
    sub.add_parser("spec")
    t = sub.add_parser("template")
    t.add_argument("path", nargs="?", default="homicide_format_template.csv")
    a = ap.parse_args()
    if a.cmd == "spec":
        sys.stdout.reconfigure(encoding="utf-8")
        print(spec_markdown())
    elif a.cmd == "template":
        row = {"country": "Exampleland", "unit": "Example Province", "unit_local": "", "unit_code": "", "admin_level": "admin1",
               "unit_type": "province", "parent_unit": "", "year": 2024, "homicide_cases": 120, "population": 3_000_000,
               "indicator_type": "police_recorded_cases", "reliability_tier": "A", "definition_flags": "",
               "validation": "what was checked, with the numbers", "indicator": "what the numerator is", "population_method": "how the denominator was built", "population_age_years": 0.0,
               "data_notes": "", "source_homicide": "https://example.org/table", "source_population": "https://example.org/pop",
               "retrieved": dt.date.today().isoformat(), "flag_outlier_year": False}
        write_csv(finalize(pd.DataFrame([row])), a.path)
        print(f"[ok] wrote {a.path}")
    else:
        ok = all([check_file(Path(f)) for f in a.files])
        sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()