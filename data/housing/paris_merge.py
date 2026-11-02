"""Shared constants and geometry helper for the Paris petite couronne merge."""

import pandas as pd

PARIS_MERGE_CODES = frozenset({'FR101', 'FR105', 'FR106', 'FR107'})
PARIS_MERGED_CODE = 'FR1PC'
PARIS_MERGED_NAME = 'Paris + Petite Couronne'


def merge_paris_geometry(gdf):
    """Merge FR101, FR105, FR106, FR107 geometries into a single FR1PC polygon."""
    import geopandas as gpd
    from shapely.ops import unary_union

    paris_rows = gdf[gdf['NUTS_ID'].isin(PARIS_MERGE_CODES)]
    if paris_rows.empty:
        return gdf

    merged_geom = unary_union(paris_rows.geometry)
    new_row = paris_rows.iloc[[0]].copy()
    new_row = new_row.assign(geometry=merged_geom)
    new_row['NUTS_ID'] = PARIS_MERGED_CODE
    new_row['NAME_LATN'] = PARIS_MERGED_NAME

    rest = gdf[~gdf['NUTS_ID'].isin(PARIS_MERGE_CODES)]
    return gpd.GeoDataFrame(pd.concat([rest, new_row], ignore_index=True),
                            crs=gdf.crs)
