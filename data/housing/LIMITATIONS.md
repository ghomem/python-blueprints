# Limitations and Data Caveats

## Wage concept differences across countries

The "wage" used in purchase effort calculations is not the same concept in
every country. This affects **cross-country** comparisons but not
**within-country** regional rankings.

| Country | Source | Concept | Includes | Excludes |
|---|---|---|---|---|
| **PT** | MTSS Quadros de Pessoal, sheet q37 | Ganho (mean monthly earnings) x 14 | Base pay, meal subsidy, shift pay, regular bonuses, overtime | Employer social security contributions (~23.75%), irregular bonuses |
| **ES** | AEAT tax returns | Salario medio anual (mean annual gross salary) | All gross pay components reported to tax authority | Employer social security contributions (~30%) |
| **FR** | INSEE DADS/DSN | Salaire brut annuel EQTP (gross annual salary, full-time equivalent) | All gross pay components | Employer social security contributions (~45%) |
| **NL** | CBS 85924NED | Beloning van werknemers / employees (compensation per employee) | Gross salary **plus employer social security contributions** | Nothing |

### Effect on purchase effort

PT, ES and FR use roughly comparable "gross salary" concepts. NL uses
"compensation of employees", which includes employer contributions on top
of gross salary.

- **NL effort is understated** by ~20-25% relative to PT/ES/FR, because the
  denominator (wage) includes employer charges the worker never sees.
- Within each country, all regions use the same wage concept, so relative
  rankings are unaffected.

### Recommendation

Use per-country plots for reliable comparisons. The combined plot is useful
for seeing overall patterns but the NL data points sit on a different wage
baseline. On the scatter plots, this manifests as NL appearing to have lower
effort than similarly priced regions in other countries.

## Eurostat NUTS-2 wage fallback

Five regions lack NUTS-3 wage data from national sources and fall back to
Eurostat NUTS-2 "compensation of employees" (nama_10r_2coe divided by
employment). This concept includes employer social security contributions,
making the wage systematically higher and the effort **understated**.

| Region | Country | NUTS-2 parent | Reason |
|---|---|---|---|
| Araba/Alava (ES211) | ES | ES21 (Pais Vasco) | Foral tax system, not in AEAT |
| Gipuzkoa (ES212) | ES | ES21 (Pais Vasco) | Foral tax system, not in AEAT |
| Bizkaia (ES213) | ES | ES21 (Pais Vasco) | Foral tax system, not in AEAT |
| Navarra (ES220) | ES | ES22 (Navarra) | Foral tax system, not in AEAT |
| Acores (PT200) | PT | PT20 (R.A. Acores) | Cloudflare blocks automated access to regional stats portal |

These regions are marked with a **black circle** on scatter plots.

The Basque Country + Navarra fallback wages are ~30% higher than the
AEAT-equivalent, meaning their true effort is roughly 1.3x what the plot
shows. For example, Gipuzkoa shows effort 0.88 but would be ~1.1 on an
AEAT-equivalent wage.

## Price concept differences

| Country | Source | Concept |
|---|---|---|
| **PT** | INE 0012235 | **Median** transaction price (EUR/m2), from notarial records |
| **ES** | Registradores de Espana | **Mean** transaction price (EUR/m2), from property registrations |
| **FR** | DVF open data | **Median** transaction price (EUR/m2), from notarial records |
| **NL** | CBS StatLine | **Mean** transaction price (EUR/m2) |

PT and FR use **median**, ES and NL use **mean**. The mean is typically
higher than the median (skewed by luxury transactions), so ES and NL prices
may be slightly inflated relative to PT and FR. The effect is small at
NUTS-3 level (typically 5-15%) but exists.

## Coverage gaps

- **PT wages**: available 2014-2024 only (MTSS Quadros de Pessoal series).
  Earlier years would require a different source.
- **FR wages**: typically lag one year. For 2023, the script uses 2022 wages
  (latest available from INSEE DADS/DSN).
- **PT prices**: INE 0012235 starts Q4 2019. For earlier years the script
  falls back to INE 0012256 (bank appraisal values, not transaction prices).
- **Tourism data**: only usable for 2023 due to NUTS code version alignment
  (tourism dataset switched to NUTS 2021 codes in 2023).

## NUTS code versions

Data from national sources uses NUTS 2024 codes. The choropleth maps use
Eurostat GISCO NUTS 2024 boundaries, so all codes match directly.

Employment and area data from Eurostat may internally use NUTS 2021 for
some years. The script handles this transparently.

## The x14 multiplier for PT wages

Portuguese workers receive 14 monthly payments per year: 12 regular months
plus mandatory holiday and Christmas subsidies (each equal to one month's
pay). The MTSS data reports monthly values; we multiply by 14 to get the
annual figure comparable to ES/FR/NL annual wages.
