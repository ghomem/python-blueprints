#!/usr/bin/env python3
"""
Employment Density vs Housing Price — NUTS-3 scatter plot
---------------------------------------------------------
Plots jobs/km² against €/m² for PT and ES NUTS-3 regions.

Data sources
~~~~~~~~~~~~
Employment (both countries):
    Eurostat dataset nama_10r_3empers — Employment by NUTS-3 regions.
    Unit: thousand persons. Filter: wstatus=EMP, nace_r2=TOTAL.
    https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/

Area (both countries):
    Eurostat dataset reg_area3 — Area by NUTS-3 regions.
    Unit: km². Filter: landuse=L0008 (land area).
    https://ec.europa.eu/eurostat/databrowser/view/reg_area3/

PT housing prices:
    INE Portugal indicator 0012256 — "Valor mediano de avaliação bancária (€/m²)"
    Median bank appraisal value per m² from the Survey on Bank Appraisal of Housing
    (Inquérito à Avaliação Bancária na Habitação). Covers 9 financial institutions
    representing ~90% of housing credit. Properties with 35–600 m² gross area.
    Available at municipality and NUTS-3 level, annual, from 2011.
    https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012256

ES housing prices:
    Ministerio de Transportes y Movilidad Sostenible — "Valor tasado medio de vivienda
    libre (€/m²)". Mean appraised value per m² from regulated appraisal companies
    (Order EHA/3011/2007), based on >100k appraisals per quarter. Available at
    provincial level (≈ NUTS-3), quarterly, from 1995.
    https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000
    Methodology: https://www.transportes.gob.es/recursos_mfom/pdf/B0E2BE62-28EF-41A8-B9D4-CCBD92A28643/144522/MetodValorVivienda.pdf

Note on comparability:
    Both price indicators are professional property valuations for mortgage purposes.
    PT reports the MEDIAN, ES reports the MEAN — means are pulled up by expensive
    outliers, which may slightly inflate ES values relative to PT.

Dependencies:
    pip install requests pandas matplotlib numpy xlrd
"""

import sys
import tempfile
from pathlib import Path
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests


# ---------------------------------------------------------------------------
# Eurostat helpers
# ---------------------------------------------------------------------------

