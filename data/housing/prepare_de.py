#!/usr/bin/env python3
"""
Prepare German data for the density_vs_price pipeline.

Prices:  raw-input/DE/kreise_preise.csv  (BBSR/AK OGA, Kreis names)
Wages:   raw-input/DE/vgrdl_r2b2_bs2025.xlsx  (VGRdL, NUTS-3 codes)
Ref:     input/NUTS_RG_10M_2024_4326_LEVL_3.geojson

Writes:  input/DE_prices.csv  (nuts3, year, price_eur_m2)
         input/DE_wages.csv   (nuts3, year, avg_annual_wage)
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RAW_PRICES = HERE / "raw-input" / "DE" / "kreise_preise.csv"
RAW_WAGES = HERE / "raw-input" / "DE" / "vgrdl_r2b2_bs2025.xlsx"
GEOJSON = HERE / "input" / "NUTS_RG_10M_2024_4326_LEVL_3.geojson"
OUT_PRICES = HERE / "input" / "DE_prices.csv"
OUT_WAGES = HERE / "input" / "DE_wages.csv"

# ── NUTS-3 reference ─────────────────────────────────────────────────────────

def load_nuts3() -> dict[str, str]:
    """Return {NUTS-3 code: name} for all DE regions."""
    with open(GEOJSON) as f:
        gj = json.load(f)
    return {
        feat["properties"]["NUTS_ID"]: feat["properties"]["NAME_LATN"]
        for feat in gj["features"]
        if feat["properties"]["NUTS_ID"].startswith("DE")
    }


def _normalize(name: str) -> str:
    """Lowercase, strip type suffixes, normalize whitespace."""
    s = name.lower().strip()
    for suffix in [", landkreis", ", kreisfreie stadt", ", stadtkreis", ", kreis"]:
        s = s.replace(suffix, "")
    s = re.sub(r"\s+", " ", s).strip()
    return s


# Map BBSR kreis_typ to the type suffixes used in NUTS names
_TYPE_MAP = {
    "Kreisfreie Stadt": "Kreisfreie Stadt",
    "Stadtkreis": "Stadtkreis",
    "Landkreis": "Landkreis",
    "Kreis": "Landkreis",  # Schleswig-Holstein uses "Kreis" = Landkreis
}


def build_matching(nuts3: dict[str, str]) -> tuple[dict[str, str], dict[tuple[str, str], str], set[str]]:
    """
    Build {normalized_kreis_name: NUTS-3 code} lookup.
    For ambiguous names (Stadt + Landkreis), store both with type suffix keys.
    Returns (lookup, list_of_nuts_codes_covered).
    """
    # Group NUTS codes by base name (before comma, strip type prefix too)
    by_base: dict[str, list[tuple[str, str]]] = {}
    for code, name in nuts3.items():
        base = name.split(",")[0].strip()
        for prefix in ["Landkreis ", "Kreis "]:
            if base.startswith(prefix):
                base = base[len(prefix):]
                break
        by_base.setdefault(base, []).append((code, name))

    lookup: dict[str, str] = {}     # normalized_name -> NUTS code
    type_lookup: dict[str, str] = {}  # (normalized_name, type) -> NUTS code

    ambiguous_norms: set[str] = set()

    for base, entries in by_base.items():
        norm = _normalize(base)
        if len(entries) == 1:
            lookup[norm] = entries[0][0]
        else:
            ambiguous_norms.add(norm)
            for code, full_name in entries:
                matched = False
                for type_label in ["Kreisfreie Stadt", "Stadtkreis", "Landkreis"]:
                    if type_label in full_name:
                        type_lookup[(norm, type_label)] = code
                        matched = True
                        break
                if not matched and "," not in full_name:
                    type_lookup[(norm, "Landkreis")] = code

    return lookup, type_lookup, ambiguous_norms


# ── Manual overrides for names that differ between BBSR and Eurostat ─────────
# BBSR name -> NUTS-3 code (or None to skip)
MANUAL = {
    # Spelling/naming differences
    "Aachen": "DEA2D",          # NUTS: "Städteregion Aachen"
    "Bitburg-Prüm": "DEB23",   # NUTS: "Eifelkreis Bitburg-Prüm"
    "Frankenthal (Pfalz)": "DEB31",
    "Landau in der Pfalz": "DEB33",
    "Ludwigshafen am Rhein": "DEB34",
    "Neustadt an der Weinstraße": "DEB36",
    "Pirmasens": "DEB37",
    "Speyer": "DEB38",
    "Worms": "DEB39",
    "Zweibrücken": "DEB3A",
    "St. Wendel": "DEC06",
    "Stadtverband Saarbrücken": "DEC01",  # NUTS: "Regionalverband Saarbrücken"
    "Saarpfalz-Kreis": "DEC05",
    # Abbreviation differences (BBSR uses no spaces in "a.d.", NUTS uses "a. d.")
    "Dillingen a.d.Donau": "DE277",
    "Friesland": "DE94A",
    "Mühldorf a.Inn": "DE21G",
    "Neumarkt i.d.OPf.": "DE236",
    "Neustadt a.d.Aisch-Bad Windsheim": "DE25A",
    "Neustadt a.d.Waldnaab": "DE237",
    "Oldenburg (Oldb)": "DE943",
    "Pfaffenhofen a.d.Ilm": "DE21J",
    "Weiden i.d.OPf.": "DE233",
    "Wunsiedel i.Fichtelgebirge": "DE24D",
}


# ── Load and match ───────────────────────────────────────────────────────────

def main() -> None:
    nuts3 = load_nuts3()
    print(f"NUTS-3 DE regions: {len(nuts3)}")

    lookup, type_lookup, ambiguous = build_matching(nuts3)

    with open(RAW_PRICES) as f:
        raw_rows = list(csv.DictReader(f))
    print(f"Raw price rows: {len(raw_rows)}")

    # Deduplicate Kreis names (one entry per year)
    kreise_per_year: dict[str, int] = {}
    for r in raw_rows:
        kreise_per_year.setdefault(r["jahr"], set()).add(r["kreis"])
    for y, names in sorted(kreise_per_year.items()):
        print(f"  {y}: {len(names)} Kreise")

    # Match each row
    matched_rows = []
    unmatched: dict[str, str] = {}  # kreis_name -> kreis_typ
    matched_nuts: set[str] = set()

    for r in raw_rows:
        name = r["kreis"]
        typ = r["kreis_typ"]
        price = int(r["preis_eur_m2"])

        if price == 0:
            continue

        # 1. Manual override
        if name in MANUAL:
            code = MANUAL[name]
            if code:
                matched_rows.append((code, r["jahr"], price))
                matched_nuts.add(code)
            continue

        norm = _normalize(name)
        mapped_type = _TYPE_MAP.get(typ, typ)

        # 2. Ambiguous names — must resolve by type
        if norm in ambiguous:
            key = (norm, mapped_type)
            if key in type_lookup:
                code = type_lookup[key]
                matched_rows.append((code, r["jahr"], price))
                matched_nuts.add(code)
                continue
            unmatched[name] = typ
            continue

        # 3. Direct lookup (unambiguous base name)
        if norm in lookup:
            code = lookup[norm]
            matched_rows.append((code, r["jahr"], price))
            matched_nuts.add(code)
            continue

        # 4. Unmatched
        unmatched[name] = typ

    print(f"\nMatched rows: {len(matched_rows)}")
    print(f"Matched NUTS-3 codes: {len(matched_nuts)} / {len(nuts3)}")

    if unmatched:
        print(f"\nUnmatched Kreise ({len(unmatched)}):")
        for name, typ in sorted(unmatched.items()):
            print(f"  {name} ({typ})")

    unmatched_nuts = set(nuts3.keys()) - matched_nuts
    if unmatched_nuts:
        print(f"\nNUTS-3 codes without price data ({len(unmatched_nuts)}):")
        for code in sorted(unmatched_nuts):
            print(f"  {code}: {nuts3[code]}")

    # Write output
    matched_rows.sort(key=lambda r: (r[0], r[1]))
    with open(OUT_PRICES, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nuts3", "year", "price_eur_m2"])
        for code, year, price in matched_rows:
            w.writerow([code, year, price])

    print(f"\nWrote {OUT_PRICES} ({len(matched_rows)} rows)")

    # ── Wages ───────────────────────────────────────────────────────────────
    prepare_wages(nuts3)


def prepare_wages(nuts3: dict[str, str]) -> None:
    import openpyxl

    print(f"\n{'='*60}")
    print("Preparing wages from VGRdL...")

    wb = openpyxl.load_workbook(RAW_WAGES, read_only=True, data_only=True)
    ws = wb["5"]

    header = list(ws.iter_rows(min_row=5, max_row=5, values_only=True))[0]
    year_cols = {}
    for i, v in enumerate(header):
        if isinstance(v, int) and 2000 <= v <= 2030:
            year_cols[v] = i

    valid_nuts3 = set(nuts3.keys())
    wage_rows = []

    for row in ws.iter_rows(min_row=7, values_only=True):
        eu_code = str(row[1]).strip() if row[1] else ""
        if not eu_code.startswith("DE"):
            continue
        # Normalize code: strip trailing 'x', pad city-states (DE3→DE300)
        code = eu_code.rstrip("x")
        if len(code) < 5:
            code = code.ljust(5, "0")
        if code not in valid_nuts3:
            continue

        for year in [2023, 2024]:
            val = row[year_cols[year]]
            if val is not None and str(val).strip() not in ("", ".", "-"):
                wage_rows.append((code, year, int(round(float(val)))))

    wb.close()

    codes = set(r[0] for r in wage_rows)
    print(f"Wage NUTS-3 codes: {len(codes)} / {len(valid_nuts3)}")

    missing = valid_nuts3 - codes
    if missing:
        print(f"Missing wage data ({len(missing)}):")
        for c in sorted(missing):
            print(f"  {c}: {nuts3[c]}")

    wage_rows.sort()
    with open(OUT_WAGES, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["nuts3", "year", "avg_annual_wage"])
        for code, year, wage in wage_rows:
            w.writerow([code, year, wage])

    print(f"Wrote {OUT_WAGES} ({len(wage_rows)} rows)")


if __name__ == "__main__":
    main()
