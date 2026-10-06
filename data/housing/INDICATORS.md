# Reliable NUTS-3 Indicators

Curated list of indicators available at NUTS-3 level across the EU, with
data directly observed (not downscaled from coarser levels). Useful for
socio-economic description of regions.

Cross-country comparisons are subject to definitional and recording
differences in most domains. Within-country regional rankings are
generally reliable.

## Demographics

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Population (1 Jan) | SNPTN | `demo_r_pjangroup` | By age and sex. Census/register based. |
| Average annual population | SNPTD | `demo_r_pjangroup` | Mid-year estimate. |
| Population change | SNPCN | Computed | Natural + net migration. |
| Age dependency ratio | SPPAN | Computed | Ratio of young+old to working-age (20-64). |
| Population density | -- | Computed | Population / area (km2). Complements job density: a dormitory suburb has high population density but low job density. |
| Median age of population | -- | `demo_r_pjanind3` | Plus old-age dependency ratio variants and detailed age brackets. Register-based. |
| Demographic balance | -- | `demo_r_gind3` | Births, deaths, net migration, natural change — totals and crude rates. Register-based. |

## Business demography

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Active enterprises | -- | `bd_size_r3` | Count of active enterprises by size class. Administrative register data. 2008-2020. |
| Enterprise birth rate | -- | `bd_size_r3` | New enterprises as % of active stock. Measures entrepreneurial dynamism. |
| Enterprise death rate | -- | `bd_size_r3` | Enterprise closures as % of active stock. |
| Survival rate (3-year) | -- | `bd_size_r3` | Share of newly born enterprises surviving 3 years. |
| Business churn | -- | `bd_size_r3` | Birth rate + death rate. High churn = dynamic but volatile economy. |

## Economic output

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| GDP | SUVGD | `nama_10r_3gdp` | Current prices, EUR and PPS. |
| GDP per capita | SUVGDP | Computed | Workplace-based: commuter regions inflate GDP/capita. |
| GVA by sector (10 NACE) | SUVGZ | `nama_10r_3gva` | Reveals the economic structure of the region. |

## Labour market

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Employment (workplace) | SNETD | `nama_10r_3empers` | Domestic concept: counts jobs, not residents. |
| Employment by sector (10 NACE) | SNETZ | Same, sectoral | Sectoral employment structure. |
| Employment per capita | SNETDP | Computed | Jobs / population; >1 in commuter-destination regions. |
| Job density | -- | Computed | Employment / area (km2). Log-linear relationship with housing prices within each country. |

## Tourism

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Tourist nights | SNTTN | `tour_occ_nin3` | By country of residence of the guest. |
| Tourism intensity (nights/pop) | SNTTNP | Computed | Comparable proxy for tourism pressure. |
| Collaborative economy nights | SNT2N | Experimental | Airbnb-type platforms. Partial coverage. |

## Crime

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Police-recorded offences | -- | `crim_gen_reg` | Homicide, assault, robbery, burglary, theft. Per 100K inhabitants. From 2008. |

Recording practices vary by country: what constitutes "assault" or
"robbery" differs in legal definition and police reporting thresholds.
Cross-country raw rates are not directly comparable. Eurostat recommends
computing deviation from the national rate for each NUTS-3 region to
neutralise country-level recording differences. Within-country regional
variation is meaningful.

## Transport accessibility

| Indicator | ARDECO | Source | Notes |
|---|---|---|---|
| Multimodal accessibility | -- | ESPON | Road + rail + air combined index. Population-weighted by travel time to all destinations. |
| Road accessibility | -- | ESPON | Road-only variant. |
| Rail accessibility | -- | ESPON | Rail-only variant. |

Source: ESPON database (`https://database.espon.eu`), indicators 1537-1542.
Available at NUTS-3 for 2001, 2006, 2011, 2014. **Not updated since 2014**
— usable as a structural baseline but does not reflect recent
infrastructure changes (e.g. new high-speed rail lines).

## Demographics – health & fertility

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Total fertility rate | -- | `demo_r_find3` | Mean number of children per woman. From civil registers (observed, not modelled). |
| Mean age of women at childbirth | -- | `demo_r_find3` | Reflects demographic structure and urbanisation patterns. |

