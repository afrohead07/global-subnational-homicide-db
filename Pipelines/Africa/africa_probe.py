#!/usr/bin/env python3
"""
Africa - PROBE of the leads of the audit report, ten countries in one run (it writes no CSV: it only saves the downloads and prints what is there).

For every lead (a page or a file) it prints what a parser needs to know:
  * a PAGE: its download-like links (pdf, xlsx, csv, zip) and the links whose text mentions crime, criminality, statistics, annual or report;
  * an EXCEL / CSV file: the sheets, their shapes and the first rows, and the rows that mention murder / homicide;
  * a PDF file: the page count, the table captions, and the lines that mention murder / homicide (with their page), in English, French and Portuguese.
Every lead comes from the audit report and is only a LEAD: a dead address or a file without homicide lines is a finding, not an error.

Countries still open: Kenya and Lesotho. Dropped (named, with the reason, when asked for): Tunisia, Mozambique, Sierra Leone, Zimbabwe, Uganda, Botswana; with their own script: Nigeria, Tanzania.

TLS         a host whose certificate the default store cannot verify is tried with the operating-system certificate store (pip install truststore) and, only with --insecure, with verification OFF (warning printed).
Folders:    this script sits in <repo>/Pipelines/Africa/ ; downloads go to <repo>/Data/Raw/Africa/Probe/
Commands:   python africa_probe.py [kenya lesotho]     (no names = both)     Options: --reuse, --insecure
Needs:      pip install pandas requests beautifulsoup4 openpyxl python-calamine pdfplumber truststore
"""
import argparse
import importlib.util
import io
import re
import sys
import time
import warnings
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))        # Pipelines/ holds homicide_format.py
try:
    import homicide_format as F        # folder layout and downloader shared by every pipeline
except ImportError:
    sys.exit("[stop] homicide_format.py must sit in the Pipelines folder, one level above this script's Region folder")
if getattr(F, "REVISION", 0) < 14:
    sys.exit("[stop] Pipelines/homicide_format.py is out of date for this script: replace it with the latest version (revision 14)")

REVISION = 9
warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")
P = F.paths(__file__, "Probe")
RAW = P.raw
ENGINE = "calamine" if importlib.util.find_spec("python_calamine") else "openpyxl"
KEY = re.compile(r"murder|homicid|manslaughter|killing|meurtre|assassinat|homic[ií]dio|crimes? (?:against|contre) (?:the )?(?:person|les personnes|as pessoas)|offences? against (?:the )?person|infraction.{0,20}personne", re.I)
LINK_TEXT = re.compile(r"crime|criminal|criminel|statistic|statistiq|estat[ií]st|annual|annuel|report|rapport|relat[oó]rio|yearbook|annuaire|data|dataset|donn", re.I)
FILE_RE = re.compile(r"\.(xlsx?|csv|zip|pdf|json)(?:[?#]|$)", re.I)

