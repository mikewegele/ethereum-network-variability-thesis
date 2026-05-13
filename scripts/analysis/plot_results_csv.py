import argparse
import os
import re
from typing import Optional, List

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
    "24kbit",
    "16kbit",
    "12kbit",
    "8kbit",
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


def bandwidth_sort_key(rate: str, explicit_order: List[str]):
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


def resolve_out_dir(out_root: str, dataset: str, scenario: str) -> str:
    return os.path.join(out_root, dataset, scenario)


def infer_dataset_from_csv(csv_path: str) -> str:
    return os.path.basename(os.path.dirname(os.path.abspath(csv_path)))


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


def phase_lines_plot(
    grouped_df: pd.DataFrame,
    x_col: str,
    xlabel: str,
    ylabel: str,
    title: str,
    out_path: str,
    baseline_mean_col: str,
    baseline_std_col: str,
    stress_mean_col: str,
    stress_std_col: str,
    recovery_mean_col: str,
    recovery_std_col: str,
    x_tick_labels=None,
):
    plt.figure()

    x = np.arange(len(grouped_df))
    labels = (
        x_tick_labels
        if x_tick_labels is not None
        else grouped_df[x_col].astype(str).tolist()
    )

    phase_specs = [
        ("Baseline", baseline_mean_col, baseline_std_col),
        ("Stress", stress_mean_col, stress_std_col),
        ("Recovery", recovery_mean_col, recovery_std_col),
    ]

    for label, mean_col, std_col in phase_specs:
        if mean_col not in grouped_df.columns:
            continue
        y = grouped_df[mean_col].to_numpy(dtype=float)
        yerr = np.array([safe_std(v) for v in grouped_df[std_col].to_numpy()])
        plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3, label=label)

    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(x, labels, rotation=25, ha="right")
    plt.legend()
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def aggregate_metric_set(sub: pd.DataFrame, group_cols):
    return (
        sub.groupby(group_cols)
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
            stall_duration_mean=("stall_duration_total_s", "mean"),
            stall_duration_std=("stall_duration_total_s", "std"),

            missing_mean=("missing_finalization_interval_count", "mean"),
            missing_std=("missing_finalization_interval_count", "std"),
            delayed_mean=("delayed_finalization_event_count", "mean"),
            delayed_std=("delayed_finalization_event_count", "std"),

            txpb_mean=("tx_per_block_mean", "mean"),
            txpb_std=("tx_per_block_mean", "std"),

            baseline_phase_bt_mean=("baseline_phase_block_time_mean_s", "mean"),
            baseline_phase_bt_std=("baseline_phase_block_time_mean_s", "std"),
            stress_phase_bt_mean=("stress_phase_block_time_mean_s", "mean"),
            stress_phase_bt_std=("stress_phase_block_time_mean_s", "std"),
            recovery_phase_bt_mean=("recovery_phase_block_time_mean_s", "mean"),
            recovery_phase_bt_std=("recovery_phase_block_time_mean_s", "std"),

            baseline_phase_cgr_mean=("baseline_phase_chain_growth_rate_blocks_per_s_windowed", "mean"),
            baseline_phase_cgr_std=("baseline_phase_chain_growth_rate_blocks_per_s_windowed", "std"),
            stress_phase_cgr_mean=("stress_phase_chain_growth_rate_blocks_per_s_windowed", "mean"),
            stress_phase_cgr_std=("stress_phase_chain_growth_rate_blocks_per_s_windowed", "std"),
            recovery_phase_cgr_mean=("recovery_phase_chain_growth_rate_blocks_per_s_windowed", "mean"),
            recovery_phase_cgr_std=("recovery_phase_chain_growth_rate_blocks_per_s_windowed", "std"),

            baseline_phase_missing_mean=("baseline_phase_missing_finalization_interval_count", "mean"),
            baseline_phase_missing_std=("baseline_phase_missing_finalization_interval_count", "std"),
            stress_phase_missing_mean=("stress_phase_missing_finalization_interval_count", "mean"),
            stress_phase_missing_std=("stress_phase_missing_finalization_interval_count", "std"),
            recovery_phase_missing_mean=("recovery_phase_missing_finalization_interval_count", "mean"),
            recovery_phase_missing_std=("recovery_phase_missing_finalization_interval_count", "std"),

            baseline_phase_stalls_mean=("baseline_phase_stall_event_count", "mean"),
            baseline_phase_stalls_std=("baseline_phase_stall_event_count", "std"),
            stress_phase_stalls_mean=("stress_phase_stall_event_count", "mean"),
            stress_phase_stalls_std=("stress_phase_stall_event_count", "std"),
            recovery_phase_stalls_mean=("recovery_phase_stall_event_count", "mean"),
            recovery_phase_stalls_std=("recovery_phase_stall_event_count", "std"),

            baseline_phase_stall_duration_mean=("baseline_phase_stall_duration_total_s", "mean"),
            baseline_phase_stall_duration_std=("baseline_phase_stall_duration_total_s", "std"),
            stress_phase_stall_duration_mean=("stress_phase_stall_duration_total_s", "mean"),
            stress_phase_stall_duration_std=("stress_phase_stall_duration_total_s", "std"),
            recovery_phase_stall_duration_mean=("recovery_phase_stall_duration_total_s", "mean"),
            recovery_phase_stall_duration_std=("recovery_phase_stall_duration_total_s", "std"),

            baseline_phase_txpb_mean=("baseline_phase_tx_per_block_mean", "mean"),
            baseline_phase_txpb_std=("baseline_phase_tx_per_block_mean", "std"),
            stress_phase_txpb_mean=("stress_phase_tx_per_block_mean", "mean"),
            stress_phase_txpb_std=("stress_phase_tx_per_block_mean", "std"),
            recovery_phase_txpb_mean=("recovery_phase_tx_per_block_mean", "mean"),
            recovery_phase_txpb_std=("recovery_phase_tx_per_block_mean", "std"),
        )
        .reset_index()
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
        "missing_finalization_interval_count",
        "delayed_finalization_event_count",
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

    metrics = [
        "block_time_mean_s",
        "chain_growth_rate_blocks_per_s_windowed",
        "tx_per_block_mean",
        "max_interblock_gap_s",
    ]
    labels = ["block_time", "cgr", "tx_per_block", "max_gap"]
    means = [float(sub[m].mean()) for m in metrics]
    stds = [safe_std(sub[m].std()) for m in metrics]

    x = np.arange(len(labels))
    plt.figure()
    plt.bar(x, means, yerr=stds, capsize=4)
    plt.xticks(x, labels, rotation=20, ha="right")
    plt.title("Baseline Summary")
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "baseline_summary_bar.pdf"))
    plt.close()


