#!/usr/bin/env python3
"""
BUILD THE DOCUMENTATION - Docs/DEFINITIONS.md, Docs/DEFINITIONS.html and Docs/definitions_matrix.csv

Merges the statements of docs_content.py (for every layer of the database: what the source calls the offence, what it counts, how that compares with the UNODC definition of intentional
homicide, element by element, with the source of each statement) with the numbers read from the master panel (rows, units, years, tiers, counting unit, definition flags), so that the
document never disagrees with the data about coverage.

The text is cross-checked against the data in the console only (a layer whose text says attempts are counted but whose rows lack the flag includes_attempts, a counting unit that differs from
the panel's, a layer present on one side only) and against a list of phrases that do not belong in a published document. Use --strict to stop with an error when anything is reported.

Usage       python build_docs.py                (reads Data/Output/global_master_panel.csv, or the five continental panels if the global one is missing)
            python build_docs.py --panel path\\to\\panel.csv --out path\\to\\Docs --strict
Needs       pip install pandas
"""
import argparse
import html
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import docs_content as C

REVISION = 6
SHORT = {"murder": "Murder", "manslaughter": "Manslaughter", "attempts": "Attempts", "nonintent": "Non-intentional", "other": "Other", "legal": "Legal"}
SHORT_STATUS = {"in": "yes", "out": "no", "mixed": "partly", "ns": "n.s."}
FORBIDDEN = re.compile(r"TO CHECK|CORRECTION|not yet|deferred|to be verified|pending|planned|not been checked|not reached|next place|earlier version|first version|\b20\d\d-\d\d-\d\d\b|typed in|would have to be|are next", re.I)


# --------------------------------------------------------------------------------------------------------------------------------------------------------- data
def load_panel(path):
    root = Path(__file__).resolve().parent.parent
    if path:
        files = [Path(path)]
    else:
        out = root / "Data" / "Output"
        g = out / "global_master_panel.csv"
        files = [g] if g.exists() else [out / f"{r}_master_panel.csv" for r in ("africa", "americas", "asia", "europe", "oceania") if (out / f"{r}_master_panel.csv").exists()]
    if not files:
        sys.exit("[stop] no master panel found in Data/Output: run the *_master_panel.py scripts first (or give --panel)")
    df = pd.concat([pd.read_csv(f, dtype=str, keep_default_na=False) for f in files], ignore_index=True, sort=False)
    for c in ("layer", "count_unit", "definition_flags", "indicator", "indicator_type", "admin_level", "reliability_tier", "population_age_years", "unit", "parent_unit", "country", "region"):
        if c not in df.columns:
            df[c] = ""
    if (df["layer"] == "").all():
        sys.exit("[stop] the panel has no `layer` column: rebuild the panels with master_panel.py")
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["age"] = pd.to_numeric(df["population_age_years"], errors="coerce")
    df["unit_key"] = df["country"] + "|" + df["parent_unit"] + "|" + df["unit"]
    return df, files


def layer_stats(df: pd.DataFrame) -> dict:
    out = {}
    for layer, g in df.groupby("layer"):
        flags = sorted({f.strip() for v in g["definition_flags"] for f in str(v).split(";") if f.strip()})
        out[layer] = {
            "rows": len(g), "units": g["unit_key"].nunique(), "countries": sorted(g["country"].unique()), "admin": sorted(g["admin_level"].unique()),
            "first": int(g["year"].min()), "last": int(g["year"].max()), "tiers": g["reliability_tier"].value_counts().to_dict(),
            "count_units": sorted(g["count_unit"][g["count_unit"] != ""].unique()), "flags": flags, "indicator_types": g["indicator_type"].value_counts().to_dict(),
            "cited": ({c: gg["igarape_source_1"][gg["igarape_source_1"] != ""].value_counts().head(3) for c, gg in g.groupby("country")} if layer == "igarape" and "igarape_source_1" in g.columns else None),
        }
    return out


