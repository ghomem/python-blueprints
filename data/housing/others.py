#!/usr/bin/env python3
"""
Miscellaneous Housing Charts
-----------------------------
Contextual/framing charts that don't belong in the main analysis scripts.

Subcommands:
    expenditure     Housing cost burden by country (EU-SILC).

"""

import argparse
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests

INPUT_DIR: Path | None = None
SAVE_MODE: bool = False
_BG_COLOR: str | None = None


def _apply_bg():
    """Re-apply --bg-color after plt.style.use (which resets rcParams)."""
    if _BG_COLOR:
        plt.rcParams.update({
            'figure.facecolor': _BG_COLOR,
            'axes.facecolor': _BG_COLOR,
            'savefig.facecolor': _BG_COLOR,
            'legend.facecolor': _BG_COLOR,
            'legend.edgecolor': _BG_COLOR,
        })


def _save_csv(df: pd.DataFrame, name: str):
    if SAVE_MODE and INPUT_DIR and not df.empty:
        path = INPUT_DIR / name
        df.to_csv(path, index=False)
        print(f"  [saved] {path}")


def _load_csv(name: str) -> pd.DataFrame | None:
    if INPUT_DIR is None or SAVE_MODE:
        return None
    path = INPUT_DIR / name
    if path.exists():
        print(f"  [local] {path}")
        return pd.read_csv(path)
    return None


def fetch_expenditure(countries: list[str], year: int) -> pd.DataFrame:
    """Fetch housing cost burden from EU-SILC (ilc_mded01)."""
    csv_name = "others_housing_cost_burden.csv"
    cached = _load_csv(csv_name)
    if cached is not None:
        return cached[(cached['geo'].isin(countries)) & (cached['year'] == year)].reset_index(drop=True)

    geo_param = '+'.join(countries)
    url = (
        'https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/'
        f'ilc_mded01/A.TOTAL.TOTAL.PC.{geo_param}'
        '?format=JSON&lang=en'
    )
    print(f"  Fetching Eurostat EU-SILC housing cost burden...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()

    dims = data['dimension']
    size = data['size']

    def idx_map(dim):
        cats = dims[dim]['category']
        return {pos: code for code, pos in cats['index'].items()}

    geo_idx = idx_map('geo')
    time_idx = idx_map('time')

    rows = []
    for flat_str, val in data['value'].items():
        flat = int(flat_str)
        t = flat % size[5]; rest = flat // size[5]
        g = rest % size[4]
        time_code = time_idx.get(t)
        geo_code = geo_idx.get(g)
        if time_code and geo_code:
            rows.append({
                'geo': geo_code,
                'year': int(time_code),
                'pct': val,
            })

    df = pd.DataFrame(rows)
    _save_csv(df, csv_name)
    df = df[df['year'] == year].reset_index(drop=True)
    if df.empty:
        available = sorted(pd.DataFrame(rows)['year'].unique())
        print(f"  [!] No data for {year}. Available years: {available}")
    return df


def plot_expenditure(df: pd.DataFrame, countries: list[str], year: int,
                     output_file: str):
    """Vertical bar chart: housing cost burden per country, sorted."""
    housing = df.set_index('geo').reindex(countries).dropna(subset=['pct'])
    housing = housing.sort_values('pct')

    codes = housing.index.tolist()
    pcts = housing['pct'].tolist()
    bar_color = '#5B9BD5'

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid'
                  in plt.style.available else 'default')
    _apply_bg()
    fig, ax = plt.subplots(figsize=(max(4, 1.5 * len(codes)), 5), dpi=300)

    bars = ax.bar(codes, pcts, color=bar_color, edgecolor='white',
                  linewidth=0.8, width=0.6)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f'{pct:.1f}%', ha='center', va='bottom', fontsize=11,
                fontweight='bold')

    ax.set_ylabel('% of disposable income', fontsize=11, labelpad=10)
    ax.set_title(f'Housing Cost Burden ({year})',
                 fontsize=13, fontweight='bold', pad=12)
    ax.set_ylim(0, min(100, max(pcts) * 1.15))
    ax.tick_params(axis='x', labelsize=12)

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] Housing cost burden chart saved to: {output_file}")


def cmd_expenditure(args):
    """Handle the 'expenditure' subcommand."""
    countries = [c.strip().upper() for c in args.countries.split(',')]
    year = args.year
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = fetch_expenditure(countries, year)
    if df.empty:
        print("[!] No data — cannot produce chart.", file=sys.stderr)
        sys.exit(1)

    png_path = str(out_dir / f"others_housing_cost_burden_{year}.png")
    plot_expenditure(df, countries, year, png_path)

    csv_path = out_dir / f"others_housing_cost_burden_{year}.csv"
    df.to_csv(csv_path, index=False, float_format='%.1f')
    print(f"[+] CSV saved to: {csv_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Miscellaneous housing-related charts")
    parser.add_argument('--bg-color', type=str, default=None,
                        help='Background color for all plots (e.g. "#f5f0e8")')
    sub = parser.add_subparsers(dest='command')

    exp = sub.add_parser('expenditure', help='Housing cost burden (EU-SILC)')
    exp.add_argument('--countries', type=str, default='ES,PT,FR,IT,NL',
                     help='Comma-separated country codes (default: ES,PT,FR,IT,NL)')
    exp.add_argument('--year', type=int, default=2023,
                     help='Reference year (default: 2023)')
    exp.add_argument('--output-dir', type=str, default='/tmp/density_vs_price',
                     help='Output directory')
    exp.add_argument('--save-data', metavar='DIR', nargs='?', const='input',
                     help='Download and save raw data to DIR (default: input/)')
    exp.add_argument('--local-data', metavar='DIR', nargs='?', const='input',
                     help='Use previously saved data from DIR')

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.bg_color:
        global _BG_COLOR
        _BG_COLOR = args.bg_color
        _apply_bg()

    if hasattr(args, 'local_data') and args.local_data:
        global INPUT_DIR, SAVE_MODE
        INPUT_DIR = Path(args.local_data)
        if not INPUT_DIR.is_dir():
            parser.error(f"--local-data directory does not exist: {INPUT_DIR}")
        print(f"[*] Using local data from {INPUT_DIR}/")
    elif hasattr(args, 'save_data') and args.save_data:
        INPUT_DIR = Path(args.save_data)
        INPUT_DIR.mkdir(parents=True, exist_ok=True)
        SAVE_MODE = True
        print(f"[*] Will save data to {INPUT_DIR}/")

    if args.command == 'expenditure':
        cmd_expenditure(args)


if __name__ == "__main__":
    main()
