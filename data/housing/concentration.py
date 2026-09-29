#!/usr/bin/env python3
"""
Regional Employment Concentration Plotter
------------------------------------------
Queries Eurostat API for NUTS-3 regional employment data and plots
concentration metrics over time.

Subcommands:
    cr <n>          Concentration ratio: share held by top n regions.
    target <pct>    Minimum regions needed to reach pct% of employment.
    eu <pct>        Compare all EU-27 countries for a given target.
    region <nuts3>  Time series for a single NUTS-3 region.
    top             Top-region share trajectories for all EU-27.
    list-regions    List all NUTS-3 regions for a country.

Dependencies:
    pip install requests pandas matplotlib
"""

import argparse
import sys
import tempfile
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd
import requests


def fetch_population(country_code: str, year: int) -> int | None:
    """Fetches national population from Eurostat (demo_r_pjanaggr3)."""
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/demo_r_pjanaggr3"
    cc = country_code.upper()
    params = {
        "format": "JSON",
        "lang": "EN",
        "sex": "T",
        "age": "TOTAL",
        "geo": cc,
        "sinceTimePeriod": str(year),
        "untilTimePeriod": str(year),
    }
    try:
        resp = requests.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        values = data.get('value', {})
        if values:
            return int(list(values.values())[0])
    except (requests.exceptions.RequestException, ValueError, KeyError):
        pass
    return None


