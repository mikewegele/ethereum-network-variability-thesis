import argparse
import os
import re
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


DEFAULT_BW_ORDER = [
    "unlimited",
    "10gbit",
    "1gbit",
    "100mbit",
    "10mbit",
    "1mbit",
    "512kbit",
    "256kbit",
    "128kbit",
    "64kbit",
    "32kbit",
]


def safe_std(x):
    if x is None:
        return 0.0
    try:
        if pd.isna(x):
            return 0.0
    except Exception:
        pass
    try:
        return float(x)
    except Exception:
        return 0.0


def rate_to_kbit(rate: Optional[str]) -> Optional[int]:
    if rate is None:
        return None
    s = str(rate).strip().lower()
    if s == "" or s == "nan":
        return None
    if s == "unlimited":
        return 10**12

    m = re.match(r"^(\d+)\s*(kbit|mbit|gbit)$", s)
    if not m:
        return None

    n = int(m.group(1))
    unit = m.group(2)
    mul = {"kbit": 1, "mbit": 1000, "gbit": 1000_000}[unit]
    return n * mul


def bandwidth_sort_key(rate: str, explicit_order):
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return 10**18
    s = str(rate).strip().lower()
    if s in explicit_order:
        return explicit_order.index(s)
    kbit = rate_to_kbit(s)
    if kbit is None:
        return 10**17
    return -kbit


def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def errorbar_plot(
    x,
    y,
    yerr,
    xlabel,
    ylabel,
    title,
    out_path,
    x_tick_labels=None,
):
    plt.figure()
    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    if x_tick_labels is not None:
        plt.xticks(x, x_tick_labels, rotation=25, ha="right")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def multi_series_plot(
    grouped_df: pd.DataFrame,
    x_col: str,
    series_col: str,
    y_mean_col: str,
    y_std_col: str,
    xlabel: str,
    ylabel: str,
    title: str,
    out_path: str,
    x_order=None,
):
    plt.figure()

    series_values = list(grouped_df[series_col].dropna().unique())
    for s in series_values:
        sub = grouped_df[grouped_df[series_col] == s].copy()

        if x_order is not None:
            sub["_order"] = sub[x_col].map(lambda v: x_order.index(v) if v in x_order else 10**9)
            sub = sub.sort_values(["_order", x_col])
        else:
            sub = sub.sort_values(x_col)

        x = np.arange(len(sub))
        y = sub[y_mean_col].to_numpy()
        yerr = np.array([safe_std(v) for v in sub[y_std_col].to_numpy()])
        labels = sub[x_col].astype(str).tolist()

        plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3, label=str(s))
        plt.xticks(x, labels, rotation=25, ha="right")

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    if len(series_values) > 1:
        plt.legend()
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def resolve_out_dir(out_root: str, dataset: str, scenario: str) -> str:
    return os.path.join(out_root, dataset, scenario)


def infer_dataset_from_csv(csv_path: str) -> str:
    return os.path.basename(csv_path).replace(".csv", "")


