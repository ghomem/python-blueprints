#!/usr/bin/env python3
"""
Employment Density vs Purchase Effort — NUTS-3 scatter plot
------------------------------------------------------------
Plots jobs/km² against purchase effort (months of gross salary per m²)
for PT, ES, FR, and NL NUTS-3 regions.

Data sources
~~~~~~~~~~~~
Employment (all countries):
    Eurostat dataset nama_10r_3empers — Employment by NUTS-3 regions.
    Unit: thousand persons. Filter: wstatus=EMP, nace_r2=TOTAL.
    https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/

Area (all countries):
    Eurostat dataset reg_area3 — Area by NUTS-3 regions.
    Unit: km². Filter: landuse=L0008 (land area).
    https://ec.europa.eu/eurostat/databrowser/view/reg_area3/

PT wages:
    DGCP/MTSSS Quadros de Pessoal — "Remuneração média mensal base" (average
    monthly base pay for full-time dependent workers), at NUTS-3 level,
    2014–2024. Annual = monthly × 14 (12 + holiday + Christmas subsidies).
    Continental Portugal only (Açores and Madeira excluded).
    https://www.dgcp.mtsss.gov.pt/documents/10182/10928/seriesqp_2014_2024.xlsx

ES wages:
    Agencia Tributaria — "Salario Medio Anual" (mean annual salary from tax
    returns, all workers, both sexes, all ages) at province level (≈ NUTS-3).
    Covers 46 provinces; Navarra and País Vasco (4 provinces) have their own
    tax systems and fall back to Eurostat NUTS-2 compensation data.
    https://sede.agenciatributaria.gob.es/.../mercado/2023/

Wages (FR, NL — fallback):
    Eurostat dataset nama_10r_2coe — Compensation of employees at NUTS-2 level
    (million EUR, nace_r2=TOTAL), divided by employment from nama_10r_3empers
    at NUTS-2 level (thousand persons), giving average annual compensation per
    employee. NUTS-3 regions inherit the wage of their parent NUTS-2 region.
    https://ec.europa.eu/eurostat/databrowser/view/nama_10r_2coe/

PT housing prices (primary):
    INE Portugal indicator 0012235 — Median apartment transaction price (€/m²).
    Quarterly from Q4 2019, at NUTS-3 level. Actual sales from notarial records.
    https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012235

PT housing prices (fallback):
    INE Portugal indicator 0012256 — "Valor mediano de avaliação bancária (€/m²)"
    Median bank appraisal value per m² from the Survey on Bank Appraisal of Housing
    (Inquérito à Avaliação Bancária na Habitação). Covers 9 financial institutions
    representing ~90% of housing credit. Properties with 35–600 m² gross area.
    Available at municipality and NUTS-3 level, annual, from 2011.
    https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012256

ES housing prices (primary):
    Colegio de Registradores de la Propiedad — actual transaction prices (€/m²) from
    property registrations. Quarterly from 2007, by province (≈ NUTS-3).
    https://opendata.registradores.org/dataset/dataset/compraventas-de-inmuebles-uso-residencial-por-provincia

ES housing prices (fallback):
    Ministerio de Transportes y Movilidad Sostenible — "Valor tasado medio de vivienda
    libre (€/m²)". Mean appraised value per m² from regulated appraisal companies
    (Order EHA/3011/2007), based on >100k appraisals per quarter. Available at
    provincial level (≈ NUTS-3), quarterly, from 1995.
    https://apps.fomento.gob.es/BoletinOnline2/?nivel=2&orden=35000000

FR housing prices:
    DVF (Demandes de Valeurs Foncières) — actual transaction prices from notarial
    records, published as open data by DGFiP/data.gouv.fr. Pre-aggregated statistics
    (median €/m²) available at département level (= NUTS-3 for France) from the
    "Statistiques DVF" dataset, covering 2019–present.
    https://www.data.gouv.fr/datasets/statistiques-dvf
    Download: https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv

NL housing prices:
    CBS (Centraal Bureau voor de Statistiek) dataset 85036NED — "Gemiddelde
    WOZ-waarde van woningen" (average WOZ property tax valuation, in €1000),
    at COROP level (= NUTS-3). WOZ is a government-assessed property value,
    updated annually, used for taxation. Not a transaction or appraisal price.
    Available 2019–2026 at all 40 COROP regions.
    https://opendata.cbs.nl/ODataApi/OData/85036NED

    To convert to approximate €/m², average dwelling floor area per COROP is
    estimated from CBS 83704NED (housing stock by floor-area class and region),
    using bin midpoints. This introduces ~10-15% noise from bin granularity.
    https://opendata.cbs.nl/ODataApi/OData/83704NED

Note on comparability:
    PT (primary, 0012235), ES (primary, Registradores), and FR use actual transaction
    prices from official records. PT (fallback, 0012256) and ES (fallback, Ministerio)
    use professional property valuations for mortgage purposes.
    NL uses WOZ (property tax valuation) divided by estimated average floor area —
    an approximation of €/m², systematically lower than market values (WOZ lags
    the market and is capped for tax purposes). NL figures are therefore not
    directly comparable in absolute level, but the spatial variation is meaningful.

Dependencies:
    pip install requests pandas matplotlib numpy xlrd
"""