# country -> (what the audit report says, [leads]); a lead is ("page", url) or ("file", url)
# a lead is (kind, url) or (kind, url, [regexes]): for a PAGE, the regexes pick the files to open and describe (the first file whose address or link text matches each regex)
LEADS = {
    "kenya": ("The population appendix 'Crime Rate for the Year 2021' (pages 39 and 40 of the 2021 police report) is printed in full: one county, Nyamira, has no row that the reader recognises; and the offences table of the 2020 report "
              "(county names alone on a line, figures on the next) is located by the first lines of pages 25 to 33", [
        ("file", "https://nationalpolice.go.ke/sites/default/files/2024-08/Annual Crime Report - 2021.pdf", None, [39, 40]),
        ("file", "https://nationalpolice.go.ke/sites/default/files/2024-08/Annual Crime Report - 2020.pdf", None, ["h25-33", 27])]),
    "lesotho": ("The crime reports are solved (python lesotho_homicide_rate.py); what is missing is a Bureau of Statistics file with the 2016 census population of the ten districts: the Bureau's pages are searched for it", [
        ("page", "https://www.bos.gov.ls/", [r"census|population"]),
        ("page", "https://www.bos.gov.ls/Statistics.html", [r"census|population"]),
        ("page", "https://www.bos.gov.ls/Demography.html", [r"census|population"]),
        ("file", "https://www.bos.gov.ls/BoS_reports/Copy of Demography/2016_Census_Analytical_Report.pdf"),
        ("file", "https://www.bos.gov.ls/BoS_reports/Copy of Demography/Lesotho_2016_Census_Report.pdf")]),
}
DROPPED = {
    "nigeria": "has its own script now: python nigeria_homicide_rate.py build",
    "zimbabwe": "the province tables of 'Crime in Zimbabwe' carry only the broad category 'acts leading to death or intending to cause death' (1,094 in Q1 2026, of which intentional homicide is 306 nationally); provincial homicide is not published and the quarterly files do not give a full year by province",
    "uganda": "the 2024 annual crime report is published as a slide presentation (39 pages, charts as images) and the full report file is not on the site; the data page has only the 2010, 2012 and 2015 abstracts",
    "botswana": "the only crime report found counts COURT-DECIDED cases by magisterial court (homicide 364 accused in 2020), not police records, and the police PDF of the audit report is dead",
    "tunisia": "the portal's crime datasets are national (coverage 'Tunisie'), have no homicide line and end in 2015",
    "mozambique": "the INE report 'Estatísticas de Crime e Justiça' gives 'crimes contra pessoas' by province, with no homicide line in its tables",
    "sierra_leone": "the annual reports are launched every year but no primary file or working police website was found (only newspaper coverage)",
}


class Ladder:
    """A downloader that climbs the TLS ladder per host: normal verification, the operating-system certificate store, then (only with --insecure) no verification."""
    def __init__(self, insecure: bool):
        spec = [("verified", {}), ("operating-system certificate store", {"os_trust": True})]
        if insecure:
            spec.append(("verification OFF (--insecure)", {"os_trust": True, "insecure": True}))
        self.names = [n for n, _ in spec]
        self.fetchers = [F.Fetcher(RAW, user_agent="Mozilla/5.0 (research pipeline)", retries=2, **kw) for _, kw in spec]
        self.ok = {}

    def get(self, url, name=None, reuse=False, suffix=None, reject_html=False, headers=None):
        host, last = urlparse(url).netloc, None
        for i in range(self.ok.get(host, 0), len(self.fetchers)):
            try:
                data = self.fetchers[i].get(url, name, reuse=reuse, suffix=suffix, reject_html=reject_html, headers=headers)
                if i and self.ok.get(host) != i:
                    print(f"   [tls] {host}: the default store cannot verify its certificate; downloading with: {self.names[i]}")
                self.ok[host] = i
                return data
            except F.RobotsDisallowed:
                raise
            except Exception as e:
                last = e
                if "SSL" not in str(e) and "certificate" not in str(e).lower():
                    raise
        raise RuntimeError(f"{last}  [certificate problem on every mode tried: {', '.join(self.names)}]")


