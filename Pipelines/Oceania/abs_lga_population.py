"""
Shared helpers of the Australian local government area (LGA) pipelines (New South Wales, Victoria, ...): the ABS "Regional population" cubes and name matching.

ABS regional population (3218.0): estimated resident population by LGA at 30 June. The cubes of the release page are identified by their CONTENT (a table 'Table 1' with the columns
'LGA code', 'LGA name' and 20 or more years; a table with 'S/T code' beside 'LGA code'), not by the numbering of the file names, which changes with the releases.
"""
import re
import sys
from urllib.parse import unquote

import pandas as pd


def norm(name) -> str:
    """Names are matched without capitals, bracketed parts ('(NSW)', '(C)'), punctuation and the words city / council."""
    t = re.sub(r"\(.*?\)", " ", str(name).lower())
    t = re.sub(r"[-'.,/]", " ", t)
    t = re.sub(r"\b(city|council|shire|municipality|regional|rural|aboriginal)\b", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def read_sheet(xl: pd.ExcelFile, sheet: str) -> pd.DataFrame:
    return pd.read_excel(xl, sheet_name=sheet, header=None, dtype=object)


def year_of(v):
    m = re.fullmatch(r"((?:19|20)\d{2})(?:\.0)?", str(v).strip())
    return int(m.group(1)) if m else None


def load_abs_population(links, get, open_excel):
    """Find, by content, the LGA time-series cube and the table that gives each LGA code its state. -> ({(code, year): ERP}, {code: (name, state)})."""
    series, state_of = None, None
    for t, u in links:
        nm = unquote(u).rsplit("/", 1)[-1]
        try:
            xl = open_excel(get(u, "abs_pop_" + re.sub(r"[^A-Za-z0-9]+", "_", nm)[:40]), ".xlsx")
        except Exception:
            continue
        for sh in xl.sheet_names:
            if not re.fullmatch(r"Table 1", sh, re.I):
                continue
            raw = read_sheet(xl, sh)
            hdr = next((i for i in range(min(15, len(raw))) if str(raw.iat[i, 0]).strip().lower() in ("lga code", "s/t code")), None)
            if hdr is None:
                continue
            cells = [str(x).strip().lower() for x in raw.iloc[hdr]]
            if cells[:2] == ["lga code", "lga name"] and series is None:
                yrow = max(range(max(0, hdr - 4), hdr), key=lambda i: sum(year_of(v) is not None for v in raw.iloc[i]))
                yrs = {j: year_of(v) for j, v in enumerate(raw.iloc[yrow]) if year_of(v) is not None}
                if len(yrs) >= 20:
                    ser = {}
                    for i in range(hdr + 1, len(raw)):
                        code = str(raw.iat[i, 0]).strip()
                        if re.fullmatch(r"\d{5}", code):
                            for j, y in yrs.items():
                                v = pd.to_numeric(raw.iat[i, j], errors="coerce")
                                if v == v:
                                    ser[(code, y)] = float(v)
                    names = {str(raw.iat[i, 0]).strip(): str(raw.iat[i, 1]).strip() for i in range(hdr + 1, len(raw)) if re.fullmatch(r"\d{5}", str(raw.iat[i, 0]).strip())}
                    series = (ser, names, nm)
            elif cells[:1] == ["s/t code"] and "lga code" in cells and state_of is None:
                ci, si = cells.index("lga code"), cells.index("s/t name")
                state_of = {str(raw.iat[i, ci]).strip(): str(raw.iat[i, si]).strip() for i in range(hdr + 1, len(raw)) if re.fullmatch(r"\d{5}", str(raw.iat[i, ci]).strip())}
        if series and state_of:
            break
    if not series:
        sys.exit("[stop] ABS: no cube with 'LGA code', 'LGA name' and 20 or more yearly columns was found among the files of the regional population page")
    if not state_of:
        sys.exit("[stop] ABS: no table with 'S/T code' beside 'LGA code' was found, so the LGAs cannot be assigned to New South Wales")
    ser, names, nm = series
    return ser, {c: (names[c], state_of.get(c)) for c in names}, nm