def checks(stats: dict) -> list:
    msgs = []
    for layer in sorted(stats):
        if layer not in C.LAYERS:
            msgs.append(f"layer '{layer}' is in the panel ({stats[layer]['rows']:,} rows) but has no entry in docs_content.py")
    for layer, d in C.LAYERS.items():
        if layer not in stats:
            msgs.append(f"layer '{layer}' has an entry in docs_content.py but is not in the panel")
            continue
        s, el = stats[layer], d["elements"]
        allowed = {d["unit"]} | set(d.get("unit_also", []))
        if s["count_units"] and not set(s["count_units"]) <= allowed:
            msgs.append(f"{layer}: the text says the counted unit is {sorted(allowed)}, the panel's count_unit is {s['count_units']}")
        if el["attempts"][0] == "in" and "includes_attempts" not in s["flags"]:
            msgs.append(f"{layer}: the text says attempts are counted but the rows carry no includes_attempts flag (flags found: {s['flags'] or 'none'})")
        if el["attempts"][0] != "in" and "includes_attempts" in s["flags"]:
            msgs.append(f"{layer}: the rows carry includes_attempts but the text does not say attempts are counted")
        if el["manslaughter"][0] == "in" and "includes_manslaughter" not in s["flags"]:
            msgs.append(f"{layer}: the text says manslaughter is counted but the rows carry no includes_manslaughter flag (flags found: {s['flags'] or 'none'})")
        if d["unit"] == "victims" and "counts_victims" not in s["flags"]:
            msgs.append(f"{layer}: the text says the unit is victims but the rows carry no counts_victims flag")
        if d["unit"] != "victims" and "counts_victims" in s["flags"]:
            msgs.append(f"{layer}: the rows carry counts_victims but the text says the unit is '{d['unit']}'")
    return msgs


def lint_text() -> list:
    out = []
    for layer, d in C.LAYERS.items():
        texts = [d.get(f, "") for f in ("term", "unit_note", "time", "verdict_note")] + list(d.get("notes", [])) + [t[2] for t in d["elements"].values()]
        for t in texts:
            m = FORBIDDEN.search(str(t))
            if m:
                out.append(f"{layer}: '{m.group(0)}' in: {str(t)[:100]}")
    for title, text in C.CROSS_CUTTING:
        m = FORBIDDEN.search(title + " " + text)
        if m:
            out.append(f"cross-cutting '{title}': '{m.group(0)}'")
    return out


# --------------------------------------------------------------------------------------------------------------------------------------------------------- text helpers
def tier_text(t: dict) -> str:
    return ", ".join(f"{k} {t[k]:,}" for k in ("A", "B", "C") if k in t) or "-"


def coverage_line(s: dict) -> str:
    return (f"{s['rows']:,} rows, {s['units']:,} unit{'s' if s['units'] != 1 else ''} ({', '.join(s['admin'])}), {s['first']}-{s['last']}; reliability tiers {tier_text(s['tiers'])}; "
            f"count unit in the panel: {', '.join(s['count_units']) or '-'}; definition flags in the rows: {', '.join(s['flags']) or 'none'}")


def h(x) -> str:
    return html.escape(str(x), quote=True)


def src_md(src: str) -> str:
    return f"[source]({src.replace(' ', '%20')})" if src.startswith("http") else (src or "")


def src_html(src: str) -> str:
    return f"<a href='{h(src)}'>source</a>" if src.startswith("http") else h(src)


def layers_by_region():
    for region in C.REGION_ORDER:
        yield region, [(k, d) for k, d in C.LAYERS.items() if d["region"] == region]


def md_cell(x: str) -> str:
    return str(x).replace("|", "/").replace("\n", " ")


