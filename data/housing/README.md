# Housing & Employment - Regional Analysis Tools

Two scripts for analysing NUTS-3 regional employment patterns across the EU,
with a focus on PT, ES, FR and NL.

**Dependencies:** `sudo apt install python3-requests python3-pandas python3-matplotlib python3-openpyxl python3-geopandas`

## density_vs_price.py

Scatter plots of employment density vs housing purchase effort and raw price
for NUTS-3 regions. Fetches data live from Eurostat, national statistics offices
and other sources, or reads from a data snapshot on local CSVs.

### Quick start

```bash
# First run - fetches everything and saves CSVs for offline use
python3 density_vs_price.py 2023 --save-data

# Subsequent runs - fast, no network
python3 density_vs_price.py 2023 --local-data

# PT + ES only, highlight outliers, both metrics
python3 density_vs_price.py 2023 --local-data --metric all --highlight-outliers --countries PT,ES

# Tourism intensity overlay (2023 only - NUTS code alignment constraint)
python3 density_vs_price.py 2023 --local-data --tourism

# Same as above plus per-country map
python3 density_vs_price.py 2023 --local-data --tourism --map
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
| `--countries CC` | Comma-separated codes for the combined plot (default: all) |
| `--linear-x` | Linear x-axis on combined plot (default: log) |
| `--tourism` | Colour by tourism intensity; 2023 only |
| `--fit-multivar` | Per-country two-variable OLS fit (see below); implies `--tourism` |
| `--map` | Choropleth map of purchase effort per NUTS-3 region (mainland only) |

### Output

Plots go to `/tmp/density_vs_price/`. Per-country scatter + combined plot +
summary CSV + data-sources CSV. With `--map`, one choropleth per country
(`{CC}_effort_map_{year}.png`); colour scale calibrated to PT+ES effort range.

### Two-variable fit (`--fit-multivar`)

Fits `effort = a·ln(job_density) + b·nights_per_worker + c` independently
per country via OLS. Eurostat NUTS-2 wage fallback regions are excluded from
the fit (different wage concept). Outputs `multivar_fit_{year}.csv` with
actual vs predicted effort and percentage error per region. Requires year
2023 (tourism data constraint).

### Data sources

| Country | Prices | Wages | Employment / Area |
|---|---|---|---|
| **PT** | INE 0012235 (median transaction €/m²) | MTSS Quadros de Pessoal (ganho × 14); Madeira from DREM (same concept) | Eurostat |
| **ES** | Registradores de España (mean transaction €/m²) | AEAT tax returns (mean annual salary); Basque Country + Navarra fall back to Eurostat NUTS-2 | Eurostat |
| **FR** | DVF open data (median transaction €/m²) | INSEE DADS/DSN (gross annual salary EQTP) | Eurostat |
| **NL** | CBS StatLine (mean transaction €/m²) | CBS 85924NED (compensation / employees) | Eurostat |

Regions using the Eurostat NUTS-2 wage fallback (different definition - includes
employer contributions) are marked with a **black circle** on plots.

### Saved data

`--save-data` writes to `input/` (one CSV per country per dataset). Files:

```
{CC}_prices.csv          {CC}_wages.csv           {CC}_employment.csv
{CC}_area.csv            {CC}_wages_eurostat.csv   ALL_tourism.csv
```

`--local-data` reads them back. Delete a file to force re-fetch of that dataset.

---

## concentration.py

Measures how concentrated employment is in a country's top regions, using
Eurostat NUTS-3 data (nama_10r_3empers).

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
python3 concentration.py eu 50

# With a different reference year
python3 concentration.py eu 50 --year 2023

# Change baseline (default: 2000; avoid 2009-2012 crisis troughs)
python3 concentration.py eu 50 --compare-year 2007

# Capital/top-region share trajectories across all EU-27
python3 concentration.py top
```

### Output

Plots go to `/tmp/concentration/`. The `eu` command produces two bar charts
(region fraction and area fraction); `top` produces small-multiples line charts
and a summary bar chart.

### Notes

- The `--compare-year` for `eu` defaults to 2000. Avoid using 2009–2012 as a
  baseline - the financial crisis hit peripheral regions harder than capitals,
  temporarily inflating concentration. Measuring from a crisis trough understates
  the real structural trend.
- Data goes back to ~2000 for most countries. 2024 is often incomplete.
- Countries with fewer than `--min-regions` NUTS-3 regions (default: 5) are
  excluded from EU comparisons.
