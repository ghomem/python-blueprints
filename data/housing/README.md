# Housing & Employment - Regional Analysis Tools

Scripts for analysing NUTS-3 regional employment patterns and housing
affordability across PT, ES, FR, IT and NL (312 regions).

**Dependencies:** `sudo apt install python3-requests python3-pandas python3-matplotlib python3-openpyxl python3-geopandas`

---

## density_vs_price.py

Scatter plots of employment density vs housing purchase effort (months of
gross salary per m²) for NUTS-3 regions. Fetches data live from Eurostat
and national statistics offices, or reads from local CSV snapshots.

### Quick start

```bash
# First run - fetches everything and saves CSVs for offline use
python3 density_vs_price.py --save-data --countries PT,ES,FR,IT,NL 2023

# Subsequent runs - fast, no network
python3 density_vs_price.py --local-data --countries PT,ES,FR,IT,NL 2023

# Full run matching the published analysis
python3 density_vs_price.py \
  --local-data input \
  --metric effort \
  --countries PT,ES,FR,IT,NL \
  --highlight-outliers \
  --tourism \
  --fit-multivar \
  --extra-fit-evidence \
  --map 2023 \
  --map-density \
  --merge-paris
```

### Options

| Flag | Effect |
|---|---|
| `--metric effort\|price\|all` | Y-axis: purchase effort (default), raw €/m², or both |
| `--save-data [DIR]` | Save fetched data as CSVs (default: `input/`) |
| `--local-data [DIR]` | Read from local CSVs instead of fetching |
| `--highlight-outliers` | Red circle on statistical outliers; exclude from fit |
| `--exclude-outliers` | Remove outliers entirely |
| `--exclude-paris` | Drop Paris (FR101) - extreme density skews the scale |
| `--merge-paris` | Merge Paris + Petite Couronne into one employment-weighted point |
| `--countries CC` | Comma-separated codes for the combined plot (default: all) |
| `--linear-x` | Linear x-axis on combined plot (default: log) |
| `--tourism` | Colour by tourism intensity; requires year 2023 |
| `--fit-multivar` | Per-country two-variable OLS fit; implies `--tourism` |
| `--extra-fit-evidence` | Summary table of single-variable R² (density-only, tourism-only) |
| `--map` | Choropleth map of purchase effort per NUTS-3 region |
| `--map-density` | Choropleth map of employment density (jobs/km², log scale) |
| `--join-maps` | Combined multi-country map (requires `--map` and/or `--map-density`) |
| `--brand-joined-map` | Add branding text to joined maps |
| `--map-values` | Show numeric values instead of region names on maps |
| `--no-map-labels` | Hide all labels from choropleth maps |
| `--map-gamma FLOAT` | Gamma for non-linear map colour scale |
| `--map-vcenter FLOAT` | Effort value that maps to white/midpoint |
| `--map-cmap COLOURS` | Override map colourmap (e.g. `"#2166ac,#ffffff,#b2182b"`) |
| `--bg-color HEX` | Background colour for all plots |
| `--bar-color HEX` | Override bar colour for bar charts |

### Output

Plots go to `/tmp/density_vs_price/`. Per-country scatter + combined plot +
summary CSV + data-sources CSV. With `--map`, one choropleth per country.
With `--fit-multivar`, a multivariate fit summary PNG + CSV.

### Two-variable fit (`--fit-multivar`)

Fits `effort = a·ln(job_density) + b·nights_per_worker + c` independently
per country via OLS. Regions using Eurostat NUTS-2 wage fallback are excluded
from the fit. Outputs `multivar_fit_{year}.csv` with actual vs predicted effort
and percentage error per region. Requires year 2023 (tourism data constraint).

### Data sources

| Country | Prices | Wages | Employment / Area |
|---|---|---|---|
| **PT** | INE 0012235 (median transaction €/m²) | MTSS Quadros de Pessoal (ganho × 14); Madeira from DREM | Eurostat |
| **ES** | Registradores de España (mean transaction €/m²) | AEAT tax returns (mean annual salary); foral provinces fall back to Eurostat NUTS-2 | Eurostat |
| **FR** | DVF open data (median transaction €/m²); Alsace-Moselle excluded | INSEE DADS/DSN (gross annual salary EQTP, 2022) | Eurostat |
| **IT** | Agenzia delle Entrate OMI (appraised market values €/m²) | INPS Osservatorio (mean gross annual pay) | Eurostat |
| **NL** | CBS StatLine (mean transaction €/m²) | CBS Regionale rekeningen (compensation / employees ÷ 1.27) | Eurostat |

Regions using the Eurostat NUTS-2 wage fallback (different definition - includes
employer contributions) are marked with a **black circle** on plots and excluded
from regression fits.

### Saved data

`--save-data` writes to `input/` (one CSV per country per dataset). Files:

```
{CC}_prices.csv          {CC}_wages.csv           ALL_tourism.csv
NUTS_RG_10M_2024_4326_LEVL_3.geojson
```

`--local-data` reads them back. Delete a file to force re-fetch of that dataset.

---

## others.py

Country-level housing burden charts from Eurostat EU-SILC and the OECD
Affordable Housing Database.

### Subcommands

