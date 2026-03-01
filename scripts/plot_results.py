import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CSV_PATH = "experiments/summary_all_runs.csv"
OUT_DIR = "experiments/plots"

def parse_delay_ms(run_dir: str):
    m = re.search(r"delay(\d+)ms", str(run_dir))
    return int(m.group(1)) if m else np.nan

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(CSV_PATH)

    # Ensure delay_ms exists / numeric
    if "delay_ms" not in df.columns:
        df["delay_ms"] = df["run_dir"].apply(parse_delay_ms)
    df["delay_ms"] = pd.to_numeric(df["delay_ms"], errors="coerce")

    # Drop known-bad measurement artifact runs (your earlier v2 run)
    df = df[~df["run_dir"].astype(str).str.contains("_v2_", regex=False)].copy()

    # Drop rows without delay
    df = df[~df["delay_ms"].isna()].copy()

    # Some columns may come in as strings; coerce
    num_cols = [
        "blocks_observed",
        "block_time_mean_s",
        "block_time_variance",
        "max_interblock_gap_s",
        "stall_event_count",
        "stall_ratio",
        "cgr_blocks_per_s",
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Aggregate per delay: mean + std + n
    agg = (
        df.groupby("delay_ms")
        .agg(
            n=("run_dir", "count"),
            cgr_mean=("cgr_blocks_per_s", "mean"),
            cgr_std=("cgr_blocks_per_s", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
            stallratio_mean=("stall_ratio", "mean"),
            stallratio_std=("stall_ratio", "std"),
            blocks_mean=("blocks_observed", "mean"),
            blocks_std=("blocks_observed", "std"),
        )
        .reset_index()
        .sort_values("delay_ms")
    )

    # Helper for errorbars: if std is NaN (n=1), use 0
    def safe_std(x):
        return 0.0 if np.isnan(x) else float(x)

    # 1) Delay vs CGR
    plt.figure()
    x = agg["delay_ms"].to_numpy()
    y = agg["cgr_mean"].to_numpy()
    yerr = np.array([safe_std(v) for v in agg["cgr_std"].to_numpy()])
    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel("Symmetric delay (ms)")
    plt.ylabel("Chain growth rate (blocks/s), window=60s")
    plt.title("IBFT2: Delay vs Chain Growth Rate")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "delay_vs_cgr.pdf"))
    plt.close()

    # 2) Delay vs Max interblock gap
    plt.figure()
    y = agg["maxgap_mean"].to_numpy()
    yerr = np.array([safe_std(v) for v in agg["maxgap_std"].to_numpy()])
    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel("Symmetric delay (ms)")
    plt.ylabel("Max interblock gap (s)")
    plt.title("IBFT2: Delay vs Max Interblock Gap")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "delay_vs_max_gap.pdf"))
    plt.close()

    # 3) Delay vs Stall ratio
    plt.figure()
    y = agg["stallratio_mean"].to_numpy()
    yerr = np.array([safe_std(v) for v in agg["stallratio_std"].to_numpy()])
    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel("Symmetric delay (ms)")
    plt.ylabel("Stall ratio (stall_events / (blocks-1))")
    plt.title("IBFT2: Delay vs Stall Ratio (k=5, baseline-median threshold)")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "delay_vs_stall_ratio.pdf"))
    plt.close()

    # Also dump the aggregated table for your thesis appendix
    agg_out = os.path.join(OUT_DIR, "aggregated_by_delay.csv")
    agg.to_csv(agg_out, index=False)

    print("Wrote:")
    print(" -", os.path.join(OUT_DIR, "delay_vs_cgr.pdf"))
    print(" -", os.path.join(OUT_DIR, "delay_vs_max_gap.pdf"))
    print(" -", os.path.join(OUT_DIR, "delay_vs_stall_ratio.pdf"))
    print(" -", agg_out)

if __name__ == "__main__":
    main()