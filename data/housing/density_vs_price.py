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

PT wages (continental):
    DGCP/MTSSS Quadros de Pessoal — "Remuneração média mensal ganho" (mean
    monthly earnings for full-time dependent workers), at NUTS-3 level,
    2014–2024. Ganho = base + meal subsidy + shift pay + regular bonuses +
    overtime. Annual = monthly × 14 (12 + holiday + Christmas subsidies).
    https://www.dgcp.mtsss.gov.pt/documents/10182/10928/seriesqp_2014_2024.xlsx

PT wages (Madeira):
    DREM Quadros de Pessoal — "Ganho médio mensal" (mean monthly earnings),
    same concept as mainland q37. Annual = monthly × 14.
    https://estatistica.madeira.gov.pt/

ES wages:
    Agencia Tributaria — "Salario Medio Anual" (mean annual salary from tax
    returns, all workers, both sexes, all ages) at province level (≈ NUTS-3).
    Covers 46 provinces; Navarra and País Vasco (4 provinces) have their own
    tax systems and fall back to Eurostat NUTS-2 compensation data.
    https://sede.agenciatributaria.gob.es/.../mercado/

FR wages:
    INSEE DADS/DSN — "Salaire brut annuel moyen en EQTP" (gross annual salary,
    full-time equivalent) by département (≈ NUTS-3), all sectors, both sexes.
    Table T401b, multi-year (2019–2022). Each year has a different publication ID.
    https://www.insee.fr/fr/statistiques/8219475

NL wages:
    CBS dataset 85924NED — "Beloning van werknemers" (compensation of employees,
    million EUR) divided by "Werknemers" (employees, thousands) at COROP level
    (≈ NUTS-3). Multi-year (1995–2024).
    https://opendata.cbs.nl/ODataApi/OData/85924NED

Wages (all countries — fallback):
    Eurostat dataset nama_10r_2coe — Compensation of employees at NUTS-2 level
    (million EUR, nace_r2=TOTAL), divided by employment from nama_10r_3empers
    at NUTS-2 level (thousand persons), giving average annual compensation per
    employee. NUTS-3 regions inherit the wage of their parent NUTS-2 region.
    Used as fallback when NUTS-3 data is missing for specific regions.
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
    records, published as open data by DGFiP. Pre-aggregated statistics (monthly
    median €/m²) at département level (= NUTS-3) from the "Statistiques DVF"
    dataset, published by data.gouv.fr (DINUM/Etalab). Monthly data aggregated
    to annual medians weighted by number of sales. Multi-year (2021–present).
    Dataset: https://www.data.gouv.fr/fr/datasets/statistiques-dvf/
    Pipeline: https://github.com/etalab/datagouvfr_data_pipelines/tree/main/data_processing/dvf
    Download: https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_dvf.csv

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
    PT (0012235), ES (Registradores), and FR (DVF) use actual transaction prices
    from official records. NL uses WOZ (property tax valuation) divided by
    estimated average floor area — an approximation of €/m², systematically lower
    than market values (WOZ lags the market and is capped for tax purposes).
    NL figures are therefore not directly comparable in absolute level, but the
    spatial variation is meaningful. The fallback sources documented above (PT
    0012256, ES Ministerio) are not used in the current code.

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
# Local-data helpers: save fetched DataFrames for offline use
# ---------------------------------------------------------------------------

INPUT_DIR: Path | None = None   # set by --local-data / --save-data
SAVE_MODE: bool = False         # True when --save-data is active


def _local_path(country: str, kind: str) -> Path:
    """Return input/<CC>_<kind>.csv for a given country and data type."""
    return INPUT_DIR / f"{country.upper()}_{kind}.csv"


def _save_df(df: pd.DataFrame, country: str, kind: str) -> None:
    if SAVE_MODE and INPUT_DIR and not df.empty:
        path = _local_path(country, kind)
        df.to_csv(path, index=False, float_format='%.6f')
        print(f"  [saved] {path}")


def _load_df(country: str, kind: str) -> pd.DataFrame | None:
    """Load a CSV from input/ if running in local-data mode, else None."""
    if INPUT_DIR is None or SAVE_MODE:
        return None
    path = _local_path(country, kind)
    if not path.exists():
        print(f"  [!] Local file not found: {path}", file=sys.stderr)
        return None
    df = pd.read_csv(path)
    print(f"  [local] {path} ({len(df)} rows)")
    return df


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
    local = _load_df(country, 'employment')
    if local is not None:
        return local
    print(f"[+] Fetching employment data [{country.upper()}]...", flush=True)
    data = _eurostat_json("nama_10r_3empers", unit="THS", wstatus="EMP", nace_r2="TOTAL")
    records = _eurostat_flat_extract(data, country)
    df = pd.DataFrame(records).rename(columns={'value': 'employment_ths'})

    total_regions = df['nuts3'].nunique()
    per_year = df.groupby('year')['nuts3'].nunique()
    good_years = per_year[per_year >= total_regions * 0.5].index
    df = df[df['year'].isin(good_years)]
    _save_df(df, country, 'employment')
    return df


def fetch_area(country: str) -> pd.DataFrame:
    local = _load_df(country, 'area')
    if local is not None:
        return local
    print(f"[+] Fetching area data [{country.upper()}]...", flush=True)
    data = _eurostat_json("reg_area3", landuse="L0008")
    records = _eurostat_flat_extract(data, country)
    df = pd.DataFrame(records).rename(columns={'value': 'area_km2'})
    df = df.sort_values('year').groupby('nuts3').last().reset_index()[['nuts3', 'area_km2']]
    _save_df(df, country, 'area')
    return df


def _fetch_wages_eurostat(country: str) -> pd.DataFrame:
    """Average annual compensation per employee at NUTS-2 level (Eurostat)."""
    local = _load_df(country, 'wages_eurostat')
    if local is not None:
        return local
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

    df = merged[['nuts2', 'year', 'avg_annual_wage']]
    _save_df(df, country, 'wages_eurostat')
    return df


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
    """NUTS-3 mean monthly earnings (ganho) from MTSS Quadros de Pessoal.

    Continental PT: sheet q37 of the DGCP/MTSSS series (ganho directly).
    Madeira (PT300): DREM series (ganho directly — same concept).
    Annual = monthly × 14 (12 + holiday + Christmas subsidies).
    """
    xls_url = ("https://www.dgcp.mtsss.gov.pt/documents/10182/10928/"
               "seriesqp_2014_2024.xlsx/d0805880-6aef-4eb1-8602-56c1b8a989a1")
    xls_path = Path(tempfile.gettempdir()) / "seriesqp_2014_2024.xlsx"

    if not xls_path.exists():
        resp = requests.get(xls_url, timeout=60, verify=False)
        resp.raise_for_status()
        xls_path.write_bytes(resp.content)

    # --- Continental: ganho from q37 ---
    df = pd.read_excel(xls_path, sheet_name='q37', header=None)
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

    # --- Madeira: ganho from DREM (same concept, no conversion needed) ---
    records.extend(_fetch_madeira_wages_drem(years))

    return pd.DataFrame(records)


