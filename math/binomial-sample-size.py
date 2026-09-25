#!/usr/bin/env python3
# Ubuntu packages: python3-scipy, python3-matplotlib
"""Exact Binomial Sample Size Calculator.

Calculates the minimal sample size (n) required for a given margin of error (E)
and confidence level (1 - alpha) at maximum dispersion (p = 0.5) using the
exact Binomial Cumulative Distribution Function (CDF).
"""

import argparse
import csv
import os
import sys
import math
import tempfile
import numpy as np
from scipy.stats import binom
from scipy.special import lambertw
from scipy.optimize import curve_fit


def verify_sample_size(n: int, E: float, alpha: float) -> bool:
    """Check if sample size n satisfies two-sided coverage at p = 0.5."""
    p = 0.5
    # k_upper is the largest integer outcome within allowable margin E
    k_upper = int(n * (p + E))

    # Evaluate exact Binomial CDF at worst-case p = 0.5
    coverage_prob = binom.cdf(k_upper, n, p)

    # Must satisfy two-sided tail coverage (1 - alpha / 2)
    return coverage_prob >= (1.0 - alpha / 2.0)


def find_minimum_sample_size_it(E: float, alpha: float, buffer_size: int, max_sample: int) -> int:
    """Find iteratively the smallest n where coverage holds for n and the subsequent buffer window."""
    for n in range(1, max_sample):
        if verify_sample_size(n, E, alpha):
            # Verify across the buffer window to guard against discrete sawtooth drop-offs
            if all(
                verify_sample_size(j, E, alpha)
                for j in range(n + 1, n + buffer_size + 1)
            ):
                return n

    raise RuntimeError(f"No suitable sample size found below ceiling max_sample={max_sample}")


def find_minimum_sample_size_lb(E: float, alpha: float = 0.05, corrected: bool = False) -> int:
    """Computes the minimum sample size n using the analytical Lambert W function

    derived from Stirling's approximation.

    Parameters:
    -----------
    E : float
        Target error margin offset around 0.5 (e.g., 0.05 for 5% margin).
    alpha : float, optional
        Significance level / tail risk (default 0.05 for 95% confidence).
    corrected : bool, optional
        If False (default), returns the pure continuous Stirling lower bound (n ≈ 358).
        If True, applies the discrete tail factor (C = 2 / (pi * alpha^2)) and the
        half-step continuity shift (-1 / (2*E)), providing a conservative discrete
        envelope (n ≈ 420) that safely bounds the discrete sawtooth floor (n = 399).

    Returns:
    --------
    int
        The minimum integer sample size n.
    """

    if corrected:
        # Discrete density factor: accounts for two-sided tail integration over unit bars
        arg = 2.0 / (math.pi * (alpha**2))
        w0_val = float(lambertw(arg).real)

        # Base scale factor: 1 / (4 * E^2)
        base_n = w0_val / (4.0 * (E**2))

        # Continuity shift: adjusts for half-unit discrete histogram bar width
        continuity_shift = 1.0 / (2.0 * E)

        n_float = base_n - continuity_shift
    else:
        # Pure continuous asymptotic lower bound
        arg = 1.0 / (math.pi * (alpha**2))
        w0_val = float(lambertw(arg).real)

        n_float = w0_val / (4.0 * (E**2))

    return math.ceil(n_float)


EXPLORE_ERRORS = [0.01, 0.02, 0.03, 0.04, 0.05, 0.07, 0.10]
EXPLORE_ALPHAS = [0.01, 0.05, 0.10]


