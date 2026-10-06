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
| **IT** | INPS Osservatorio dipendenti | Retribuzione annua / numero lavoratori (total annual compensation / headcount) | Social security taxable base including employee contributions | Employer contributions, agriculture, domestic workers |

### Effect on purchase effort

PT, ES, FR and IT use roughly comparable "gross salary" concepts. NL uses
"compensation of employees", which includes employer contributions on top
of gross salary.

- **NL effort is understated** by ~20-25% relative to the other countries,
  because the denominator (wage) includes employer charges the worker never
  sees.
- **PT and IT wages cover private-sector employees only.** PT Quadros de
  Pessoal excludes public administration; IT INPS excludes public sector,
  agriculture, and domestic workers. Public employment is ~15% of total
  employment in PT (OECD/DGAEP, 2023) and ~14% in IT. In regions with
  large public employment (e.g. Roma, Lisboa), the true average wage is
  higher than reported, meaning effort is slightly overstated.
  An alternative was investigated for PT: INE's "Estatísticas do Rendimento
  ao Nível Local" publishes tax-return-based income at municipality and
  NUTS-3 level, but only as total gross declared income across all IRS
  categories (employment, pensions, self-employment, capital gains) with no
  breakdown by category. This makes it unsuitable — retirement-heavy regions
  (Algarve, Alentejo) would show inflated "wages". Portugal's tax authority
  (AT) does not publish employment-only income at regional level, unlike
  Spain's AEAT which publishes employment-specific salary data by province.
- **ES and FR wages include public and private sectors.** AEAT tax returns
  cover all employment income; INSEE DADS/DSN covers all sectors.
- Within each country, all regions use the same wage concept, so relative
  rankings are unaffected.

### Recommendation

Use per-country plots for reliable comparisons. The combined plot is useful
for seeing overall patterns but the NL data points sit on a different wage
baseline. On the scatter plots, this manifests as NL appearing to have lower
effort than similarly priced regions in other countries.

### Why not use Eurostat/ARDECO "compensation of employees"?

The ARDECO database (JRC) provides "compensation of employees" (ESA 2010
code D.1) at NUTS-3 level, with a single harmonised definition across all
EU countries. This was evaluated as a potential common denominator for
cross-country effort comparisons, but it is **not suitable** for this
purpose:

1. **It measures cost of work, not purchasing power.** Compensation of
   employees includes employer social contributions on top of gross salary.
   These contributions vary widely by country (PT ~24%, ES ~30%, IT ~33%,
   FR ~45%), so a worker with the same gross salary and the same purchasing
   power appears to earn very different amounts depending on the country's
   social security system. Purchase effort should reflect what the worker
   can spend, not what they cost the employer.

2. **Cross-country divergence is worse, not better.** Empirical comparison
   (2023) shows ARDECO compensation/employee is 1.22× the national wage in
   PT, 1.36× in ES, 1.46× in IT, 1.21× in FR, and 0.87× in NL. These
   country-specific multipliers reflect employer contribution rates, not
   meaningful differences in purchasing power. NL falls below 1.0 because
   its national source (CBS) already includes employer contributions.

3. **NUTS-3 values are synthetic.** ARDECO's source is Eurostat
   `nama_10r_2coe` (NUTS-2). NUTS-3 estimates are derived by distributing
   the NUTS-2 total proportionally to sectoral employment
   (`RUWC_NUTS3 = SNETX_NUTS3 / SNETX_NUTS2 × RUWC_NUTS2`). This means
   all NUTS-3 regions within a NUTS-2 area share the same underlying wage,
   adjusted only by industry mix — losing the real within-NUTS-2 variation
   that national sources capture (e.g. AEAT province-level salaries in ES,
   MTSS municipality-aggregated wages in PT).

4. **Within-country rankings are unaffected.** Spearman rank correlations
   between national-source effort and ARDECO-source effort are 0.90–0.98
   across all five countries, confirming that the choice of wage source
   does not change regional rankings within a country.

### Why not use household disposable income?

Household net disposable income (Eurostat `nama_10r_2hhinc`, ARDECO code
`RUVNH`) would in principle be the ideal denominator for purchase effort:
it reflects what people actually have to spend after taxes, social
contributions and transfers. However:

- **It is only available at NUTS-2 level.** Eurostat publishes household
  income accounts at NUTS-2; there is no official NUTS-3 breakdown. ARDECO
  does not downscale it to NUTS-3 (unlike compensation, which it estimates
  via employment proxies).
- **Eurostat advises against cross-country use.** The regional household
  income statistics page explicitly warns that these data should not be
  used to compare income across countries, because they exclude social
  transfers in kind (public healthcare, education, housing subsidies),
  which vary substantially between countries.

If a NUTS-3 disposable income dataset becomes available in the future, it
would be worth revisiting as an alternative effort metric.

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
| **IT** | OMI (Agenzia delle Entrate) | **Mean** appraised quotation (EUR/m2), expert-assessed market value ranges |

PT and FR use **median**, ES and NL use **mean**. The mean is typically
higher than the median (skewed by luxury transactions), so ES and NL prices
may be slightly inflated relative to PT and FR. The effect is small at
NUTS-3 level (typically 5-15%) but exists.