# --------------------------------------------------------------------------------------------------------------------------------------------------------- markdown
def build_md(stats, files, df) -> str:
    R = C.REFERENCE
    L = ["# Definitions: what each series in the database counts", "",
         f"How each source in the database defines and counts homicide, compared with the UNODC definition of intentional homicide. Every statement gives the page or file it comes from. "
         f"Built from {', '.join(f.name for f in files)} ({len(df):,} rows, {df['layer'].nunique()} layers).", ""]
    L += ["## 1. Reference definition: UNODC / ICCS 0101", "", f"**{R['name']}**", "", f"> {R['definition']}", "", "Three elements make a killing an intentional homicide:", ""]
    L += [f"- {e}" for e in R["elements"]]
    L += ["", "Included: " + "; ".join(R["includes"]) + ".", "", "Excluded: " + "; ".join(R["excludes"]) + ".", "", R["health"], "", "Sources: " + "; ".join(f"[{t}]({u})" for t, u in R["sources"]), ""]
    L += ["## 2. How to read the tables", "",
          "Every layer is one source file. For each layer, six elements of the reference definition are compared with what the source counts. The treatment of an element is one of: "
          "**counted**, **not counted**, **partly counted**, **not stated** (the source does not say).", "",
          "The verdict places the series as a whole against the reference:", ""]
    L += [f"- **{k}**: {v}" for k, v in C.VERDICTS.items()]
    L += ["", "## 3. Summary", "", "yes = counted, no = not counted, partly = partly counted, n.s. = not stated.", "",
          "| Layer | Counted unit | " + " | ".join(SHORT[k] for k, _ in C.ELEMENTS) + " | Verdict |", "|---|---|" + "---|" * len(C.ELEMENTS) + "---|"]
    for region, items in layers_by_region():
        for k, d in items:
            L.append(f"| [{md_cell(d['title'])}](#{k}) | {d['unit']} | " + " | ".join(SHORT_STATUS[d["elements"][e][0]] for e, _ in C.ELEMENTS) + f" | {d['verdict']} |")
    L += ["", "## 4. Cross-cutting issues", ""]
    for t, x in C.CROSS_CUTTING:
        L += [f"**{t}.** {x}", ""]
    L += ["## 5. Layer by layer", ""]
    for region, items in layers_by_region():
        if not items:
            continue
        L += [f"### {region}", ""]
        for k, d in items:
            s = stats.get(k)
            L += [f"<a id=\"{k}\"></a>", f"#### {d['title']}", "", f"- Source: {d['source']}", f"- Term in the source: {d['term']}",
                  f"- Counted unit: {d['unit']}. {d['unit_note'] or C.UNIT_NOTE.get(d['unit'], '')}", f"- Time reference: {d['time']}",
                  f"- Verdict against the reference: **{d['verdict']}**. {d['verdict_note']}"]
            if s:
                L.append(f"- In the database: {coverage_line(s)}")
            L += ["", "| Element | Treatment | What the source says | |", "|---|---|---|---|"]
            for e, label in C.ELEMENTS:
                st = d["elements"][e]
                L.append(f"| {md_cell(label)} | {C.STATUS[st[0]][0]} | {md_cell(st[2])} | {src_md(st[3]) if len(st) > 3 else ''} |")
            L.append("")
            for n in d.get("notes", []):
                L.append(f"- {n}")
            if s and s.get("cited"):
                L += ["", "The three sources most cited by each country's rows (the definition of every series is that of its source):", "", "| Country | Most cited sources (rows) |", "|---|---|"]
                L += [f"| {md_cell(c)} | " + md_cell("; ".join(f"{str(a)[:90]} ({int(b):,})" for a, b in ser.items())) + " |" for c, ser in s["cited"].items()]
            L += ["", "Sources: " + "; ".join(f"[{t}]({u.replace(' ', '%20')})" for t, u in d["sources"]), ""]
    return "\n".join(L) + "\n"


# --------------------------------------------------------------------------------------------------------------------------------------------------------- html
CSS = ("body{font-family:system-ui,-apple-system,'Segoe UI',Roboto,Arial,sans-serif;max-width:62rem;margin:2rem auto;padding:0 1rem;line-height:1.5;color:#111;background:#fff}"
       "h1,h2,h3,h4{line-height:1.25}h2{margin-top:2.2rem;border-bottom:1px solid #bbb;padding-bottom:.2rem}h4{margin-top:2rem}"
       "table{border-collapse:collapse;width:100%;margin:.8rem 0;font-size:.92rem}th,td{border:1px solid #bbb;padding:.3rem .5rem;text-align:left;vertical-align:top}th{background:#f1f1f1}"
       "blockquote{border-left:3px solid #bbb;margin:1rem 0;padding:.1rem 1rem;color:#333}a{color:#0645ad}.wrap{overflow-x:auto}")


