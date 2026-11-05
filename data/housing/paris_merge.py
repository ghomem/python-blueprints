"""Shared constants and helpers for the Paris petite couronne merge."""

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


def merge_paris_raw_df(df: pd.DataFrame) -> pd.DataFrame:
    """Merge Paris NUTS-3 codes into a single row per year in a raw employment DataFrame.

    Expects columns: region_code, region_name, year, employment.
    """
    paris_mask = df['region_code'].isin(PARIS_MERGE_CODES)
    if paris_mask.sum() == 0:
        return df
    rest = df[~paris_mask].copy()
    paris = df[paris_mask].groupby('year', as_index=False).agg(
        employment=('employment', 'sum')
    )
    paris['region_code'] = PARIS_MERGED_CODE
    paris['region_name'] = PARIS_MERGED_NAME
    return pd.concat([rest, paris], ignore_index=True)


def merge_paris_in_year_data(year_regions: list[dict]) -> list[dict]:
    """Merge FR101+FR105+FR106+FR107 into a single FR1PC entry in a year's region list.

    Each dict must have keys: region_code, region_name, employment.
    """
    paris = [r for r in year_regions if r['region_code'] in PARIS_MERGE_CODES]
    if len(paris) == 0:
        return year_regions
    rest = [r for r in year_regions if r['region_code'] not in PARIS_MERGE_CODES]
    rest.append({
        'region_code': PARIS_MERGED_CODE,
        'region_name': PARIS_MERGED_NAME,
        'employment': sum(r['employment'] for r in paris),
    })
    return rest


def merge_paris_share_data(df: pd.DataFrame) -> pd.DataFrame:
    """Merge Paris + petite couronne into a single row, recomputing shares.

    Expects columns: nuts3, country, emp_start, emp_end, share_start, share_end,
    share_delta_pp, emp_change_pct.
    """
    paris_mask = df['nuts3'].isin(PARIS_MERGE_CODES)
    if paris_mask.sum() == 0:
        return df
    paris = df[paris_mask]
    rest = df[~paris_mask].copy()

    emp_start = paris['emp_start'].sum()
    emp_end = paris['emp_end'].sum()

    fr_total_start = df[df['country'] == 'FR']['emp_start'].sum()
    fr_total_end = df[df['country'] == 'FR']['emp_end'].sum()
    share_start = emp_start / fr_total_start * 100 if fr_total_start else 0
    share_end = emp_end / fr_total_end * 100 if fr_total_end else 0

    merged_row = pd.DataFrame([{
        'country': 'FR',
        'nuts3': PARIS_MERGED_CODE,
        'region_name': PARIS_MERGED_NAME,
        'share_start': share_start,
        'share_end': share_end,
        'share_delta_pp': share_end - share_start,
        'emp_start': emp_start,
        'emp_end': emp_end,
        'emp_change_pct': ((emp_end - emp_start) / emp_start * 100
                           if emp_start > 0 else None),
    }])
    return pd.concat([rest, merged_row], ignore_index=True)


def merge_paris_regions(df: pd.DataFrame) -> pd.DataFrame:
    """Merge FR101, FR105, FR106, FR107 into a single 'Paris + Petite Couronne'.

    Uses employment-weighted averages for effort, price, and wage.
    Density is recomputed as total_employment / total_area.
    Expects columns: nuts3, name, employment_ths, area_km2, price_eur_m2,
    avg_annual_wage, effort_months_per_m2.
    """
    paris = df[df['nuts3'].isin(PARIS_MERGE_CODES)]
    if paris.empty:
        return df
    rest = df[~df['nuts3'].isin(PARIS_MERGE_CODES)].copy()

    total_emp = paris['employment_ths'].sum()
    if total_emp == 0:
        return df

    total_area = paris['area_km2'].sum()
    w = paris['employment_ths']

    merged_row = {
        'nuts3': PARIS_MERGED_CODE,
        'name': PARIS_MERGED_NAME,
        'employment_ths': total_emp,
        'area_km2': total_area,
        'jobs_per_km2': (total_emp * 1000) / total_area,
        'price_eur_m2': (paris['price_eur_m2'] * w).sum() / total_emp,
        'avg_annual_wage': (paris['avg_annual_wage'] * w).sum() / total_emp,
        'effort_months_per_m2': (paris['effort_months_per_m2'] * w).sum() / total_emp,
        'wage_fallback': False,
    }
    merged_row['monthly_wage'] = merged_row['avg_annual_wage'] / 12

    if 'nuts2' in paris.columns:
        merged_row['nuts2'] = 'FR10'

    return pd.concat([rest, pd.DataFrame([merged_row])], ignore_index=True)
