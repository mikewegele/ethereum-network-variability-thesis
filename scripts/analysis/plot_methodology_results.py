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
    "24kbit",
    "16kbit",
    "12kbit",
    "8kbit",
]


SCENARIO_LABELS = {
    "latency": "Latency (ms)",
    "packetloss": "Packet loss (%)",
    "bandwidth": "Bandwidth limit",
    "offline": "Offline validators",
}


def ensure_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


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


def get_x_config(df: pd.DataFrame, scenario: str, bw_order):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return None, None, None

    if scenario == "latency":
        x_col = "latency_ms"
        levels = sorted(sub[x_col].dropna().unique())
        x_positions = {v: v for v in levels}
        x_tick_positions = levels
        x_tick_labels = [str(int(v)) for v in levels]

        return x_col, x_positions, (x_tick_positions, x_tick_labels)

    if scenario == "packetloss":
        x_col = "packet_loss_pct"
        levels = sorted(sub[x_col].dropna().unique())
        x_positions = {v: v for v in levels}
        x_tick_positions = levels
        x_tick_labels = [str(int(v)) for v in levels]

        return x_col, x_positions, (x_tick_positions, x_tick_labels)

    if scenario == "offline":
        x_col = "offline_n"
        levels = sorted(sub[x_col].dropna().unique())
        x_positions = {v: v for v in levels}
        x_tick_positions = levels
        x_tick_labels = [str(int(v)) for v in levels]

        return x_col, x_positions, (x_tick_positions, x_tick_labels)

    if scenario == "bandwidth":
        x_col = "bandwidth"
        levels = sorted(
            sub[x_col].dropna().astype(str).str.lower().unique(),
            key=lambda v: bandwidth_sort_key(v, bw_order),
        )
        x_positions = {v: i for i, v in enumerate(levels)}
        x_tick_positions = list(range(len(levels)))
        x_tick_labels = levels

        return x_col, x_positions, (x_tick_positions, x_tick_labels)

    return None, None, None


def aggregate_median_iqr(sub: pd.DataFrame, x_col: str, metric_col: str) -> pd.DataFrame:
    agg = (
        sub.groupby(x_col)[metric_col]
        .agg(
            median="median",
            q1=lambda s: s.quantile(0.25),
            q3=lambda s: s.quantile(0.75),
            count="count",
        )
        .reset_index()
        .dropna(subset=["median"])
    )

    return agg


def get_jitter_width(scenario: str, x_positions) -> float:
    if scenario == "bandwidth":
        return 0.12

    if scenario == "offline":
        return 0.035

    levels = sorted([float(v) for v in x_positions.values()])

    if len(levels) > 1:
        min_step = min(abs(b - a) for a, b in zip(levels, levels[1:]))
        return min_step * 0.06

    return 0.1