def build_html(stats, files, df) -> str:
    R = C.REFERENCE
    P = [f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width, initial-scale=1'><title>Definitions: what each series in the database counts</title><style>{CSS}</style></head><body>"]
    P.append("<h1>Definitions: what each series in the database counts</h1>")
    P.append(f"<p>How each source in the database defines and counts homicide, compared with the UNODC definition of intentional homicide. Every statement gives the page or file it comes from. "
             f"Built from {h(', '.join(f.name for f in files))} ({len(df):,} rows, {df['layer'].nunique()} layers).</p>")
    P.append("<h2>1. Reference definition: UNODC / ICCS 0101</h2>")
    P.append(f"<p><strong>{h(R['name'])}</strong></p><blockquote>{h(R['definition'])}</blockquote><p>Three elements make a killing an intentional homicide:</p><ul>" + "".join(f"<li>{h(e)}</li>" for e in R["elements"]) + "</ul>")
    P.append(f"<p>Included: {h('; '.join(R['includes']))}.</p><p>Excluded: {h('; '.join(R['excludes']))}.</p><p>{h(R['health'])}</p><p>Sources: " + "; ".join(f"<a href='{h(u)}'>{h(t)}</a>" for t, u in R["sources"]) + "</p>")
    P.append("<h2>2. How to read the tables</h2><p>Every layer is one source file. For each layer, six elements of the reference definition are compared with what the source counts. The treatment of an element is one of: "
             "<strong>counted</strong>, <strong>not counted</strong>, <strong>partly counted</strong>, <strong>not stated</strong> (the source does not say).</p><p>The verdict places the series as a whole against the reference:</p><ul>"
             + "".join(f"<li><strong>{h(k)}</strong>: {h(v)}</li>" for k, v in C.VERDICTS.items()) + "</ul>")
    P.append("<h2>3. Summary</h2><p>yes = counted, no = not counted, partly = partly counted, n.s. = not stated.</p><div class='wrap'><table><tr><th>Layer</th><th>Counted unit</th>"
             + "".join(f"<th>{h(SHORT[k])}</th>" for k, _ in C.ELEMENTS) + "<th>Verdict</th></tr>")
    for region, items in layers_by_region():
        for k, d in items:
            P.append(f"<tr><td><a href='#{k}'>{h(d['title'])}</a></td><td>{h(d['unit'])}</td>" + "".join(f"<td>{SHORT_STATUS[d['elements'][e][0]]}</td>" for e, _ in C.ELEMENTS) + f"<td>{h(d['verdict'])}</td></tr>")
    P.append("</table></div>")
    P.append("<h2>4. Cross-cutting issues</h2>" + "".join(f"<p><strong>{h(t)}.</strong> {h(x)}</p>" for t, x in C.CROSS_CUTTING))
    P.append("<h2>5. Layer by layer</h2>")
    for region, items in layers_by_region():
        if not items:
            continue
        P.append(f"<h3>{h(region)}</h3>")
        for k, d in items:
            s = stats.get(k)
            P.append(f"<section id='{k}'><h4>{h(d['title'])}</h4><ul><li>Source: {h(d['source'])}</li><li>Term in the source: {h(d['term'])}</li>"
                     f"<li>Counted unit: {h(d['unit'])}. {h(d['unit_note'] or C.UNIT_NOTE.get(d['unit'], ''))}</li><li>Time reference: {h(d['time'])}</li>"
                     f"<li>Verdict against the reference: <strong>{h(d['verdict'])}</strong>. {h(d['verdict_note'])}</li>" + (f"<li>In the database: {h(coverage_line(s))}</li>" if s else "") + "</ul>")
            P.append("<div class='wrap'><table><tr><th>Element</th><th>Treatment</th><th>What the source says</th><th></th></tr>")
            for e, label in C.ELEMENTS:
                st = d["elements"][e]
                P.append(f"<tr><td>{h(label)}</td><td>{h(C.STATUS[st[0]][0])}</td><td>{h(st[2])}</td><td>{src_html(st[3]) if len(st) > 3 else ''}</td></tr>")
            P.append("</table></div>")
            if d.get("notes"):
                P.append("<ul>" + "".join(f"<li>{h(n)}</li>" for n in d["notes"]) + "</ul>")
            if s and s.get("cited"):
                P.append("<p>The three sources most cited by each country's rows (the definition of every series is that of its source):</p><div class='wrap'><table><tr><th>Country</th><th>Most cited sources (rows)</th></tr>"
                         + "".join(f"<tr><td>{h(c)}</td><td>" + h("; ".join(f"{str(a)[:90]} ({int(b):,})" for a, b in ser.items())) + "</td></tr>" for c, ser in s["cited"].items()) + "</table></div>")
            P.append("<p>Sources: " + "; ".join(f"<a href='{h(u)}'>{h(t)}</a>" for t, u in d["sources"]) + "</p></section>")
    P.append("</body></html>")
    return "\n".join(P)


# --------------------------------------------------------------------------------------------------------------------------------------------------------- matrix csv
def build_matrix(stats) -> pd.DataFrame:
    rows = []
    for layer, d in C.LAYERS.items():
        s = stats.get(layer, {})
        r = {"region": d["region"], "layer": layer, "country": d["country"], "title": d["title"], "term": d["term"], "counted_unit": d["unit"], "time_reference": d["time"], "verdict": d["verdict"]}
        for k, _ in C.ELEMENTS:
            e = d["elements"][k]
            r[f"{k}_treatment"], r[f"{k}_text"], r[f"{k}_source"] = C.STATUS[e[0]][0], e[2], (e[3] if len(e) > 3 else "")
        r.update({"rows": s.get("rows"), "units": s.get("units"), "first_year": s.get("first"), "last_year": s.get("last"), "tier_A": s.get("tiers", {}).get("A", 0) if s else None,
                  "tier_B": s.get("tiers", {}).get("B", 0) if s else None, "tier_C": s.get("tiers", {}).get("C", 0) if s else None, "definition_flags_in_rows": ";".join(s.get("flags", [])) if s else None})
        rows.append(r)
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--panel")
    ap.add_argument("--out")
    ap.add_argument("--strict", action="store_true", help="exit with an error when the text and the data disagree or a forbidden phrase is found")
    a = ap.parse_args()
    root = Path(__file__).resolve().parent.parent
    out = Path(a.out) if a.out else root / "Docs"
    out.mkdir(parents=True, exist_ok=True)
    df, files = load_panel(a.panel)
    stats = layer_stats(df)
    msgs, lint = checks(stats), lint_text()
    (out / "DEFINITIONS.md").write_text(build_md(stats, files, df), encoding="utf-8")
    (out / "DEFINITIONS.html").write_text(build_html(stats, files, df), encoding="utf-8")
    build_matrix(stats).to_csv(out / "definitions_matrix.csv", index=False, encoding="utf-8-sig")
    print(f"[build_docs.py revision {REVISION}] panel: {', '.join(f.name for f in files)}: {len(df):,} rows, {len(stats)} layers; entries in docs_content.py: {len(C.LAYERS)}")
    print(f"[consistency] {len(msgs)} point(s) where the text and the data disagree:" if msgs else "[consistency] the text and the data agree on every checked point")
    for m in msgs:
        print("   - " + m)
    print(f"[wording] {len(lint)} phrase(s) that do not belong in a published document:" if lint else "[wording] no forbidden phrase found")
    for m in lint:
        print("   - " + m)
    print(f"\n[ok] wrote {out / 'DEFINITIONS.md'}, {out / 'DEFINITIONS.html'} and {out / 'definitions_matrix.csv'}")
    if a.strict and (msgs or lint):
        sys.exit(1)


if __name__ == "__main__":
    main()