def fetch_area_data(country_code: str) -> dict[str, float]:
    """Fetches NUTS-3 land area (km²) from Eurostat reg_area3. Returns {nuts3: km²}."""
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/reg_area3"
    cc = country_code.upper()
    print(f"[+] Querying Eurostat API for NUTS-3 area data [{cc}]...", flush=True)
    params = {"format": "JSON", "lang": "EN", "landuse": "L0008"}
    try:
        resp = requests.get(url, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.RequestException as e:
        print(f"[-] Eurostat area API Error: {e}", file=sys.stderr)
        return {}

    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    dim_ids = data['id']
    dim_sizes = data['size']

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
    latest = {}
    for code in nuts3:
        for t_str, t_pos in sorted(time_idx.items()):
            coords = {geo_dim: geo_idx[code], time_dim: t_pos}
            coords.update(defaults)
            flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
            val = values.get(str(flat))
            if val is not None:
                latest[code] = float(val)
    return latest


def fetch_eurostat_data(country_code: str) -> pd.DataFrame:
    """Fetches NUTS-3 employment data from the Eurostat REST API (nama_10r_3empers)."""
    url = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/nama_10r_3empers"

    params = {
        "format": "JSON",
        "lang": "EN",
        "unit": "THS",
        "wstatus": "EMP",
        "nace_r2": "TOTAL",
    }

    cc = country_code.upper()
    print(f"[+] Querying Eurostat API for NUTS-3 employment data [{cc}]...", flush=True)

    try:
        response = requests.get(url, params=params, timeout=60)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"[-] Eurostat API Error: {e}", file=sys.stderr)
        sys.exit(1)

    dimensions = data['dimension']
    geo_dimension = dimensions['geo']['category']['index']
    time_dimension = dimensions['time']['category']['index']
    geo_labels = dimensions['geo']['category']['label']

    dim_ids = data['id']
    dim_sizes = data['size']

    nuts3_codes = [
        code for code in geo_dimension.keys()
        if code.startswith(cc) and len(code) == 5
    ]

    if not nuts3_codes:
        print(f"[-] No NUTS-3 records found for '{cc}'. Use valid EU 2-letter codes (e.g., PT, ES, FR, DE, IT).", file=sys.stderr)
        sys.exit(1)

    geo_dim_idx = dim_ids.index('geo')
    time_dim_idx = dim_ids.index('time')

    strides = [1] * len(dim_sizes)
    for i in range(len(dim_sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * dim_sizes[i + 1]

    default_indices = {}
    for d_idx, d_name in enumerate(dim_ids):
        if d_name not in ['geo', 'time']:
            cats = dimensions[d_name]['category']['index']
            default_indices[d_idx] = min(cats.values())

    values = data['value']
    records = []

    for code in nuts3_codes:
        geo_pos = geo_dimension[code]
        region_name = geo_labels.get(code, code)

        for time_str, time_pos in time_dimension.items():
            coords = {}
            coords[geo_dim_idx] = geo_pos
            coords[time_dim_idx] = time_pos
            coords.update(default_indices)

            flat_pos = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
            flat_key = str(flat_pos)

            if flat_key in values and values[flat_key] is not None:
                records.append({
                    'region_code': code,
                    'region_name': region_name,
                    'year': int(time_str),
                    'employment': float(values[flat_key])
                })

    df = pd.DataFrame(records)
    if df.empty:
        return df

    total_regions = df['region_code'].nunique()
    regions_per_year = df.groupby('year')['region_code'].nunique()
    complete_years = regions_per_year[regions_per_year >= total_regions * 0.5].index
    dropped = set(df['year'].unique()) - set(complete_years)
    if dropped:
        print(f"[!] Dropping years with incomplete data: {sorted(dropped)}")
    return df[df['year'].isin(complete_years)].reset_index(drop=True)


def calculate_cr_n(df: pd.DataFrame, n: int,
                   area: dict[str, float] | None = None) -> pd.DataFrame:
    """Calculates CR_n concentration percentage over time."""
    total_area = sum(area.values()) if area else 0
    results = []

    for yr in sorted(df['year'].unique()):
        df_yr = df[df['year'] == yr].sort_values(by='employment', ascending=False).reset_index(drop=True)
        if df_yr.empty:
            continue

        total_emp = df_yr['employment'].sum()
        if total_emp == 0:
            continue

        total_regions = len(df_yr)
        top_n = df_yr.head(n)
        cr_val = (top_n['employment'].sum() / total_emp) * 100

        top_area = sum(area.get(c, 0) for c in top_n['region_code']) if area else 0
        area_pct = (top_area / total_area * 100) if total_area > 0 else 0

        regions_formatted = [
            f"{row['region_name']} ({row['region_code']}) - {(row['employment'] / total_emp) * 100:.2f}%"
            for _, row in top_n.iterrows()
        ]

        results.append({
            'year': yr,
            'metric_val': cr_val,
            'total_emp': total_emp,
            'total_regions': total_regions,
            'area_pct': area_pct,
            'top_regions': regions_formatted,
        })

    return pd.DataFrame(results)


def calculate_n_for_percentage(df: pd.DataFrame, target_pct: float) -> pd.DataFrame:
    """Finds minimum number of regions needed to reach target_pct% of employment per year."""
    results = []

    for yr in sorted(df['year'].unique()):
        df_yr = df[df['year'] == yr].sort_values(by='employment', ascending=False).reset_index(drop=True)
        if df_yr.empty:
            continue

        total_emp = df_yr['employment'].sum()
        if total_emp == 0:
            continue

        df_yr['indiv_pct'] = (df_yr['employment'] / total_emp) * 100
        df_yr['cum_pct'] = df_yr['indiv_pct'].cumsum()

        qualifying = df_yr[df_yr['cum_pct'] >= target_pct]
        if qualifying.empty:
            n_required = len(df_yr)
            actual_pct = df_yr['cum_pct'].iloc[-1]
            discovered_df = df_yr
        else:
            first_match_idx = qualifying.index[0]
            n_required = first_match_idx + 1
            actual_pct = df_yr.loc[first_match_idx, 'cum_pct']
            discovered_df = df_yr.head(n_required)

        regions_list = [
            f"{row['region_name']} ({row['region_code']}) — {row['indiv_pct']:.2f}%"
            for _, row in discovered_df.iterrows()
        ]

        results.append({
            'year': yr,
            'metric_val': n_required,
            'actual_pct': actual_pct,
            'total_emp': total_emp,
            'top_regions': regions_list
        })

    return pd.DataFrame(results)


def print_regions_for_percentage(results_df: pd.DataFrame, target_pct: float):
    """Prints NUTS-3 regions needed to reach a target employment percentage."""
    print("\n" + "=" * 80)
    print(f" NUTS-3 REGIONS NEEDED TO REACH {target_pct}% EMPLOYMENT")
    print("=" * 80)

    for _, row in results_df.tail(5).iterrows():
        yr = row['year']
        n = int(row['metric_val'])
        pct = row['actual_pct']

        print(f"\n Year {yr} | Required Regions (n) = {n} | Total Coverage = {pct:.2f}%")
        print("-" * 65)
        for i, reg in enumerate(row['top_regions'], 1):
            print(f"  {i}. {reg}")

    print("\n" + "=" * 80 + "\n")


def print_regions_for_cr(results_df: pd.DataFrame, n: int):
    """Prints the top-n NUTS-3 regions by employment share."""
    print("\n" + "=" * 80)
    print(f" TOP-{n} NUTS-3 REGIONS BY EMPLOYMENT SHARE")
    print("=" * 80)

    for _, row in results_df.tail(5).iterrows():
        yr = row['year']
        cr = row['metric_val']

        print(f"\n Year {yr} | CR_{n} = {cr:.2f}%")
        print("-" * 65)
        for i, reg in enumerate(row['top_regions'], 1):
            print(f"  {i}. {reg}")

    print("\n" + "=" * 80 + "\n")


def plot_distribution(raw_df: pd.DataFrame, country_code: str, target_pct: float,
                      n_required: int, output_file: str,
                      area: dict[str, float] | None = None):
    """Bar chart of regional employment shares with cumulative line for the latest year."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    cc = country_code.upper()
    latest_year = raw_df['year'].max()
    df_yr = raw_df[raw_df['year'] == latest_year].sort_values(
        by='employment', ascending=False
    ).reset_index(drop=True)

    total_emp = df_yr['employment'].sum()
    df_yr['share'] = (df_yr['employment'] / total_emp) * 100
    df_yr['cum_share'] = df_yr['share'].cumsum()

    fig, ax1 = plt.subplots(figsize=(14, 6), dpi=300)

    colors = ['#d95f02' if i < n_required else '#a0a0a0' for i in range(len(df_yr))]
    max_label = 28
    labels = [row['region_name'][:max_label] for _, row in df_yr.iterrows()]

    ax1.bar(range(len(df_yr)), df_yr['share'], color=colors, edgecolor='white', linewidth=0.3)
    ax1.set_ylabel('Employment Share (%)', fontsize=11, labelpad=10)
    ax1.set_xlabel('NUTS-3 Regions (ranked by employment)', fontsize=11, labelpad=10)
    ax1.set_xticks(range(len(df_yr)))
    ax1.set_xticklabels(labels, rotation=90, fontsize=7)

    ax2 = ax1.twinx()
    ax2.plot(range(len(df_yr)), df_yr['cum_share'], color='#1f77b4',
             linewidth=2, marker='.', markersize=4)
    ax2.set_ylabel('Cumulative Share (%)', fontsize=11, labelpad=10, color='#1f77b4')
    ax2.tick_params(axis='y', labelcolor='#1f77b4')

    ax2.axhline(y=target_pct, color='#1f77b4', linestyle='--', linewidth=1, alpha=0.7)
    ax2.text(len(df_yr) - 1, target_pct + 1.5, f'{target_pct}% target',
             ha='right', fontsize=9, color='#1f77b4', fontstyle='italic')

    if n_required > 0 and n_required < len(df_yr):
        ax1.axvline(x=n_required - 0.5, color='#d95f02', linestyle='--', linewidth=1, alpha=0.7)
        ax1.text(n_required - 0.5, ax1.get_ylim()[1] * 0.95, f' n={n_required}',
                 fontsize=9, color='#d95f02', fontweight='bold', va='top')

    subtitle = f'Top {n_required} regions (orange) reach {target_pct}% of national employment'
    if area:
        total_area = sum(area.values())
        top_codes = df_yr.head(n_required)['region_code']
        top_area = sum(area.get(c, 0) for c in top_codes)
        if total_area > 0:
            subtitle += f', representing {top_area / total_area * 100:.1f}% of the country area'

    ax1.set_title(
        f'NUTS-3 Employment Distribution — {cc} ({latest_year})\n{subtitle}',
        fontsize=13, fontweight='bold', pad=15
    )

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    print(f"[+] Distribution plot saved to: {output_file}")


EU27 = [
    'AT', 'BE', 'BG', 'CY', 'CZ', 'DE', 'DK', 'EE', 'EL', 'ES',
    'FI', 'FR', 'HR', 'HU', 'IE', 'IT', 'LT', 'LU', 'LV', 'MT',
    'NL', 'PL', 'PT', 'RO', 'SE', 'SI', 'SK',
]


def _fetch_all_eurostat(dataset: str, **extra_params) -> dict:
    """Single Eurostat API call, returns raw JSON-stat response."""
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}"
    params = {"format": "JSON", "lang": "EN"}
    params.update(extra_params)
    resp = requests.get(url, params=params, timeout=120)
    resp.raise_for_status()
    return resp.json()


def _extract_all_nuts3(data: dict, year: int) -> dict[str, list[dict]]:
    """Extract NUTS-3 employment from JSON-stat, grouped by 2-letter country code."""
    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    geo_labels = dims['geo']['category']['label']
    dim_ids = data['id']
    dim_sizes = data['size']

    if str(year) not in time_idx:
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
    by_country: dict[str, list[dict]] = {}
    for code, g_pos in geo_idx.items():
        if len(code) != 5:
            continue
        cc = code[:2]
        coords = {geo_dim: g_pos, time_dim: t_pos}
        coords.update(defaults)
        flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
        val = values.get(str(flat))
        if val is not None:
            by_country.setdefault(cc, []).append({
                'region_code': code,
                'region_name': geo_labels.get(code, code),
                'employment': float(val),
            })
    return by_country


def _extract_all_area(data: dict) -> dict[str, dict[str, float]]:
    """Extract NUTS-3 area from JSON-stat, grouped by country. Uses latest year per region."""
    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    dim_ids = data['id']
    dim_sizes = data['size']

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
    by_country: dict[str, dict[str, float]] = {}
    for code, g_pos in geo_idx.items():
        if len(code) != 5:
            continue
        cc = code[:2]
        for t_str, t_pos in sorted(time_idx.items()):
            coords = {geo_dim: g_pos, time_dim: t_pos}
            coords.update(defaults)
            flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
            val = values.get(str(flat))
            if val is not None:
                by_country.setdefault(cc, {})[code] = float(val)
    return by_country


def _compute_concentration(target_pct: float, emp_by_cc: dict, area_by_cc: dict,
                           min_regions: int = 0) -> pd.DataFrame:
    """Compute concentration metrics for all EU-27 countries from pre-fetched data."""
    results = []
    for cc in EU27:
        regions = emp_by_cc.get(cc, [])
        if len(regions) < min_regions:
            continue
        regions.sort(key=lambda r: r['employment'], reverse=True)
        total_emp = sum(r['employment'] for r in regions)
        if total_emp == 0:
            continue

        cum = 0.0
        n_required = 0
        for r in regions:
            cum += r['employment']
            n_required += 1
            if (cum / total_emp) * 100 >= target_pct:
                break

        total_regions = len(regions)
        area_dict = area_by_cc.get(cc, {})
        total_area = sum(area_dict.values())
        top_codes = [r['region_code'] for r in regions[:n_required]]
        top_area = sum(area_dict.get(c, 0) for c in top_codes)
        area_pct = (top_area / total_area * 100) if total_area > 0 else 0

        results.append({
            'country': cc,
            'n_required': n_required,
            'total_regions': total_regions,
            'region_fraction': n_required / total_regions * 100,
            'area_pct': area_pct,
            'actual_pct': cum / total_emp * 100,
        })

    return pd.DataFrame(results)


def eu_comparison(target_pct: float, year: int, min_regions: int = 0,
                  compare_year: int | None = None):
    """Compute concentration metrics for all EU-27 countries."""
    years = [year]
    if compare_year:
        years.append(compare_year)

    print(f"[+] Fetching EU-wide employment data...", flush=True)
    emp_raw = _fetch_all_eurostat("nama_10r_3empers", unit="THS",
                                  wstatus="EMP", nace_r2="TOTAL")

    print("[+] Fetching EU-wide area data...", flush=True)
    area_data = _fetch_all_eurostat("reg_area3", landuse="L0008")
    area_by_cc = _extract_all_area(area_data)

    emp_by_year = {}
    for yr in years:
        emp_by_year[yr] = _extract_all_nuts3(emp_raw, yr)

    df = _compute_concentration(target_pct, emp_by_year[year], area_by_cc, min_regions)

    if compare_year and compare_year in emp_by_year:
        df_cmp = _compute_concentration(target_pct, emp_by_year[compare_year],
                                        area_by_cc, min_regions)
        if not df_cmp.empty:
            cmp = df_cmp.set_index('country')
            df['region_fraction_cmp'] = df['country'].map(
                cmp['region_fraction']).astype(float)
            df['area_pct_cmp'] = df['country'].map(
                cmp['area_pct']).astype(float)

    return df


def plot_eu_comparison(df: pd.DataFrame, target_pct: float, year: int,
                       compare_year: int | None = None):
    """Two bar charts: region fraction and area fraction to reach target_pct%."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    out_dir = Path(tempfile.gettempdir()) / "concentration"
    out_dir.mkdir(exist_ok=True)
    has_cmp = compare_year and 'region_fraction_cmp' in df.columns

    # Plot 1: region fraction (n/M)
    df1 = df.sort_values('region_fraction', ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
    ax.bar(range(len(df1)), df1['region_fraction'], color='#1f77b4',
           edgecolor='white', linewidth=0.5)
    if has_cmp:
        ax.scatter(range(len(df1)), df1['region_fraction_cmp'], color='#333333',
                   marker='_', s=200, linewidths=2, zorder=5, label=str(compare_year))
    ax.set_xticks(range(len(df1)))
    ax.set_xticklabels(df1['country'], fontsize=9, fontweight='bold')
    ax.set_ylabel('Fraction of NUTS-3 regions (%)', fontsize=11, labelpad=10)
    title1 = f'Share of NUTS-3 regions needed to reach {target_pct}% of national employment ({year})'
    ax.set_title(title1, fontsize=13, fontweight='bold', pad=15)
    for i, row in df1.iterrows():
        label = f"{int(row['n_required'])}/{int(row['total_regions'])}"
        if has_cmp and pd.notna(row.get('region_fraction_cmp')):
            delta = row['region_fraction'] - row['region_fraction_cmp']
            sign = '+' if delta >= 0 else ''
            label += f"\n{sign}{delta:.1f}pp"
        ax.text(i, row['region_fraction'] + 0.5, label,
                ha='center', fontsize=7, color='#333333')
    if has_cmp:
        ax.legend(fontsize=10, loc='upper right')
    fig.tight_layout()
    path1 = out_dir / f"EU_target{int(target_pct)}pct_regions_{year}.png"
    plt.savefig(path1, dpi=300)
    plt.close(fig)
    print(f"[+] Region fraction plot saved to: {path1}")

    # Plot 2: area fraction
    df2 = df.sort_values('area_pct', ascending=False).reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(14, 7), dpi=300)
    ax.bar(range(len(df2)), df2['area_pct'], color='#d95f02',
           edgecolor='white', linewidth=0.5)
    if has_cmp:
        ax.scatter(range(len(df2)), df2['area_pct_cmp'], color='#333333',
                   marker='_', s=200, linewidths=2, zorder=5, label=str(compare_year))
    ax.set_xticks(range(len(df2)))
    ax.set_xticklabels(df2['country'], fontsize=9, fontweight='bold')
    ax.set_ylabel('Country area (%)', fontsize=11, labelpad=10)
    title2 = f'Share of country area covering {target_pct}% of national employment ({year})'
    ax.set_title(title2, fontsize=13, fontweight='bold', pad=15)
    for i, row in df2.iterrows():
        label = f"{row['area_pct']:.1f}%"
        if has_cmp and pd.notna(row.get('area_pct_cmp')):
            delta = row['area_pct'] - row['area_pct_cmp']
            sign = '+' if delta >= 0 else ''
            label += f"\n{sign}{delta:.1f}pp"
        ax.text(i, row['area_pct'] + 0.5, label,
                ha='center', fontsize=7, color='#333333')
    if has_cmp:
        ax.legend(fontsize=10, loc='upper right')
    fig.tight_layout()
    path2 = out_dir / f"EU_target{int(target_pct)}pct_area_{year}.png"
    plt.savefig(path2, dpi=300)
    plt.close(fig)
    print(f"[+] Area fraction plot saved to: {path2}")


def _extract_all_nuts3_all_years(data: dict) -> dict[int, dict[str, list[dict]]]:
    """Extract NUTS-3 employment from JSON-stat for ALL years at once.
    Returns {year: {cc: [{region_code, region_name, employment}]}}."""
    dims = data['dimension']
    geo_idx = dims['geo']['category']['index']
    time_idx = dims['time']['category']['index']
    geo_labels = dims['geo']['category']['label']
    dim_ids = data['id']
    dim_sizes = data['size']

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
    result: dict[int, dict[str, list[dict]]] = {}
    for t_str, t_pos in time_idx.items():
        year = int(t_str)
        by_cc: dict[str, list[dict]] = {}
        for code, g_pos in geo_idx.items():
            if len(code) != 5:
                continue
            cc = code[:2]
            coords = {geo_dim: g_pos, time_dim: t_pos}
            coords.update(defaults)
            flat = sum(coords[i] * strides[i] for i in range(len(dim_ids)))
            val = values.get(str(flat))
            if val is not None:
                by_cc.setdefault(cc, []).append({
                    'region_code': code,
                    'region_name': geo_labels.get(code, code),
                    'employment': float(val),
                })
        result[year] = by_cc
    return result


def top_region_analysis(min_regions: int = 5) -> pd.DataFrame:
    """For each EU-27 country, find the top employment region and build a full time series."""
    print("[+] Fetching EU-wide employment data...", flush=True)
    emp_raw = _fetch_all_eurostat("nama_10r_3empers", unit="THS",
                                  wstatus="EMP", nace_r2="TOTAL")
    all_years_data = _extract_all_nuts3_all_years(emp_raw)
    years = sorted(all_years_data.keys())

    rows = []
    for cc in EU27:
        cc_year_counts = {yr: len(all_years_data[yr].get(cc, []))
                          for yr in years}
        max_count = max(cc_year_counts.values()) if cc_year_counts else 0
        if max_count < min_regions:
            continue
        good_years = [yr for yr, n in cc_year_counts.items()
                      if n >= max_count * 0.8]

        ref_year = max(y for y in good_years if y <= 2023) if any(y <= 2023 for y in good_years) else good_years[-1]
        ref_regions = all_years_data[ref_year].get(cc, [])
        ref_regions.sort(key=lambda r: r['employment'], reverse=True)
        ref_total = sum(r['employment'] for r in ref_regions)
        if ref_total == 0:
            continue
        top_code = ref_regions[0]['region_code']
        top_name = ref_regions[0]['region_name']

        for yr in good_years:
            yr_regions = all_years_data[yr].get(cc, [])
            if not yr_regions:
                continue
            total = sum(r['employment'] for r in yr_regions)
            emp = next((r['employment'] for r in yr_regions
                        if r['region_code'] == top_code), None)
            if emp is not None and total > 0:
                rows.append({
                    'country': cc, 'region_code': top_code, 'region_name': top_name,
                    'year': yr, 'employment_k': emp, 'share_pct': emp / total * 100,
                })

    return pd.DataFrame(rows)


def plot_top_regions(df: pd.DataFrame):
    """Small-multiples line chart of capital share trajectories + summary bar chart."""
    out_dir = Path(tempfile.gettempdir()) / "concentration"
    out_dir.mkdir(exist_ok=True)
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')

    countries = sorted(df['country'].unique())
    n = len(countries)
    cols = 5
    plot_rows = (n + cols - 1) // cols
    fig, axes = plt.subplots(plot_rows, cols, figsize=(20, 3.5 * plot_rows), dpi=200)
    axes = axes.flatten()

    for i, cc in enumerate(countries):
        ax = axes[i]
        cdf = df[df['country'] == cc].sort_values('year')
        name = cdf.iloc[0]['region_name']
        if len(name) > 22:
            name = name[:20] + '..'

        ax.plot(cdf['year'], cdf['share_pct'], linewidth=2, color='#1f77b4')
        ax.fill_between(cdf['year'], cdf['share_pct'], alpha=0.15, color='#1f77b4')
        ax.set_title(f"{cc}: {name}", fontsize=10, fontweight='bold')
        ax.tick_params(labelsize=8)

        first, last = cdf.iloc[0], cdf.iloc[-1]
        delta = last['share_pct'] - first['share_pct']
        sign = '+' if delta >= 0 else ''
        color = '#c62828' if delta > 1 else ('#2e7d32' if delta < -1 else '#555555')
        ax.annotate(f"{last['share_pct']:.1f}%\n({sign}{delta:.1f}pp)",
                    xy=(1, 1), xycoords='axes fraction', ha='right', va='top',
                    fontsize=8, fontweight='bold', color=color,
                    bbox=dict(boxstyle='round,pad=0.2', fc='white', ec=color, alpha=0.8))

        y_min = cdf['share_pct'].min()
        y_max = cdf['share_pct'].max()
        margin = max((y_max - y_min) * 0.2, 0.3)
        ax.set_ylim(y_min - margin, y_max + margin)

    for j in range(i + 1, len(axes)):
        axes[j].set_visible(False)

    fig.suptitle('Top Region Employment Share Trajectories — EU Countries',
                 fontsize=15, fontweight='bold', y=1.01)
    fig.tight_layout()
    path1 = out_dir / "EU_top_region_trajectories.png"
    plt.savefig(path1, dpi=200, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Trajectories plot saved to: {path1}")

    # Summary bar chart: total change (latest - earliest) sorted
    summary = []
    for cc in countries:
        cdf = df[df['country'] == cc].sort_values('year')
        first, last = cdf.iloc[0], cdf.iloc[-1]
        summary.append({
            'country': cc,
            'region_name': cdf.iloc[0]['region_name'],
            'first_share': first['share_pct'],
            'last_share': last['share_pct'],
            'delta': last['share_pct'] - first['share_pct'],
            'first_year': int(first['year']),
            'last_year': int(last['year']),
        })
    sdf = pd.DataFrame(summary).sort_values('delta', ascending=True)

    fig, ax = plt.subplots(figsize=(12, 8), dpi=300)
    colors = ['#c62828' if d > 0 else '#2e7d32' for d in sdf['delta']]
    bars = ax.barh(range(len(sdf)), sdf['delta'], color=colors, edgecolor='white', linewidth=0.5)
    ax.set_yticks(range(len(sdf)))
    labels = [f"{r['country']} — {r['region_name'][:25]}" for _, r in sdf.iterrows()]
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel('Change in national employment share (pp)', fontsize=11, labelpad=10)
    yr_range = f"{sdf.iloc[0]['first_year']}–{sdf.iloc[0]['last_year']}"
    ax.set_title(f'Change in Top Region Employment Share ({yr_range})',
                 fontsize=14, fontweight='bold', pad=15)
    ax.axvline(0, color='black', linewidth=0.8)

    for i, (_, row) in enumerate(sdf.iterrows()):
        sign = '+' if row['delta'] >= 0 else ''
        offset = 0.2 if row['delta'] >= 0 else -0.2
        ha = 'left' if row['delta'] >= 0 else 'right'
        ax.text(row['delta'] + offset, i, f"{sign}{row['delta']:.1f}pp",
                va='center', ha=ha, fontsize=8, fontweight='bold')

    ax.grid(True, axis='x', linestyle='--', alpha=0.6)
    fig.tight_layout()
    path2 = out_dir / "EU_top_region_delta.png"
    plt.savefig(path2, dpi=300)
    plt.close(fig)
    print(f"[+] Delta plot saved to: {path2}")

    csv_path = out_dir / "EU_top_region_timeseries.csv"
    df.to_csv(csv_path, index=False)
    print(f"[+] CSV exported to: {csv_path}")


def plot_region_timeseries(raw_df: pd.DataFrame, nuts3: str, output_file: str):
    """Dual-axis time series: nominal employment and share of national total."""
    cc = nuts3[:2]
    region_df = raw_df[raw_df['region_code'] == nuts3].sort_values('year')
    if region_df.empty:
        print(f"[-] No data for region {nuts3}", file=sys.stderr)
        return

    region_name = region_df.iloc[0]['region_name']
    totals = raw_df.groupby('year')['employment'].sum()
    region_df = region_df.copy()
    region_df['share'] = region_df.apply(
        lambda r: r['employment'] / totals[r['year']] * 100
        if r['year'] in totals.index and totals[r['year']] > 0 else 0, axis=1)

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax1 = plt.subplots(figsize=(12, 6), dpi=300)

    color1 = '#1f77b4'
    ax1.plot(region_df['year'], region_df['employment'], marker='o', linewidth=2,
             color=color1, label='Employment (thousands)')
    ax1.set_xlabel('Year', fontsize=11, labelpad=10)
    ax1.set_ylabel('Employment (thousand persons)', fontsize=11, labelpad=10, color=color1)
    ax1.tick_params(axis='y', labelcolor=color1)

    color2 = '#d95f02'
    ax2 = ax1.twinx()
    ax2.plot(region_df['year'], region_df['share'], marker='s', linewidth=2,
             color=color2, linestyle='--', label=f'Share of {cc} total (%)')
    ax2.set_ylabel(f'Share of {cc} total employment (%)', fontsize=11, labelpad=10, color=color2)
    ax2.tick_params(axis='y', labelcolor=color2)

    ax1.set_title(f'Employment — {region_name} ({nuts3})',
                  fontsize=14, fontweight='bold', pad=15)

    lines1, labels1 = ax1.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax1.legend(lines1 + lines2, labels1 + labels2, fontsize=10, loc='upper left')

    latest = region_df.iloc[-1]
    ax1.annotate(f"{latest['employment']:.1f}k",
                 (latest['year'], latest['employment']),
                 textcoords="offset points", xytext=(-10, 10), ha='center',
                 fontsize=9, fontweight='bold', color=color1)
    ax2.annotate(f"{latest['share']:.2f}%",
                 (latest['year'], latest['share']),
                 textcoords="offset points", xytext=(10, -15), ha='center',
                 fontsize=9, fontweight='bold', color=color2)

    ax1.grid(True, linestyle='--', alpha=0.6)
    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] Region plot saved to: {output_file}")

    print(f"\n{'Year':>6}  {'Employment (k)':>15}  {'Share (%)':>10}")
    print("-" * 35)
    for _, r in region_df.iterrows():
        print(f"{int(r['year']):>6}  {r['employment']:>15.1f}  {r['share']:>9.2f}%")


def default_output_path(country_code: str, mode: str, val, suffix: str = "") -> str:
    cc = country_code.upper()
    out_dir = Path(tempfile.gettempdir()) / "concentration"
    out_dir.mkdir(exist_ok=True)
    if mode == 'cr':
        name = f"{cc}_cr{int(val)}{suffix}.png"
    elif mode == 'region':
        name = f"{cc}_region_{val}{suffix}.png"
    else:
        name = f"{cc}_target{int(val)}pct{suffix}.png"
    return str(out_dir / name)


def plot_results(df: pd.DataFrame, country_code: str, mode: str, target_val: float, output_file: str):
    """Generates time-series visualization."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    cc = country_code.upper()

    if mode == 'cr':
        n = int(target_val)
        ax.plot(df['year'], df['metric_val'], marker='o', linewidth=2.5, color='#1f77b4', label=f'CR_{n} Share (%)')

        latest = df.iloc[-1]
        total_m = int(latest['total_regions'])
        area_pct = latest['area_pct']
        title = f'Top-{n} Regional Employment Concentration Ratio ($CR_{{{n}}}$) — {cc}'
        subtitle = f'{n}/{total_m} regions, representing {area_pct:.1f}% of the country area'
        ax.set_title(title, fontsize=14, fontweight='bold', pad=25)
        fig.text(0.5, 0.92, subtitle, ha='center', fontsize=11, style='italic')
        ax.set_ylabel('Share of Total National Employment (%)', fontsize=11, labelpad=10)

        ax.annotate(
            f"{latest['metric_val']:.1f}%",
            (latest['year'], latest['metric_val']),
            textcoords="offset points", xytext=(-15, 10), ha='center',
            fontsize=10, fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="#e1f5fe", ec="#0288d1", lw=1)
        )
    else:
        pct = target_val
        ax.plot(df['year'], df['metric_val'], marker='s', linewidth=2.5, color='#d95f02', label=f'Regions needed for {pct}% Share')
        ax.set_title(f'Number of Regions ($n$) Required to Reach {pct}% National Employment — {cc}', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Number of Top NUTS-3 Regions ($n$)', fontsize=11, labelpad=10)

        ax.yaxis.get_major_locator().set_params(integer=True)

        latest = df.iloc[-1]
        ax.annotate(
            f"n = {int(latest['metric_val'])} regions\n({latest['actual_pct']:.1f}%)",
            (latest['year'], latest['metric_val']),
            textcoords="offset points", xytext=(-20, 15), ha='center',
            fontsize=9, fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="#fff3e0", ec="#e65100", lw=1)
        )

    ax.set_xlabel('Year', fontsize=11, labelpad=10)
    ax.grid(True, linestyle='--', alpha=0.6)
    plt.tight_layout()

    plt.savefig(output_file, dpi=300)
    print(f"[+] Plot saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Measure NUTS-3 regional employment concentration over time."
    )
    subparsers = parser.add_subparsers(dest="mode", required=True)

    cr_parser = subparsers.add_parser("cr", help="Concentration ratio of top n regions")
    cr_parser.add_argument("country", type=str, help="2-letter EU country code")
    cr_parser.add_argument("n", type=int, help="Number of top regions")
    cr_parser.add_argument("-o", "--output", type=str, default=None)

    target_parser = subparsers.add_parser("target", help="Minimum regions to reach a percentage")
    target_parser.add_argument("country", type=str, help="2-letter EU country code")
    target_parser.add_argument("pct", type=float, help="Target employment share (e.g. 40 for 40%%)")
    target_parser.add_argument("-o", "--output", type=str, default=None)

    eu_parser = subparsers.add_parser("eu", help="Compare all EU-27 countries")
    eu_parser.add_argument("pct", type=float, help="Target employment share (e.g. 50 for 50%%)")
    eu_parser.add_argument("--year", type=int, default=2022,
                           help="Reference year (default: 2022)")
    eu_parser.add_argument("--min-regions", type=int, default=5,
                           help="Exclude countries with fewer NUTS-3 regions (default: 5)")
    eu_parser.add_argument("--compare-year", type=int, default=None,
                           help="Show trend from this year (e.g. 2012 for a 10-year diff)")

    region_parser = subparsers.add_parser("region", help="Time series for a single NUTS-3 region")
    region_parser.add_argument("nuts3", type=str, help="NUTS-3 code (e.g. PT1A0, ES300, DE600)")
    region_parser.add_argument("-o", "--output", type=str, default=None)

    cap_parser = subparsers.add_parser("top",
                                       help="Top-region share trajectories for all EU-27")
    cap_parser.add_argument("--min-regions", type=int, default=5,
                            help="Exclude countries with fewer NUTS-3 regions (default: 5)")

    list_parser = subparsers.add_parser("list-regions",
                                        help="List all NUTS-3 regions for a country")
    list_parser.add_argument("country", type=str, help="2-letter EU country code")

    args = parser.parse_args()

    if args.mode == 'list-regions':
        raw_df = fetch_eurostat_data(args.country)
        if raw_df.empty:
            print("[-] No data", file=sys.stderr)
            sys.exit(1)
        latest_year = int(raw_df['year'].max())
        regions = (raw_df[raw_df['year'] == latest_year]
                   .sort_values('region_code')[['region_code', 'region_name']]
                   .drop_duplicates())
        print(f"\nNUTS-3 regions for {args.country.upper()} ({len(regions)} regions):\n")
        for _, r in regions.iterrows():
            print(f"  {r['region_code']}  {r['region_name']}")
        return

    if args.mode == 'top':
        df = top_region_analysis(min_regions=args.min_regions)
        if df.empty:
            print("[-] No data", file=sys.stderr)
            sys.exit(1)

        countries = sorted(df['country'].unique())
        print(f"\n{'CC':>3}  {'Region':<35}  {'Start':>6}  {'Peak':>6}  {'PkYr':>5}"
              f"  {'Latest':>6}  {'5yr Δ':>7}  {'Shape'}")
        print("-" * 105)
        for cc in countries:
            cdf = df[df['country'] == cc].sort_values('year')
            name = cdf.iloc[0]['region_name'][:35]
            first = cdf.iloc[0]['share_pct']
            last = cdf.iloc[-1]['share_pct']
            peak_row = cdf.loc[cdf['share_pct'].idxmax()]
            peak = peak_row['share_pct']
            peak_yr = int(peak_row['year'])
            recent = cdf[cdf['year'] >= 2018]
            delta5 = (recent.iloc[-1]['share_pct'] - recent.iloc[0]['share_pct']
                      if len(recent) >= 2 else 0)
            if peak_yr <= 2015 and (peak - last) > 0.5:
                shape = "PLATEAU/DECLINE"
            elif abs(delta5) < 0.3 and abs(last - first) < 1.0:
                shape = "FLAT"
            elif delta5 > 0.3:
                shape = "STILL RISING"
            elif delta5 < -0.3:
                shape = "DECLINING"
            else:
                shape = "LEVELLING?"
            print(f"{cc:>3}  {name:<35}  {first:>5.1f}%  {peak:>5.1f}%  {peak_yr:>5}"
                  f"  {last:>5.1f}%  {delta5:>+6.2f}pp  {shape}")

        plot_top_regions(df)
        return

    if args.mode == 'eu':
        df = eu_comparison(args.pct, args.year, min_regions=args.min_regions,
                           compare_year=args.compare_year)
        if df.empty:
            print("[-] No data for any EU country", file=sys.stderr)
            sys.exit(1)
        has_cmp = args.compare_year and 'area_pct_cmp' in df.columns
        header = f"\n{'Country':>8}  {'n/M':>8}  {'% regions':>10}  {'% area':>8}"
        if has_cmp:
            header += f"  {'Δ regions':>10}  {'Δ area':>8}"
        print(header)
        print("-" * (40 + (22 if has_cmp else 0)))
        for _, row in df.sort_values('area_pct', ascending=False).iterrows():
            line = (f"{row['country']:>8}  "
                    f"{int(row['n_required']):>3}/{int(row['total_regions']):<4}  "
                    f"{row['region_fraction']:>9.1f}%  "
                    f"{row['area_pct']:>7.1f}%")
            if has_cmp and pd.notna(row.get('area_pct_cmp')):
                dr = row['region_fraction'] - row['region_fraction_cmp']
                da = row['area_pct'] - row['area_pct_cmp']
                line += f"  {dr:>+9.1f}pp  {da:>+7.1f}pp"
            print(line)
        plot_eu_comparison(df, args.pct, args.year, compare_year=args.compare_year)
        return

    if args.mode == 'region':
        cc = args.nuts3[:2].upper()
        raw_df = fetch_eurostat_data(cc)
        if raw_df.empty:
            print(f"[-] No data for country {cc}", file=sys.stderr)
            sys.exit(1)
        output_file = args.output or default_output_path(
            cc, 'region', args.nuts3)
        plot_region_timeseries(raw_df, args.nuts3, output_file)
        return

    raw_df = fetch_eurostat_data(args.country)
    if raw_df.empty:
        print("[-] Error: No data retrieved.", file=sys.stderr)
        sys.exit(1)

    area = fetch_area_data(args.country)

    if args.mode == 'cr':
        results_df = calculate_cr_n(raw_df, args.n, area=area)
        print_regions_for_cr(results_df, args.n)
        target_val = float(args.n)
    else:
        results_df = calculate_n_for_percentage(raw_df, args.pct)
        print_regions_for_percentage(results_df, args.pct)
        target_val = args.pct

        latest = results_df.iloc[-1]
        n_regions = int(latest['metric_val'])
        year = int(latest['year'])
        total_regions = raw_df[raw_df['year'] == year]['region_code'].nunique()
        cc = args.country.upper()
        population = fetch_population(cc, year)
        pct_regions = n_regions / total_regions * 100
        summary = (f"{n_regions}/{total_regions} NUTS-3 regions required to reach {args.pct}%"
                   f" concentration for {cc} in {year}."
                   f" {pct_regions:.1f}% of the country's NUTS-3 regions.")
        if population:
            regions_per_million = n_regions / (population / 1_000_000)
            summary += f" {regions_per_million:.2f} regions per million residents."
        print(summary)

    output_file = args.output or default_output_path(args.country, args.mode, target_val)
    plot_results(results_df, args.country, args.mode, target_val, output_file)

    if args.mode == 'target':
        dist_file = default_output_path(args.country, args.mode, target_val, suffix="_dist")
        plot_distribution(raw_df, args.country, args.pct, n_regions, dist_file, area=area)


if __name__ == "__main__":
    main()
