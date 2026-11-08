#!/usr/bin/env python3
"""
Miscellaneous Housing Charts
-----------------------------
Contextual/framing charts that don't belong in the main analysis scripts.

Subcommands:
    expenditure     Housing cost burden by country (EU-SILC).
    burden          Subjective housing burden by country (EU-SILC).
    oecd-burden     Mortgage burden by country (OECD HC1.2).

"""

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import openpyxl
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


# ── Housing cost burden (ilc_mded01) ────────────────────────────────────────

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
    ax.set_title(f'Share of Housing Costs in Disposable Income ({year})',
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


# ── Subjective housing burden (ilc_mded04) ──────────────────────────────────

def fetch_burden(countries: list[str], year: int) -> pd.DataFrame:
    """Fetch subjective housing burden from EU-SILC (ilc_mded04)."""
    csv_name = "others_housing_burden_subjective.csv"
    cached = _load_csv(csv_name)
    if cached is not None:
        return cached[(cached['geo'].isin(countries)) & (cached['year'] == year)].reset_index(drop=True)

    geo_param = '+'.join(countries)
    url = (
        'https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1/data/'
        f'ilc_mded04/A.TOTAL.TOTAL..PC.{geo_param}'
        '?format=JSON&lang=en'
    )
    print(f"  Fetching Eurostat EU-SILC subjective housing burden...")
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    data = r.json()

    dims = data['dimension']
    size = data['size']

    def idx_map(dim):
        cats = dims[dim]['category']
        return {pos: code for code, pos in cats['index'].items()}

    bur_idx = idx_map('lev_bur')
    geo_idx = idx_map('geo')
    time_idx = idx_map('time')

    rows = []
    for flat_str, val in data['value'].items():
        flat = int(flat_str)
        indices = []
        for s in reversed(size):
            indices.append(flat % s)
            flat //= s
        indices.reverse()

        dim_names = list(dims.keys())
        bur_pos = dim_names.index('lev_bur')
        geo_pos = dim_names.index('geo')
        time_pos = dim_names.index('time')

        bur_code = bur_idx.get(indices[bur_pos])
        geo_code = geo_idx.get(indices[geo_pos])
        time_code = time_idx.get(indices[time_pos])

        if time_code and geo_code and bur_code:
            rows.append({
                'geo': geo_code,
                'year': int(time_code),
                'burden': bur_code,
                'pct': val,
            })

    df = pd.DataFrame(rows)
    _save_csv(df, csv_name)
    df = df[df['year'] == year].reset_index(drop=True)
    if df.empty:
        available = sorted(pd.DataFrame(rows)['year'].unique())
        print(f"  [!] No data for {year}. Available years: {available}")
    return df


def plot_burden(df: pd.DataFrame, countries: list[str], year: int,
                output_file: str):
    """Vertical bar chart: % of population reporting heavy housing burden."""
    heavy = df[df['burden'] == 'HVY'].copy()
    heavy = heavy.set_index('geo').reindex(countries).dropna(subset=['pct'])
    heavy = heavy.sort_values('pct')

    codes = heavy.index.tolist()
    pcts = heavy['pct'].tolist()
    bar_color = '#9b2335'

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid'
                  in plt.style.available else 'default')
    _apply_bg()
    fig, ax = plt.subplots(figsize=(max(4, 1.5 * len(codes)), 5), dpi=300)

    bars = ax.bar(codes, pcts, color=bar_color, edgecolor='white',
                  linewidth=0.8, width=0.6)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.5,
                f'{pct:.1f}%', ha='center', va='bottom', fontsize=11,
                fontweight='bold')

    ax.set_ylabel('% of population', fontsize=11, labelpad=10)
    ax.set_title(f'Financial Burden of the Total Housing Cost · Heavy ({year})',
                 fontsize=13, fontweight='bold', pad=12)
    ax.set_ylim(0, min(100, max(pcts) * 1.15))
    ax.tick_params(axis='x', labelsize=12)

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] Subjective burden chart saved to: {output_file}")


def cmd_burden(args):
    """Handle the 'burden' subcommand."""
    countries = [c.strip().upper() for c in args.countries.split(',')]
    year = args.year
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = fetch_burden(countries, year)
    if df.empty:
        print("[!] No data — cannot produce chart.", file=sys.stderr)
        sys.exit(1)

    png_path = str(out_dir / f"others_housing_burden_subjective_{year}.png")
    plot_burden(df, countries, year, png_path)

    csv_path = out_dir / f"others_housing_burden_subjective_{year}.csv"
    df.to_csv(csv_path, index=False, float_format='%.1f')
    print(f"[+] CSV saved to: {csv_path}")