def save_single_metric_plot(
    df: pd.DataFrame,
    scenario: str,
    metric_col: str,
    ylabel: str,
    title: str,
    out_path: str,
    bw_order,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty or metric_col not in sub.columns:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    agg = aggregate_median_iqr(sub, x_col, metric_col)

    if agg.empty:
        return

    if scenario == "bandwidth":
        agg[x_col] = agg[x_col].astype(str).str.lower()

    agg["_x"] = agg[x_col].map(x_positions)
    agg = agg.sort_values("_x")

    x = agg["_x"].to_numpy(dtype=float)
    median = agg["median"].to_numpy(dtype=float)
    q1 = agg["q1"].to_numpy(dtype=float)
    q3 = agg["q3"].to_numpy(dtype=float)

    plt.figure(figsize=(10.5, 5.8))
    plt.plot(x, median, linewidth=2.2)
    plt.fill_between(x, q1, q3, alpha=0.2)
    plt.scatter(x, median, s=28)

    tick_positions, tick_labels = tick_cfg
    plt.xticks(
        tick_positions,
        tick_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )
    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_single_metric_plot_with_points(
    df: pd.DataFrame,
    scenario: str,
    metric_col: str,
    ylabel: str,
    title: str,
    out_path: str,
    bw_order,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty or metric_col not in sub.columns:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    agg = aggregate_median_iqr(sub, x_col, metric_col)

    if agg.empty:
        return

    if scenario == "bandwidth":
        sub[x_col] = sub[x_col].astype(str).str.lower()
        agg[x_col] = agg[x_col].astype(str).str.lower()

    sub["_x"] = sub[x_col].map(x_positions)
    agg["_x"] = agg[x_col].map(x_positions)

    sub = sub.dropna(subset=["_x", metric_col]).copy()
    agg = agg.dropna(subset=["_x"]).sort_values("_x")

    if sub.empty or agg.empty:
        return

    x = agg["_x"].to_numpy(dtype=float)
    median = agg["median"].to_numpy(dtype=float)
    q1 = agg["q1"].to_numpy(dtype=float)
    q3 = agg["q3"].to_numpy(dtype=float)

    rng = np.random.default_rng(42)
    jitter_width = get_jitter_width(scenario, x_positions)

    point_x = sub["_x"].to_numpy(dtype=float)
    point_y = sub[metric_col].to_numpy(dtype=float)
    jitter = rng.uniform(-jitter_width, jitter_width, size=len(point_x))

    plt.figure(figsize=(10.5, 5.8))
    plt.scatter(point_x + jitter, point_y, s=24, alpha=0.55)
    plt.plot(x, median, linewidth=2.2)
    plt.fill_between(x, q1, q3, alpha=0.2)
    plt.scatter(x, median, s=38)

    tick_positions, tick_labels = tick_cfg
    plt.xticks(
        tick_positions,
        tick_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )
    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_phase_metric_plot(
    df: pd.DataFrame,
    scenario: str,
    phase_metric_specs,
    ylabel: str,
    title: str,
    out_path: str,
    bw_order,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    plt.figure(figsize=(10.5, 5.8))
    plotted_any = False

    for label, metric_col in phase_metric_specs:
        if metric_col not in sub.columns:
            continue

        agg = aggregate_median_iqr(sub, x_col, metric_col)

        if agg.empty:
            continue

        if scenario == "bandwidth":
            agg[x_col] = agg[x_col].astype(str).str.lower()

        agg["_x"] = agg[x_col].map(x_positions)
        agg = agg.sort_values("_x")

        x = agg["_x"].to_numpy(dtype=float)
        median = agg["median"].to_numpy(dtype=float)
        q1 = agg["q1"].to_numpy(dtype=float)
        q3 = agg["q3"].to_numpy(dtype=float)

        plt.plot(x, median, linewidth=2.2, label=label)
        plt.fill_between(x, q1, q3, alpha=0.15)
        plt.scatter(x, median, s=24)
        plotted_any = True

    if not plotted_any:
        plt.close()
        return

    tick_positions, tick_labels = tick_cfg
    plt.xticks(
        tick_positions,
        tick_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )
    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_phase_metric_boxplot(
    df: pd.DataFrame,
    scenario: str,
    phase_metric_specs,
    ylabel: str,
    title: str,
    out_path: str,
    bw_order,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    phase_offsets = [-0.22, 0.0, 0.22]
    width = 0.18

    plt.figure(figsize=(11.5, 6.2))
    plotted_any = False

    for (label, metric_col), offset in zip(phase_metric_specs, phase_offsets):
        if metric_col not in sub.columns:
            continue

        phase_sub = sub[[x_col, metric_col]].dropna().copy()

        if phase_sub.empty:
            continue

        if scenario == "bandwidth":
            phase_sub[x_col] = phase_sub[x_col].astype(str).str.lower()

        grouped = []
        positions = []

        for level, xpos in sorted(x_positions.items(), key=lambda kv: kv[1]):
            vals = phase_sub.loc[phase_sub[x_col] == level, metric_col].dropna().tolist()

            if len(vals) == 0:
                continue

            grouped.append(vals)
            positions.append(xpos + offset)

        if not grouped:
            continue

        bp = plt.boxplot(
            grouped,
            positions=positions,
            widths=width,
            patch_artist=True,
            manage_ticks=False,
            showfliers=True,
        )

        color = None

        if label.lower() == "baseline":
            color = "tab:blue"
        elif label.lower() == "stress":
            color = "tab:orange"
        elif label.lower() == "recovery":
            color = "tab:green"
        else:
            color = "tab:gray"

        for box in bp["boxes"]:
            box.set(facecolor=color, alpha=0.28, edgecolor=color, linewidth=1.6)

        for whisker in bp["whiskers"]:
            whisker.set(color=color, linewidth=1.3)

        for cap in bp["caps"]:
            cap.set(color=color, linewidth=1.3)

        for median in bp["medians"]:
            median.set(color=color, linewidth=2.0)

        for flier in bp["fliers"]:
            flier.set(
                marker="o",
                markersize=4,
                markerfacecolor=color,
                markeredgecolor=color,
                alpha=0.7,
            )

        plt.plot([], [], color=color, linewidth=2.2, label=label)
        plotted_any = True

    if not plotted_any:
        plt.close()
        return

    tick_positions, tick_labels = tick_cfg
    plt.xticks(
        tick_positions,
        tick_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )
    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_phase_metric_scatter(
    df: pd.DataFrame,
    scenario: str,
    phase_metric_specs,
    ylabel: str,
    title: str,
    out_path: str,
    bw_order,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    phase_offsets = [-0.22, 0.0, 0.22]
    rng = np.random.default_rng(42)

    plt.figure(figsize=(11.5, 6.2))
    plotted_any = False

    for (label, metric_col), offset in zip(phase_metric_specs, phase_offsets):
        if metric_col not in sub.columns:
            continue

        phase_sub = sub[[x_col, metric_col]].dropna().copy()

        if phase_sub.empty:
            continue

        if scenario == "bandwidth":
            phase_sub[x_col] = phase_sub[x_col].astype(str).str.lower()

        phase_sub["_x"] = phase_sub[x_col].map(x_positions)
        phase_sub = phase_sub.dropna(subset=["_x", metric_col])

        if phase_sub.empty:
            continue

        point_x = phase_sub["_x"].to_numpy(dtype=float)
        point_y = phase_sub[metric_col].to_numpy(dtype=float)
        jitter = rng.uniform(-0.04, 0.04, size=len(point_x))

        if label.lower() == "baseline":
            color = "tab:blue"
        elif label.lower() == "stress":
            color = "tab:orange"
        elif label.lower() == "recovery":
            color = "tab:green"
        else:
            color = "tab:gray"

        plt.scatter(point_x + offset + jitter, point_y, s=20, alpha=0.5, label=label, color=color)
        plotted_any = True

    if not plotted_any:
        plt.close()
        return

    tick_positions, tick_labels = tick_cfg
    plt.xticks(
        tick_positions,
        tick_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )
    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def make_scenario_plots(df: pd.DataFrame, scenario: str, out_dir: str, bw_order):
    os.makedirs(out_dir, exist_ok=True)

    save_single_metric_plot(
        df=df,
        scenario=scenario,
        metric_col="stress_phase_block_time_mean_s",
        ylabel="Median inter-block time (s)",
        title=f"{scenario.capitalize()} vs Stress Inter-Block Time",
        out_path=os.path.join(out_dir, f"{scenario}_stress_interblock_time_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot_with_points(
        df=df,
        scenario=scenario,
        metric_col="stress_phase_block_time_mean_s",
        ylabel="Stress-phase inter-block time (s)",
        title=f"{scenario.capitalize()} vs Stress Inter-Block Time with Individual Runs",
        out_path=os.path.join(out_dir, f"{scenario}_stress_interblock_time_points_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_phase_metric_plot(
        df=df,
        scenario=scenario,
        phase_metric_specs=[
            ("Baseline", "baseline_phase_stall_duration_total_s"),
            ("Stress", "stress_phase_stall_duration_total_s"),
            ("Recovery", "recovery_phase_stall_duration_total_s"),
        ],
        ylabel="Median stall duration (s)",
        title=f"{scenario.capitalize()} vs Stall Duration by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_stall_duration_by_phase_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot_with_points(
        df=df,
        scenario=scenario,
        metric_col="stress_phase_stall_duration_total_s",
        ylabel="Stress-phase stall duration (s)",
        title=f"{scenario.capitalize()} vs Stress Stall Duration with Individual Runs",
        out_path=os.path.join(out_dir, f"{scenario}_stress_stall_duration_points_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_phase_metric_boxplot(
        df=df,
        scenario=scenario,
        phase_metric_specs=[
            ("Baseline", "baseline_phase_missing_finalization_interval_count"),
            ("Stress", "stress_phase_missing_finalization_interval_count"),
            ("Recovery", "recovery_phase_missing_finalization_interval_count"),
        ],
        ylabel="Missing-finalization intervals",
        title=f"{scenario.capitalize()} vs Missing Finalization by Phase",
        out_path=os.path.join(out_dir, f"{scenario}_missing_finalization_by_phase_boxplot.pdf"),
        bw_order=bw_order,
    )

    save_phase_metric_scatter(
        df=df,
        scenario=scenario,
        phase_metric_specs=[
            ("Baseline", "baseline_phase_missing_finalization_interval_count"),
            ("Stress", "stress_phase_missing_finalization_interval_count"),
            ("Recovery", "recovery_phase_missing_finalization_interval_count"),
        ],
        ylabel="Missing-finalization intervals",
        title=f"{scenario.capitalize()} vs Missing Finalization by Phase with Individual Runs",
        out_path=os.path.join(out_dir, f"{scenario}_missing_finalization_by_phase_points.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot(
        df=df,
        scenario=scenario,
        metric_col="stress_phase_chain_growth_rate_blocks_per_s_windowed",
        ylabel="Median chain growth rate (blocks/s)",
        title=f"{scenario.capitalize()} vs Stress Chain Growth Rate",
        out_path=os.path.join(out_dir, f"{scenario}_stress_chain_growth_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot_with_points(
        df=df,
        scenario=scenario,
        metric_col="stress_phase_chain_growth_rate_blocks_per_s_windowed",
        ylabel="Stress-phase chain growth rate (blocks/s)",
        title=f"{scenario.capitalize()} vs Stress Chain Growth Rate with Individual Runs",
        out_path=os.path.join(out_dir, f"{scenario}_stress_chain_growth_points_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot(
        df=df,
        scenario=scenario,
        metric_col="delayed_finalization_event_count",
        ylabel="Median delayed finalization events",
        title=f"{scenario.capitalize()} vs Delayed Finalization Events",
        out_path=os.path.join(out_dir, f"{scenario}_delayed_finalization_median_iqr.pdf"),
        bw_order=bw_order,
    )

    save_single_metric_plot_with_points(
        df=df,
        scenario=scenario,
        metric_col="delayed_finalization_event_count",
        ylabel="Delayed finalization events",
        title=f"{scenario.capitalize()} vs Delayed Finalization Events with Individual Runs",
        out_path=os.path.join(out_dir, f"{scenario}_delayed_finalization_points_median_iqr.pdf"),
        bw_order=bw_order,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-root", default="experiments/plots/final_series/methodology")
    ap.add_argument(
        "--scenario",
        default="all",
        choices=["all", "latency", "packetloss", "bandwidth", "offline"],
    )
    ap.add_argument("--bw-order", default=",".join(DEFAULT_BW_ORDER))
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    df = ensure_numeric(
        df,
        [
            "latency_ms",
            "packet_loss_pct",
            "offline_n",
            "stress_phase_block_time_mean_s",
            "baseline_phase_stall_duration_total_s",
            "stress_phase_stall_duration_total_s",
            "recovery_phase_stall_duration_total_s",
            "baseline_phase_missing_finalization_interval_count",
            "stress_phase_missing_finalization_interval_count",
            "recovery_phase_missing_finalization_interval_count",
            "stress_phase_chain_growth_rate_blocks_per_s_windowed",
            "delayed_finalization_event_count",
        ],
    )

    if "bandwidth" in df.columns:
        df["bandwidth"] = df["bandwidth"].astype(str).str.lower()

    bw_order = [s.strip().lower() for s in args.bw_order.split(",") if s.strip()]
    scenarios = ["latency", "packetloss", "bandwidth", "offline"] if args.scenario == "all" else [args.scenario]

    for scenario in scenarios:
        make_scenario_plots(
            df=df,
            scenario=scenario,
            out_dir=os.path.join(args.out_root, scenario),
            bw_order=bw_order,
        )

    print(args.out_root)


if __name__ == "__main__":
    main()