def _fetch_madeira_wages_drem(mainland_years: list[int]) -> list[dict]:
    """Madeira wages from DREM Quadros de Pessoal (ganho × 14, same concept as mainland q37)."""
    drem_url = ("https://estatistica.madeira.gov.pt/download-now/social/"
                "merctrab-pt/2015-11-19-16-43-36/serie-retrospetiva-quadro-pessoal/"
                "send/464-quadros-de-pessoal-serie-retrospetiva/"
                "20007-serie-retrospetiva-das-estatisticas-dos-quadros-de-pessoal-"
                "1995-2024.html")
    drem_path = Path(tempfile.gettempdir()) / "s_quadpessoal_9524.xlsx"

    if not drem_path.exists():
        resp = requests.get(drem_url, timeout=60)
        resp.raise_for_status()
        drem_path.write_bytes(resp.content)

    try:
        drem = pd.read_excel(drem_path, sheet_name='Q2', header=None)
    except Exception:
        return []

    # Row 3: years; Row 5: R.A. Madeira, HM (both sexes)
    drem_years = [int(drem.iloc[3, c]) for c in range(3, drem.shape[1])
                  if pd.notna(drem.iloc[3, c])]

    records = []
    for j, yr in enumerate(drem_years):
        if yr not in mainland_years:
            continue
        ganho = drem.iloc[5, j + 3]
        if pd.notna(ganho):
            records.append({
                'nuts3': 'PT300',
                'year': yr,
                'avg_annual_wage': float(ganho) * 14,
            })

    if records:
        print(f"  Madeira: {len(records)} years from DREM (ganho × 14)")
    return records


# ---------------------------------------------------------------------------
# ES wages: Agencia Tributaria — "Salario Medio Anual" by province
# Mean annual salary from tax returns (IRPF), all workers, both sexes, all ages.
# Covers all provinces except Navarra and País Vasco (own tax systems);
# those 4 fall back to Eurostat NUTS-2.
# https://sede.agenciatributaria.gob.es/.../mercado/
# ---------------------------------------------------------------------------

ES_AEAT_PROVINCE_TO_NUTS3 = {
    'Almería': 'ES611', 'Cádiz': 'ES612', 'Córdoba': 'ES613',
    'Granada': 'ES614', 'Huelva': 'ES615', 'Jaén': 'ES616',
    'Málaga': 'ES617', 'Sevilla': 'ES618',
    'Huesca': 'ES241', 'Teruel': 'ES242', 'Zaragoza': 'ES243',
    'Asturias': 'ES120',
    'Balears': 'ES530', 'Baleares': 'ES530',
    'Las Palmas': 'ES701',
    'Santa Cruz de Tenerife': 'ES702', 'S. C. Tenerife': 'ES702',
    'Cantabria': 'ES130',
    'Ávila': 'ES411', 'Burgos': 'ES412', 'León': 'ES413',
    'Palencia': 'ES414', 'Salamanca': 'ES415', 'Segovia': 'ES416',
    'Soria': 'ES417', 'Valladolid': 'ES418', 'Zamora': 'ES419',
    'Albacete': 'ES421', 'Ciudad Real': 'ES422', 'Cuenca': 'ES423',
    'Guadalajara': 'ES424', 'Toledo': 'ES425',
    'Barcelona': 'ES511', 'Girona': 'ES512', 'Lleida': 'ES513',
    'Tarragona': 'ES514',
    'Alicante': 'ES521', 'Castellón': 'ES522', 'Valencia': 'ES523',
    'Badajoz': 'ES431', 'Cáceres': 'ES432',
    'A Coruña': 'ES111', 'Lugo': 'ES112', 'Ourense': 'ES113',
    'Pontevedra': 'ES114',
    'Madrid': 'ES300',
    'Murcia': 'ES620',
    'La Rioja': 'ES230',
    'Ceuta': 'ES630', 'Melilla': 'ES640',
}

ES_AEAT_SALARY = {
    2021: {
        'ES611': 16220, 'ES612': 18086, 'ES613': 16670, 'ES614': 17671,
        'ES615': 15296, 'ES616': 15190, 'ES617': 18112, 'ES618': 18751,
        'ES241': 20141, 'ES242': 19745, 'ES243': 22288,
        'ES120': 22286,
        'ES530': 19791,
        'ES701': 18127, 'ES702': 17697,
        'ES130': 20893,
        'ES411': 18574, 'ES412': 21891, 'ES413': 20358, 'ES414': 20140,
        'ES415': 20138, 'ES416': 19566, 'ES417': 20825, 'ES418': 22319,
        'ES419': 18270,
        'ES421': 18798, 'ES422': 18557, 'ES423': 17893, 'ES424': 21904,
        'ES425': 19135,
        'ES511': 25319, 'ES512': 20691, 'ES513': 20506, 'ES514': 21387,
        'ES521': 17649, 'ES522': 20449, 'ES523': 20860,
        'ES431': 16195, 'ES432': 16840,
        'ES111': 22000, 'ES112': 19823, 'ES113': 19398, 'ES114': 20046,
        'ES300': 27981,
        'ES620': 18696,
        'ES230': 20341,
        'ES630': 23545, 'ES640': 22311,
    },
    2022: {
        'ES611': 16962, 'ES612': 18988, 'ES613': 17580, 'ES614': 18658,
        'ES615': 16190, 'ES616': 16012, 'ES617': 19443, 'ES618': 19851,
        'ES241': 21026, 'ES242': 20777, 'ES243': 23346,
        'ES120': 23405,
        'ES530': 21765,
        'ES701': 19889, 'ES702': 19267,
        'ES130': 22036,
        'ES411': 19533, 'ES412': 23002, 'ES413': 21389, 'ES414': 21160,
        'ES415': 21174, 'ES416': 20391, 'ES417': 21720, 'ES418': 23407,
        'ES419': 19254,
        'ES421': 19680, 'ES422': 19438, 'ES423': 18728, 'ES424': 23045,
        'ES425': 20266,
        'ES511': 26736, 'ES512': 21836, 'ES513': 21565, 'ES514': 22527,
        'ES521': 19112, 'ES522': 21506, 'ES523': 22248,
        'ES431': 17040, 'ES432': 17811,
        'ES111': 23456, 'ES112': 20788, 'ES113': 20355, 'ES114': 21097,
        'ES300': 29447,
        'ES620': 19469,
        'ES230': 21257,
        'ES630': 23841, 'ES640': 22354,
    },
    2023: {
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
        'ES630': 24812, 'ES640': 23275,
    },
    2024: {
        'ES611': 18733, 'ES612': 20811, 'ES613': 19488, 'ES614': 20584,
        'ES615': 18012, 'ES616': 17792, 'ES617': 21479, 'ES618': 21876,
        'ES241': 22866, 'ES242': 22767, 'ES243': 25448,
        'ES120': 25470,
        'ES530': 24254,
        'ES701': 21902, 'ES702': 21321,
        'ES130': 23787,
        'ES411': 21267, 'ES412': 24884, 'ES413': 23315, 'ES414': 23057,
        'ES415': 23060, 'ES416': 22430, 'ES417': 23569, 'ES418': 25571,
        'ES419': 20975,
        'ES421': 21576, 'ES422': 21511, 'ES423': 20472, 'ES424': 25037,
        'ES425': 22188,
        'ES511': 29255, 'ES512': 24017, 'ES513': 23538, 'ES514': 24677,
        'ES521': 20984, 'ES522': 23117, 'ES523': 24209,
        'ES431': 18927, 'ES432': 19769,
        'ES111': 25959, 'ES112': 22704, 'ES113': 22294, 'ES114': 23182,
        'ES300': 31911,
        'ES620': 21483,
        'ES230': 23161,
        'ES630': 26041, 'ES640': 24572,
    },
}


# ---------------------------------------------------------------------------
# FR wages: INSEE DADS/DSN — gross annual salary (EQTP) by département
# Source: "Salaires dans le secteur privé et les entreprises publiques",
# Table T401b, all occupational categories, all sectors, both sexes.
# Each year has a different INSEE publication ID but identical CSV format.
# https://www.insee.fr/fr/statistiques/8219475
# ---------------------------------------------------------------------------

