import argparse
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


def ensure_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def smooth_series(x: np.ndarray, y: np.ndarray, points: int = 800, window: int = 31):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)

    order = np.argsort(x)
    x = x[order]
    y = y[order]

    x_dense = np.linspace(x.min(), x.max(), points)
    y_dense = np.interp(x_dense, x, y)

    if window > 1:
        if window % 2 == 0:
            window += 1
        pad = window // 2
        kernel = np.ones(window, dtype=float) / window
        y_pad = np.pad(y_dense, (pad, pad), mode="edge")
        y_smooth = np.convolve(y_pad, kernel, mode="valid")
    else:
        y_smooth = y_dense

    return x_dense, y_smooth


def plot_mean_with_band(df: pd.DataFrame, out_dir: str):
    sub = df[df["scenario"] == "latency"].copy()
    if sub.empty:
        return

    phase_specs = [
        ("Baseline", "baseline_phase_stall_duration_total_s", "tab:blue"),
        ("Stress", "stress_phase_stall_duration_total_s", "tab:orange"),
        ("Recovery", "recovery_phase_stall_duration_total_s", "tab:green"),
    ]

    plt.figure(figsize=(13, 6))

    for label, col, color in phase_specs:
        agg = (
            sub.groupby("latency_ms")[col]
            .agg(["mean", "std", "count"])
            .reset_index()
            .dropna(subset=["mean"])
            .sort_values("latency_ms")
        )

        if agg.empty or len(agg) < 2:
            continue

        agg["std"] = agg["std"].fillna(0.0)
        agg["count"] = agg["count"].fillna(0.0)

        se = np.where(agg["count"] > 0, agg["std"] / np.sqrt(agg["count"]), 0.0)
        ci = 1.96 * se

        x = agg["latency_ms"].to_numpy(dtype=float)
        mean = agg["mean"].to_numpy(dtype=float)
        lower = mean - ci
        upper = mean + ci

        x_dense, mean_smooth = smooth_series(x, mean, points=800, window=31)
        _, lower_smooth = smooth_series(x, lower, points=800, window=31)
        _, upper_smooth = smooth_series(x, upper, points=800, window=31)

        plt.plot(x_dense, mean_smooth, color=color, linewidth=2.5, label=label)
        plt.fill_between(x_dense, lower_smooth, upper_smooth, color=color, alpha=0.20)

        plt.scatter(x, mean, color=color, s=28, alpha=0.9)

    latency_levels = sorted(sub["latency_ms"].dropna().unique())
    plt.xticks(latency_levels, [str(int(v)) for v in latency_levels], rotation=45, ha="right")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Mean stall duration (s)")
    plt.title("Latency vs Stall Duration by Phase")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "latency_stall_mean_with_ci.pdf"))
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", default="experiments/plots/final_series/latency_advanced")
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = ensure_numeric(
        df,
        [
            "latency_ms",
            "baseline_phase_stall_duration_total_s",
            "stress_phase_stall_duration_total_s",
            "recovery_phase_stall_duration_total_s",
        ],
    )

    os.makedirs(args.out_dir, exist_ok=True)
    plot_mean_with_band(df, args.out_dir)
    print(args.out_dir)


if __name__ == "__main__":
    main()