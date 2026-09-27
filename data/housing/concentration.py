#!/usr/bin/env python3
"""
Dynamic CR_n / Target Concentration Ratio Plotter
-------------------------------------------------
Queries Eurostat API directly for NUTS-3 regional employment data.

Execution Modes:
1. Fixed-N Mode: Pass `country` and `n` -> Calculates CR_n (%) over time.
2. Percentage Target Mode: Pass `country` and `--percentage P` -> Finds minimal n(t)
   required to reach P% and prints the exact NUTS-3 regions with individual % shares.

Dependencies:
    pip install requests pandas matplotlib
"""

import argparse
import sys
import matplotlib.pyplot as plt
import pandas as pd
import requests


def fetch_eurostat_data(country_code: str) -> pd.DataFrame:
    """
    Fetches NUTS-3 employment data directly from Eurostat REST API.
    Dataset: nama_10r_3emp (Employment by NUTS 3 regions)
    """
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
    time_labels = list(dimensions['time']['category']['index'].keys())

    # Identify size of each dimension to calculate flat index offsets
    dim_ids = data['id']
    dim_sizes = data['size']

    # Filter NUTS-3 codes matching country prefix (5 chars, e.g., PT111, ES300)
    nuts3_codes = [
        code for code in geo_dimension.keys()
        if code.startswith(cc) and len(code) == 5
    ]

    if not nuts3_codes:
        print(f"[-] No NUTS-3 records found for '{cc}'. Use valid EU 2-letter codes (e.g., PT, ES, FR, DE, IT).", file=sys.stderr)
        sys.exit(1)

    # Multi-dimensional array indexing setup
    # Eurostat stores flat dictionary keys corresponding to row-major array indices
    geo_dim_idx = dim_ids.index('geo')
    time_dim_idx = dim_ids.index('time')

    # Calculate strides for index conversion
    strides = [1] * len(dim_sizes)
    for i in range(len(dim_sizes) - 2, -1, -1):
        strides[i] = strides[i + 1] * dim_sizes[i + 1]

    # Select default indices for remaining dimensions (e.g., unit, wstat, nace_r2)
    default_indices = {}
    for d_idx, d_name in enumerate(dim_ids):
        if d_name not in ['geo', 'time']:
            # Pick first available category index for other dimensions
            cats = dimensions[d_name]['category']['index']
            default_indices[d_idx] = min(cats.values())

    values = data['value']
    records = []

    for code in nuts3_codes:
        geo_pos = geo_dimension[code]
        region_name = geo_labels.get(code, code)

        for time_str, time_pos in time_dimension.items():
            # Build full coordinate array across all dimensions
            coords = {}
            coords[geo_dim_idx] = geo_pos
            coords[time_dim_idx] = time_pos
            coords.update(default_indices)

            # Calculate flat position
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

    # Drop years where fewer than half the regions reported (incomplete data)
    total_regions = df['region_code'].nunique()
    regions_per_year = df.groupby('year')['region_code'].nunique()
    complete_years = regions_per_year[regions_per_year >= total_regions * 0.5].index
    dropped = set(df['year'].unique()) - set(complete_years)
    if dropped:
        print(f"[!] Dropping years with incomplete data: {sorted(dropped)}")
    return df[df['year'].isin(complete_years)].reset_index(drop=True)


def calculate_cr_n_fixed(df: pd.DataFrame, n: int) -> pd.DataFrame:
    """Mode 1: Fixed N -> Calculates concentration percentage over time."""
    results = []
    years = sorted(df['year'].unique())

    for yr in years:
        df_yr = df[df['year'] == yr].sort_values(by='employment', ascending=False).reset_index(drop=True)
        if df_yr.empty:
            continue

        total_emp = df_yr['employment'].sum()
        if total_emp == 0:
            continue

        top_n = df_yr.head(n)
        top_n_emp = top_n['employment'].sum()
        cr_val = (top_n_emp / total_emp) * 100

        regions_formatted = [
            f"{row['region_name']} ({row['region_code']}) - {(row['employment'] / total_emp) * 100:.2f}%"
            for _, row in top_n.iterrows()
        ]

        results.append({
            'year': yr,
            'metric_val': cr_val,
            'total_emp': total_emp,
            'top_regions': regions_formatted
        })

    return pd.DataFrame(results)