def plot_latency(df: pd.DataFrame, out_dir: str):
    sub = df[df["scenario"] == "latency"].copy()
    if sub.empty:
        return

    agg = (
        sub.groupby("latency_ms")
        .agg(
            n=("run_id", "count"),
            cgr_mean=("chain_growth_rate_blocks_per_s_windowed", "mean"),
            cgr_std=("chain_growth_rate_blocks_per_s_windowed", "std"),
            bt_mean=("block_time_mean_s", "mean"),
            bt_std=("block_time_mean_s", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
            stallratio_mean=("stall_ratio", "mean"),
            stallratio_std=("stall_ratio", "std"),
            stalls_mean=("stall_event_count", "mean"),
            stalls_std=("stall_event_count", "std"),
            txpb_mean=("tx_per_block_mean", "mean"),
            txpb_std=("tx_per_block_mean", "std"),
        )
        .reset_index()
        .sort_values("latency_ms")
    )

    agg.to_csv(os.path.join(out_dir, "aggregated_latency.csv"), index=False)

    x = agg["latency_ms"].to_numpy()

    errorbar_plot(
        x, agg["cgr_mean"].to_numpy(), agg["cgr_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Chain growth rate (blocks/s)",
        "Latency vs Chain Growth Rate",
        os.path.join(out_dir, "latency_vs_cgr.pdf")
    )

    errorbar_plot(
        x, agg["bt_mean"].to_numpy(), agg["bt_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Mean block time (s)",
        "Latency vs Mean Block Time",
        os.path.join(out_dir, "latency_vs_block_time.pdf")
    )

    errorbar_plot(
        x, agg["maxgap_mean"].to_numpy(), agg["maxgap_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Max interblock gap (s)",
        "Latency vs Max Interblock Gap",
        os.path.join(out_dir, "latency_vs_max_gap.pdf")
    )

    errorbar_plot(
        x, agg["stallratio_mean"].to_numpy(), agg["stallratio_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Stall ratio",
        "Latency vs Stall Ratio",
        os.path.join(out_dir, "latency_vs_stall_ratio.pdf")
    )

    errorbar_plot(
        x, agg["stalls_mean"].to_numpy(), agg["stalls_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Mean stall event count",
        "Latency vs Stall Event Count",
        os.path.join(out_dir, "latency_vs_stall_events.pdf")
    )

    errorbar_plot(
        x, agg["txpb_mean"].to_numpy(), agg["txpb_std"].fillna(0).to_numpy(),
        "Latency (ms)", "Transactions per block (mean)",
        "Latency vs Transactions per Block",
        os.path.join(out_dir, "latency_vs_tx_per_block.pdf")
    )


def plot_bandwidth(df: pd.DataFrame, out_dir: str, bw_order):
    sub = df[df["scenario"] == "bandwidth"].copy()
    if sub.empty:
        return

    sub["bandwidth"] = sub["bandwidth"].astype(str).str.lower()

    agg = (
        sub.groupby("bandwidth")
        .agg(
            n=("run_id", "count"),
            cgr_mean=("chain_growth_rate_blocks_per_s_windowed", "mean"),
            cgr_std=("chain_growth_rate_blocks_per_s_windowed", "std"),
            bt_mean=("block_time_mean_s", "mean"),
            bt_std=("block_time_mean_s", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
            stallratio_mean=("stall_ratio", "mean"),
            stallratio_std=("stall_ratio", "std"),
            stalls_mean=("stall_event_count", "mean"),
            stalls_std=("stall_event_count", "std"),
            txpb_mean=("tx_per_block_mean", "mean"),
            txpb_std=("tx_per_block_mean", "std"),
        )
        .reset_index()
    )

    agg["_order"] = agg["bandwidth"].map(lambda v: bandwidth_sort_key(v, bw_order))
    agg = agg.sort_values(["_order", "bandwidth"]).drop(columns="_order")
    agg.to_csv(os.path.join(out_dir, "aggregated_bandwidth.csv"), index=False)

    x = np.arange(len(agg))
    labels = agg["bandwidth"].tolist()

    errorbar_plot(
        x, agg["cgr_mean"].to_numpy(), agg["cgr_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Chain growth rate (blocks/s)",
        "Bandwidth vs Chain Growth Rate",
        os.path.join(out_dir, "bandwidth_vs_cgr.pdf"),
        x_tick_labels=labels
    )

    errorbar_plot(
        x, agg["bt_mean"].to_numpy(), agg["bt_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Mean block time (s)",
        "Bandwidth vs Mean Block Time",
        os.path.join(out_dir, "bandwidth_vs_block_time.pdf"),
        x_tick_labels=labels
    )

    errorbar_plot(
        x, agg["maxgap_mean"].to_numpy(), agg["maxgap_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Max interblock gap (s)",
        "Bandwidth vs Max Interblock Gap",
        os.path.join(out_dir, "bandwidth_vs_max_gap.pdf"),
        x_tick_labels=labels
    )

    errorbar_plot(
        x, agg["stallratio_mean"].to_numpy(), agg["stallratio_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Stall ratio",
        "Bandwidth vs Stall Ratio",
        os.path.join(out_dir, "bandwidth_vs_stall_ratio.pdf"),
        x_tick_labels=labels
    )

    errorbar_plot(
        x, agg["stalls_mean"].to_numpy(), agg["stalls_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Mean stall event count",
        "Bandwidth vs Stall Event Count",
        os.path.join(out_dir, "bandwidth_vs_stall_events.pdf"),
        x_tick_labels=labels
    )

    errorbar_plot(
        x, agg["txpb_mean"].to_numpy(), agg["txpb_std"].fillna(0).to_numpy(),
        "Bandwidth limit", "Transactions per block (mean)",
        "Bandwidth vs Transactions per Block",
        os.path.join(out_dir, "bandwidth_vs_tx_per_block.pdf"),
        x_tick_labels=labels
    )


def plot_offline(df: pd.DataFrame, out_dir: str):
    sub = df[df["scenario"] == "offline"].copy()
    if sub.empty:
        return

    agg = (
        sub.groupby("offline_n")
        .agg(
            n=("run_id", "count"),
            cgr_mean=("chain_growth_rate_blocks_per_s_windowed", "mean"),
            cgr_std=("chain_growth_rate_blocks_per_s_windowed", "std"),
            bt_mean=("block_time_mean_s", "mean"),
            bt_std=("block_time_mean_s", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
            stallratio_mean=("stall_ratio", "mean"),
            stallratio_std=("stall_ratio", "std"),
            stalls_mean=("stall_event_count", "mean"),
            stalls_std=("stall_event_count", "std"),
            txpb_mean=("tx_per_block_mean", "mean"),
            txpb_std=("tx_per_block_mean", "std"),
        )
        .reset_index()
        .sort_values("offline_n")
    )

    agg.to_csv(os.path.join(out_dir, "aggregated_offline.csv"), index=False)

    x = agg["offline_n"].to_numpy()

    errorbar_plot(
        x, agg["cgr_mean"].to_numpy(), agg["cgr_std"].fillna(0).to_numpy(),
        "Offline validators", "Chain growth rate (blocks/s)",
        "Offline Validators vs Chain Growth Rate",
        os.path.join(out_dir, "offline_vs_cgr.pdf")
    )

    errorbar_plot(
        x, agg["bt_mean"].to_numpy(), agg["bt_std"].fillna(0).to_numpy(),
        "Offline validators", "Mean block time (s)",
        "Offline Validators vs Mean Block Time",
        os.path.join(out_dir, "offline_vs_block_time.pdf")
    )

    errorbar_plot(
        x, agg["maxgap_mean"].to_numpy(), agg["maxgap_std"].fillna(0).to_numpy(),
        "Offline validators", "Max interblock gap (s)",
        "Offline Validators vs Max Interblock Gap",
        os.path.join(out_dir, "offline_vs_max_gap.pdf")
    )

    errorbar_plot(
        x, agg["stallratio_mean"].to_numpy(), agg["stallratio_std"].fillna(0).to_numpy(),
        "Offline validators", "Stall ratio",
        "Offline Validators vs Stall Ratio",
        os.path.join(out_dir, "offline_vs_stall_ratio.pdf")
    )

    errorbar_plot(
        x, agg["stalls_mean"].to_numpy(), agg["stalls_std"].fillna(0).to_numpy(),
        "Offline validators", "Mean stall event count",
        "Offline Validators vs Stall Event Count",
        os.path.join(out_dir, "offline_vs_stall_events.pdf")
    )


def plot_combined(df: pd.DataFrame, out_dir: str, bw_order):
    sub = df[df["scenario"] == "combined"].copy()
    if sub.empty:
        return

    sub["bandwidth"] = sub["bandwidth"].astype(str).str.lower()

    agg = (
        sub.groupby(["latency_ms", "bandwidth"])
        .agg(
            n=("run_id", "count"),
            cgr_mean=("chain_growth_rate_blocks_per_s_windowed", "mean"),
            cgr_std=("chain_growth_rate_blocks_per_s_windowed", "std"),
            bt_mean=("block_time_mean_s", "mean"),
            bt_std=("block_time_mean_s", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
            stallratio_mean=("stall_ratio", "mean"),
            stallratio_std=("stall_ratio", "std"),
            stalls_mean=("stall_event_count", "mean"),
            stalls_std=("stall_event_count", "std"),
        )
        .reset_index()
    )

    agg["_bw_order"] = agg["bandwidth"].map(lambda v: bandwidth_sort_key(v, bw_order))
    agg = agg.sort_values(["latency_ms", "_bw_order", "bandwidth"]).drop(columns="_bw_order")
    agg.to_csv(os.path.join(out_dir, "aggregated_combined.csv"), index=False)

    multi_series_plot(
        grouped_df=agg,
        x_col="latency_ms",
        series_col="bandwidth",
        y_mean_col="cgr_mean",
        y_std_col="cgr_std",
        xlabel="Latency (ms)",
        ylabel="Chain growth rate (blocks/s)",
        title="Combined Stress: Latency and Bandwidth vs Chain Growth Rate",
        out_path=os.path.join(out_dir, "combined_latency_bandwidth_vs_cgr.pdf"),
    )

    multi_series_plot(
        grouped_df=agg,
        x_col="latency_ms",
        series_col="bandwidth",
        y_mean_col="bt_mean",
        y_std_col="bt_std",
        xlabel="Latency (ms)",
        ylabel="Mean block time (s)",
        title="Combined Stress: Latency and Bandwidth vs Mean Block Time",
        out_path=os.path.join(out_dir, "combined_latency_bandwidth_vs_block_time.pdf"),
    )

    multi_series_plot(
        grouped_df=agg,
        x_col="latency_ms",
        series_col="bandwidth",
        y_mean_col="stallratio_mean",
        y_std_col="stallratio_std",
        xlabel="Latency (ms)",
        ylabel="Stall ratio",
        title="Combined Stress: Latency and Bandwidth vs Stall Ratio",
        out_path=os.path.join(out_dir, "combined_latency_bandwidth_vs_stall_ratio.pdf"),
    )

    multi_series_plot(
        grouped_df=agg,
        x_col="latency_ms",
        series_col="bandwidth",
        y_mean_col="maxgap_mean",
        y_std_col="maxgap_std",
        xlabel="Latency (ms)",
        ylabel="Max interblock gap (s)",
        title="Combined Stress: Latency and Bandwidth vs Max Interblock Gap",
        out_path=os.path.join(out_dir, "combined_latency_bandwidth_vs_max_gap.pdf"),
    )


def plot_baseline_summary(df: pd.DataFrame, out_dir: str):
    sub = df[df["scenario"] == "baseline"].copy()
    if sub.empty:
        return

    cols = [
        "block_time_mean_s",
        "max_interblock_gap_s",
        "chain_growth_rate_blocks_per_s_windowed",
        "tx_per_block_mean",
        "stall_event_count",
    ]

    summary = {}
    for c in cols:
        if c in sub.columns:
            summary[c] = {
                "mean": sub[c].mean(),
                "std": sub[c].std(),
                "median": sub[c].median(),
                "min": sub[c].min(),
                "max": sub[c].max(),
                "n": sub[c].count(),
            }

    pd.DataFrame(summary).T.to_csv(os.path.join(out_dir, "baseline_summary_stats.csv"))

    agg = (
        sub.agg(
            bt_mean=("block_time_mean_s", "mean"),
            bt_std=("block_time_mean_s", "std"),
            cgr_mean=("chain_growth_rate_blocks_per_s_windowed", "mean"),
            cgr_std=("chain_growth_rate_blocks_per_s_windowed", "std"),
            txpb_mean=("tx_per_block_mean", "mean"),
            txpb_std=("tx_per_block_mean", "std"),
            maxgap_mean=("max_interblock_gap_s", "mean"),
            maxgap_std=("max_interblock_gap_s", "std"),
        )
        if not sub.empty else None
    )

    if agg is not None:
        metrics = ["block_time", "cgr", "tx_per_block", "max_gap"]
        means = [
            float(sub["block_time_mean_s"].mean()),
            float(sub["chain_growth_rate_blocks_per_s_windowed"].mean()),
            float(sub["tx_per_block_mean"].mean()),
            float(sub["max_interblock_gap_s"].mean()),
        ]
        stds = [
            safe_std(sub["block_time_mean_s"].std()),
            safe_std(sub["chain_growth_rate_blocks_per_s_windowed"].std()),
            safe_std(sub["tx_per_block_mean"].std()),
            safe_std(sub["max_interblock_gap_s"].std()),
        ]

        x = np.arange(len(metrics))
        plt.figure()
        plt.bar(x, means, yerr=stds, capsize=4)
        plt.xticks(x, metrics, rotation=20, ha="right")
        plt.title("Baseline Summary")
        plt.tight_layout()
        plt.savefig(os.path.join(out_dir, "baseline_summary_bar.pdf"))
        plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-root", default="experiments/plots")
    ap.add_argument(
        "--scenario",
        default="all",
        choices=["all", "baseline", "latency", "bandwidth", "offline", "combined"],
    )
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--only-ok", action="store_true", default=True)
    ap.add_argument("--include-nonok", action="store_true")
    ap.add_argument("--bw-order", default=",".join(DEFAULT_BW_ORDER))
    args = ap.parse_args()

    dataset = args.dataset or infer_dataset_from_csv(args.csv)
    out_dir = resolve_out_dir(args.out_root, dataset, args.scenario)
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(args.csv)

    numeric_cols = [
        "rep",
        "latency_ms",
        "offline_n",
        "blocks_observed",
        "block_time_mean_s",
        "block_time_variance",
        "max_interblock_gap_s",
        "stall_threshold_s",
        "baseline_median_block_time_s",
        "k",
        "block_period_s",
        "stall_event_count",
        "stall_ratio",
        "chain_growth_rate_blocks_per_s_windowed",
        "chain_growth_window_s",
        "tx_total",
        "tx_per_block_mean",
        "tx_per_block_median",
        "tx_per_block_p95",
        "tx_per_block_max",
    ]
    df = coerce_numeric(df, numeric_cols)

    only_ok = False if args.include_nonok else bool(args.only_ok)
    if only_ok and "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    bw_order = [s.strip().lower() for s in args.bw_order.split(",") if s.strip()]

    if args.scenario in ("all", "baseline"):
        plot_baseline_summary(df, out_dir)

    if args.scenario in ("all", "latency"):
        plot_latency(df, out_dir)

    if args.scenario in ("all", "bandwidth"):
        plot_bandwidth(df, out_dir, bw_order)

    if args.scenario in ("all", "offline"):
        plot_offline(df, out_dir)

    if args.scenario in ("all", "combined"):
        plot_combined(df, out_dir, bw_order)

    print(out_dir)


if __name__ == "__main__":
    main()