import argparse
import csv as csvmod
import sys
import tempfile
from collections import defaultdict
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


def _eurostat_flat_extract(data: dict, country: str, nuts_len: int = 5) -> list[dict]:
    """Extract values from Eurostat JSON-stat flat format for NUTS codes."""
    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    geo_labels = dims['geo']['category']['label']
    dim_ids = data['id']
    dim_sizes = data['size']

    cc = country.upper()
    nuts3 = [c for c in geo_idx if c.startswith(cc) and len(c) == nuts_len]

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


def _fetch_wages_eurostat(country: str) -> pd.DataFrame:
    """Average annual compensation per employee at NUTS-2 level (Eurostat)."""
    coe_data = _eurostat_json("nama_10r_2coe", currency="MIO_EUR", nace_r2="TOTAL")
    coe_recs = _eurostat_flat_extract(coe_data, country, nuts_len=4)
    coe_df = pd.DataFrame(coe_recs).rename(columns={'nuts3': 'nuts2', 'value': 'comp_mio'})

    emp_data = _eurostat_json("nama_10r_3empers", unit="THS", wstatus="EMP", nace_r2="TOTAL")
    emp_recs = _eurostat_flat_extract(emp_data, country, nuts_len=4)
    emp_df = pd.DataFrame(emp_recs).rename(columns={'nuts3': 'nuts2', 'value': 'emp_ths'})

    merged = coe_df[['nuts2', 'year', 'comp_mio']].merge(
        emp_df[['nuts2', 'year', 'emp_ths']], on=['nuts2', 'year'])
    merged = merged[(merged['comp_mio'] > 0) & (merged['emp_ths'] > 0)]
    merged['avg_annual_wage'] = (merged['comp_mio'] * 1e6) / (merged['emp_ths'] * 1e3)

    return merged[['nuts2', 'year', 'avg_annual_wage']]


# ---------------------------------------------------------------------------
# PT wages: MTSS Quadros de Pessoal — NUTS-3 monthly base pay
# Source: DGCP/MTSSS, "Séries Quadros de Pessoal", sheet q25.
# Monthly base pay for full-time dependent workers. Annual = monthly × 14
# (12 months + holiday + Christmas subsidies).
# https://www.dgcp.mtsss.gov.pt/documents/10182/10928/seriesqp_2014_2024.xlsx
# ---------------------------------------------------------------------------

PT_QP_NAME_TO_NUTS3 = {
    'Alto Minho':                   'PT111',
    'Cávado':                       'PT112',
    'Ave':                          'PT119',
    'Área Metropolitana do Porto':  'PT11A',
    'Alto Tâmega e Barroso':        'PT11B',
    'Tâmega e Sousa':               'PT11C',
    'Douro':                        'PT11D',
    'Terras de Trás-os-Montes':     'PT11E',
    'Região de Aveiro':             'PT191',
    'Região de Coimbra':            'PT192',
    'Região de Leiria':             'PT193',
    'Viseu Dão Lafões':             'PT194',
    'Beira Baixa':                  'PT195',
    'Beiras e Serra da Estrela':    'PT196',
    'Oeste':                        'PT1D1',
    'Médio Tejo':                   'PT1D2',
    'Lezíria do Tejo':              'PT1D3',
    'Grande Lisboa':                'PT1A0',
    'Península de Setúbal':         'PT1B0',
    'Alentejo Litoral':             'PT1C1',
    'Baixo Alentejo':               'PT1C2',
    'Alto Alentejo':                'PT1C3',
    'Alentejo Central':             'PT1C4',
    'Algarve':                      'PT150',
}