def plot_scenario_family(
    df: pd.DataFrame,
    out_dir: str,
    scenario: str,
    x_col: str,
    xlabel: str,
    sort_kind: str = "numeric",
    bw_order: Optional[List[str]] = None,
):
    sub = df[df["scenario"] == scenario].copy()
    if sub.empty:
        return

    agg = aggregate_metric_set(sub, [x_col])

    if sort_kind == "numeric":
        agg = agg.sort_values(x_col)
        x_labels = agg[x_col].astype(str).tolist()
    elif sort_kind == "bandwidth":
        agg["_order"] = agg[x_col].map(lambda v: bandwidth_sort_key(v, bw_order or DEFAULT_BW_ORDER))
        agg = agg.sort_values(["_order", x_col]).drop(columns="_order")
        x_labels = agg[x_col].astype(str).tolist()
    else:
        x_labels = agg[x_col].astype(str).tolist()

    agg.to_csv(os.path.join(out_dir, f"aggregated_{scenario}.csv"), index=False)

    x_numeric = np.arange(len(agg))

    errorbar_plot(
        x_numeric,
        agg["cgr_mean"].to_numpy(),
        agg["cgr_std"].fillna(0).to_numpy(),
        xlabel,
        "Chain growth rate (blocks/s)",
        f"{scenario.capitalize()} vs Chain Growth Rate",
        os.path.join(out_dir, f"{scenario}_vs_cgr.pdf"),
        x_tick_labels=x_labels,
    )

    errorbar_plot(
        x_numeric,
        agg["bt_mean"].to_numpy(),
        agg["bt_std"].fillna(0).to_numpy(),
        xlabel,
        "Mean block time (s)",
        f"{scenario.capitalize()} vs Mean Block Time",
        os.path.join(out_dir, f"{scenario}_vs_block_time.pdf"),
        x_tick_labels=x_labels,
    )

    errorbar_plot(
        x_numeric,
        agg["missing_mean"].to_numpy(),
        agg["missing_std"].fillna(0).to_numpy(),
        xlabel,
        "Missing finalization intervals",
        f"{scenario.capitalize()} vs Missing Finalization Intervals",
        os.path.join(out_dir, f"{scenario}_vs_missing_finalization.pdf"),
        x_tick_labels=x_labels,
    )

    errorbar_plot(
        x_numeric,
        agg["stall_duration_mean"].to_numpy(),
        agg["stall_duration_std"].fillna(0).to_numpy(),
        xlabel,
        "Total stall duration (s)",
        f"{scenario.capitalize()} vs Stall Duration",
        os.path.join(out_dir, f"{scenario}_vs_stall_duration.pdf"),
        x_tick_labels=x_labels,
    )

    errorbar_plot(
        x_numeric,
        agg["delayed_mean"].to_numpy(),
        agg["delayed_std"].fillna(0).to_numpy(),
        xlabel,
        "Delayed finalization events",
        f"{scenario.capitalize()} vs Delayed Finalization Events",
        os.path.join(out_dir, f"{scenario}_vs_delayed_finalization.pdf"),
        x_tick_labels=x_labels,
    )

    errorbar_plot(
        x_numeric,
        agg["txpb_mean"].to_numpy(),
        agg["txpb_std"].fillna(0).to_numpy(),
        xlabel,
        "Transactions per block (mean)",
        f"{scenario.capitalize()} vs Transactions per Block",
        os.path.join(out_dir, f"{scenario}_vs_tx_per_block.pdf"),
        x_tick_labels=x_labels,
    )

    phase_lines_plot(
        grouped_df=agg,
        x_col=x_col,
        xlabel=xlabel,
        ylabel="Mean block time (s)",
        title=f"{scenario.capitalize()} vs Block Time by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_phase_block_time.pdf"),
        baseline_mean_col="baseline_phase_bt_mean",
        baseline_std_col="baseline_phase_bt_std",
        stress_mean_col="stress_phase_bt_mean",
        stress_std_col="stress_phase_bt_std",
        recovery_mean_col="recovery_phase_bt_mean",
        recovery_std_col="recovery_phase_bt_std",
        x_tick_labels=x_labels,
    )

    phase_lines_plot(
        grouped_df=agg,
        x_col=x_col,
        xlabel=xlabel,
        ylabel="Chain growth rate (blocks/s)",
        title=f"{scenario.capitalize()} vs Chain Growth Rate by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_phase_cgr.pdf"),
        baseline_mean_col="baseline_phase_cgr_mean",
        baseline_std_col="baseline_phase_cgr_std",
        stress_mean_col="stress_phase_cgr_mean",
        stress_std_col="stress_phase_cgr_std",
        recovery_mean_col="recovery_phase_cgr_mean",
        recovery_std_col="recovery_phase_cgr_std",
        x_tick_labels=x_labels,
    )

    phase_lines_plot(
        grouped_df=agg,
        x_col=x_col,
        xlabel=xlabel,
        ylabel="Missing finalization intervals",
        title=f"{scenario.capitalize()} vs Missing Finalization by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_phase_missing_finalization.pdf"),
        baseline_mean_col="baseline_phase_missing_mean",
        baseline_std_col="baseline_phase_missing_std",
        stress_mean_col="stress_phase_missing_mean",
        stress_std_col="stress_phase_missing_std",
        recovery_mean_col="recovery_phase_missing_mean",
        recovery_std_col="recovery_phase_missing_std",
        x_tick_labels=x_labels,
    )

    phase_lines_plot(
        grouped_df=agg,
        x_col=x_col,
        xlabel=xlabel,
        ylabel="Stall duration (s)",
        title=f"{scenario.capitalize()} vs Stall Duration by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_phase_stall_duration.pdf"),
        baseline_mean_col="baseline_phase_stall_duration_mean",
        baseline_std_col="baseline_phase_stall_duration_std",
        stress_mean_col="stress_phase_stall_duration_mean",
        stress_std_col="stress_phase_stall_duration_std",
        recovery_mean_col="recovery_phase_stall_duration_mean",
        recovery_std_col="recovery_phase_stall_duration_std",
        x_tick_labels=x_labels,
    )

    phase_lines_plot(
        grouped_df=agg,
        x_col=x_col,
        xlabel=xlabel,
        ylabel="Transactions per block (mean)",
        title=f"{scenario.capitalize()} vs Transactions per Block by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_phase_tx_per_block.pdf"),
        baseline_mean_col="baseline_phase_txpb_mean",
        baseline_std_col="baseline_phase_txpb_std",
        stress_mean_col="stress_phase_txpb_mean",
        stress_std_col="stress_phase_txpb_std",
        recovery_mean_col="recovery_phase_txpb_mean",
        recovery_std_col="recovery_phase_txpb_std",
        x_tick_labels=x_labels,
    )