# ── OECD mortgage burden (HC1.2) ──────────────────────────────────────────

OECD_HC12_URL = (
    'https://webfs.oecd.org/Els-com/Affordable_Housing_Database/'
    'HC1-2-Housing-costs-over-income.xlsx'
)
OECD_XLSX_NAME = 'others_oecd_hc12.xlsx'
OECD_CSV_NAME = 'others_oecd_mortgage_burden.csv'

OECD_COUNTRY_MAP = {
    'France': 'FR', 'Italy': 'IT', 'Netherlands': 'NL',
    'Portugal': 'PT', 'Spain': 'ES', 'Germany': 'DE',
    'Austria': 'AT', 'Belgium': 'BE', 'Finland': 'FI',
    'Greece': 'EL', 'Ireland': 'IE', 'Luxembourg': 'LU',
}


def _parse_oecd_xlsx(xlsx_path: Path) -> pd.DataFrame:
    """Extract mortgage burden time series from OECD HC1.2 XLSX."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb['HC12_A1']

    years: dict[int, int] = {}
    for row in ws.iter_rows(min_row=1, max_row=10, values_only=False):
        for cell in row:
            if isinstance(cell.value, (int, float)) and 2000 <= cell.value <= 2100:
                years[cell.column] = int(cell.value)
        if years:
            break

    rows = []
    for row in ws.iter_rows(min_row=2, max_row=ws.max_row, values_only=False):
        first = row[0].value
        if (first and isinstance(first, str)
                and first.strip() == 'Owner with mortgage'):
            country_cell = ws.cell(row=row[0].row - 1, column=1).value
            if not country_cell or country_cell.strip() not in OECD_COUNTRY_MAP:
                continue
            cc = OECD_COUNTRY_MAP[country_cell.strip()]
            for cell in row:
                if (cell.column in years
                        and cell.value is not None and cell.value != ''):
                    rows.append({
                        'geo': cc,
                        'year': years[cell.column],
                        'pct': float(cell.value) * 100,
                    })
    wb.close()
    return pd.DataFrame(rows)


def fetch_oecd_burden(countries: list[str]) -> pd.DataFrame:
    """Get OECD mortgage burden data, preferring local CSV."""
    cached = _load_csv(OECD_CSV_NAME)
    if cached is not None:
        return cached[cached['geo'].isin(countries)].reset_index(drop=True)

    xlsx_local = INPUT_DIR / OECD_XLSX_NAME if INPUT_DIR else None
    if xlsx_local and xlsx_local.exists():
        print(f"  [local] {xlsx_local}")
        df = _parse_oecd_xlsx(xlsx_local)
    else:
        print(f"  Downloading OECD HC1.2 XLSX...")
        r = requests.get(OECD_HC12_URL, timeout=120)
        r.raise_for_status()
        tmp = Path(tempfile.mktemp(suffix='.xlsx'))
        tmp.write_bytes(r.content)
        df = _parse_oecd_xlsx(tmp)
        if SAVE_MODE and INPUT_DIR:
            dest = INPUT_DIR / OECD_XLSX_NAME
            shutil.copy2(tmp, dest)
            print(f"  [saved] {dest}")
        tmp.unlink()

    _save_csv(df, OECD_CSV_NAME)
    return df[df['geo'].isin(countries)].reset_index(drop=True)


def plot_oecd_burden(df: pd.DataFrame, countries: list[str],
                     avg_years: list[int], output_file: str):
    """Bar chart: OECD mortgage burden, N-year average, sorted."""
    avg_df = (df[df['year'].isin(avg_years)]
              .groupby('geo')['pct'].mean()
              .reindex(countries).dropna()
              .sort_values())

    codes = avg_df.index.tolist()
    pcts = avg_df.values.tolist()
    bar_color = '#9b2335'

    yr_label = f'{min(avg_years)}–{max(avg_years)}'

    plt.style.use('seaborn-v0_8-whitegrid' if 'seaborn-v0_8-whitegrid'
                  in plt.style.available else 'default')
    _apply_bg()
    fig, ax = plt.subplots(figsize=(max(4, 1.5 * len(codes)), 6), dpi=300)

    bars = ax.bar(codes, pcts, color=bar_color, edgecolor='white',
                  linewidth=0.8, width=0.6)
    for bar, pct in zip(bars, pcts):
        ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.3,
                f'{pct:.1f}%', ha='center', va='bottom', fontsize=11,
                fontweight='bold')

    ax.set_ylabel('% of disposable income', fontsize=11, labelpad=10)
    fig.suptitle('Median Mortgage Burden', fontsize=13, fontweight='bold',
                 y=0.98)
    ax.set_title(f'OECD HC1.2 · {len(avg_years)}-year average ({yr_label})',
                 fontsize=10, pad=8)
    ax.set_ylim(0, min(100, max(pcts) * 1.35))
    ax.tick_params(axis='x', labelsize=12)

    source = ('OECD Affordable Housing Database, indicator HC 1.2\n'
              'Median of mortgage repayment (principal + interest) / disposable income')
    ax.text(0.98, 0.95, source,
            transform=ax.transAxes, fontsize=7, ha='right', va='top',
            bbox=dict(boxstyle='round,pad=0.3', fc=_BG_COLOR or '#f5f0e8',
                      ec='#999'))

    fig.tight_layout()
    plt.savefig(output_file, dpi=300)
    plt.close(fig)
    print(f"[+] OECD mortgage burden chart saved to: {output_file}")


def cmd_oecd_burden(args):
    """Handle the 'oecd-burden' subcommand."""
    countries = [c.strip().upper() for c in args.countries.split(',')]
    avg_years = list(range(args.year_start, args.year_end + 1))
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = fetch_oecd_burden(countries)
    if df.empty:
        print("[!] No data — cannot produce chart.", file=sys.stderr)
        sys.exit(1)

    yr_label = f'{min(avg_years)}_{max(avg_years)}'
    png_path = str(out_dir / f'others_oecd_mortgage_burden_{yr_label}.png')
    plot_oecd_burden(df, countries, avg_years, png_path)

    avg_df = (df[df['year'].isin(avg_years)]
              .groupby('geo')['pct'].mean()
              .reset_index()
              .rename(columns={'pct': 'avg_pct'}))
    avg_df['year_start'] = min(avg_years)
    avg_df['year_end'] = max(avg_years)
    csv_path = out_dir / f'others_oecd_mortgage_burden_{yr_label}.csv'
    avg_df.to_csv(csv_path, index=False, float_format='%.1f')
    print(f"[+] CSV saved to: {csv_path}")


# ── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Miscellaneous housing-related charts")
    parser.add_argument('--bg-color', type=str, default=None,
                        help='Background color for all plots (e.g. "#f5f0e8")')
    sub = parser.add_subparsers(dest='command')

    for name, help_text in [('expenditure', 'Housing cost burden (EU-SILC)'),
                            ('burden', 'Subjective housing burden (EU-SILC)')]:
        sp = sub.add_parser(name, help=help_text)
        sp.add_argument('--countries', type=str, default='ES,PT,FR,IT,NL',
                        help='Comma-separated country codes (default: ES,PT,FR,IT,NL)')
        sp.add_argument('--year', type=int, default=2023,
                        help='Reference year (default: 2023)')
        sp.add_argument('--output-dir', type=str, default='/tmp/density_vs_price',
                        help='Output directory')
        sp.add_argument('--save-data', metavar='DIR', nargs='?', const='input',
                        help='Download and save raw data to DIR (default: input/)')
        sp.add_argument('--local-data', metavar='DIR', nargs='?', const='input',
                        help='Use previously saved data from DIR')

    sp_oecd = sub.add_parser('oecd-burden',
                             help='Mortgage burden by country (OECD HC1.2)')
    sp_oecd.add_argument('--countries', type=str, default='ES,PT,FR,IT,NL',
                         help='Comma-separated country codes (default: ES,PT,FR,IT,NL)')
    sp_oecd.add_argument('--year-start', type=int, default=2022,
                         help='First year of averaging window (default: 2022)')
    sp_oecd.add_argument('--year-end', type=int, default=2024,
                         help='Last year of averaging window (default: 2024)')
    sp_oecd.add_argument('--output-dir', type=str, default='/tmp/density_vs_price',
                         help='Output directory')
    sp_oecd.add_argument('--save-data', metavar='DIR', nargs='?', const='input',
                         help='Download and save raw data to DIR (default: input/)')
    sp_oecd.add_argument('--local-data', metavar='DIR', nargs='?', const='input',
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
    elif args.command == 'burden':
        cmd_burden(args)
    elif args.command == 'oecd-burden':
        cmd_oecd_burden(args)


if __name__ == "__main__":
    main()
