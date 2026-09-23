#!/usr/bin/env python3
"""Exact Binomial Sample Size Calculator.

Calculates the minimal sample size (n) required for a given margin of error (E)
and confidence level (1 - alpha) at maximum dispersion (p = 0.5) using the
exact Binomial Cumulative Distribution Function (CDF).
"""

import argparse
import sys
import math
from scipy.stats import binom
from scipy.special import lambertw


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


def find_minimum_sample_size_lb(E: float, alpha: float = 0.05) -> int:
    """
    Computes sample size n using the Stirling-to-Lambert W continuous approximation.
    Formula: n = ceil( (1 / (4 * E^2)) * W_0( 1 / (pi * alpha^2) ) )
    """

    arg = 1.0 / (math.pi * (alpha ** 2))
    w0_val = float(lambertw(arg).real)
    scale = 1.0 / (4.0 * (E ** 2))

    return math.ceil(scale * w0_val)


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

    args = parser.parse_args()

    # Input validation
    if not (0 < args.error < 0.5):
        parser.error("Margin of error must be between 0 and 0.5")
    if not (0 < args.alpha < 1.0):
        parser.error("Alpha significance level must be between 0 and 1.0")

    try:
        n_min_it = find_minimum_sample_size_it(E=args.error, alpha=args.alpha, buffer_size=args.buffer, max_sample=args.max_sample)
        n_min_lb = find_minimum_sample_size_lb(E=args.error, alpha=args.alpha)

        # add margin
        n_min_lb_adjusted = int(n_min_lb * 1.15)

        lb_deviation_pct = round(((n_min_lb - n_min_it) / n_min_it) * 100, 1)
        lb_safe_deviation_pct = round(((n_min_lb_adjusted - n_min_it) / n_min_it) * 100, 1)

        confidence_pct = (1.0 - args.alpha) * 100
        error_pct = args.error * 100

        print(f"Confidence Level : {confidence_pct:.1f}% (alpha = {args.alpha})")
        print(f"Error margin     : ±{error_pct:.2f}% (E = {args.error})")
        print()
        if args.verbose:
            print(f"Minimum Sample Size (n) - iterative method:        {n_min_it}")
            print(f"Minimum Sample Size (n) - Lambert method:          {n_min_lb} - deviation from iterative: {lb_deviation_pct}%")
            print(f"Minimum Sample Size (n) - Lambert method adjusted: {n_min_lb_adjusted} - deviation from iterative: {lb_safe_deviation_pct}%")
        else:
            print(f"Minimum Sample Size (n): {n_min_it}")

    except RuntimeError as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