```bash
# Housing cost burden (ilc_mded01) - share of housing costs in disposable income
python3 others.py expenditure --local-data input --year 2023

# Subjective housing burden (ilc_mded04) - heavy/some/none
python3 others.py burden --local-data input --year 2023

# OECD median mortgage burden (HC1.2) - 3-year average
python3 others.py oecd-burden --local-data input
```

### Options (all subcommands)

| Flag | Effect |
|---|---|
| `--countries CC` | Comma-separated codes (default: `ES,PT,FR,IT,NL`) |
| `--save-data [DIR]` | Download and save raw data (default: `input/`) |
| `--local-data [DIR]` | Use previously saved data |
| `--bg-color HEX` | Background colour for plots |

The `oecd-burden` subcommand additionally takes `--year-start` (default: 2022)
and `--year-end` (default: 2024) to control the averaging window.

### Output

Plots go to `/tmp/density_vs_price/`:
- `others_housing_cost_burden_{year}.png` + `.csv`
- `others_housing_burden_subjective_{year}.png` + `.csv`
- `others_oecd_mortgage_burden_{start}_{end}.png` + `.csv`

### Saved data

```
input/others_housing_cost_burden.csv        Eurostat ilc_mded01 (all years, all countries)
input/others_housing_burden_subjective.csv  Eurostat ilc_mded04 (all years, all countries)
input/others_oecd_hc12.xlsx                 OECD HC1.2 Excel workbook
input/others_oecd_mortgage_burden.csv       Extracted mortgage burden (all years, all countries)
```

---

## concentration.py

Measures how concentrated employment is in a country's top regions, using
Eurostat NUTS-3 data (nama_10r_3empers).

### Local data

All EU-wide subcommands fetch from Eurostat by default. To avoid re-fetching
on every run, download once and reuse:

```bash
# Download all Eurostat datasets to input/
python3 concentration.py fetch

# Any subcommand can then read from local CSVs
python3 concentration.py --local-data eu 50 --year 2023
python3 concentration.py --local-data top --merge-paris
python3 concentration.py --local-data share-map --countries PT,ES,FR,IT,NL --merge-paris
python3 concentration.py --local-data share-scatter --countries PT,ES,FR,IT,NL --target-pct 25
```

`fetch` saves to `input/` by default; `--local-data` reads from `input/` by
default. Pass a directory argument to either to use a different path. Files:

```
nama_10r_3empers.csv     NUTS-3 employment (all EU-27, all years)
reg_area3.csv            NUTS-3 land area (km²)
gdp_per_capita.csv       GDP per capita by country
gini.csv                 Gini coefficient by country
fertility.csv            Fertility rate by country
```

### Subcommands

**Single country:**

```bash
# Share of employment held by top 3 regions, over time
python3 concentration.py cr PT 3

# How many regions needed to reach 50% of employment, over time
python3 concentration.py target ES 50

# Time series for a single NUTS-3 region (employment + national share)
python3 concentration.py region PT11D

# List all NUTS-3 codes for a country
python3 concentration.py list-regions ES
```

**EU-wide:**

```bash
# Compare all EU-27: how many regions / how much area to reach 50% of employment
python3 concentration.py eu 50 --year 2023

# With a different reference year
python3 concentration.py eu 50 --year 2023 --compare-year 2007

# Capital/top-region share trajectories across all EU-27
python3 concentration.py top --year 2023 --merge-paris

# NUTS-3 employment share change maps
python3 concentration.py share-map --countries PT,ES,FR,IT,NL --year 2023 --compare-year 2000 --merge-paris

# Share vs share-change scatter
python3 concentration.py share-scatter --countries PT,ES,FR,IT,NL --target-pct 25 --year 2023 --compare-year 2000 --merge-paris
```

### Options

| Flag | Effect |
|---|---|
| `--bg-color HEX` | Background colour for all plots |
| `--bar-color HEX` | Bar colour for bar charts |
| `--bar-color-neg HEX` | Bar colour for negative values |
| `--local-data [DIR]` | Read from local CSVs |
| `--merge-paris` | Merge Paris + Petite Couronne (available on `target`, `top`, `share-map`, `share-scatter`) |
| `--map-values` | Show numeric values on choropleth maps (share-map) |

### Output

Plots go to `/tmp/concentration/`. The `eu` command produces two bar charts
(region fraction and area fraction); `top` produces small-multiples line charts
and a summary bar chart; `share-map` produces choropleth maps and employment
change maps; `share-scatter` produces a scatter plot of starting share vs change.

### Notes

- The `--compare-year` for `eu` defaults to 2000. Avoid using 2009-2012 as a
  baseline - the financial crisis hit peripheral regions harder than capitals,
  temporarily inflating concentration. Measuring from a crisis trough understates
  the real structural trend.
- Data goes back to ~2000 for most countries. 2024 is often incomplete.
- Countries with fewer than `--min-regions` NUTS-3 regions (default: 5) are
  excluded from EU comparisons.

---

## Supporting modules

- **paris_merge.py** - Merges Paris (FR101) with its Petite Couronne
  départements (FR105, FR106, FR107) into a single employment-weighted data
  point. Used by `density_vs_price.py --merge-paris` and
  `concentration.py --merge-paris`.

- **map_utils.py** - Shared choropleth map rendering utilities used by both
  `density_vs_price.py` and `concentration.py`.