## Climate

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Heating degree days | -- | `nrg_chddr2_a` | Annual. Proxy for winter energy costs and climate amenity. |
| Cooling degree days | -- | `nrg_chddr2_a` | Annual. Proxy for summer energy costs. |

## Housing stock

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Conventional dwellings | -- | `cens_21dwob_r3` | Total, occupied and unoccupied dwellings by building type. Census 2021 (and 2011 via `cens_11dwob_r3`). |
| Vacancy rate | -- | Computed | Unoccupied / total dwellings. Regions with high vacancy have different price dynamics than tight markets. |
| Occupied dwellings | -- | `cens_21dwob_r3` | Proxy for number of households. |

## Geography

| Indicator | ARDECO | Eurostat | Notes |
|---|---|---|---|
| Surface area | SAREA | GISCO | Total and land area (km2). |

## Not included (and why)

| Indicator | Reason |
|---|---|
| Compensation per employee (RUWCDW) | Downscaled from NUTS-2 via employment proxies. Measures employer cost, not purchasing power. See LIMITATIONS.md. |
| Household disposable income (RUVNH) | NUTS-2 only. Not downscaled by ARDECO. Eurostat advises against cross-country use. |
| Housing cost overburden rate (`ilc_lvho07`) | NUTS-2 only. From EU-SILC survey; sample too small for NUTS-3. Conceptually close to purchase effort but measures % of population spending >40% of income on housing costs. |
| Quality of Government (EQI) | NUTS-2 only. Survey-based index of corruption, service quality and impartiality (Univ. of Gothenburg). Waves: 2010, 2013, 2017, 2021, 2024. The closest measure of bureaucracy friction at subnational level in the EU, but survey samples cannot support NUTS-3. |
| Unemployment (RNUTN) | Marked "experimental" in ARDECO. LFS sample too small at NUTS-3; values are modelled. |
| Education attainment (RPDTN) | Same LFS sample-size problem. |
| Capital formation (RUIGT) | Downscaled from national/NUTS-2 using GVA proxies. |
| Hours worked (RNLHT) | Derived from employment x national average; not observed regionally. |
| Labour productivity (SUVGDE) | GVA/employment is mechanically computable but conflates sectoral mix with productivity without the by-sector breakdown. |
| Wage/income Gini | Does not exist at NUTS-3. EU-SILC samples are designed for national/NUTS-1 representativeness. |
| Life expectancy (`demo_r_mlifexp`) | NUTS-2 only. |
| Cost of living / price indices | National only. No subnational price index or PPP exists in Eurostat. |
| At-risk-of-poverty rate (`ilc_li41`) | NUTS-2 only. EU-SILC survey; sample too small for NUTS-3. |
| Household debt / mortgage levels | National only. No subnational household debt data in Eurostat. Some national central banks publish regional credit statistics but no harmonised cross-country source exists. |
| Patent applications (`pat_ep_rtot`) | NUTS-3 but ends in 2012. Too stale for current analysis. |
| Vehicles (`tran_r_vehst`) | NUTS-2 only. |
| R&D expenditure (`rd_e_gerdreg`) | NUTS-2 only. |
| Broadband access (`isoc_r_broad_h`) | NUTS-2 only. |
| Number of households (`lfst_r_lfsd2hh`) | NUTS-2 only (LFS). Census occupied dwellings is the NUTS-3 proxy. |
| Building permits (`sts_cobp_a`) | National only. |

## Data access

ARDECO variables can be downloaded via the ARDECO Explorer
(`https://territorial.ec.europa.eu/ardeco/explorer`) or the REST API:

```
https://territorial.ec.europa.eu/ardeco-api-v2/rest/export/{VARIABLE}?versions=2024&level_id=3&format=csv-table
```

Optional filters: `unit=`, `year=`, `territory_id=` (e.g. `PT,ES`).

Eurostat tables are accessible via the bulk download facility or the
JSON API (`https://ec.europa.eu/eurostat/api/dissemination/`).

An R package (`ARDECO` on CRAN) provides programmatic access to all
ARDECO variables via GraphQL.