**IT prices are not transaction prices.** OMI quotations are expert-assessed
market value ranges (min/max EUR/m2) per micro-zone, informed by transaction
data but processed through professional appraisal. They are methodologically
closer to ES Registradores (valuation-derived) than to PT INE or FR DVF
(actual transaction records). The province-level figure is the mean of
sub-provincial macro-area averages (unweighted by volume).

## Coverage gaps

- **PT wages**: available 2014-2024 only (MTSS Quadros de Pessoal series).
  Earlier years would require a different source.
- **FR wages**: typically lag one year. For 2023, the script uses 2022 wages
  (latest available from INSEE DADS/DSN).
- **PT prices**: INE 0012235 starts Q4 2019. For earlier years the script
  falls back to INE 0012256 (bank appraisal values, not transaction prices).
- **IT prices**: OMI data from 2016 onward. One province missing: Sud
  Sardegna (ITG2H), created in 2016 and not yet in the OMI compilation.
- **IT wages**: INPS data from 2019 onward. Some provinces show no data for
  years before boundary reclassifications (Monza e della Brianza,
  Barletta-Andria-Trani, Sud Sardegna before 2022).
- **Tourism data**: only usable for 2023 due to NUTS code version alignment
  (tourism dataset switched to NUTS 2021 codes in 2023).

## IT requires --local-data

Italy has no public API for prices or wages. Both datasets are prepared
offline and must be provided via `--local-data`:

- **Prices**: OMI quotations aggregated from the GitHub compilation at
  `github.com/eugeniodalpozzo/italy_omi_housing_provincial_prices`
  (original source: Agenzia delle Entrate).
- **Wages**: INPS "Osservatorio sui lavoratori dipendenti del settore
  privato", exported from the interactive observatory at
  `servizi2.inps.it/servizi/osservatoristatistici/15`. The export provides
  total annual compensation and worker headcount by province; average wage
  is computed as the ratio.

Running with `--countries IT` without `--local-data` produces an error.
Running with `--save-data` and IT in the country list is also rejected,
since there is nothing to fetch.

## NUTS code versions

Data from national sources uses NUTS 2024 codes. The choropleth maps use
Eurostat GISCO NUTS 2024 boundaries, so all codes match directly.

Employment and area data from Eurostat may internally use NUTS 2021 for
some years. The script handles this transparently.

## Monthly payment multipliers (PT x14, IT x13)

Portuguese workers receive 14 monthly payments per year: 12 regular months
plus mandatory holiday and Christmas subsidies (each equal to one month's
pay). The MTSS data reports monthly values; we multiply by 14 to get the
annual figure comparable to ES/FR/NL annual wages.

Italian workers receive 13 monthly payments (the "tredicesima"). The INPS
data already reports total annual compensation, so no multiplier is needed
in the code — the x13 is implicit in the ratio of annual pay to headcount.

## Two-variable fit (`--fit-multivar`)

The per-country OLS fit `effort = a·ln(density) + b·npw + c` is fitted
independently per country. Key caveats:

- **Eurostat fallback regions are excluded** (Basque Country, Navarra,
  Açores) because their wage concept differs. The CSV omits them entirely.
- **Fit quality varies by country.** PT and FR achieve R² ~0.85-0.81; ES
  ~0.76; IT ~0.57. Italy's lower R² reflects the North-South structural
  gap in wages, construction costs and land markets — two variables cannot
  capture this, and the residual scatter is pervasive rather than driven by
  a few outliers.
- **Coefficients are not comparable across countries** without accounting
  for the wage and price concept differences documented above. The tourism
  coefficient (b) is comparable in direction and order of magnitude, but
  the density coefficient (a) absorbs country-specific baseline effects.
- **NL fit quality is affected** by Haarlem (residential spillover from
  Amsterdam — prices carry the Amsterdam premium but local density and
  wages don't) and The Hague (seat of government — extreme public-sector
  job density inflates the denominator). These two pull the regression in
  opposite directions at the high-density end. The compensation-based wage
  concept (see above) compounds the issue.
- **Why ln(density) but linear tourism.** The two variables use different
  functional forms because they capture different economic mechanisms.
  Job density operates through a local equilibrium: more jobs attract more
  workers who compete for housing, but wages and supply respond, producing
  diminishing marginal returns — hence the logarithm. Tourism intensity
  operates as an external demand shock: tourist spending and short-term
  rental yields are priced by visitors' home-country purchasing power, not
  local wages. Selling a house in a touristic region means giving up a
  stream of rental income driven by external demand, so prices scale
  linearly with tourism volume — there is no local dampening mechanism at
  NUTS-3 scale. A log-log model was tested and performed worse across all
  countries (PT R² dropped from 0.85 to 0.74), confirming that the
  linear-in-tourism specification is not just empirically better but
  structurally appropriate.
- **Workplace-residence mismatch** in dense metro areas (Paris petite
  couronne, The Hague, Milan) can produce large residuals: employment
  density is measured where jobs sit, but housing prices reflect the
  residential market. Regions that are primarily commuter job destinations
  will show lower actual effort than predicted.