def explore(output_dir: str, buffer_size: int, max_sample: int) -> None:
    """Sweep the (E, alpha) grid, write a CSV table and a plot."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results = {}
    total = len(EXPLORE_ERRORS) * len(EXPLORE_ALPHAS)
    done = 0
    for E in EXPLORE_ERRORS:
        for alpha in EXPLORE_ALPHAS:
            done += 1
            print(f"\r  Computing {done}/{total}  (E={E}, alpha={alpha}) ...", end="", flush=True)
            n = find_minimum_sample_size_it(E, alpha, buffer_size, max_sample)
            results[(E, alpha)] = n
    print()

    csv_path = os.path.join(output_dir, "sample_sizes.csv")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        header = ["E \\ alpha"] + [str(a) for a in EXPLORE_ALPHAS]
        writer.writerow(header)
        for E in EXPLORE_ERRORS:
            row = [str(E)] + [str(results[(E, a)]) for a in EXPLORE_ALPHAS]
            writer.writerow(row)

    fig, ax = plt.subplots(figsize=(9, 6))
    for alpha in reversed(EXPLORE_ALPHAS):
        ns = [results[(E, alpha)] for E in EXPLORE_ERRORS]
        confidence = f"{(1 - alpha) * 100:.0f}%"
        ax.plot(EXPLORE_ERRORS, ns, marker="o", label=f"{confidence} confidence (α={alpha})")
    ax.set_yscale("linear")
    ax.set_xlabel("Margin of Error (E)")
    ax.set_ylabel("Minimum Sample Size (n)")
    ax.set_title("Exact Binomial Sample Size vs. Margin of Error")
    ax.legend()
    ax.grid(True, which="both", linestyle="--", alpha=0.5)
    ax.set_xticks(EXPLORE_ERRORS)
    ax.set_xticklabels([f"{e:.0%}" for e in EXPLORE_ERRORS])
    fig.tight_layout()

    plot_path = os.path.join(output_dir, "sample_sizes.png")
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    # Second plot: fit n = C^2 / E^2 for each alpha
    def model(E, C):
        return C**2 / E**2

    E_arr = np.array(EXPLORE_ERRORS)
    E_smooth = np.linspace(E_arr.min(), E_arr.max(), 200)

    fig2, ax2 = plt.subplots(figsize=(9, 6))
    for alpha in reversed(EXPLORE_ALPHAS):
        n_arr = np.array([results[(E, alpha)] for E in EXPLORE_ERRORS], dtype=float)
        popt, _ = curve_fit(model, E_arr, n_arr, p0=[1.0])
        C_fit = popt[0]

        n_pred = model(E_arr, C_fit)
        ss_res = np.sum((n_arr - n_pred)**2)
        ss_tot = np.sum((n_arr - np.mean(n_arr))**2)
        r2 = 1.0 - ss_res / ss_tot

        confidence = f"{(1 - alpha) * 100:.0f}%"
        ax2.plot(E_arr, n_arr, "o", color=ax2._get_lines.get_next_color())
        color = ax2.get_lines()[-1].get_color()
        ax2.plot(E_smooth, model(E_smooth, C_fit), "-", color=color,
                 label=f"{confidence} (α={alpha})  C={C_fit:.4f}  R²={r2:.6f}")
    ax2.set_xlabel("Margin of Error (E)")
    ax2.set_ylabel("Minimum Sample Size (n)")
    ax2.set_title("Fitted n = C² / E²  per Confidence Level")
    ax2.legend()
    ax2.grid(True, which="both", linestyle="--", alpha=0.5)
    ax2.set_xticks(EXPLORE_ERRORS)
    ax2.set_xticklabels([f"{e:.0%}" for e in EXPLORE_ERRORS])
    fig2.tight_layout()

    fit_path = os.path.join(output_dir, "sample_sizes_fit.png")
    fig2.savefig(fit_path, dpi=150)
    plt.close(fig2)

    print(f"CSV  : {csv_path}")
    print(f"Plot : {plot_path}")
    print(f"Fit  : {fit_path}")


def main():

    parser = argparse.ArgumentParser(description=(
            "Compute the exact minimal sample size (n) for Binomial proportion estimation without relying on continuous Gaussian approximations." ),
            formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument("-e", "--error",      type=float, default=0.05,   help="Target half-width margin of error E as a decimal (e.g., 0.05 for 5%%).",)
    parser.add_argument("-a", "--alpha",      type=float, default=0.05,   help="Significance level alpha for (1 - alpha) confidence (e.g., 0.05 for 95%% confidence).",)
    parser.add_argument("-b", "--buffer",     type=int,   default=30,     help="Forward check buffer size to prevent false positives from discrete sawtooth oscillations.", )
    parser.add_argument("-m", "--max-sample", type=int,   default=200000, help="Upper ceiling for sample size search iteration.",)

    parser.add_argument("--verbose", help="Print other esimations as well", action="store_true")
    parser.add_argument("--explore", action="store_true", help="Sweep industry-standard (E, alpha) combinations and produce a CSV table and plot. Mutually exclusive with --error and --alpha.")
    parser.add_argument("--output-dir", type=str, default=None, help="Output directory for --explore files (default: Python tempdir).")

    args = parser.parse_args()

    if args.explore:
        if any(a.dest in ("error", "alpha") for a in parser._actions
               if a.option_strings and any(s in sys.argv for s in a.option_strings)):
            parser.error("--explore is mutually exclusive with --error and --alpha")

        output_dir = args.output_dir or tempfile.mkdtemp(prefix="binomial_explore_")
        os.makedirs(output_dir, exist_ok=True)
        try:
            explore(output_dir, args.buffer, args.max_sample)
        except RuntimeError as err:
            print(f"Error: {err}", file=sys.stderr)
            sys.exit(1)
        return

    # Input validation
    if not (0 < args.error < 0.5):
        parser.error("Margin of error must be between 0 and 0.5")
    if not (0 < args.alpha < 1.0):
        parser.error("Alpha significance level must be between 0 and 1.0")

    try:
        n_min_it = find_minimum_sample_size_it(E=args.error, alpha=args.alpha, buffer_size=args.buffer, max_sample=args.max_sample)
        n_min_lb = find_minimum_sample_size_lb(E=args.error, alpha=args.alpha)
        n_min_lb_cc = find_minimum_sample_size_lb(E=args.error, alpha=args.alpha, corrected=True)

        # add adhoc margin
        n_min_lb_adhoc = int(n_min_lb * 1.15)

        lb_deviation_pct = round(((n_min_lb - n_min_it) / n_min_it) * 100, 1)
        lb_adhoc_deviation_pct = round(((n_min_lb_adhoc - n_min_it) / n_min_it) * 100, 1)
        lb_corrected_deviation_pct = round(((n_min_lb_cc - n_min_it) / n_min_it) * 100, 1)

        confidence_pct = (1.0 - args.alpha) * 100
        error_pct = args.error * 100

        print(f"Confidence Level : {confidence_pct:.1f}% (alpha = {args.alpha})")
        print(f"Error margin     : ±{error_pct:.2f}% (E = {args.error})")
        print()
        if args.verbose:
            print(f"Minimum Sample Size (n) - iterative method:         {n_min_it}")
            print(f"Minimum Sample Size (n) - Lambert method base:      {n_min_lb} - deviation from iterative: {lb_deviation_pct}%")
            print(f"Minimum Sample Size (n) - Lambert method corrected: {n_min_lb_cc} - deviation from iterative: {lb_corrected_deviation_pct}%")
            print(f"Minimum Sample Size (n) - Lambert method adhoc :    {n_min_lb_adhoc} - deviation from iterative: {lb_adhoc_deviation_pct}%")
        else:
            print(f"Minimum Sample Size (n): {n_min_it}")

    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
