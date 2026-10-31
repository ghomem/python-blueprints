"""
Shared choropleth map utilities for NUTS-3 region maps.

Provides:
    - SymmetricGammaNorm: diverging colormap normalisation with gamma compression
    - fetch_nuts3_geometry(): download/cache NUTS-3 boundaries
    - plot_choropleth(): render a single-country NUTS-3 choropleth with colorbar
"""

import tempfile
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LinearSegmentedColormap, Normalize

MAINLAND_BBOX = {
    'PT': (-9.7, 36.9, -6.0, 42.2),
    'ES': (-9.5, 35.8, 3.4, 43.9),
    'FR': (-5.3, 41.2, 9.7, 51.2),
    'IT': (6.5, 36.5, 18.7, 47.2),
    'NL': (3.2, 50.6, 7.4, 53.7),
}

# Ultra-peripheral regions to exclude from joined maps (NUTS-3 prefixes)
_ULTRA_PERIPHERAL_PREFIXES = (
    'ES70',   # Canaries
    'ES630',  # Ceuta
    'ES640',  # Melilla
    'PT200',  # Azores
    'PT300',  # Madeira
)

_NUTS3_GEOJSON = "NUTS_RG_10M_2024_4326_LEVL_3.geojson"


class SymmetricGammaNorm(Normalize):
    """Apply gamma symmetrically around vcenter using a single scale.

    Equal data distances from vcenter produce equal color intensity
    on both sides, regardless of the asymmetry of vmin/vmax.
    """
    def __init__(self, gamma, vmin, vmax, vcenter=None, clip=True):
        self.gamma = gamma
        self.vcenter = vcenter if vcenter is not None else (vmin + vmax) / 2
        self.max_extent = max(abs(self.vcenter - vmin), abs(vmax - self.vcenter))
        super().__init__(vmin=vmin, vmax=vmax, clip=clip)

    def __call__(self, value, clip=None):
        val = np.ma.asarray(value, dtype=float)
        if clip is None:
            clip = self.clip
        if clip:
            val = np.ma.clip(val, self.vmin, self.vmax)
        d = (val - self.vcenter) / self.max_extent
        signed_gamma = np.sign(d) * np.abs(d) ** self.gamma
        x = 0.5 + 0.5 * signed_gamma
        return np.ma.array(x, mask=getattr(val, 'mask', None))


def fetch_nuts3_geometry(input_dir: Path | None = None,
                         save_mode: bool = False):
    """Download (and cache) NUTS-3 boundaries from Eurostat GISCO (NUTS 2024)."""
    import geopandas as gpd
    import requests

    local = input_dir / _NUTS3_GEOJSON if input_dir else None
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
    if save_mode and local:
        import shutil
        shutil.copy2(cache, local)
        print(f"  [saved] {local}")
    return gpd.read_file(cache)