def _fetch_pt_wages_qp() -> pd.DataFrame:
    """NUTS-3 monthly base pay from MTSS Quadros de Pessoal (continental PT)."""
    xls_url = ("https://www.dgcp.mtsss.gov.pt/documents/10182/10928/"
               "seriesqp_2014_2024.xlsx/d0805880-6aef-4eb1-8602-56c1b8a989a1")
    xls_path = Path(tempfile.gettempdir()) / "seriesqp_2014_2024.xlsx"

    if not xls_path.exists():
        resp = requests.get(xls_url, timeout=60, verify=False)
        resp.raise_for_status()
        xls_path.write_bytes(resp.content)

    df = pd.read_excel(xls_path, sheet_name='q25', header=None)
    years = [int(df.iloc[3, c]) for c in range(1, df.shape[1]) if pd.notna(df.iloc[3, c])]

    records = []
    for i in range(4, len(df)):
        name = str(df.iloc[i, 0]).strip() if pd.notna(df.iloc[i, 0]) else ''
        nuts3 = PT_QP_NAME_TO_NUTS3.get(name)
        if not nuts3:
            continue
        for j, year in enumerate(years):
            val = df.iloc[i, j + 1]
            if pd.notna(val):
                records.append({
                    'nuts3': nuts3,
                    'year': year,
                    'avg_annual_wage': float(val) * 14,
                })
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# ES wages: Agencia Tributaria — "Salario Medio Anual" by province
# Mean annual salary from tax returns (IRPF), all workers, both sexes, all ages.
# Covers all provinces except Navarra and País Vasco (own tax systems);
# those 4 fall back to Eurostat NUTS-2.
# https://sede.agenciatributaria.gob.es/.../mercado/2023/
# ---------------------------------------------------------------------------

ES_AEAT_SALARY_2023 = {
    'ES611': 18037, 'ES612': 20014, 'ES613': 18668, 'ES614': 19687,
    'ES615': 17143, 'ES616': 17014, 'ES617': 20648, 'ES618': 21050,
    'ES241': 22033, 'ES242': 21815, 'ES243': 24533,
    'ES120': 24581,
    'ES530': 23126,
    'ES701': 20962, 'ES702': 20422,
    'ES130': 22989,
    'ES411': 20487, 'ES412': 24046, 'ES413': 22396, 'ES414': 22128,
    'ES415': 22204, 'ES416': 21502, 'ES417': 22641, 'ES418': 24657,
    'ES419': 20227,
    'ES421': 20702, 'ES422': 20613, 'ES423': 19700, 'ES424': 24116,
    'ES425': 21320,
    'ES511': 28108, 'ES512': 22947, 'ES513': 22471, 'ES514': 23653,
    'ES521': 20186, 'ES522': 22227, 'ES523': 23359,
    'ES431': 18069, 'ES432': 18827,
    'ES111': 24840, 'ES112': 21939, 'ES113': 21473, 'ES114': 22259,
    'ES300': 30769,
    'ES620': 20552,
    'ES230': 22335,
}


def _fetch_es_wages_aeat() -> pd.DataFrame:
    """Provincial mean annual salary from Agencia Tributaria (2023)."""
    records = [{'nuts3': n, 'year': 2023, 'avg_annual_wage': float(v)}
               for n, v in ES_AEAT_SALARY_2023.items()]
    return pd.DataFrame(records)


def fetch_wages(country: str) -> pd.DataFrame:
    """Fetch wage data — NUTS-3 where available, NUTS-2 otherwise.

    Returns a DataFrame with columns:
      - 'nuts3' + 'year' + 'avg_annual_wage'  (NUTS-3 granularity), OR
      - 'nuts2' + 'year' + 'avg_annual_wage'  (NUTS-2 fallback)
    The caller checks which column is present to decide the merge key.
    """
    print(f"[+] Fetching wage data [{country.upper()}]...", flush=True)

    if country.upper() == 'PT':
        df = _fetch_pt_wages_qp()
        if not df.empty:
            print(f"  Using MTSS Quadros de Pessoal (NUTS-3, {len(df)} rows)")
            return df

    if country.upper() == 'ES':
        df = _fetch_es_wages_aeat()
        if not df.empty:
            print(f"  Using AEAT salary data (NUTS-3, {len(df)} rows)")
            return df

    return _fetch_wages_eurostat(country)


# ---------------------------------------------------------------------------
# Housing price: Portugal (INE PT)
# ---------------------------------------------------------------------------

# Primary: Indicator 0012235 — Median transaction price for apartments (€/m²)
# Source: Estatísticas de preços da habitação ao nível local (Metodologia 2022)
# Quarterly from Q4 2019, at NUTS-3 and municipality level.
# https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012235