def _eurostat_json(dataset: str, **params) -> dict:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    params.update({"format": "JSON", "lang": "EN"})
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def _eurostat_flat_extract(data: dict, country: str) -> list[dict]:
    """Extract values from Eurostat JSON-stat flat format for NUTS-3 codes."""
    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    geo_labels = dims['geo']['category']['label']
    dim_ids = data['id']
    dim_sizes = data['size']

    cc = country.upper()
    nuts3 = [c for c in geo_idx if c.startswith(cc) and len(c) == 5]

    geo_dim = dim_ids.index('geo')
    time_dim = dim_ids.index('time')

    strides = [1] * len(dim_sizes)
    for i in range(len(dim_sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * dim_sizes[i + 1]

    defaults = {}
    for i, name in enumerate(dim_ids):
        if name not in ('geo', 'time'):
            defaults[i] = min(dims[name]['category']['index'].values())

    values = data['value']
    records = []
    for code in nuts3:
        for t_str, t_pos in time_idx.items():
            coords = {geo_dim: geo_idx[code], time_dim: t_pos}
            coords.update(defaults)
            flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
            val = values.get(str(flat))
            if val is not None:
                records.append({
                    'nuts3': code,
                    'name': geo_labels.get(code, code),
                    'year': int(t_str),
                    'value': float(val),
                })
    return records


def fetch_employment(country: str) -> pd.DataFrame:
    print(f"[+] Fetching employment data [{country.upper()}]...", flush=True)
    data = _eurostat_json("nama_10r_3empers", unit="THS", wstatus="EMP", nace_r2="TOTAL")
    records = _eurostat_flat_extract(data, country)
    df = pd.DataFrame(records).rename(columns={'value': 'employment_ths'})

    total_regions = df['nuts3'].nunique()
    per_year = df.groupby('year')['nuts3'].nunique()
    good_years = per_year[per_year >= total_regions * 0.5].index
    return df[df['year'].isin(good_years)]


def fetch_area(country: str) -> pd.DataFrame:
    print(f"[+] Fetching area data [{country.upper()}]...", flush=True)
    data = _eurostat_json("reg_area3", landuse="L0008")
    records = _eurostat_flat_extract(data, country)
    df = pd.DataFrame(records).rename(columns={'value': 'area_km2'})
    return df.sort_values('year').groupby('nuts3').last().reset_index()[['nuts3', 'area_km2']]


# ---------------------------------------------------------------------------
# Housing price: Portugal (INE PT)
# Indicator 0012256: Median bank appraisal value (€/m²)
# Source: Inquérito à Avaliação Bancária na Habitação (IABH)
# API: https://www.ine.pt/ine/json_indicador/pindica.jsp?op=2&varcd=0012256
# ---------------------------------------------------------------------------

def fetch_pt_prices() -> pd.DataFrame:
    print("[+] Fetching PT housing prices (INE)...", flush=True)
    url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
    params = {"op": "2", "varcd": "0012256", "Dim1": "T", "lang": "EN"}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    dados = data[0]['Dados'] if isinstance(data, list) else data.get('Dados', {})

    records = []
    for year_str, entries in dados.items():
        if not isinstance(entries, list):
            continue
        try:
            year = int(year_str)
        except ValueError:
            continue

        for entry in entries:
            geocod = entry.get('geocod', '')
            if len(geocod) != 3 or entry.get('dim_3') != 'T':
                continue
            valor = entry.get('valor')
            if not valor:
                continue
            try:
                records.append({
                    'nuts3': 'PT' + geocod,
                    'year': year,
                    'price_eur_m2': float(valor),
                })
            except (ValueError, TypeError):
                continue

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Housing price: Spain (Ministerio de Transportes XLS)
# "Valor tasado medio de vivienda libre" — mean appraised value (€/m²)
# Source: regulated appraisal companies (Order EHA/3011/2007), >100k appraisals/quarter
# Data: https://apps.fomento.gob.es/BoletinOnline2/sedal/35101000.XLS
# Methodology: https://www.transportes.gob.es/recursos_mfom/pdf/B0E2BE62-28EF-41A8-B9D4-CCBD92A28643/144522/MetodValorVivienda.pdf
# ---------------------------------------------------------------------------

ES_PROVINCE_TO_NUTS3 = {
    'Almería': 'ES611', 'Cádiz': 'ES612', 'Córdoba': 'ES613',
    'Granada': 'ES614', 'Huelva': 'ES615', 'Jaén': 'ES616',
    'Málaga': 'ES617', 'Sevilla': 'ES618',
    'Huesca': 'ES241', 'Teruel': 'ES242', 'Zaragoza': 'ES243',
    'Asturias (Principado de )': 'ES120',
    'Balears (Illes)': 'ES530',
    'Palmas (Las)': 'ES701', 'Santa Cruz de Tenerife': 'ES702',
    'Cantabria': 'ES130',
    'Ávila': 'ES411', 'Burgos': 'ES412', 'León': 'ES413',
    'Palencia': 'ES414', 'Salamanca': 'ES415', 'Segovia': 'ES416',
    'Soria': 'ES417', 'Valladolid': 'ES418', 'Zamora': 'ES419',
    'Albacete': 'ES421', 'Ciudad Real': 'ES422', 'Cuenca': 'ES423',
    'Guadalajara': 'ES424', 'Toledo': 'ES425',
    'Barcelona': 'ES511', 'Girona': 'ES512', 'Lleida': 'ES513',
    'Tarragona': 'ES514',
    'Alicante/Alacant': 'ES521', 'Castellón/Castelló': 'ES522',
    'Valencia/València': 'ES523',
    'Badajoz': 'ES431', 'Cáceres': 'ES432',
    'Coruña (A)': 'ES111', 'Lugo': 'ES112',
    'Ourense': 'ES113', 'Pontevedra': 'ES114',
    'Madrid (Comunidad de)': 'ES300',
    'Murcia (Región de)': 'ES620',
    'Navarra (Comunidad Foral de)': 'ES220',
    'Araba/Alava': 'ES211', 'Gipuzkoa': 'ES212', 'Bizkaia': 'ES213',
    'Rioja (La)': 'ES230',
    'Ceuta': 'ES630', 'Melilla': 'ES640',
}


def fetch_es_prices() -> pd.DataFrame:
    print("[+] Fetching ES housing prices (Ministerio)...", flush=True)
    xls_url = "https://apps.fomento.gob.es/BoletinOnline2/sedal/35101000.XLS"
    xls_path = Path(tempfile.gettempdir()) / "es_housing_prices.XLS"

    if not xls_path.exists():
        resp = requests.get(xls_url, timeout=60)
        resp.raise_for_status()
        xls_path.write_bytes(resp.content)

    xls = pd.ExcelFile(xls_path)
    records = []

    for sheet_name in xls.sheet_names:
        df = pd.read_excel(xls, sheet_name=sheet_name, header=None)

        # Extract the 4 years from the header row (row 11 typically)
        years = []
        for col in range(df.shape[1]):
            cell = df.iloc[11, col] if 11 < df.shape[0] else None
            if isinstance(cell, str) and cell.startswith('Año'):
                years.append((col, int(cell.split()[-1])))

        for _, row in df.iloc[14:].iterrows():
            province = str(row.iloc[1]).strip() if pd.notna(row.iloc[1]) else ''
            nuts3 = ES_PROVINCE_TO_NUTS3.get(province)
            if not nuts3:
                continue

            for start_col, year in years:
                # Q4 column is start_col + 3
                q4_val = row.iloc[start_col + 3] if start_col + 3 < len(row) else None
                if pd.notna(q4_val):
                    try:
                        records.append({
                            'nuts3': nuts3,
                            'year': year,
                            'price_eur_m2': float(q4_val),
                        })
                    except (ValueError, TypeError):
                        continue

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def build_scatter_data(country: str, prices_df: pd.DataFrame, year: int) -> pd.DataFrame:
    emp_df = fetch_employment(country)
    area_df = fetch_area(country)

    emp_yr = emp_df[emp_df['year'] == year][['nuts3', 'name', 'employment_ths']]
    prices_yr = prices_df[prices_df['year'] == year][['nuts3', 'price_eur_m2']]

    merged = emp_yr.merge(area_df, on='nuts3').merge(prices_yr, on='nuts3')
    merged['jobs_per_km2'] = (merged['employment_ths'] * 1000) / merged['area_km2']

    # Exclude non-representative enclaves
    exclude = {'ES630', 'ES640'}
    merged = merged[~merged['nuts3'].isin(exclude)]

    return merged


def plot_scatter(df: pd.DataFrame, country: str, year: int, output_file: str):
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)

    cc = country.upper()
    ax.scatter(df['jobs_per_km2'], df['price_eur_m2'], s=60, alpha=0.7,
               color='#d95f02', edgecolors='white', linewidth=0.5)

    for _, row in df.iterrows():
        ax.annotate(row['name'], (row['jobs_per_km2'], row['price_eur_m2']),
                    fontsize=7, alpha=0.7, xytext=(4, 4),
                    textcoords='offset points')

    # Fit and plot log trend line
    x = df['jobs_per_km2'].values
    y = df['price_eur_m2'].values
    mask = x > 0
    if mask.sum() > 2:
        log_x = np.log(x[mask])
        coeffs = np.polyfit(log_x, y[mask], 1)
        x_smooth = np.linspace(x[mask].min(), x[mask].max(), 200)
        y_smooth = coeffs[0] * np.log(x_smooth) + coeffs[1]
        ax.plot(x_smooth, y_smooth, '--', color='#1f77b4', alpha=0.6, linewidth=1.5)

        r_squared = 1 - np.sum((y[mask] - (coeffs[0] * log_x + coeffs[1])) ** 2) / \
            np.sum((y[mask] - y[mask].mean()) ** 2)
        ax.text(0.05, 0.95, f'$R^2 = {r_squared:.3f}$ (log fit)',
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    ax.set_xlabel('Employment Density (jobs / km²)', fontsize=12, labelpad=10)
    ax.set_ylabel('Housing Price (€ / m²)', fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs Housing Price — {cc} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"[+] Scatter plot saved to: {output_file}")


def plot_combined(datasets: list[tuple[str, pd.DataFrame]], year: int, output_file: str):
    """Combined scatter plot for multiple countries, using region names as labels."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(16, 10), dpi=300)

    colors = {'PT': '#d95f02', 'ES': '#1f77b4'}
    all_x, all_y = [], []

    for country, df in datasets:
        cc = country.upper()
        ax.scatter(df['jobs_per_km2'], df['price_eur_m2'], s=60, alpha=0.7,
                   color=colors.get(cc, '#333333'), edgecolors='white', linewidth=0.5,
                   label=cc, zorder=3)

        for _, row in df.iterrows():
            ax.annotate(row['name'], (row['jobs_per_km2'], row['price_eur_m2']),
                        fontsize=6, alpha=0.7, xytext=(4, 4),
                        textcoords='offset points', color=colors.get(cc, '#333333'))

        all_x.extend(df['jobs_per_km2'].values)
        all_y.extend(df['price_eur_m2'].values)

    x = np.array(all_x)
    y = np.array(all_y)
    mask = x > 0
    if mask.sum() > 2:
        log_x = np.log(x[mask])
        coeffs = np.polyfit(log_x, y[mask], 1)
        x_smooth = np.linspace(x[mask].min(), x[mask].max(), 200)
        y_smooth = coeffs[0] * np.log(x_smooth) + coeffs[1]
        ax.plot(x_smooth, y_smooth, '--', color='#666666', alpha=0.5, linewidth=1.5, zorder=2)

        r_squared = 1 - np.sum((y[mask] - (coeffs[0] * log_x + coeffs[1])) ** 2) / \
            np.sum((y[mask] - y[mask].mean()) ** 2)
        ax.text(0.05, 0.95, f'$R^2 = {r_squared:.3f}$ (log fit, combined)',
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    ax.set_xlabel('Employment Density (jobs / km²)', fontsize=12, labelpad=10)
    ax.set_ylabel('Housing Price (€ / m²)', fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs Housing Price — PT + ES NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11, loc='lower right')

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"[+] Combined plot saved to: {output_file}")


def main():
    year = int(sys.argv[1]) if len(sys.argv) > 1 else 2023

    combined = []
    for country, fetch_prices in [('PT', fetch_pt_prices), ('ES', fetch_es_prices)]:
        try:
            prices_df = fetch_prices()
            if prices_df.empty:
                print(f"[-] No price data for {country}", file=sys.stderr)
                continue

            available_years = sorted(prices_df['year'].unique())
            use_year = year if year in available_years else available_years[-1]
            if use_year != year:
                print(f"[!] {country}: year {year} not available, using {use_year}")

            df = build_scatter_data(country, prices_df, use_year)
            print(f"\n[{country}] {len(df)} NUTS-3 regions matched for {use_year}:")
            print(df[['nuts3', 'name', 'jobs_per_km2', 'price_eur_m2']]
                  .sort_values('jobs_per_km2', ascending=False)
                  .to_string(index=False))

            out = str(Path(tempfile.gettempdir()) / f"{country}_density_vs_price_{use_year}.png")
            plot_scatter(df, country, use_year, out)
            combined.append((country, df))

        except Exception as e:
            print(f"[-] {country} failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    if len(combined) > 1:
        out = str(Path(tempfile.gettempdir()) / f"PTES_density_vs_price_{year}.png")
        plot_combined(combined, year, out)


if __name__ == "__main__":
    main()