def plot_choropleth(gdf, data_df, country: str, value_col: str,
                    merge_left: str, merge_right: str,
                    title: str, colorbar_label: str,
                    output_file: str,
                    vmin: float = None, vmax: float = None,
                    vcenter: float = None,
                    gamma: float = None,
                    norm=None,
                    cmap_spec: str = 'YlOrRd',
                    bg_color: str | None = None,
                    label_regions: bool = True,
                    label_fontsize_override: dict[str, int] | None = None,
                    text_color_fn=None,
                    figsize: tuple = (10, 10)):
    """Render a NUTS-3 choropleth map for one country.

    Parameters
    ----------
    gdf : GeoDataFrame
        Full NUTS-3 geometry (will be filtered to *country*).
    data_df : DataFrame
        Must contain *merge_right* and *value_col* columns.
    country : str
        Two-letter country code.
    value_col : str
        Column in *data_df* to colour by.
    merge_left, merge_right : str
        Join keys: gdf[merge_left] == data_df[merge_right].
    title : str
        Figure title.
    colorbar_label : str
        Label next to the colourbar.
    output_file : str
        Path for the saved PNG.
    vmin, vmax : float
        Colour range.
    vcenter : float or None
        Midpoint for SymmetricGammaNorm.
    gamma : float or None
        Gamma exponent; if given, SymmetricGammaNorm is used.
    cmap_spec : str
        Matplotlib cmap name, or comma-separated hex colours.
    bg_color : str or None
        Background colour.
    label_regions : bool
        Whether to draw region name labels at centroids.
    label_fontsize_override : dict
        Per-country font size overrides, e.g. {'FR': 5, 'ES': 5}.
    text_color_fn : callable or None
        f(value) -> colour string for region labels.  Default: '#333333'.
    figsize : tuple
        Figure size in inches.
    """
    import geopandas as gpd

    cc = country.upper()
    geo = gdf[gdf['CNTR_CODE'] == cc].copy()
    merged = geo.merge(data_df[[merge_right, value_col]],
                       left_on=merge_left, right_on=merge_right, how='left')

    bbox = MAINLAND_BBOX.get(cc)
    if bbox:
        merged = merged.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]

    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    if bbox:
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])

    if norm is None:
        if gamma is not None:
            norm = SymmetricGammaNorm(gamma=gamma, vmin=vmin, vmax=vmax,
                                      vcenter=vcenter)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax, clip=True)

    no_data = merged[merged[value_col].isna()]
    if not no_data.empty:
        no_data.plot(ax=ax, color='#e0e0e0', edgecolor='white', linewidth=0.5)

    if ',' in str(cmap_spec):
        hex_colors = [c.strip() for c in cmap_spec.split(',')]
        cmap = LinearSegmentedColormap.from_list('custom', hex_colors, N=256)
    else:
        cmap = cmap_spec

    has_data = merged[merged[value_col].notna()]
    if not has_data.empty:
        has_data.plot(ax=ax, column=value_col, cmap=cmap, norm=norm,
                      edgecolor='white', linewidth=0.5, legend=False)

    # Colorbar
    cax = fig.add_axes([0.92, 0.25, 0.015, 0.5])
    if isinstance(norm, SymmetricGammaNorm):
        cmap_obj = plt.cm.get_cmap(cmap) if isinstance(cmap, str) else cmap
        pos_lo = float(norm(norm.vmin))
        pos_hi = float(norm(norm.vmax))
        gradient = np.linspace(pos_lo, pos_hi, 256).reshape(-1, 1)
        cax.imshow(gradient, aspect='auto', cmap=cmap_obj, origin='lower',
                   extent=[0, 1, pos_lo, pos_hi], vmin=0, vmax=1)
        cax.set_xlim(0, 1)
        cax.set_ylim(pos_lo, pos_hi)
        cax.xaxis.set_visible(False)
        g_inv = 1.0 / norm.gamma
        me = norm.max_extent
        vc = norm.vcenter
        n_ticks = 9
        positions = np.linspace(pos_lo, pos_hi, n_ticks)
        tick_vals = []
        for p in positions:
            s = 2 * p - 1
            d = np.sign(s) * np.abs(s) ** g_inv * me
            tick_vals.append(vc + d)
        fmt = lambda v: f'{v:.0f}' if abs(v) >= 10 else f'{v:.2f}'
        labels = [fmt(v) for v in tick_vals]
        asymmetric = pos_lo > 0.01 or pos_hi < 0.99
        if asymmetric:
            labels[0] = '≤' + labels[0]
            labels[-1] = '≥' + labels[-1]
        cax.set_yticks(positions)
        cax.set_yticklabels(labels)
        cax.yaxis.set_ticks_position('right')
        cax.yaxis.set_label_position('right')
        cax.set_ylabel(colorbar_label, fontsize=10)
    else:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(colorbar_label, fontsize=10)

    # Region name labels at centroids
    if label_regions:
        fontsize_map = label_fontsize_override or {}
        default_fs = fontsize_map.get(cc, 6)
        for _, row in merged.iterrows():
            if row.geometry is None:
                continue
            c = row.geometry.centroid
            name = row.get('NAME_LATN', '')
            if not name:
                continue
            val = row.get(value_col, None)
            if text_color_fn and val is not None:
                txt_color = text_color_fn(val)
            else:
                txt_color = '#333333'
            ax.text(c.x, c.y, name, fontsize=default_fs, ha='center',
                    va='center', color=txt_color, fontweight='medium')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_axis_off()
    ax.set_aspect('equal')

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Map saved to: {output_file}")