FR_INSEE_WAGE_PUBLICATIONS = {
    2019: '5418716',
    2020: '6524757',
    2021: '7656166',
    2022: '8219475',
}


def _fetch_fr_wages_insee() -> pd.DataFrame:
    """Gross annual salary (EQTP) by département from INSEE DADS/DSN (2019–2022)."""
    records = []
    for year, pub_id in FR_INSEE_WAGE_PUBLICATIONS.items():
        csv_url = f"https://www.insee.fr/fr/statistiques/fichier/{pub_id}/T401b.csv"
        csv_path = Path(tempfile.gettempdir()) / f"insee_T401b_{year}.csv"
        if not csv_path.exists():
            resp = requests.get(csv_url, timeout=60)
            resp.raise_for_status()
            csv_path.write_bytes(resp.content)

        with open(csv_path, encoding='utf-8') as f:
            reader = csvmod.DictReader(f, delimiter=';')
            for row in reader:
                cs1 = row.get('CS1', row.get('"CS1"', '')).strip('"')
                ce  = row.get('CE',  row.get('"CE"',  '')).strip('"')
                sexe = row.get('SEXE', row.get('"SEXE"', '')).strip('"')
                if cs1 != 'T' or ce != 'T' or sexe != 'E':
                    continue
                regdep = row.get('REGDEP', row.get('"REGDEP"', '')).strip('"')
                if len(regdep) == 4:
                    dept = regdep[2:]
                elif len(regdep) == 5 and regdep[0] == '0':
                    dept = regdep[2:]
                else:
                    continue
                nuts3 = FR_DEPT_TO_NUTS3.get(dept)
                if not nuts3:
                    continue
                try:
                    brut = row.get('BRUT_EQTP', row.get('"BRUT_EQTP"', '')).strip('"')
                    records.append({
                        'nuts3': nuts3,
                        'year': year,
                        'avg_annual_wage': float(brut),
                    })
                except (ValueError, TypeError):
                    continue
    return pd.DataFrame(records)


# ---------------------------------------------------------------------------
# NL wages: CBS 85924NED — compensation per employee by COROP region
# BeloningVanWerknemers_6 (million EUR) / Werknemers_11 (thousand persons)
# = average annual compensation per employee.
# https://opendata.cbs.nl/ODataApi/OData/85924NED
# ---------------------------------------------------------------------------


def _fetch_nl_wages_cbs() -> pd.DataFrame:
    """Average annual compensation per employee by COROP from CBS 85924NED."""
    records = []
    for year in range(2019, 2027):
        url = ("https://opendata.cbs.nl/ODataApi/OData/85924NED/TypedDataSet?"
               f"$filter=startswith(RegioS,'CR')%20and%20Perioden%20eq%20'{year}JJ00'")
        data = _cbs_json(url)
        for row in data.get('value', []):
            regio = row.get('RegioS', '').strip()
            comp = row.get('BeloningVanWerknemers_6')
            emp = row.get('Werknemers_11')
            if not regio.startswith('CR') or comp is None or emp is None or emp <= 0:
                continue
            nuts3 = NL_COROP_TO_NUTS3.get(regio)
            if nuts3:
                records.append({
                    'nuts3': nuts3,
                    'year': year,
                    'avg_annual_wage': (comp * 1e6) / (emp * 1e3),
                })
    return pd.DataFrame(records)


def _fetch_es_wages_aeat() -> pd.DataFrame:
    """Provincial mean annual salary from Agencia Tributaria (2022–2024)."""
    records = []
    for yr, data in ES_AEAT_SALARY.items():
        for nuts3, wage in data.items():
            records.append({'nuts3': nuts3, 'year': yr,
                            'avg_annual_wage': float(wage)})
    return pd.DataFrame(records)


def fetch_wages(country: str) -> pd.DataFrame:
    """Fetch wage data — NUTS-3 where available, NUTS-2 otherwise.

    Returns a DataFrame with columns:
      - 'nuts3' + 'year' + 'avg_annual_wage'  (NUTS-3 granularity), OR
      - 'nuts2' + 'year' + 'avg_annual_wage'  (NUTS-2 fallback)
    The caller checks which column is present to decide the merge key.
    """
    local = _load_df(country, 'wages')
    if local is not None:
        return local
    print(f"[+] Fetching wage data [{country.upper()}]...", flush=True)

    if country.upper() == 'PT':
        df = _fetch_pt_wages_qp()
        if not df.empty:
            print(f"  Using MTSS Quadros de Pessoal (NUTS-3, {len(df)} rows)")
            _save_df(df, country, 'wages')
            return df

    if country.upper() == 'ES':
        df = _fetch_es_wages_aeat()
        if not df.empty:
            print(f"  Using AEAT salary data (NUTS-3, {len(df)} rows)")
            _save_df(df, country, 'wages')
            return df

    if country.upper() == 'FR':
        df = _fetch_fr_wages_insee()
        if not df.empty:
            print(f"  Using INSEE DADS/DSN (NUTS-3, {len(df)} rows)")
            _save_df(df, country, 'wages')
            return df

    if country.upper() == 'NL':
        df = _fetch_nl_wages_cbs()
        if not df.empty:
            print(f"  Using CBS 85924NED (NUTS-3, {len(df)} rows)")
            _save_df(df, country, 'wages')
            return df

    df = _fetch_wages_eurostat(country)
    _save_df(df, country, 'wages')
    return df


# ---------------------------------------------------------------------------
# Housing price: Portugal (INE PT)
# ---------------------------------------------------------------------------

# Primary: Indicator 0012235 — Median transaction price for apartments (€/m²)
# Source: Estatísticas de preços da habitação ao nível local (Metodologia 2022)
# Quarterly from Q4 2019, at NUTS-3 and municipality level.
# https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012235

def fetch_pt_prices() -> pd.DataFrame:
    """Median apartment transaction price (€/m²) — actual sales, quarterly."""
    local = _load_df('PT', 'prices')
    if local is not None:
        return local
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
    df = df.groupby(['nuts3', 'year']).last().reset_index()[['nuts3', 'year', 'price_eur_m2']]
    _save_df(df, 'PT', 'prices')
    return df



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
    local = _load_df('ES', 'prices')
    if local is not None:
        return local
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
    df = df.groupby(['nuts3', 'year']).last().reset_index()[['nuts3', 'year', 'price_eur_m2']]
    _save_df(df, 'ES', 'prices')
    return df



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
    """Median €/m² from DVF transaction data by département, per year (2021–present)."""
    local = _load_df('FR', 'prices')
    if local is not None:
        return local
    print("[+] Fetching FR housing prices (DVF stats)...", flush=True)
    csv_url = "https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_dvf.csv"
    csv_path = Path(tempfile.gettempdir()) / "dvf_stats_dvf.csv"

    if not csv_path.exists():
        print("  Downloading stats_dvf.csv (~277 MB)...", flush=True)
        resp = requests.get(csv_url, timeout=300)
        resp.raise_for_status()
        csv_path.write_bytes(resp.content)

    monthly = defaultdict(lambda: defaultdict(lambda: {'price_sum': 0.0, 'sales': 0}))
    with open(csv_path, encoding='utf-8') as f:
        reader = csvmod.DictReader(f)
        for row in reader:
            if row.get('echelle_geo') != 'departement':
                continue
            dept_code = row.get('code_geo', '')
            nuts3 = FR_DEPT_TO_NUTS3.get(dept_code)
            if not nuts3:
                continue
            med = row.get('med_prix_m2_apt_maison')
            nb  = row.get('nb_ventes_apt_maison')
            ym  = row.get('annee_mois', '')
            if not med or not nb or not ym or len(ym) < 4:
                continue
            try:
                year = int(ym[:4])
                price = float(med)
                sales = int(float(nb))
            except (ValueError, TypeError):
                continue
            if sales <= 0:
                continue
            bucket = monthly[nuts3][year]
            bucket['price_sum'] += price * sales
            bucket['sales'] += sales

    records = []
    for nuts3, years in monthly.items():
        for year, bucket in years.items():
            if bucket['sales'] > 0:
                records.append({
                    'nuts3': nuts3,
                    'year': year,
                    'price_eur_m2': bucket['price_sum'] / bucket['sales'],
                })

    df = pd.DataFrame(records)
    _save_df(df, 'FR', 'prices')
    return df


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
    local = _load_df('NL', 'prices')
    if local is not None:
        return local
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

    df = pd.DataFrame(price_records)
    _save_df(df, 'NL', 'prices')
    return df