def fetch_pt_prices() -> pd.DataFrame:
    """Median apartment transaction price (€/m²) — actual sales, quarterly."""
    print("[+] Fetching PT transaction prices (INE 0012235)...", flush=True)
    url = "https://www.ine.pt/ine/json_indicador/pindica.jsp"
    params = {"op": "2", "varcd": "0012235", "Dim1": "T", "lang": "PT"}
    resp = requests.get(url, params=params, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    dados = data[0]['Dados'] if isinstance(data, list) else data.get('Dados', {})

    records = []
    for period_str, entries in dados.items():
        if not isinstance(entries, list):
            continue
        # Extract year from "4.º Trimestre de 2023" or "1.º Trimestre de 2024"
        if 'Trimestre' not in period_str:
            continue
        parts = period_str.split()
        try:
            year = int(parts[-1])
            quarter = int(parts[0][0])
        except (ValueError, IndexError):
            continue

        for entry in entries:
            geocod = entry.get('geocod', '')
            if len(geocod) != 3:
                continue
            valor = entry.get('valor')
            if not valor:
                continue
            try:
                records.append({
                    'nuts3': 'PT' + geocod,
                    'year': year,
                    'quarter': quarter,
                    'price_eur_m2': float(valor),
                })
            except (ValueError, TypeError):
                continue

    df = pd.DataFrame(records)
    if df.empty:
        return df
    # Keep Q4 for each year as the annual value (or latest quarter available)
    df = df.sort_values(['nuts3', 'year', 'quarter'])
    return df.groupby(['nuts3', 'year']).last().reset_index()[['nuts3', 'year', 'price_eur_m2']]


# Fallback: Indicator 0012256 — Median bank appraisal value (€/m²)
# Source: Inquérito à Avaliação Bancária na Habitação (IABH)
# Annual from 2011. Covers all housing types (not just apartments).
# https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012256

def fetch_pt_prices_appraisal() -> pd.DataFrame:
    """Median bank appraisal value (€/m²) — professional valuations, annual."""
    print("[+] Fetching PT appraisal prices (INE 0012256)...", flush=True)
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
# Housing price: Spain (Registradores de la Propiedad — transaction prices)
# Actual registered transaction prices (€/m²) from property registrars.
# Quarterly from 2007, by province (≈ NUTS-3).
# https://opendata.registradores.org/dataset/dataset/compraventas-de-inmuebles-uso-residencial-por-provincia
# ---------------------------------------------------------------------------

ES_INE_TO_NUTS3 = {
    1: 'ES211',  2: 'ES421',  3: 'ES521',  4: 'ES611',  5: 'ES411',
    6: 'ES431',  7: 'ES530',  8: 'ES511',  9: 'ES412', 10: 'ES432',
    11: 'ES612', 12: 'ES522', 13: 'ES422', 14: 'ES613', 15: 'ES111',
    16: 'ES423', 17: 'ES512', 18: 'ES614', 19: 'ES424', 20: 'ES212',
    21: 'ES615', 22: 'ES241', 23: 'ES616', 24: 'ES413', 25: 'ES513',
    26: 'ES230', 27: 'ES112', 28: 'ES300', 29: 'ES617', 30: 'ES620',
    31: 'ES220', 32: 'ES113', 33: 'ES120', 34: 'ES414', 35: 'ES701',
    36: 'ES114', 37: 'ES415', 38: 'ES702', 39: 'ES130', 40: 'ES416',
    41: 'ES618', 42: 'ES417', 43: 'ES514', 44: 'ES242', 45: 'ES425',
    46: 'ES523', 47: 'ES418', 48: 'ES213', 49: 'ES419', 50: 'ES243',
}


def fetch_es_prices() -> pd.DataFrame:
    """Mean transaction price (€/m²) from property registrars."""
    print("[+] Fetching ES transaction prices (Registradores)...", flush=True)
    csv_url = ("https://opendata.registradores.org/data-integration/"
               "compraventas-residencial-trimestres-provincias-es/"
               "RP_ComprvResid_2007-2t2026.csv")
    csv_path = Path(tempfile.gettempdir()) / "es_registradores_compraventas.csv"

    if not csv_path.exists() or csv_path.stat().st_size < 1000:
        resp = requests.get(csv_url, timeout=60, headers={
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
                          " (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36",
            "Accept": "text/csv,text/plain,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Referer": "https://opendata.registradores.org/",
        })
        resp.raise_for_status()
        if b'ano;trim;geo' not in resp.content[:200]:
            print("  [-] WAF blocked download — use browser cache", file=sys.stderr)
            return pd.DataFrame()
        csv_path.write_bytes(resp.content)

    records = []
    with open(csv_path, encoding='utf-8-sig') as f:
        reader = csvmod.DictReader(f, delimiter=';')
        for row in reader:
            if row.get('geo') != 'Provincia':
                continue
            try:
                code = int(row['cod-prv'])
            except (ValueError, KeyError):
                continue
            nuts3 = ES_INE_TO_NUTS3.get(code)
            if not nuts3:
                continue
            pm2 = row.get('viv-pm2', '')
            if not pm2:
                continue
            try:
                records.append({
                    'nuts3': nuts3,
                    'year': int(row['ano']),
                    'quarter': int(row['trim']),
                    'price_eur_m2': float(pm2.replace(',', '.')),
                })
            except (ValueError, TypeError):
                continue

    df = pd.DataFrame(records)
    if df.empty:
        return df
    df = df.sort_values(['nuts3', 'year', 'quarter'])
    return df.groupby(['nuts3', 'year']).last().reset_index()[['nuts3', 'year', 'price_eur_m2']]


# ---------------------------------------------------------------------------
# Housing price: Spain — fallback (Ministerio de Transportes XLS)
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


def fetch_es_prices_appraisal() -> pd.DataFrame:
    """Mean appraised value (€/m²) — professional valuations, quarterly."""
    print("[+] Fetching ES appraisal prices (Ministerio)...", flush=True)
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
# Housing price: France (DVF — Statistiques DVF, data.gouv.fr)
# Median €/m² from actual property transactions (notarial records, DGFiP).
# Aggregated statistics at département level published by data-pipeline-open.
# Download: https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv
# Dataset page: https://www.data.gouv.fr/datasets/statistiques-dvf
# ---------------------------------------------------------------------------

FR_DEPT_TO_NUTS3 = {
    '01': 'FRK21', '02': 'FRE21', '03': 'FRK11', '04': 'FRL01', '05': 'FRL02',
    '06': 'FRL03', '07': 'FRK22', '08': 'FRF21', '09': 'FRJ21', '10': 'FRF22',
    '11': 'FRJ11', '12': 'FRJ22', '13': 'FRL04', '14': 'FRD11', '15': 'FRK12',
    '16': 'FRI31', '17': 'FRI32', '18': 'FRB01', '19': 'FRI21', '21': 'FRC11',
    '22': 'FRH01', '23': 'FRI22', '24': 'FRI11', '25': 'FRC21', '26': 'FRK23',
    '27': 'FRD21', '28': 'FRB02', '29': 'FRH02', '2A': 'FRM01', '2B': 'FRM02',
    '30': 'FRJ12', '31': 'FRJ23', '32': 'FRJ24', '33': 'FRI12', '34': 'FRJ13',
    '35': 'FRH03', '36': 'FRB03', '37': 'FRB04', '38': 'FRK24', '39': 'FRC22',
    '40': 'FRI13', '41': 'FRB05', '42': 'FRK25', '43': 'FRK13', '44': 'FRG01',
    '45': 'FRB06', '46': 'FRJ25', '47': 'FRI14', '48': 'FRJ14', '49': 'FRG02',
    '50': 'FRD12', '51': 'FRF23', '52': 'FRF24', '53': 'FRG03', '54': 'FRF31',
    '55': 'FRF32', '56': 'FRH04', '57': 'FRF33', '58': 'FRC12', '59': 'FRE11',
    '60': 'FRE22', '61': 'FRD13', '62': 'FRE12', '63': 'FRK14', '64': 'FRI15',
    '65': 'FRJ26', '66': 'FRJ15', '67': 'FRF11', '68': 'FRF12', '69': 'FRK26',
    '70': 'FRC23', '71': 'FRC13', '72': 'FRG04', '73': 'FRK27', '74': 'FRK28',
    '75': 'FR101', '76': 'FRD22', '77': 'FR102', '78': 'FR103', '79': 'FRI33',
    '80': 'FRE23', '81': 'FRJ27', '82': 'FRJ28', '83': 'FRL05', '84': 'FRL06',
    '85': 'FRG05', '86': 'FRI34', '87': 'FRI23', '88': 'FRF34', '89': 'FRC14',
    '90': 'FRC24', '91': 'FR104', '92': 'FR105', '93': 'FR106', '94': 'FR107',
    '95': 'FR108',
}


def fetch_fr_prices() -> pd.DataFrame:
    """Median €/m² from DVF transaction data, all-period aggregate by département."""
    print("[+] Fetching FR housing prices (DVF stats)...", flush=True)
    csv_url = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_whole_period.csv"
    csv_path = Path(tempfile.gettempdir()) / "dvf_stats_whole_period.csv"

    if not csv_path.exists():
        resp = requests.get(csv_url, timeout=120)
        resp.raise_for_status()
        csv_path.write_bytes(resp.content)

    records = []
    with open(csv_path, encoding='utf-8') as f:
        reader = csvmod.DictReader(f)
        for row in reader:
            if row['echelle_geo'] != 'departement':
                continue
            dept_code = row['code_geo']
            nuts3 = FR_DEPT_TO_NUTS3.get(dept_code)
            if not nuts3:
                continue
            med = row.get('med_prix_m2_whole_apt_maison')
            if not med:
                continue
            try:
                records.append({
                    'nuts3': nuts3,
                    'year': 2023,
                    'price_eur_m2': float(med),
                })
            except (ValueError, TypeError):
                continue

    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# Housing price: Netherlands (CBS — WOZ valuation / estimated floor area)
# Average WOZ value per dwelling (€1000): CBS 85036NED, COROP level (= NUTS-3).
# Dwelling stock by floor-area class: CBS 83704NED, COROP level.
# WOZ / avg_floor_area → approximate €/m².
# https://opendata.cbs.nl/ODataApi/OData/85036NED
# https://opendata.cbs.nl/ODataApi/OData/83704NED
# ---------------------------------------------------------------------------

NL_COROP_TO_NUTS3 = {
    'CR01': 'NL114', 'CR02': 'NL112', 'CR03': 'NL115', 'CR04': 'NL127',
    'CR05': 'NL128', 'CR06': 'NL126', 'CR07': 'NL131', 'CR08': 'NL132',
    'CR09': 'NL133', 'CR10': 'NL211', 'CR11': 'NL212', 'CR12': 'NL213',
    'CR13': 'NL221', 'CR14': 'NL225', 'CR15': 'NL226', 'CR16': 'NL224',
    'CR17': 'NL350', 'CR18': 'NL321', 'CR19': 'NL328', 'CR20': 'NL323',
    'CR21': 'NL32A', 'CR22': 'NL325', 'CR23': 'NL32B', 'CR24': 'NL327',
    'CR25': 'NL363', 'CR26': 'NL361', 'CR27': 'NL362', 'CR28': 'NL365',
    'CR29': 'NL366', 'CR30': 'NL364', 'CR31': 'NL341', 'CR32': 'NL342',
    'CR33': 'NL411', 'CR34': 'NL415', 'CR35': 'NL416', 'CR36': 'NL414',
    'CR37': 'NL421', 'CR38': 'NL422', 'CR39': 'NL423', 'CR40': 'NL230',
}

NL_AREA_CLASS_MIDPOINTS = {
    'A041692': 8.5,    # 2-15 m²
    'A025407': 32.5,   # 15-50 m²
    'A025408': 62.5,   # 50-75 m²
    'A025409': 87.5,   # 75-100 m²
    'A025410': 125.0,  # 100-150 m²
    'A025411': 200.0,  # 150-250 m²
    'A025412': 375.0,  # 250-500 m²
    'A041691': 750.0,  # 500-10000 m²
}


def _cbs_json(url: str) -> dict:
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_nl_avg_floor_area(year_key: str) -> dict[str, float]:
    """Estimate average dwelling floor area (m²) per COROP from area-class distribution."""
    url = ("https://opendata.cbs.nl/ODataApi/OData/83704NED/TypedDataSet?"
           f"$filter=Woningtype%20eq%20'T001100'%20and%20Perioden%20eq%20'{year_key}'"
           "&$top=5000")

    data = _cbs_json(url)
    corop = defaultdict(lambda: {'total': 0, 'weighted': 0.0})

    for row in data.get('value', []):
        regio = row.get('RegioS', '').strip()
        opp = row.get('Oppervlakteklasse', '').strip()
        count = row.get('BeginstandWoningvoorraad_1')
        if not regio.startswith('CR') or count is None or opp not in NL_AREA_CLASS_MIDPOINTS:
            continue
        corop[regio]['total'] += count
        corop[regio]['weighted'] += count * NL_AREA_CLASS_MIDPOINTS[opp]

    return {cr: d['weighted'] / d['total'] for cr, d in corop.items() if d['total'] > 0}


def fetch_nl_prices() -> pd.DataFrame:
    """Approximate €/m² from WOZ valuation divided by estimated average floor area."""
    print("[+] Fetching NL housing prices (CBS WOZ)...", flush=True)

    records = []
    for year in range(2019, 2027):
        year_key = f'{year}JJ00'
        url = ("https://opendata.cbs.nl/ODataApi/OData/85036NED/TypedDataSet?"
               f"$filter=Eigendom%20eq%20'T001132'%20and%20Perioden%20eq%20'{year_key}'"
               "&$top=500")
        data = _cbs_json(url)
        for row in data.get('value', []):
            regio = row.get('RegioS', '').strip()
            val = row.get('GemiddeldeWOZWaardeVanWoningen_1')
            if regio.startswith('CR') and val is not None:
                nuts3 = NL_COROP_TO_NUTS3.get(regio)
                if nuts3:
                    records.append({
                        'nuts3': nuts3,
                        'corop': regio,
                        'year': year,
                        'woz_eur': val * 1000,
                    })

    if not records:
        return pd.DataFrame(columns=['nuts3', 'year', 'price_eur_m2'])

    df = pd.DataFrame(records)

    print("[+] Estimating NL floor areas (CBS 83704NED)...", flush=True)
    latest_year = df['year'].max()
    avg_area = _fetch_nl_avg_floor_area(f'{latest_year}JJ00')

    price_records = []
    for _, row in df.iterrows():
        area = avg_area.get(row['corop'])
        if area and area > 0:
            price_records.append({
                'nuts3': row['nuts3'],
                'year': row['year'],
                'price_eur_m2': row['woz_eur'] / area,
            })

    return pd.DataFrame(price_records)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COUNTRY_COLORS = {
    'PT': '#d95f02',
    'ES': '#1f77b4',
    'FR': '#2ca02c',
    'NL': '#7570b3',
}

METRIC_CONFIG = {
    'effort': {
        'y_col':  'effort_months_per_m2',
        'ylabel': 'Purchase Effort (months of gross salary / m²)',
        'title':  'Purchase Effort',
        'slug':   'effort',
    },
    'price': {
        'y_col':  'price_eur_m2',
        'ylabel': 'Price (€ / m²)',
        'title':  'Housing Price',
        'slug':   'price',
    },
}


def build_scatter_data(country: str, prices_df: pd.DataFrame, year: int) -> pd.DataFrame:
    emp_df = fetch_employment(country)
    area_df = fetch_area(country)
    wages_df = fetch_wages(country)

    emp_yr = emp_df[emp_df['year'] == year][['nuts3', 'name', 'employment_ths']]
    prices_yr = prices_df[prices_df['year'] == year][['nuts3', 'price_eur_m2']]

    merged = emp_yr.merge(area_df, on='nuts3').merge(prices_yr, on='nuts3')
    merged['jobs_per_km2'] = (merged['employment_ths'] * 1000) / merged['area_km2']

    nuts3_wages = 'nuts3' in wages_df.columns
    wage_key = 'nuts3' if nuts3_wages else 'nuts2'
    if not nuts3_wages:
        merged['nuts2'] = merged['nuts3'].str[:4]
    wages_yr = wages_df[wages_df['year'] == year][[wage_key, 'avg_annual_wage']]
    if wages_yr.empty:
        closest = wages_df['year'].max()
        wages_yr = wages_df[wages_df['year'] == closest][[wage_key, 'avg_annual_wage']]
        if not wages_yr.empty:
            print(f"  [!] Wage data: using {closest} (no {year})")
    merged = merged.merge(wages_yr, on=wage_key, how='left')

    missing = merged['avg_annual_wage'].isna().sum()
    if missing > 0 and nuts3_wages:
        merged['nuts2'] = merged['nuts3'].str[:4]
        fallback = _fetch_wages_eurostat(country)
        fb_yr = fallback[fallback['year'] == year][['nuts2', 'avg_annual_wage']]
        if fb_yr.empty:
            fb_yr = fallback[fallback['year'] == fallback['year'].max()][['nuts2', 'avg_annual_wage']]
        fb_map = fb_yr.set_index('nuts2')['avg_annual_wage']
        mask = merged['avg_annual_wage'].isna()
        merged.loc[mask, 'avg_annual_wage'] = merged.loc[mask, 'nuts2'].map(fb_map)
        filled = missing - merged['avg_annual_wage'].isna().sum()
        if filled > 0:
            print(f"  [!] {filled} regions filled from Eurostat NUTS-2 fallback")

    merged['monthly_wage'] = merged['avg_annual_wage'] / 12
    merged['effort_months_per_m2'] = merged['price_eur_m2'] / merged['monthly_wage']

    exclude = {
        'ES630', 'ES640',
        'FRY10', 'FRY20', 'FRY30', 'FRY40', 'FRY50', 'FRZZZ',
        'NLZZZ',
    }
    merged = merged[~merged['nuts3'].isin(exclude)]
    merged = merged.dropna(subset=['effort_months_per_m2'])

    return merged


def _fit_log_trend(ax, x, y):
    """Fit y = a*ln(x) + b, plot the line, return R²."""
    mask = x > 0
    if mask.sum() <= 2:
        return None
    log_x = np.log(x[mask])
    coeffs = np.polyfit(log_x, y[mask], 1)
    x_smooth = np.geomspace(x[mask].min(), x[mask].max(), 200)
    y_smooth = coeffs[0] * np.log(x_smooth) + coeffs[1]
    ax.plot(x_smooth, y_smooth, '--', color='#666666', alpha=0.5, linewidth=1.5, zorder=2)
    ss_res = np.sum((y[mask] - (coeffs[0] * log_x + coeffs[1])) ** 2)
    ss_tot = np.sum((y[mask] - y[mask].mean()) ** 2)
    return 1 - ss_res / ss_tot


def plot_scatter(df: pd.DataFrame, country: str, year: int, output_file: str,
                 metric: str = 'effort'):
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)

    mc = METRIC_CONFIG[metric]
    cc = country.upper()
    y_col = mc['y_col']
    ax.scatter(df['jobs_per_km2'], df[y_col], s=60, alpha=0.7,
               color=COUNTRY_COLORS.get(cc, '#d95f02'), edgecolors='white', linewidth=0.5)

    for _, row in df.iterrows():
        ax.annotate(row['name'], (row['jobs_per_km2'], row[y_col]),
                    fontsize=7, alpha=0.7, xytext=(4, 4),
                    textcoords='offset points')

    r2 = _fit_log_trend(ax, df['jobs_per_km2'].values, df[y_col].values)
    if r2 is not None:
        ax.text(0.05, 0.95, f'$R^2 = {r2:.3f}$ (log fit)',
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    ax.set_xlabel('Employment Density (jobs / km²)', fontsize=12, labelpad=10)
    ax.set_ylabel(mc['ylabel'], fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs {mc["title"]} — {cc} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"[+] Scatter plot saved to: {output_file}")


def plot_combined(datasets: list[tuple[str, pd.DataFrame]], year: int, output_file: str,
                  metric: str = 'effort'):
    """Combined scatter plot for multiple countries, using region names as labels."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(16, 10), dpi=300)

    mc = METRIC_CONFIG[metric]
    all_x, all_y = [], []
    label_size = 6 if len(datasets) <= 2 else 5

    y_col = mc['y_col']
    for country, df in datasets:
        cc = country.upper()
        color = COUNTRY_COLORS.get(cc, '#333333')
        ax.scatter(df['jobs_per_km2'], df[y_col], s=60, alpha=0.7,
                   color=color, edgecolors='white', linewidth=0.5,
                   label=cc, zorder=3)

        for _, row in df.iterrows():
            ax.annotate(row['name'], (row['jobs_per_km2'], row[y_col]),
                        fontsize=label_size, alpha=0.7, xytext=(4, 4),
                        textcoords='offset points', color=color)

        all_x.extend(df['jobs_per_km2'].values)
        all_y.extend(df[y_col].values)

    r2 = _fit_log_trend(ax, np.array(all_x), np.array(all_y))
    if r2 is not None:
        ax.text(0.05, 0.95, f'$R^2 = {r2:.3f}$ (log fit, combined)',
                transform=ax.transAxes, fontsize=10, va='top',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    countries_label = ' + '.join(cc for cc, _ in datasets)
    ax.set_xscale('log')
    ax.set_xlabel('Employment Density (jobs / km², log scale)', fontsize=12, labelpad=10)
    ax.set_ylabel(mc['ylabel'], fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs {mc["title"]} — {countries_label} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11, loc='lower right')

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"[+] Combined plot saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Employment Density vs Housing metrics — NUTS-3 scatter plot')
    parser.add_argument('year', nargs='?', type=int, default=2023,
                        help='Reference year (default: 2023)')
    parser.add_argument('--metric', choices=['effort', 'price'], default='effort',
                        help='Y-axis metric: "effort" = months of gross salary / m² '
                             '(default), "price" = raw € / m²')
    args = parser.parse_args()

    year   = args.year
    metric = args.metric

    out_dir = Path(tempfile.gettempdir()) / "density_vs_price"
    out_dir.mkdir(exist_ok=True)

    fetchers = [
        ('PT', fetch_pt_prices),
        ('ES', fetch_es_prices),
        ('FR', fetch_fr_prices),
        ('NL', fetch_nl_prices),
    ]

    mc   = METRIC_CONFIG[metric]
    slug = mc['slug']

    combined = []
    for country, fetch_prices in fetchers:
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
            print(df[['nuts3', 'name', 'jobs_per_km2', 'price_eur_m2', 'effort_months_per_m2']]
                  .sort_values('jobs_per_km2', ascending=False)
                  .to_string(index=False))

            out = str(out_dir / f"{country}_density_vs_{slug}_{use_year}.png")
            plot_scatter(df, country, use_year, out, metric=metric)
            combined.append((country, df))

        except Exception as e:
            print(f"[-] {country} failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    if len(combined) > 1:
        tag = ''.join(cc for cc, _ in combined)
        out = str(out_dir / f"{tag}_density_vs_{slug}_{year}.png")
        plot_combined(combined, year, out, metric=metric)

        all_df = pd.concat(
            [df.assign(country=cc) for cc, df in combined],
            ignore_index=True,
        )
        cols = ['country', 'nuts3', 'name', 'employment_ths', 'area_km2',
                'jobs_per_km2', 'price_eur_m2', 'avg_annual_wage',
                'effort_months_per_m2']
        all_df = all_df[cols].sort_values(['country', 'nuts3'])
        csv_path = out_dir / f"density_vs_{slug}_{year}.csv"
        all_df.to_csv(csv_path, index=False, float_format='%.2f')
        print(f"[+] Dataset saved to: {csv_path} ({len(all_df)} regions)")


if __name__ == "__main__":
    main()