def plot_joined_choropleth(gdf, data_dfs: list[tuple[str, 'pd.DataFrame']],
                           value_col: str,
                           merge_left: str, merge_right: str,
                           title: str, colorbar_label: str,
                           output_file: str,
                           vmin: float = None, vmax: float = None,
                           vcenter: float = None,
                           gamma: float = None,
                           norm=None,
                           cmap_spec: str = 'YlOrRd',
                           bg_color: str | None = None,
                           label_regions: bool = True,
                           label_fontsize: int = 4,
                           text_color_fn=None,
                           figsize: tuple = (14, 12)):
    """Render a NUTS-3 choropleth map for multiple countries on one figure.

    Parameters
    ----------
    gdf : GeoDataFrame
        Full NUTS-3 geometry (will be filtered to the given countries).
    data_dfs : list of (country_code, DataFrame)
        Each DataFrame must contain *merge_right* and *value_col* columns.
    value_col : str
        Column in data DataFrames to colour by.
    merge_left, merge_right : str
        Join keys: gdf[merge_left] == data_df[merge_right].
    title : str
        Figure title.
    colorbar_label : str
        Label next to the colourbar.
    output_file : str
        Path for the saved PNG.
    vmin, vmax : float
        Colour range.
    vcenter : float or None
        Midpoint for SymmetricGammaNorm.
    gamma : float or None
        Gamma exponent; if given, SymmetricGammaNorm is used.
    cmap_spec : str
        Matplotlib cmap name, or comma-separated hex colours.
    bg_color : str or None
        Background colour.
    label_regions : bool
        Whether to draw region name labels at centroids.
    label_fontsize : int
        Font size for region labels (default 4 for multi-country view).
    text_color_fn : callable or None
        f(value) -> colour string for region labels.  Default: '#333333'.
    figsize : tuple
        Figure size in inches.
    """
    import geopandas as gpd
    import pandas as pd

    countries = [cc.upper() for cc, _ in data_dfs]

    # Compute the combined bounding box from per-country MAINLAND_BBOX entries
    bboxes = [MAINLAND_BBOX[cc] for cc in countries if cc in MAINLAND_BBOX]
    if bboxes:
        xmin = min(b[0] for b in bboxes)
        ymin = min(b[1] for b in bboxes)
        xmax = max(b[2] for b in bboxes)
        ymax = max(b[3] for b in bboxes)
        bbox = (xmin, ymin, xmax, ymax)
    else:
        bbox = None

    # Filter geometry to the requested countries and exclude ultra-peripheral
    geo = gdf[gdf['CNTR_CODE'].isin(countries)].copy()
    for prefix in _ULTRA_PERIPHERAL_PREFIXES:
        geo = geo[~geo['NUTS_ID'].str.startswith(prefix)]

    # Merge all country data into a single DataFrame
    all_data = pd.concat([df[[merge_right, value_col]] for _, df in data_dfs],
                         ignore_index=True)
    merged = geo.merge(all_data, left_on=merge_left, right_on=merge_right,
                       how='left')

    # Clip to the combined bounding box
    if bbox:
        merged = merged.cx[bbox[0]:bbox[2], bbox[1]:bbox[3]]

    fig, ax = plt.subplots(figsize=figsize, dpi=300)
    if bbox:
        ax.set_xlim(bbox[0], bbox[2])
        ax.set_ylim(bbox[1], bbox[3])

    if norm is None:
        if gamma is not None:
            norm = SymmetricGammaNorm(gamma=gamma, vmin=vmin, vmax=vmax,
                                      vcenter=vcenter)
        else:
            norm = Normalize(vmin=vmin, vmax=vmax, clip=True)

    no_data = merged[merged[value_col].isna()]
    if not no_data.empty:
        no_data.plot(ax=ax, color='#e0e0e0', edgecolor='white', linewidth=0.3)

    if ',' in str(cmap_spec):
        hex_colors = [c.strip() for c in cmap_spec.split(',')]
        cmap = LinearSegmentedColormap.from_list('custom', hex_colors, N=256)
    else:
        cmap = cmap_spec

    has_data = merged[merged[value_col].notna()]
    if not has_data.empty:
        has_data.plot(ax=ax, column=value_col, cmap=cmap, norm=norm,
                      edgecolor='white', linewidth=0.3, legend=False)

    # Colorbar
    cax = fig.add_axes([0.92, 0.25, 0.015, 0.5])
    if isinstance(norm, SymmetricGammaNorm):
        cmap_obj = plt.cm.get_cmap(cmap) if isinstance(cmap, str) else cmap
        pos_lo = float(norm(norm.vmin))
        pos_hi = float(norm(norm.vmax))
        gradient = np.linspace(pos_lo, pos_hi, 256).reshape(-1, 1)
        cax.imshow(gradient, aspect='auto', cmap=cmap_obj, origin='lower',
                   extent=[0, 1, pos_lo, pos_hi], vmin=0, vmax=1)
        cax.set_xlim(0, 1)
        cax.set_ylim(pos_lo, pos_hi)
        cax.xaxis.set_visible(False)
        g_inv = 1.0 / norm.gamma
        me = norm.max_extent
        vc = norm.vcenter
        n_ticks = 9
        positions = np.linspace(pos_lo, pos_hi, n_ticks)
        tick_vals = []
        for p in positions:
            s = 2 * p - 1
            d = np.sign(s) * np.abs(s) ** g_inv * me
            tick_vals.append(vc + d)
        fmt = lambda v: f'{v:.0f}' if abs(v) >= 10 else f'{v:.2f}'
        labels = [fmt(v) for v in tick_vals]
        asymmetric = pos_lo > 0.01 or pos_hi < 0.99
        if asymmetric:
            labels[0] = '≤' + labels[0]
            labels[-1] = '≥' + labels[-1]
        cax.set_yticks(positions)
        cax.set_yticklabels(labels)
        cax.yaxis.set_ticks_position('right')
        cax.yaxis.set_label_position('right')
        cax.set_ylabel(colorbar_label, fontsize=10)
    else:
        sm = plt.cm.ScalarMappable(cmap=cmap, norm=norm)
        sm.set_array([])
        cbar = fig.colorbar(sm, cax=cax)
        cbar.set_label(colorbar_label, fontsize=10)

    # Region name labels at centroids
    if label_regions:
        for _, row in merged.iterrows():
            if row.geometry is None:
                continue
            c = row.geometry.centroid
            name = row.get('NAME_LATN', '')
            if not name:
                continue
            val = row.get(value_col, None)
            if text_color_fn and val is not None:
                txt_color = text_color_fn(val)
            else:
                txt_color = '#333333'
            ax.text(c.x, c.y, name, fontsize=label_fontsize, ha='center',
                    va='center', color=txt_color, fontweight='medium')

    ax.set_title(title, fontsize=14, fontweight='bold')
    ax.set_axis_off()
    ax.set_aspect('equal')

    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"[+] Map saved to: {output_file}")
