#!/usr/bin/env python3
"""
Regional Employment Concentration Plotter
------------------------------------------
Queries Eurostat API for NUTS-3 regional employment data and plots
concentration metrics over time.

Subcommands:
    cr <n>          Concentration ratio: share held by top n regions.
    target <pct>    Minimum regions needed to reach pct% of employment.

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


def default_output_path(country_code: str, mode: str, val, suffix: str = "") -> str:
    cc = country_code.upper()
    out_dir = Path(tempfile.gettempdir()) / "concentration"
    out_dir.mkdir(exist_ok=True)
    if mode == 'cr':
        name = f"{cc}_cr{int(val)}{suffix}.png"
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
    parser.add_argument(
        "country",
        type=str,
        help="2-letter EU country code (e.g., PT, ES, FR, DE, IT)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Output image path (default: auto-named file in tempdir)"
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    cr_parser = subparsers.add_parser("cr", help="Concentration ratio of top n regions")
    cr_parser.add_argument("n", type=int, help="Number of top regions")

    target_parser = subparsers.add_parser("target", help="Minimum regions to reach a percentage")
    target_parser.add_argument("pct", type=float, help="Target employment share (e.g. 40 for 40%%)")

    args = parser.parse_args()

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