def plot_combined(df: pd.DataFrame, out_dir: str, bw_order: List[str]):
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
            missing_mean=("missing_finalization_interval_count", "mean"),
            missing_std=("missing_finalization_interval_count", "std"),
            stall_duration_mean=("stall_duration_total_s", "mean"),
            stall_duration_std=("stall_duration_total_s", "std"),
        )
        .reset_index()
    )

    agg["_bw_order"] = agg["bandwidth"].map(lambda v: bandwidth_sort_key(v, bw_order))
    agg = agg.sort_values(["latency_ms", "_bw_order", "bandwidth"]).drop(columns="_bw_order")
    agg.to_csv(os.path.join(out_dir, "aggregated_combined.csv"), index=False)

    plt.figure()
    for bw in agg["bandwidth"].dropna().unique():
        sub_bw = agg[agg["bandwidth"] == bw].sort_values("latency_ms")
        x = np.arange(len(sub_bw))
        y = sub_bw["cgr_mean"].to_numpy()
        yerr = np.array([safe_std(v) for v in sub_bw["cgr_std"].to_numpy()])
        labels = sub_bw["latency_ms"].astype(str).tolist()
        plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3, label=str(bw))
        plt.xticks(x, labels, rotation=25, ha="right")
    plt.xlabel("Latency (ms)")
    plt.ylabel("Chain growth rate (blocks/s)")
    plt.title("Combined Stress: Latency and Bandwidth vs Chain Growth Rate")
    plt.legend()
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(os.path.join(out_dir, "combined_latency_bandwidth_vs_cgr.pdf"))
    plt.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-root", default="experiments/plots")
    ap.add_argument(
        "--scenario",
        default="all",
        choices=["all", "baseline", "latency", "packetloss", "bandwidth", "offline", "combined"],
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
        "packet_loss_pct",
        "offline_n",
        "blocks_observed",
        "raw_blocks_observed",
        "analysis_start_offset_s",
        "analysis_start_block",
        "block_time_mean_s",
        "block_time_variance",
        "max_interblock_gap_s",
        "stall_threshold_s",
        "baseline_median_block_time_s",
        "baseline_p95_block_time_s",
        "baseline_analysis_start_block",
        "k",
        "block_period_s",
        "stall_event_count",
        "stall_ratio",
        "stall_duration_total_s",
        "missing_finalization_interval_threshold_s",
        "missing_finalization_interval_count",
        "delayed_finalization_threshold_s",
        "delayed_finalization_event_count",
        "chain_growth_rate_blocks_per_s_windowed",
        "chain_growth_window_s",
        "tx_total",
        "tx_per_block_mean",
        "tx_per_block_median",
        "tx_per_block_p95",
        "tx_per_block_max",
        "baseline_phase_blocks_observed",
        "baseline_phase_block_time_mean_s",
        "baseline_phase_block_time_median_s",
        "baseline_phase_block_time_p95_s",
        "baseline_phase_max_interblock_gap_s",
        "baseline_phase_chain_growth_rate_blocks_per_s_windowed",
        "baseline_phase_tx_total",
        "baseline_phase_tx_per_block_mean",
        "baseline_phase_stall_event_count",
        "baseline_phase_stall_duration_total_s",
        "baseline_phase_missing_finalization_interval_count",
        "stress_phase_blocks_observed",
        "stress_phase_block_time_mean_s",
        "stress_phase_block_time_median_s",
        "stress_phase_block_time_p95_s",
        "stress_phase_max_interblock_gap_s",
        "stress_phase_chain_growth_rate_blocks_per_s_windowed",
        "stress_phase_tx_total",
        "stress_phase_tx_per_block_mean",
        "stress_phase_stall_event_count",
        "stress_phase_stall_duration_total_s",
        "stress_phase_missing_finalization_interval_count",
        "recovery_phase_blocks_observed",
        "recovery_phase_block_time_mean_s",
        "recovery_phase_block_time_median_s",
        "recovery_phase_block_time_p95_s",
        "recovery_phase_max_interblock_gap_s",
        "recovery_phase_chain_growth_rate_blocks_per_s_windowed",
        "recovery_phase_tx_total",
        "recovery_phase_tx_per_block_mean",
        "recovery_phase_stall_event_count",
        "recovery_phase_stall_duration_total_s",
        "recovery_phase_missing_finalization_interval_count",
    ]
    df = coerce_numeric(df, numeric_cols)

    only_ok = False if args.include_nonok else bool(args.only_ok)
    if only_ok and "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    bw_order = [s.strip().lower() for s in args.bw_order.split(",") if s.strip()]

    if args.scenario in ("all", "baseline"):
        plot_baseline_summary(df, out_dir)

    if args.scenario in ("all", "latency"):
        plot_scenario_family(
            df=df,
            out_dir=out_dir,
            scenario="latency",
            x_col="latency_ms",
            xlabel="Latency (ms)",
            sort_kind="numeric",
        )

    if args.scenario in ("all", "packetloss"):
        plot_scenario_family(
            df=df,
            out_dir=out_dir,
            scenario="packetloss",
            x_col="packet_loss_pct",
            xlabel="Packet loss (%)",
            sort_kind="numeric",
        )

    if args.scenario in ("all", "bandwidth"):
        plot_scenario_family(
            df=df,
            out_dir=out_dir,
            scenario="bandwidth",
            x_col="bandwidth",
            xlabel="Bandwidth limit",
            sort_kind="bandwidth",
            bw_order=bw_order,
        )

    if args.scenario in ("all", "offline"):
        plot_scenario_family(
            df=df,
            out_dir=out_dir,
            scenario="offline",
            x_col="offline_n",
            xlabel="Offline validators",
            sort_kind="numeric",
        )

    if args.scenario in ("all", "combined"):
        plot_combined(df, out_dir, bw_order)

    print(out_dir)


if __name__ == "__main__":
    main()