def slug(url: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", urlparse(url).netloc + urlparse(url).path)[-60:].strip("_")


def pdf_pages(data: bytes) -> list:
    try:
        import pdfplumber
        with pdfplumber.open(io.BytesIO(data)) as pdf:
            return [(pg.extract_text() or "") for pg in pdf.pages]
    except ImportError:
        try:
            from pypdf import PdfReader
            return [(pg.extract_text() or "") for pg in PdfReader(io.BytesIO(data)).pages]
        except ImportError:
            sys.exit("[stop] reading PDFs needs a library: pip install pdfplumber")


def describe_pdf(data: bytes, cap_lines: int = 45, show=None):
    pages = pdf_pages(data)
    print(f"   PDF: {len(pages)} pages; characters per page (first 12): {[len(t) for t in pages[:12]]}")
    caps = [(k + 1, ln.strip()) for k, t in enumerate(pages) for ln in t.splitlines() if re.match(r"^\s*(?:table|tableau|tabela|quadro|figure)\s*[\dA-Z]", ln, re.I)]
    print(f"   table captions ({len(caps)}), the first 28:")
    for k, ln in caps[:28]:
        print(f"      p{k}: {ln[:130]}")
    hit = [(k + 1, re.sub(r"\s+", " ", ln.strip())) for k, t in enumerate(pages) for ln in t.splitlines() if KEY.search(ln)]
    print(f"   lines that mention murder / homicide ({len(hit)}), the first {cap_lines}:")
    for k, ln in hit[:cap_lines]:
        print(f"      p{k}: {ln[:150]}")
    for k in (show or []):
        if isinstance(k, str) and re.fullmatch(r"h\d+-\d+", k):                 # "h36-59": the first three lines of every page from 36 to 59
            a, b = (int(x) for x in k[1:].split("-"))
            print(f"   --- the first three lines of pages {a} to {b}:")
            for q in range(a, min(b, len(pages)) + 1):
                print(f"      p{q}: " + " | ".join(x.strip()[:60] for x in pages[q - 1].splitlines()[:3]))
        elif isinstance(k, int) and 0 < k <= len(pages):
            print(f"   --- page {k} in full (the first 70 lines):")
            for ln in pages[k - 1].splitlines()[:70]:
                print("      " + ln[:170])


def open_excel(data: bytes, suffix: str = ".xlsx"):
    last = None
    for how in ("bytes", "path", "openpyxl"):
        try:
            if how == "bytes":
                return pd.ExcelFile(io.BytesIO(data), engine=ENGINE)
            if how == "path":
                tmp = RAW / ("_open" + suffix)
                tmp.write_bytes(data)
                return pd.ExcelFile(tmp, engine=ENGINE)
            return pd.ExcelFile(io.BytesIO(data), engine="openpyxl")
        except Exception as e:
            last = e
    raise last


def describe_table(data: bytes, url: str):
    if re.search(r"\.csv(?:[?#]|$)", url, re.I):
        try:
            df = pd.read_csv(io.BytesIO(data), header=None, dtype=object, encoding_errors="replace", sep=None, engine="python")
        except Exception as e:
            print(f"   CSV could not be read: {str(e)[:100]}")
            return
        frames = {"csv": df}
    else:
        xl = open_excel(data, ".xls" if re.search(r"\.xls(?:[?#]|$)", url, re.I) else ".xlsx")
        print(f"   sheets ({len(xl.sheet_names)}): {xl.sheet_names[:14]}")
        frames = {sh: pd.read_excel(xl, sheet_name=sh, header=None, dtype=object) for sh in xl.sheet_names[:8]}
    for sh, raw in frames.items():
        print(f"   --- {sh}: {raw.shape}")
        print(raw.iloc[:7, :9].to_string(max_colwidth=22, header=False))
        txt = raw.iloc[:, :20].fillna("").astype(str)
        hit = raw[[bool(KEY.search(" ".join(r))) for r in txt.itertuples(index=False)]]
        if len(hit):
            print(f"   rows that mention murder / homicide ({len(hit)}), the first 8:")
            print(hit.iloc[:8, :12].to_string(max_colwidth=22, header=False))


def links_of(html: str, base: str):
    from bs4 import BeautifulSoup
    out, seen = [], set()
    for a in BeautifulSoup(html, "html.parser").find_all("a", href=True):
        u, t = urljoin(base, a["href"].strip()), a.get_text(" ", strip=True)
        if u in seen or u.startswith(("mailto:", "javascript:", "tel:")):
            continue
        if FILE_RE.search(u) or LINK_TEXT.search(t) or LINK_TEXT.search(unquote(u).rsplit("/", 1)[-1]):
            seen.add(u)
            out.append((t, u))
    return out


def kind_of(data: bytes, url: str) -> str:
    if data[:4] == b"%PDF":
        return ".pdf"
    if data[:2] == b"PK":
        return ".xlsx"
    if data[:4] == b"\xd0\xcf\x11\xe0":
        return ".xls"
    return ".csv" if re.search(r"\.csv(?:[?#]|$)", url, re.I) else ".bin"


def probe_lead(kind: str, url: str, fetch, reuse: bool, follow=None, show=None):
    print(f"\n  --- {kind.upper()} {url}", flush=True)
    try:
        t0 = time.time()
        if kind == "page":
            html = fetch.get(url, "probe_" + slug(url), reuse=reuse, suffix=".html").decode("utf-8", "replace")
            ls = links_of(html, url)
            files = [(t, u) for t, u in ls if FILE_RE.search(u)]
            print(f"   page of {len(html):,} characters; {len(ls)} relevant link(s), {len(files)} of them files; files first, then pages (the first 60):")
            for t, u in (files + [x for x in ls if x not in files])[:60]:
                print(f"      {t[:48]:48} {unquote(u)[:118]}")
            if len(html) < 400:
                print("   (a very short answer: probably a bot-protection stub, a redirect or an empty page)")
            for rx in (follow or []):
                hit = next(((t, u) for t, u in ls if FILE_RE.search(u) and re.search(rx, unquote(u) + " " + t, re.I)), None)
                if hit:
                    probe_lead("file", hit[1], fetch, reuse, None, show)
                else:
                    print(f"   [follow] no file link matches /{rx}/")
            return
        data = fetch.get(url, "probe_" + slug(url), reuse=reuse, suffix=".bin", reject_html=True)
        suffix = kind_of(data, url)
        print(f"   downloaded {len(data) / 1e6:.2f} MB in {time.time() - t0:.0f} s; it is a {suffix[1:].upper()} file", flush=True)
        if suffix == ".pdf":
            describe_pdf(data, 45, show)
        elif suffix == ".bin":
            print("   the file is neither a PDF nor a workbook: first bytes " + repr(data[:60]))
        else:
            describe_table(data, url if suffix == ".csv" else "x" + suffix)
    except F.RobotsDisallowed:
        print("   [robots] this address is not open to automated reading: save the file by hand as manual_<name> in " + str(RAW))
    except Exception as e:
        print(f"   [no] {str(e)[:170]}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("countries", nargs="*", help="country names (default: all ten)")
    ap.add_argument("--reuse", action="store_true")
    ap.add_argument("--insecure", action="store_true", help="last resort: TLS verification OFF for a host whose certificate cannot be verified")
    a = ap.parse_args()
    print(f"[africa_probe.py revision {REVISION}]")
    names = a.countries or list(LEADS)
    bad = [n for n in names if n not in LEADS and n not in DROPPED]
    if bad:
        sys.exit(f"[stop] unknown country {bad}; choose from {list(LEADS)}")
    for n in names:
        if n in DROPPED:
            print(f"[dropped] {n}: {DROPPED[n]}")
    names = [n for n in names if n in LEADS]
    fetch = Ladder(a.insecure)
    for n in names:
        note, leads = LEADS[n]
        print("\n" + "=" * 100 + f"\n{n.upper().replace('_', ' ')}: {note}\n" + "=" * 100)
        for lead in leads:
            probe_lead(lead[0], lead[1], fetch, a.reuse, lead[2] if len(lead) > 2 else None, lead[3] if len(lead) > 3 else None)
    for p in sorted(RAW.glob("manual_*")):
        print(f"\n===== manual file {p.name} =====")
        describe_pdf(p.read_bytes()) if p.suffix.lower() == ".pdf" else describe_table(p.read_bytes(), p.name)
    print("\n[probe only] nothing written but the downloads; paste this output and the parsers will be written against what the files really contain")


if __name__ == "__main__":
    main()