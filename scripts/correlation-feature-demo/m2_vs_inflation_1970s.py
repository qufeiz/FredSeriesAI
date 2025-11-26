#!/usr/bin/env python
"""Correlate M2 growth with CPI inflation in the 1970s (one-off script)."""

import argparse
import os
import sys
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from fredapi import Fred

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--start", default="1970-01-01", help="Inclusive start date (default: 1970-01-01).")
parser.add_argument("--end", default="1979-12-31", help="Inclusive end date (default: 1979-12-31).")
parser.add_argument(
    "--export",
    type=Path,
    help="Optional path to export the aligned YoY dataframe (CSV or Parquet based on extension).",
)
parser.add_argument(
    "--plot",
    action="store_true",
    help="Display a quick line chart comparing the two YoY series (requires matplotlib).",
)
parser.add_argument(
    "--plot-lag",
    action="store_true",
    help="Plot correlation vs lag (requires matplotlib).",
)
parser.add_argument(
    "--max-lag",
    type=int,
    default=48,
    help="Maximum lag (months) to test when correlating M2 and CPI (default: 48).",
)
parser.add_argument(
    "--trend",
    action="store_true",
    help="Also report correlation between log levels (long-run trend).",
)
args = parser.parse_args()

load_dotenv()
api_key = os.getenv("FRED_API_KEY")
if not api_key:
    sys.exit("Set FRED_API_KEY in your environment or .env before running this script.")

fred = Fred(api_key=api_key)


def load_series(series_id: str) -> pd.Series:
    series = fred.get_series(series_id)
    series.index = pd.to_datetime(series.index)
    window = (series.index >= args.start) & (series.index <= args.end)
    return series.loc[window]


m2 = load_series("GDPC1")
cpi = load_series("UNRATE")

df = (
    pd.concat(
        {
            "M2_yoy": m2.pct_change(12) * 100,
            "CPI_yoy": cpi.pct_change(12) * 100,
        },
        axis=1,
    )
    .dropna()
)

corr = df["M2_yoy"].corr(df["CPI_yoy"])
print(f"Correlation between M2 YoY growth and CPI YoY inflation: {corr:.4f}")

lag_results: dict[int, float] = {}
for lag in range(0, args.max_lag + 1):
    shifted = df["M2_yoy"].shift(lag)
    aligned = pd.concat(
        {"M2_yoy_shifted": shifted, "CPI_yoy": df["CPI_yoy"]},
        axis=1,
    ).dropna()
    if aligned.empty:
        continue
    lag_results[lag] = aligned["M2_yoy_shifted"].corr(aligned["CPI_yoy"])

if lag_results:
    best_lag = max(lag_results, key=lag_results.get)
    print(
        f"Highest correlation occurs when M2 leads CPI by {best_lag} month(s): "
        f"{lag_results[best_lag]:.4f}"
    )
    worst_lag = min(lag_results, key=lag_results.get)
    if worst_lag != best_lag:
        print(
            f"Most negative correlation occurs when M2 leads CPI by {worst_lag} month(s): "
            f"{lag_results[worst_lag]:.4f}"
        )

print("\nSummary statistics:")
print(df.describe().round(2))

if args.export:
    args.export.parent.mkdir(parents=True, exist_ok=True)
    if args.export.suffix.lower() == ".parquet":
        df.to_parquet(args.export)
    else:
        df.to_csv(args.export, index_label="date")
    print(f"\nExported {len(df):,} rows to {args.export.resolve()}")

if args.plot:
    try:
        import matplotlib.pyplot as plt

        df.plot(title="M2 YoY Growth vs CPI YoY Inflation (1970s)", figsize=(10, 5))
        plt.ylabel("Percent")
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("matplotlib not installed; skipping plot.", file=sys.stderr)

if args.plot_lag and lag_results:
    try:
        import matplotlib.pyplot as plt

        lags = sorted(lag_results)
        corrs = [lag_results[lag] for lag in lags]
        plt.figure(figsize=(8, 4))
        plt.plot(lags, corrs, marker="o")
        plt.title("Correlation vs Lag (M2 leads CPI)")
        plt.xlabel("Lag (months)")
        plt.ylabel("Correlation")
        plt.axhline(0.0, color="black", linewidth=0.8, linestyle="--", alpha=0.7)
        plt.tight_layout()
        plt.show()
    except ImportError:
        print("matplotlib not installed; skipping lag plot.", file=sys.stderr)

if args.trend:
    import numpy as np  # localized import to keep base script light

    trend_df = (
        pd.concat(
            {
                "log_M2": pd.Series(np.log(m2)),
                "log_CPI": pd.Series(np.log(cpi)),
            },
            axis=1,
        )
        .dropna()
    )
    trend_corr = trend_df["log_M2"].corr(trend_df["log_CPI"])
    print(f"\nCorrelation between log levels (M2 vs CPI): {trend_corr:.4f}")