# ---------------------------------------------------------------------------
# Housing price: Italy (OMI — local data only)
# ---------------------------------------------------------------------------
#
# Source: OMI (Osservatorio del Mercato Immobiliare) via Agenzia delle Entrate.
# Average appraised quotation (€/m²) per province, aggregated from sub-provincial
# macro-areas.  NOT transaction prices — comparable to ES Registradores.
#
# No public API; data prepared offline from the GitHub compilation at
# github.com/eugeniodalpozzo/italy_omi_housing_provincial_prices.
# Requires --local-data with input/IT_prices.csv pre-populated.

LOCAL_ONLY_COUNTRIES = {'IT'}


def fetch_it_prices() -> pd.DataFrame:
    """Load Italian OMI housing prices from local CSV."""
    local = _load_df('IT', 'prices')
    if local is not None:
        return local
    raise SystemExit(
        "IT requires --local-data: no public API for OMI prices.\n"
        "Run with --local-data <dir> where <dir>/IT_prices.csv exists."
    )


# ---------------------------------------------------------------------------
# Tourism intensity (nights per worker)
# ---------------------------------------------------------------------------
#
# Source: Eurostat tour_occ_nin2 — nights spent at tourist accommodation
# establishments, by NUTS-3 region, annual.
#
# NUTS code version caveat:
#   Eurostat is migrating from the pre-2021 NUTS codes to NUTS 2021. The
#   tourism dataset publishes BOTH code versions, each covering different
#   years. For PT and NL, the NUTS 2021 codes sometimes represent MERGED
#   regions (e.g. PT170 "Área Metropolitana de Lisboa" = old PT1A0 "Grande
#   Lisboa" + PT1B0 "Península de Setúbal"), so the boundaries don't match
#   the employment data (which uses old codes).
#
#   As of 2025-09, year 2023 is the only year where the tourism dataset uses
#   the OLD codes for all four countries (PT, ES, FR, NL), matching the
#   employment dataset exactly. Years 2021–2022 would need a crosswalk for
#   PT and NL, with the Lisboa merge making PT impossible without splitting.
#
#   This is why --tourism is restricted to year 2023.

TOURISM_NPW_CAP = 86  # nights/worker: Algarve-level; above this → max saturation

def fetch_tourism_nights(year: int = 2023) -> dict[str, float]:
    """Fetch total tourist nights per NUTS-3 region from Eurostat tour_occ_nin2.

    Returns {nuts3_code: total_nights} for all available regions.
    Only year 2023 uses codes consistent with the employment dataset
    (see module-level comment above).
    """
    local = _load_df('ALL', 'tourism')
    if local is not None:
        return dict(zip(local['nuts3'], local['tourist_nights']))

    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/tour_occ_nin2"
    params = {
        "format": "JSON", "lang": "EN",
        "c_resid": "TOTAL", "unit": "NR",
        "nace_r2": "I551-I553",
        "time": str(year),
    }
    print(f"[+] Fetching tourist nights data from Eurostat ({year})...", flush=True)
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[-] Tourism data fetch failed: {e}", file=sys.stderr)
        return {}

    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    dim_ids = data['id']
    dim_sizes = data['size']

    if str(year) not in time_idx:
        print(f"[-] Year {year} not in tourism dataset", file=sys.stderr)
        return {}
    t_pos = time_idx[str(year)]

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
    result = {}
    for code, g_pos in geo_idx.items():
        if len(code) != 5:
            continue
        coords = {geo_dim: g_pos, time_dim: t_pos}
        coords.update(defaults)
        flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
        val = values.get(str(flat))
        if val is not None:
            result[code] = float(val)
    print(f"  [{len(result)} NUTS-3 regions with tourism data]")

    df = pd.DataFrame([
        {'nuts3': code, 'tourist_nights': nights}
        for code, nights in result.items()
    ])
    _save_df(df, 'ALL', 'tourism')

    return result


def add_tourism_intensity(df: pd.DataFrame,
                          tourism: dict[str, float]) -> pd.DataFrame:
    """Add nights_per_worker column to scatter DataFrame."""
    df = df.copy()
    df['tourist_nights'] = df['nuts3'].map(tourism)
    df['nights_per_worker'] = (
        df['tourist_nights'] / (df['employment_ths'] * 1000))
    return df


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

COUNTRY_COLORS = {
    'PT': '#d95f02',
    'ES': '#0051b5',
    'FR': '#2ca02c',
    'NL': '#7b2d8e',
    'IT': '#228b22',
}