def calculate_n_for_percentage(df: pd.DataFrame, target_pct: float) -> pd.DataFrame:
    """
    Mode 2: Target Percentage -> Finds minimum number of regions n(t) needed
    to reach or exceed target_pct% of national employment for each year.
    Stores exact NUTS-3 regions discovered along with individual % shares.
    """
    results = []
    years = sorted(df['year'].unique())

    for yr in years:
        df_yr = df[df['year'] == yr].sort_values(by='employment', ascending=False).reset_index(drop=True)
        if df_yr.empty:
            continue

        total_emp = df_yr['employment'].sum()
        if total_emp == 0:
            continue

        df_yr['indiv_pct'] = (df_yr['employment'] / total_emp) * 100
        df_yr['cum_pct'] = df_yr['indiv_pct'].cumsum()

        # Find minimum regions needed to cross target_pct
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

        # Format region string with name, code, and individual percentage
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


def print_regions_for_fixed_n(results_df: pd.DataFrame, n: int):
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


def plot_results(df: pd.DataFrame, country_code: str, mode: str, target_val: float, output_file: str = None):
    """Generates time-series visualization for both fixed-N and target-percentage modes."""
    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid' in plt.style.available else 'default')
    fig, ax = plt.subplots(figsize=(10, 6), dpi=300)

    cc = country_code.upper()

    if mode == 'fixed_n':
        n = int(target_val)
        y_vals = df['metric_val']
        ax.plot(df['year'], y_vals, marker='o', linewidth=2.5, color='#1f77b4', label=f'CR_{n} Share (%)')
        ax.set_title(f'Top-{n} Regional Employment Concentration Ratio ($CR_{{{n}}}$) — {cc}', fontsize=14, fontweight='bold', pad=15)
        ax.set_ylabel('Share of Total National Employment (%)', fontsize=11, labelpad=10)

        latest = df.iloc[-1]
        ax.annotate(
            f"{latest['metric_val']:.1f}%",
            (latest['year'], latest['metric_val']),
            textcoords="offset points", xytext=(-15, 10), ha='center',
            fontsize=10, fontweight='bold',
            bbox=dict(boxstyle="round,pad=0.3", fc="#e1f5fe", ec="#0288d1", lw=1)
        )
    else:
        pct = target_val
        y_vals = df['metric_val']
        ax.plot(df['year'], y_vals, marker='s', linewidth=2.5, color='#d95f02', label=f'Regions needed for {pct}% Share')
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

    if output_file:
        plt.savefig(output_file, dpi=300)
        print(f"[+] Plot saved to: '{output_file}'")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(
        description="Compute CR_n or find n(t) required to reach a target employment percentage across EU countries."
    )
    parser.add_argument(
        "country",
        type=str,
        help="2-letter ISO/EU country code (e.g., PT, ES, FR, DE, IT)"
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "n",
        type=int,
        nargs="?",
        default=None,
        help="Fixed number of top regions (n) to compute CR_n percentage."
    )
    group.add_argument(
        "-p", "--percentage",
        type=float,
        help="Target employment share percentage (e.g. 40 for 40%%). Finds minimal n(t) required."
    )

    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Optional image file path to save plot (e.g., pt_40pct.png)"
    )

    args = parser.parse_args()

    raw_df = fetch_eurostat_data(args.country)
    if raw_df.empty:
        print("[-] Error: No data retrieved.", file=sys.stderr)
        sys.exit(1)

    if args.percentage is not None:
        mode = 'pct'
        target_val = args.percentage
        results_df = calculate_n_for_percentage(raw_df, target_val)
        print_regions_for_percentage(results_df, target_val)
    else:
        mode = 'fixed_n'
        target_val = float(args.n)
        results_df = calculate_cr_n_fixed(raw_df, args.n)
        print_regions_for_fixed_n(results_df, args.n)

    plot_results(results_df, args.country, mode, target_val, args.output)


if __name__ == "__main__":
    main()
