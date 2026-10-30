# Map colour scales

All choropleth maps use the same blue–white–red colormap (`#2166ac,#ffffff,#b2182b`)
and the same visual metaphor: blue = cold/low, white = neutral reference, red = hot/high.

The normalisation differs by map type because the data distributions differ.

## Normalisation by map type

### Effort maps (`density_vs_price.py --map`)

**Norm:** `SymmetricGammaNorm(gamma=0.4, vcenter=0.7, vmin=data_min, vmax=data_max)`

- `vcenter=0.7` — white on the map. This is the effort threshold at which a 50 m²
  apartment can be repaid in ~10 years at maximum mortgage effort (90% LTV, 4% rate,
  45% of net salary).
- `gamma=0.4` — concave compression. Near the centre, small value changes produce
  large colour changes (high sensitivity). Away from centre, values compress — you
  need larger differences to see a colour shift. This pushes most of the colour
  variation into the mid-range where the interesting differentiation happens.
- `vmin/vmax` come from the actual data, so the range is roughly symmetric and the
  colorbar covers the full 0-to-1 gradient with no cropping.

### Density maps (`density_vs_price.py --map-density`)

**Norm:** `SymmetricGammaNorm(gamma=0.4, vcenter=53, vmin=4, vmax=1011)`

- `vcenter=53` — median employment density across all 312 regions. White on the map.
  Half the regions are blue (below median), half are red (above).
- `vmin=4` — Teruel (ES242), the least dense region in the dataset (4.18 j/km²).
  Full blue reference.
- `vmax=1011` — Grande Lisboa (PT1A0), used as the full red reference (1,011 j/km²).
  Regions above this (Paris at 21,720, Ceuta, Melilla) clip to the same red.
- The range is **heavily asymmetric** (4→53 below centre vs 53→1011 above). This means
  `max_extent = 958` and the colorbar is cropped: the blue side is short, the red side
  is long. This is correct — it reflects the real skew of the data.

### Share-delta and employment-change maps (`concentration.py share-map`)

**Norm:** `SymmetricGammaNorm(gamma=0.4, vcenter=0.0, vmin=-max, vmax=+max)`

- `vcenter=0.0` — no change. White means a region's employment share (or absolute
  employment) stayed the same between the two years.
- Symmetric by nature: gains (red) and losses (blue) mirror each other around zero.
- `vmin/vmax` are computed per country as the symmetric extent of the data.

## SymmetricGammaNorm — how it works

```
d = (value - vcenter) / max_extent
colour_position = 0.5 + 0.5 × sign(d) × |d|^gamma
```

- `max_extent = max(|vcenter - vmin|, |vmax - vcenter|)` — the longer side sets the
  scale for both sides, so equal data distances from centre produce equal colour
  intensity regardless of range asymmetry.
- `gamma < 1` (concave): more colour variation near centre, less at extremes.
- `gamma = 1`: linear (no compression).
- `gamma > 1` (convex): more variation at extremes, less near centre.

## Colorbar implementation (`map_utils.py`)

The colorbar is drawn manually for `SymmetricGammaNorm` because matplotlib cannot
auto-generate one for a custom norm.

Key details:
- The gradient is drawn with `imshow` using `vmin=0, vmax=1` to prevent matplotlib
  from renormalising the gradient values. Without this, white on the colorbar drifts
  away from white on the map.
- When the range is asymmetric (one side cropped), ticks are placed only in the
  live portion (`pos_lo` to `pos_hi`) with evenly spaced positions and non-evenly
  spaced labels (the labels reflect the gamma compression).
- Endpoints are labelled `≤` / `≥` when the colorbar is cropped (asymmetric range),
  to signal that values beyond the displayed range clip to the boundary colour.
- Tick labels use integer formatting for values ≥ 10, two decimal places otherwise.

## Why not other norms?

Alternatives tried for density maps and why they were rejected:

| Norm | Problem |
|------|---------|
| `LogNorm` | Colorbar ticks and white position don't align with the map without custom handling. Separate code path from the other maps. |
| `PowerNorm(gamma=0.4)` | Most regions fall below the gamma-shifted midpoint (~182 j/km²), making the map overwhelmingly blue. |
| `Normalize` (linear) | White at the arithmetic midpoint (~500 j/km²). Almost everything is blue because most regions are far below 500. |

`SymmetricGammaNorm` with the median as `vcenter` gives the best balance: half the
regions blue, half red, with gamma compression providing differentiation where the
data is densest.