DATA_SOURCES = {
    'ALL': {
        'geometry':   ('Eurostat GISCO NUTS-3 boundaries (NUTS 2024; 1:10M)',
                       'https://gisco-services.ec.europa.eu/distribution/v2/nuts/geojson/NUTS_RG_10M_2024_4326_LEVL_3.geojson'),
    },
    'PT': {
        'prices':     ('INE PT 0012235 — median transaction price',
                       'https://www.ine.pt/xportal/xmain?xpid=INE&xpgid=ine_indicadores&indOcorrCod=0012235'),
        'wages':      ('MTSS Quadros de Pessoal q37 — ganho (mean monthly earnings) × 14',
                       'https://www.dgcp.mtsss.gov.pt/documents/10182/10928/seriesqp_2014_2024.xlsx'),
        'wages_madeira': ('DREM Quadros de Pessoal — ganho × 14 (Madeira; same concept)',
                          'https://estatistica.madeira.gov.pt/'),
        'wages_eurostat': ('Eurostat nama_10r_2coe / nama_10r_2empers — NUTS-2 fallback (Açores)',
                           'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_2coe/'),
        'employment': ('Eurostat nama_10r_3empers',
                       'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/'),
        'area':       ('Eurostat reg_area3',
                       'https://ec.europa.eu/eurostat/databrowser/view/reg_area3/'),
        'tourism':    ('Eurostat tour_occ_nin2 — tourist nights by NUTS-3',
                       'https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nin2/'),
    },
    'ES': {
        'prices':     ('Registradores de España — mean transaction price',
                       'https://www.registradores.org/actualidad/portal-estadistico-registral/estadisticas-de-propiedad/evolucion-precio-medio-m2'),
        'wages':      ('Agencia Tributaria — salario medio anual (IRPF)',
                       'https://sede.agenciatributaria.gob.es/AEAT/Contenidos_Comunes/La_Agencia_Tributaria/Estadisticas/Publicaciones/sites/mercado/2023/'),
        'wages_eurostat': ('Eurostat nama_10r_2coe / nama_10r_2empers — NUTS-2 fallback (Basque+Navarra)',
                           'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_2coe/'),
        'employment': ('Eurostat nama_10r_3empers',
                       'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/'),
        'area':       ('Eurostat reg_area3',
                       'https://ec.europa.eu/eurostat/databrowser/view/reg_area3/'),
        'tourism':    ('Eurostat tour_occ_nin2 — tourist nights by NUTS-3',
                       'https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nin2/'),
    },
    'FR': {
        'prices':     ('DVF — median transaction price (monthly → annual)',
                       'https://data-pipeline-open.s3.sbg.io.cloud.ovh.net/dvf/stats_dvf.csv'),
        'wages':      ('INSEE DADS/DSN T401b — gross annual salary EQTP (2019–2022)',
                       'https://www.insee.fr/fr/statistiques/8219475'),
        'employment': ('Eurostat nama_10r_3empers',
                       'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/'),
        'area':       ('Eurostat reg_area3',
                       'https://ec.europa.eu/eurostat/databrowser/view/reg_area3/'),
        'tourism':    ('Eurostat tour_occ_nin2 — tourist nights by NUTS-3',
                       'https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nin2/'),
    },
    'NL': {
        'prices':     ('CBS 85036NED WOZ / 83704NED floor area',
                       'https://opendata.cbs.nl/ODataApi/OData/85036NED'),
        'wages':      ('CBS 85924NED — compensation per employee by COROP',
                       'https://opendata.cbs.nl/ODataApi/OData/85924NED'),
        'employment': ('Eurostat nama_10r_3empers',
                       'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/'),
        'area':       ('Eurostat reg_area3',
                       'https://ec.europa.eu/eurostat/databrowser/view/reg_area3/'),
        'tourism':    ('Eurostat tour_occ_nin2 — tourist nights by NUTS-3',
                       'https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nin2/'),
    },
    'IT': {
        'prices':     ('OMI (Agenzia delle Entrate) — average appraised quotation per province',
                       'https://servizi2.inps.it/servizi/osservatoristatistici/15'),
        'wages':      ('INPS Osservatorio dipendenti — retribuzione media per provincia',
                       'https://servizi2.inps.it/servizi/osservatoristatistici/15/32/51/o/492'),
        'employment': ('Eurostat nama_10r_3empers',
                       'https://ec.europa.eu/eurostat/databrowser/view/nama_10r_3empers/'),
        'area':       ('Eurostat reg_area3',
                       'https://ec.europa.eu/eurostat/databrowser/view/reg_area3/'),
        'tourism':    ('Eurostat tour_occ_nin2 — tourist nights by NUTS-3',
                       'https://ec.europa.eu/eurostat/databrowser/view/tour_occ_nin2/'),
    },
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

    merged['wage_fallback'] = False
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
        merged.loc[mask, 'wage_fallback'] = True
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


def _tourism_colors(base_hex, npw_values, norm):
    """Per-point RGB with saturation driven by tourism intensity."""
    from matplotlib.colors import rgb_to_hsv, hsv_to_rgb, to_rgb
    rgb = np.array(to_rgb(base_hex))
    hsv = rgb_to_hsv(rgb.reshape(1, 1, 3)).reshape(3)
    t = norm(npw_values)
    n = len(npw_values)
    hsv_arr = np.tile(hsv, (n, 1))
    hsv_arr[:, 1] = t * hsv[1]
    return hsv_to_rgb(hsv_arr.reshape(n, 1, 3)).reshape(n, 3)


def _detect_outliers(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    """IQR on log-linear residuals: True for outlier points."""
    valid = x > 0
    outlier = np.zeros(len(x), dtype=bool)
    if valid.sum() <= 2:
        return outlier
    log_x = np.log(x[valid])
    coeffs = np.polyfit(log_x, y[valid], 1)
    residuals = y[valid] - (coeffs[0] * log_x + coeffs[1])
    q1, q3 = np.percentile(residuals, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    outlier_valid = (residuals < lo) | (residuals > hi)
    outlier[valid] = outlier_valid
    return outlier


def _fit_log_trend(ax, x, y, exclude_mask=None):
    """Fit y = a*ln(x) + b, plot the line, return (R², a, b, RMSE) or None.

    If exclude_mask is given, those points are ignored for the fit and R²
    but the trend line spans the full x-range.
    """
    mask = x > 0
    if exclude_mask is not None:
        mask = mask & ~exclude_mask
    if mask.sum() <= 2:
        return None
    log_x = np.log(x[mask])
    coeffs = np.polyfit(log_x, y[mask], 1)
    x_all = x[x > 0]
    x_smooth = np.geomspace(x_all.min(), x_all.max(), 200)
    y_smooth = coeffs[0] * np.log(x_smooth) + coeffs[1]
    ax.plot(x_smooth, y_smooth, '--', color='#666666', alpha=0.5, linewidth=1.5, zorder=2)
    residuals = y[mask] - (coeffs[0] * log_x + coeffs[1])
    ss_res = np.sum(residuals ** 2)
    ss_tot = np.sum((y[mask] - y[mask].mean()) ** 2)
    r2 = 1 - ss_res / ss_tot
    rmse = np.sqrt(ss_res / mask.sum())
    return r2, coeffs[0], coeffs[1], rmse


def plot_scatter(df: pd.DataFrame, country: str, year: int, output_file: str,
                 metric: str = 'effort', outliers: str | None = None,
                 tourism: bool = False):
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)

    mc = METRIC_CONFIG[metric]
    cc = country.upper()
    y_col = mc['y_col']
    x_vals = df['jobs_per_km2'].values
    y_vals = df[y_col].values
    base_color = COUNTRY_COLORS.get(cc, '#d95f02')

    is_outlier = _detect_outliers(x_vals, y_vals) if outliers else np.zeros(len(df), dtype=bool)
    n_outliers = int(is_outlier.sum())
    plot_df = df[~is_outlier].reset_index(drop=True) if outliers == 'exclude' else df

    from matplotlib.colors import Normalize, LinearSegmentedColormap
    tourism_norm = Normalize(vmin=0, vmax=TOURISM_NPW_CAP, clip=True) if tourism else None

    if tourism and 'nights_per_worker' in plot_df.columns:
        npw = plot_df['nights_per_worker'].fillna(0).values
        colors = _tourism_colors(base_color, npw, tourism_norm)
        ax.scatter(plot_df['jobs_per_km2'], plot_df[y_col], s=60, alpha=0.7,
                   c=colors, edgecolors=base_color, linewidth=0.5)
    else:
        ax.scatter(plot_df['jobs_per_km2'], plot_df[y_col], s=60, alpha=0.7,
                   color=base_color, edgecolors='white', linewidth=0.5)

    if outliers == 'highlight' and n_outliers:
        ax.scatter(x_vals[is_outlier], y_vals[is_outlier], s=60,
                   facecolors='none', edgecolors='red', linewidth=0.5, zorder=4)

    if 'wage_fallback' in plot_df.columns and plot_df['wage_fallback'].any():
        fb = plot_df['wage_fallback'].values
        ax.scatter(plot_df.loc[fb, 'jobs_per_km2'], plot_df.loc[fb, y_col], s=60,
                   facecolors='none', edgecolors='black', linewidth=0.5, zorder=4)

    for i, row in df.iterrows():
        if outliers == 'exclude' and is_outlier[i]:
            continue
        ax.annotate(row['name'], (row['jobs_per_km2'], row[y_col]),
                    fontsize=7, alpha=0.7, xytext=(4, 4),
                    textcoords='offset points')

    if tourism:
        cbar_cmap = LinearSegmentedColormap.from_list(
            'tourism_sat', ['#cccccc', base_color], N=256)
        sm = plt.cm.ScalarMappable(cmap=cbar_cmap, norm=tourism_norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, ax=ax, location='left', pad=0.08, shrink=0.7)
        cbar.set_label('Tourist nights / worker / year', fontsize=10, labelpad=10)

    fit = _fit_log_trend(ax, x_vals, y_vals, exclude_mask=is_outlier if outliers else None)
    r2 = None
    if fit is not None:
        r2, a, b, rmse = fit
        sign = '+' if b >= 0 else '−'
        eq_label = f'$y = {a:.3f} \\ln(x) {sign} {abs(b):.3f}$'
        r2_label = 'log fit'
        if outliers and n_outliers:
            r2_label += f', excl. {n_outliers} outlier{"s" if n_outliers != 1 else ""}'
        ax.text(0.95, 0.05,
                f'{eq_label}\n$R^2 = {r2:.3f}$, RMSE $= {rmse:.3f}$ ({r2_label})',
                transform=ax.transAxes, fontsize=10, ha='right', va='bottom',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    ax.set_xlabel('Employment Density (jobs / km²)', fontsize=12, labelpad=10)
    ax.set_ylabel(mc['ylabel'], fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs {mc["title"]} — {cc} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] Scatter plot saved to: {output_file}")
    return {'r2': r2, 'n_regions': len(df), 'n_outliers': n_outliers}


def plot_combined(datasets: list[tuple[str, pd.DataFrame]], year: int, output_file: str,
                  metric: str = 'effort', outliers: str | None = None,
                  log_x: bool = True, tourism: bool = False):
    """Combined scatter plot for multiple countries, using region names as labels."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(16, 10), dpi=300)

    mc = METRIC_CONFIG[metric]
    y_col = mc['y_col']
    label_size = 6 if len(datasets) <= 2 else 5

    # Collect all points first so outlier detection is global
    all_x, all_y, all_cc = [], [], []
    for country, df in datasets:
        all_x.extend(df['jobs_per_km2'].values)
        all_y.extend(df[y_col].values)
        all_cc.extend([country.upper()] * len(df))
    all_x = np.array(all_x)
    all_y = np.array(all_y)

    is_outlier = _detect_outliers(all_x, all_y) if outliers else np.zeros(len(all_x), dtype=bool)
    n_outliers = int(is_outlier.sum())

    from matplotlib.colors import Normalize
    tourism_norm = Normalize(vmin=0, vmax=TOURISM_NPW_CAP, clip=True) if tourism else None

    offset = 0
    for country, df in datasets:
        cc = country.upper()
        color = COUNTRY_COLORS.get(cc, '#333333')
        n = len(df)
        chunk_outlier = is_outlier[offset:offset + n]

        x_vals = df['jobs_per_km2'].values
        y_vals = df[y_col].values

        if outliers == 'exclude':
            keep = ~chunk_outlier
            plot_x, plot_y = x_vals[keep], y_vals[keep]
        else:
            keep = np.ones(n, dtype=bool)
            plot_x, plot_y = x_vals, y_vals

        if tourism and 'nights_per_worker' in df.columns:
            npw = df['nights_per_worker'].fillna(0).values[keep]
            colors = _tourism_colors(color, npw, tourism_norm)
            ax.scatter(plot_x, plot_y, s=60, alpha=0.7,
                       c=colors, edgecolors=color, linewidth=0.5,
                       label=cc, zorder=3)
        else:
            ax.scatter(plot_x, plot_y, s=60, alpha=0.7,
                       color=color, edgecolors='white', linewidth=0.5,
                       label=cc, zorder=3)

        if outliers == 'highlight' and chunk_outlier.any():
            ax.scatter(x_vals[chunk_outlier], y_vals[chunk_outlier], s=60,
                       facecolors='none', edgecolors='red', linewidth=0.5, zorder=4)

        if 'wage_fallback' in df.columns and df['wage_fallback'].any():
            fb = df['wage_fallback'].values & keep
            if fb.any():
                ax.scatter(x_vals[fb], y_vals[fb], s=60,
                           facecolors='none', edgecolors='black', linewidth=0.5, zorder=4)

        for j, (_, row) in enumerate(df.iterrows()):
            if outliers == 'exclude' and chunk_outlier[j]:
                continue
            ax.annotate(row['name'], (row['jobs_per_km2'], row[y_col]),
                        fontsize=label_size, alpha=0.7, xytext=(4, 4),
                        textcoords='offset points', color=color)

        offset += n

    fit = _fit_log_trend(ax, all_x, all_y, exclude_mask=is_outlier if outliers else None)
    r2 = None
    r2_label = 'log fit, combined'
    if outliers and n_outliers:
        r2_label += f', excl. {n_outliers} outlier{"s" if n_outliers != 1 else ""}'
    info_y = 0.05
    if fit is not None:
        r2, a, b, rmse = fit
        sign = '+' if b >= 0 else '−'
        eq_label = f'$y = {a:.3f} \\ln(x) {sign} {abs(b):.3f}$'
        ax.text(0.95, info_y,
                f'{eq_label}\n$R^2 = {r2:.3f}$, RMSE $= {rmse:.3f}$ ({r2_label})',
                transform=ax.transAxes, fontsize=10, ha='right', va='bottom',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))
        info_y += 0.08
    if tourism:
        ax.text(0.95, info_y,
                f'Saturation = tourism intensity (0–{TOURISM_NPW_CAP} nights/worker/year)',
                transform=ax.transAxes, fontsize=9, ha='right', va='bottom',
                bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    countries_label = ' + '.join(cc for cc, _ in datasets)
    if log_x:
        ax.set_xscale('log')
    ax.set_xlabel('Employment Density (jobs / km²' + (', log scale)' if log_x else ')'),
                  fontsize=12, labelpad=10)
    ax.set_ylabel(mc['ylabel'], fontsize=12, labelpad=10)
    ax.set_title(f'Employment Density vs {mc["title"]} — {countries_label} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold', pad=15)
    ax.legend(fontsize=11, loc='upper right')

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] Combined plot saved to: {output_file}")
    n_total = sum(len(df) for _, df in datasets)
    return {'r2': r2, 'n_regions': n_total, 'n_outliers': n_outliers}


# ---------------------------------------------------------------------------
# Tourism correlation scatter — metric vs nights/worker
# ---------------------------------------------------------------------------


def plot_tourism_scatter(datasets: list[tuple[str, pd.DataFrame]], year: int,
                         output_file: str, metric: str = 'effort',
                         outliers: str | None = None):
    """Scatter of a housing metric (Y) vs tourism intensity (X), all countries."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)

    mc = METRIC_CONFIG[metric]
    y_col = mc['y_col']

    all_x, all_y, n_outliers = [], [], 0
    for cc, df in datasets:
        sub = df.dropna(subset=['nights_per_worker', y_col])
        if sub.empty:
            continue
        # Detect outliers on the density-vs-metric axes (same as main scatter)
        is_out = _detect_outliers(sub['jobs_per_km2'].values,
                                  sub[y_col].values) if outliers else np.zeros(len(sub), dtype=bool)
        n_outliers += int(is_out.sum())

        color = COUNTRY_COLORS.get(cc, '#d95f02')
        show = sub[~is_out] if outliers == 'exclude' else sub
        ax.scatter(show['nights_per_worker'], show[y_col], s=60, alpha=0.7,
                   color=color, edgecolors='white', linewidth=0.5, label=cc)

        if outliers == 'highlight' and is_out.any():
            out_df = sub[is_out]
            ax.scatter(out_df['nights_per_worker'], out_df[y_col], s=60,
                       facecolors='none', edgecolors='red', linewidth=0.5, zorder=4)

        for _, row in show.iterrows():
            ax.annotate(row['name'], (row['nights_per_worker'], row[y_col]),
                        fontsize=6, alpha=0.6, xytext=(4, 4),
                        textcoords='offset points')

        fit_sub = sub[~is_out] if outliers else sub
        all_x.extend(fit_sub['nights_per_worker'].values)
        all_y.extend(fit_sub[y_col].values)

    if len(all_x) > 2:
        all_x = np.array(all_x)
        all_y = np.array(all_y)
        coeffs = np.polyfit(all_x, all_y, 1)
        x_line = np.linspace(all_x.min(), all_x.max(), 200)
        ax.plot(x_line, np.polyval(coeffs, x_line), '--', color='#666666',
                alpha=0.5, linewidth=1.5)
        ss_res = np.sum((all_y - np.polyval(coeffs, all_x)) ** 2)
        ss_tot = np.sum((all_y - all_y.mean()) ** 2)
        r2 = 1 - ss_res / ss_tot if ss_tot > 0 else None
        r2_label = 'linear fit'
        if outliers and n_outliers:
            r2_label += f', excl. {n_outliers} outlier{"s" if n_outliers != 1 else ""}'
        if r2 is not None:
            ax.text(0.95, 0.05, f'$R^2 = {r2:.3f}$ ({r2_label})',
                    transform=ax.transAxes, fontsize=10, ha='right', va='bottom',
                    bbox=dict(boxstyle='round,pad=0.3', fc='white', ec='gray', alpha=0.8))

    ax.set_xlabel('Tourist nights / worker / year', fontsize=12)
    ax.set_ylabel(mc['ylabel'], fontsize=12)
    tag = '_'.join(cc for cc, _ in datasets)
    ax.set_title(f'Tourism Intensity vs {mc["title"]} — {tag} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold')
    ax.legend(fontsize=10)
    fig.tight_layout()
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Tourism scatter saved to: {output_file}")


# ---------------------------------------------------------------------------
# Choropleth map — NUTS-3 regions coloured by metric value
# ---------------------------------------------------------------------------


# Mainland bounding boxes (lon_min, lat_min, lon_max, lat_max)
_MAINLAND_BBOX = {
    'PT': (-9.7, 36.9, -6.0, 42.2),
    'ES': (-9.5, 35.8, 3.4, 43.9),
    'FR': (-5.3, 41.2, 9.7, 51.2),
    'NL': (3.2, 50.6, 7.4, 53.7),
}


_NUTS3_GEOJSON = "NUTS_RG_10M_2024_4326_LEVL_3.geojson"


def _fetch_nuts3_geometry():
    """Download (and cache) NUTS-3 boundaries from Eurostat GISCO (NUTS 2024)."""
    import geopandas as gpd
    local = INPUT_DIR / _NUTS3_GEOJSON if INPUT_DIR else None
    if local and local.exists():
        print(f"  [local] {local}")
        return gpd.read_file(local)
    cache = Path(tempfile.gettempdir()) / _NUTS3_GEOJSON
    if not cache.exists():
        url = ("https://gisco-services.ec.europa.eu/distribution/v2/nuts/"
               "geojson/" + _NUTS3_GEOJSON)
        print("[+] Downloading NUTS-3 boundaries (GISCO)...", flush=True)
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        cache.write_bytes(resp.content)
    if SAVE_MODE and local:
        import shutil
        shutil.copy2(cache, local)
        print(f"  [saved] {local}")
    return gpd.read_file(cache)


def plot_map(df: pd.DataFrame, country: str, year: int, output_file: str,
             metric: str = 'effort', vmin: float = None, vmax: float = None):
    """Choropleth map of a metric for one country's NUTS-3 regions."""
    import geopandas as gpd

    mc = METRIC_CONFIG[metric]
    y_col = mc['y_col']
    cc = country.upper()

    gdf = _fetch_nuts3_geometry()
    geo = gdf[gdf['CNTR_CODE'] == cc].copy()

    merged = geo.merge(df[['nuts3', y_col]], left_on='NUTS_ID', right_on='nuts3',
                        how='left')

    bbox = _MAINLAND_BBOX.get(cc)
    if bbox:
        merged = merged.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]

    fig, ax = plt.subplots(figsize=(10, 10), dpi=300)
    if bbox:
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])

    from matplotlib.colors import Normalize
    norm = Normalize(vmin=vmin, vmax=vmax, clip=True)

    no_data = merged[merged[y_col].isna()]
    if not no_data.empty:
        no_data.plot(ax=ax, color='#e0e0e0', edgecolor='white', linewidth=0.5)

    has_data = merged[merged[y_col].notna()]
    if not has_data.empty:
        has_data.plot(ax=ax, column=y_col, cmap='YlOrRd', norm=norm,
                      edgecolor='white', linewidth=0.5, legend=False)

    sm = plt.cm.ScalarMappable(cmap='YlOrRd', norm=norm)
    sm.set_array([])
    cax = fig.add_axes([0.92, 0.25, 0.015, 0.5])
    cbar = fig.colorbar(sm, cax=cax)
    cbar.set_label(mc['ylabel'], fontsize=10)

    # Region name labels at centroids
    for _, row in merged.iterrows():
        if row.geometry is None:
            continue
        c = row.geometry.centroid
        name = row.get('NAME_LATN', '')
        if not name:
            continue
        fontsize = 5 if cc in ('FR', 'ES') else 6
        val = row.get(y_col, None)
        txt_color = 'white' if (val is not None and val >= 1.75) else '#333333'
        ax.text(c.x, c.y, name, fontsize=fontsize, ha='center', va='center',
                color=txt_color, fontweight='medium')

    ax.set_title(f'{mc["title"]} — {cc} NUTS-3 ({year})',
                 fontsize=14, fontweight='bold')
    ax.set_axis_off()
    ax.set_aspect('equal')

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Map saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Employment Density vs Housing metrics — NUTS-3 scatter plot')
    parser.add_argument('year', type=int,
                        help='Reference year. Complete data: 2021, 2022. '
                             '2023 uses FR wages from 2022 (latest available).')
    parser.add_argument('--metric', choices=['effort', 'price', 'all'], default='effort',
                        help='Y-axis metric: "effort" = months of gross salary / m² '
                             '(default), "price" = raw € / m², "all" = both')
    parser.add_argument('--save-data', metavar='DIR', nargs='?', const='input',
                        help='Save fetched data as CSVs into DIR (default: input/)')
    parser.add_argument('--local-data', metavar='DIR', nargs='?', const='input',
                        help='Load data from local CSVs in DIR instead of fetching '
                             '(default: input/)')
    outlier_grp = parser.add_mutually_exclusive_group()
    outlier_grp.add_argument('--highlight-outliers', action='store_true',
                             help='Highlight outliers (red diamond) and exclude from fit')
    outlier_grp.add_argument('--exclude-outliers', action='store_true',
                             help='Remove outliers from the plot and fit')
    parser.add_argument('--exclude-paris', action='store_true',
                        help='Exclude Paris (FR101) from all plots and fits')
    parser.add_argument('--countries', metavar='CC',
                        help='Comma-separated country codes for the combined plot '
                             '(default: all). Example: --countries PT,ES')
    parser.add_argument('--linear-x', action='store_true',
                        help='Use linear x-axis on the combined plot (default: log)')
    parser.add_argument('--tourism', action='store_true',
                        help='Color points by tourism intensity (nights/worker). '
                             'Requires year=2023 (only year with matching NUTS codes '
                             'between employment and tourism datasets).')
    parser.add_argument('--map', action='store_true',
                        help='Choropleth map of purchase effort by NUTS-3 region '
                             '(mainland only). Colour scale calibrated to PT+ES range.')
    args = parser.parse_args()

    if args.tourism and args.year != 2023:
        parser.error("--tourism requires year 2023. Tourism and employment datasets "
                     "use incompatible NUTS region codes for other years "
                     "(NUTS 2021 reclassification merged some regions).")

    global INPUT_DIR, SAVE_MODE
    if args.local_data:
        INPUT_DIR = Path(args.local_data)
        if not INPUT_DIR.is_dir():
            parser.error(f"--local-data directory does not exist: {INPUT_DIR}")
    elif args.save_data:
        INPUT_DIR = Path(args.save_data)
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        SAVE_MODE = True

    year     = args.year
    outliers = ('highlight' if args.highlight_outliers
                else 'exclude' if args.exclude_outliers else None)
    metrics  = list(METRIC_CONFIG) if args.metric == 'all' else [args.metric]

    out_dir = Path(tempfile.gettempdir()) / "density_vs_price"
    out_dir.mkdir(exist_ok=True)

    all_fetchers = [
        ('PT', fetch_pt_prices),
        ('ES', fetch_es_prices),
        ('FR', fetch_fr_prices),
        ('NL', fetch_nl_prices),
        ('IT', fetch_it_prices),
    ]
    if args.countries:
        selected = [c.strip().upper() for c in args.countries.split(',')]
        fetchers = [(cc, f) for cc, f in all_fetchers if cc in selected]
        if not fetchers:
            parser.error(f"No valid countries in: {args.countries}")
    else:
        fetchers = all_fetchers

    local_only_requested = {cc for cc, _ in fetchers} & LOCAL_ONLY_COUNTRIES
    if local_only_requested and (not INPUT_DIR or SAVE_MODE):
        print(f"Error: {', '.join(sorted(local_only_requested))} require --local-data "
              f"(no public API for prices/wages).\n"
              f"Use --local-data <dir> or exclude with --countries.",
              file=sys.stderr)
        sys.exit(1)

    if INPUT_DIR:
        mode = "Using local data from" if not SAVE_MODE else "Will save fetched data to"
        print(f"[*] {mode} {INPUT_DIR}/")

    # Fetch tourism data once if requested (before country loop)
    tourism = fetch_tourism_nights(year) if args.tourism else {}

    # Fetch data once (shared across metrics)
    country_data = []
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
            if args.exclude_paris:
                df = df[df['nuts3'] != 'FR101'].reset_index(drop=True)
            if tourism:
                df = add_tourism_intensity(df, tourism)
                matched = df['nights_per_worker'].notna().sum()
                print(f"  [{country}] Tourism data matched for {matched}/{len(df)} regions")
            print(f"[{country}] {len(df)} NUTS-3 regions matched for {use_year}")
            country_data.append((country, df, use_year))
        except (requests.exceptions.ConnectionError,
                requests.exceptions.Timeout,
                requests.exceptions.HTTPError) as e:
            print(f"[-] {country} skipped: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[-] {country} failed: {e}", file=sys.stderr)
            import traceback
            traceback.print_exc()

    summary_rows = []

    for metric in metrics:
        mc   = METRIC_CONFIG[metric]
        slug = mc['slug']

        combined = []
        for country, df, use_year in country_data:
            out = str(out_dir / f"{country}_density_vs_{slug}_{use_year}.png")
            stats = plot_scatter(
                df, country, use_year, out, metric=metric, outliers=outliers,
                tourism=args.tourism)
            if args.tourism and 'nights_per_worker' in df.columns:
                tout = str(out_dir / f"{country}_tourism_vs_{slug}_{use_year}.png")
                plot_tourism_scatter([(country, df)], use_year, tout,
                                     metric=metric, outliers=outliers)
                if outliers:
                    tout_all = str(out_dir / f"{country}_tourism_vs_{slug}_{use_year}_all.png")
                    plot_tourism_scatter([(country, df)], use_year, tout_all,
                                         metric=metric, outliers=None)
            combined.append((country, df))
            summary_rows.append({
                'metric': metric, 'scope': country, 'year': use_year,
                'n_regions': stats['n_regions'],
                'n_outliers': stats['n_outliers'],
                'r2': stats['r2'],
            })

        if len(combined) > 1:
            tag = '_'.join(cc for cc, _ in combined)
            out = str(out_dir / f"{tag}_density_vs_{slug}_{year}.png")
            stats = plot_combined(
                combined, year, out, metric=metric, outliers=outliers,
                log_x=not args.linear_x, tourism=args.tourism)
            summary_rows.append({
                'metric': metric, 'scope': tag, 'year': year,
                'n_regions': stats['n_regions'],
                'n_outliers': stats['n_outliers'],
                'r2': stats['r2'],
            })

            all_df = pd.concat(
                [df.assign(country=cc) for cc, df in combined],
                ignore_index=True,
            )
            cols = ['country', 'nuts3', 'name', 'employment_ths', 'area_km2',
                    'jobs_per_km2', 'price_eur_m2', 'avg_annual_wage',
                    'effort_months_per_m2']
            if args.tourism and 'nights_per_worker' in all_df.columns:
                cols += ['tourist_nights', 'nights_per_worker']
            all_df = all_df[cols].sort_values(['country', 'nuts3'])
            csv_path = out_dir / f"density_vs_{slug}_{year}.csv"
            all_df.to_csv(csv_path, index=False, float_format='%.2f')
            print(f"[+] Dataset saved to: {csv_path} ({len(all_df)} regions)")

        if args.tourism and combined:
            tout = str(out_dir / f"tourism_vs_{slug}_{year}.png")
            plot_tourism_scatter(combined, year, tout, metric=metric,
                                 outliers=outliers)
            if outliers:
                tout_all = str(out_dir / f"tourism_vs_{slug}_{year}_all.png")
                plot_tourism_scatter(combined, year, tout_all, metric=metric,
                                     outliers=None)

    if args.map and country_data:
        # Compute PT+ES effort range for colour scale calibration
        pt_es = [df for cc, df, _ in country_data if cc in ('PT', 'ES')]
        if pt_es:
            all_effort = pd.concat(pt_es)['effort_months_per_m2'].dropna()
            vmin, vmax = all_effort.min(), all_effort.max()
        else:
            all_vals = pd.concat([df for _, df, _ in country_data])['effort_months_per_m2'].dropna()
            vmin, vmax = all_vals.min(), all_vals.max()
        for country, df, use_year in country_data:
            map_out = str(out_dir / f"{country}_effort_map_{use_year}.png")
            plot_map(df, country, use_year, map_out, metric='effort',
                     vmin=vmin, vmax=vmax)

    if summary_rows:
        summary_df = pd.DataFrame(summary_rows)
        summary_df['r2'] = summary_df['r2'].map(
            lambda v: f'{v:.4f}' if v is not None else '')
        summary_path = out_dir / f"summary_{year}.csv"
        summary_df.to_csv(summary_path, index=False)
        print(f"[+] Summary saved to: {summary_path}")

        countries_used = [cc for cc, _, _ in country_data]
        source_rows = []
        for cc in ['ALL'] + countries_used:
            for dtype, (desc, url) in DATA_SOURCES.get(cc, {}).items():
                source_rows.append({
                    'country': cc, 'data_type': dtype,
                    'source': desc, 'url': url,
                })
        sources_path = out_dir / "data_sources.csv"
        pd.DataFrame(source_rows).to_csv(sources_path, index=False)
        print(f"[+] Data sources saved to: {sources_path}")


if __name__ == "__main__":
    main()
