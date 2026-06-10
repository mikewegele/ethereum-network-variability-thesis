import os

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.ticker import MaxNLocator

from plot_utils import (
    SCENARIO_LABELS,
    aggregate_median_iqr,
    get_jitter_width,
    get_x_config,
)


def apply_axis_formatting(scenario, tick_cfg, ylabel, title):
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


def get_phase_color(label: str) -> str:
    lower = label.lower()

    if lower == "baseline":
        return "tab:blue"

    if lower == "stress":
        return "tab:orange"

    if lower == "recovery":
        return "tab:green"

    return "tab:gray"


def get_scenario_title(scenario):
    return {
        "latency": "Latency",
        "packetloss": "Packet Loss",
        "bandwidth": "Bandwidth",
        "partition": "Network Partition",
    }.get(scenario, scenario.capitalize())


def save_single_metric_plot(df, scenario, metric_col, ylabel, title, out_path, bw_order):
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
    plt.scatter(x, median, s=24)

    apply_axis_formatting(scenario, tick_cfg, ylabel, title)

    plt.savefig(out_path)
    plt.close()


def save_single_metric_scatter_only(
    df,
    scenario,
    metric_col,
    ylabel,
    title,
    out_path,
    bw_order,
    reference_line_y=None,
    reference_line_label=None,
):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty or metric_col not in sub.columns:
        return

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return

    if scenario == "bandwidth":
        sub[x_col] = sub[x_col].astype(str).str.lower()

    sub["_x"] = sub[x_col].map(x_positions)
    sub = sub.dropna(subset=["_x", metric_col]).copy()

    if sub.empty:
        return

    rng = np.random.default_rng(42)
    jitter_width = get_jitter_width(scenario, x_positions)

    point_x = sub["_x"].to_numpy(dtype=float)
    point_y = sub[metric_col].to_numpy(dtype=float)
    jitter = rng.uniform(-jitter_width, jitter_width, size=len(point_x))

    plt.figure(figsize=(10.5, 5.8))
    plt.scatter(point_x + jitter, point_y, s=22, alpha=0.62)

    if reference_line_y is not None:
        plt.axhline(
            reference_line_y,
            linestyle="--",
            linewidth=1.0,
            alpha=0.75,
            label=reference_line_label,
        )
        if reference_line_label:
            plt.legend()

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
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_phase_metric_plot(df, scenario, phase_metric_specs, ylabel, title, out_path, bw_order):
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

    apply_axis_formatting(scenario, tick_cfg, ylabel, title)
    plt.legend()

    plt.savefig(out_path)
    plt.close()


def save_phase_metric_boxplot(df, scenario, phase_metric_specs, ylabel, title, out_path, bw_order):
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

        color = get_phase_color(label)

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

    apply_axis_formatting(scenario, tick_cfg, ylabel, title)
    plt.legend()

    plt.savefig(out_path)
    plt.close()


def save_phase_metric_scatter(df, scenario, phase_metric_specs, ylabel, title, out_path, bw_order):
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
        color = get_phase_color(label)

        plt.scatter(
            point_x + offset + jitter,
            point_y,
            s=20,
            alpha=0.5,
            label=label,
            color=color,
        )
        plotted_any = True

    if not plotted_any:
        plt.close()
        return

    apply_axis_formatting(scenario, tick_cfg, ylabel, title)
    plt.legend()

    plt.savefig(out_path)
    plt.close()


def is_nan(value):
    try:
        return np.isnan(value)
    except TypeError:
        return True


def get_float(row, key):
    value = row.get(key)
    return None if is_nan(value) else float(value)


def classify_stability_regime(row):
    growth = get_float(row, "stress_phase_chain_growth_rate_blocks_per_s_windowed")
    stall_duration = get_float(row, "stress_phase_stall_duration_total_s")
    missing = get_float(row, "stress_phase_missing_finalization_interval_count")

    block_period_s = get_float(row, "block_period_s")
    if block_period_s is None or block_period_s <= 0:
        block_period_s = 2.0

    stress_duration_s = 180.0
    nominal_growth = 1.0 / block_period_s
    stalled_growth_threshold = 0.50 * nominal_growth
    expected_blocks = stress_duration_s / block_period_s

    missing_share = None
    if missing is not None and expected_blocks > 0:
        missing_share = missing / expected_blocks

    stall_share = None
    if stall_duration is not None and stress_duration_s > 0:
        stall_share = stall_duration / stress_duration_s

    if growth is not None and growth < stalled_growth_threshold:
        return "stalled"

    if missing_share is not None and missing_share >= 0.48:
        return "stalled"

    if stall_share is not None and stall_share >= (1.0 / 3.0):
        return "stalled"

    if (
        stall_duration is not None
        and missing is not None
        and stall_duration == 0
        and missing == 0
    ):
        return "stable"

    if growth is not None or stall_duration is not None or missing is not None:
        return "degraded"

    return None


def get_regime_counts(df, scenario, bw_order):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return None, None, None, None

    x_col, x_positions, tick_cfg = get_x_config(df, scenario, bw_order)

    if x_col is None:
        return None, None, None, None

    if scenario == "bandwidth":
        sub[x_col] = sub[x_col].astype(str).str.lower()

    if scenario == "partition":
        sub[x_col] = sub[x_col].astype(str)

    if "stress_phase_regime" in sub.columns:
        sub["regime"] = sub["stress_phase_regime"]
    else:
        required_cols = [
            "stress_phase_chain_growth_rate_blocks_per_s_windowed",
            "stress_phase_stall_duration_total_s",
            "stress_phase_missing_finalization_interval_count",
        ]

        for col in required_cols:
            if col not in sub.columns:
                return None, None, None, None

        sub["regime"] = sub.apply(classify_stability_regime, axis=1)

    sub = sub.dropna(subset=["regime", x_col]).copy()

    if sub.empty:
        return None, None, None, None

    counts = sub.groupby([x_col, "regime"]).size().unstack(fill_value=0)

    for regime in ["stable", "degraded", "stalled"]:
        if regime not in counts.columns:
            counts[regime] = 0

    counts = counts[["stable", "degraded", "stalled"]]

    if scenario == "bandwidth":
        counts.index = counts.index.astype(str).str.lower()
        ordered_levels = sorted(counts.index, key=lambda v: x_positions.get(v, 10**18))
        counts = counts.loc[ordered_levels]
        x = np.arange(len(counts))
        x_labels = [str(v) for v in counts.index]

    elif scenario == "partition":
        counts.index = counts.index.astype(str)
        ordered_levels = sorted(counts.index, key=lambda v: x_positions.get(v, 10**18))
        counts = counts.loc[ordered_levels]
        x = np.arange(len(counts))
        x_labels = [str(v) for v in counts.index]

    else:
        ordered_levels = sorted(counts.index, key=lambda v: x_positions.get(v, 10**18))
        counts = counts.loc[ordered_levels]
        x = counts.index.to_numpy(dtype=float)
        x_labels = [str(int(v)) for v in counts.index]

    return counts, x, x_labels, x_col


def save_regime_distribution_area_plot(df, scenario, out_path, bw_order, normalize=True):
    counts, x, x_labels, _ = get_regime_counts(df, scenario, bw_order)

    if counts is None:
        return

    values = counts.copy()

    if normalize:
        row_sums = values.sum(axis=1).replace(0, np.nan)
        values = values.div(row_sums, axis=0) * 100
        ylabel = "Share of runs (%)"
        title = f"{get_scenario_title(scenario)}: Share of Runs by Stability Regime"
    else:
        ylabel = "Number of runs"
        title = f"{get_scenario_title(scenario)}: Number of Runs by Stability Regime"

    stable = values["stable"].to_numpy(dtype=float)
    degraded = values["degraded"].to_numpy(dtype=float)
    stalled = values["stalled"].to_numpy(dtype=float)

    plt.figure(figsize=(11.5, 6.2))
    plt.stackplot(
        x,
        stable,
        degraded,
        stalled,
        labels=["Stable", "Degraded", "Stalled"],
        colors=["tab:green", "tab:orange", "tab:red"],
        alpha=0.82,
    )

    plt.xticks(
        x if scenario == "bandwidth" else x,
        x_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )

    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend(loc="upper left")
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def save_regime_distribution_bar_plot(df, scenario, out_path, bw_order, normalize=False):
    counts, x, x_labels, _ = get_regime_counts(df, scenario, bw_order)

    if counts is None:
        return

    values = counts.copy()

    if normalize:
        row_sums = values.sum(axis=1).replace(0, np.nan)
        values = values.div(row_sums, axis=0) * 100
        ylabel = "Share of runs (%)"
        title = f"{get_scenario_title(scenario)}: Share of Runs by Stability Regime"
    else:
        ylabel = "Number of runs"
        title = f"{get_scenario_title(scenario)}: Number of Runs by Stability Regime"

    stable = values["stable"].to_numpy(dtype=float)
    degraded = values["degraded"].to_numpy(dtype=float)
    stalled = values["stalled"].to_numpy(dtype=float)

    xpos = np.arange(len(values))

    plt.figure(figsize=(11.5, 6.2))
    plt.bar(xpos, stable, label="Stable", color="tab:green", alpha=0.82)
    plt.bar(xpos, degraded, bottom=stable, label="Degraded", color="tab:orange", alpha=0.82)
    plt.bar(
        xpos,
        stalled,
        bottom=stable + degraded,
        label="Stalled",
        color="tab:red",
        alpha=0.82,
    )

    totals = values.sum(axis=1).to_numpy(dtype=float)

    if normalize:
        plt.ylim(0, 100)
    else:
        plt.ylim(0, max(totals) + 1)

    plt.xticks(
        xpos,
        x_labels,
        rotation=35 if scenario == "bandwidth" else 30,
        ha="right",
    )

    plt.xlabel(SCENARIO_LABELS[scenario])
    plt.ylabel(ylabel)
    plt.title(title)
    plt.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)
    plt.legend(loc="upper left")

    if not normalize:
        ax = plt.gca()
        ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def make_scenario_plots(df, scenario, out_dir, bw_order):
    os.makedirs(out_dir, exist_ok=True)

    scenario_title = get_scenario_title(scenario)

    save_single_metric_plot(
        df,
        scenario,
        "stress_phase_block_time_mean_s",
        "Median stress-phase mean inter-block time (s)",
        f"{scenario_title} vs Stress-Phase Mean Inter-Block Time",
        os.path.join(out_dir, f"{scenario}_stress_interblock_time_median_iqr.pdf"),
        bw_order,
    )

    save_single_metric_scatter_only(
        df,
        scenario,
        "stress_phase_block_time_mean_s",
        "Stress-phase mean inter-block time (s)",
        f"{scenario_title} vs Stress-Phase Mean Inter-Block Time",
        os.path.join(out_dir, f"{scenario}_stress_interblock_time_scatter.pdf"),
        bw_order,
        reference_line_y=2.0,
        reference_line_label="Configured block period (2 s)",
    )

    save_phase_metric_plot(
        df,
        scenario,
        [
            ("Baseline", "baseline_phase_stall_duration_total_s"),
            ("Stress", "stress_phase_stall_duration_total_s"),
            ("Recovery", "recovery_phase_stall_duration_total_s"),
        ],
        "Median stall duration (s)",
        f"{scenario_title} vs Stall Duration by Phase",
        os.path.join(out_dir, f"{scenario}_stall_duration_by_phase_median_iqr.pdf"),
        bw_order,
    )

    save_single_metric_scatter_only(
        df,
        scenario,
        "stress_phase_stall_duration_total_s",
        "Stress-phase stall duration (s)",
        f"{scenario_title} vs Stress-Phase Stall Duration",
        os.path.join(out_dir, f"{scenario}_stress_stall_duration_scatter.pdf"),
        bw_order,
    )

    save_single_metric_plot(
        df,
        scenario,
        "stress_phase_chain_growth_rate_blocks_per_s_windowed",
        "Median stress-phase chain growth rate (blocks/s)",
        f"{scenario_title} vs Stress-Phase Chain Growth Rate",
        os.path.join(out_dir, f"{scenario}_stress_chain_growth_median_iqr.pdf"),
        bw_order,
    )

    save_single_metric_scatter_only(
        df,
        scenario,
        "stress_phase_chain_growth_rate_blocks_per_s_windowed",
        "Stress-phase chain growth rate (blocks/s)",
        f"{scenario_title} vs Stress-Phase Chain Growth Rate",
        os.path.join(out_dir, f"{scenario}_stress_chain_growth_scatter.pdf"),
        bw_order,
    )

    save_single_metric_scatter_only(
        df,
        scenario,
        "stress_phase_missing_finalization_interval_count",
        "Stress-phase missing finalization intervals",
        f"{scenario_title} vs Stress-Phase Missing Finalization Intervals",
        os.path.join(out_dir, f"{scenario}_stress_missing_finalization_scatter.pdf"),
        bw_order,
    )

    if "stress_phase_missing_share" in df.columns:
        save_single_metric_scatter_only(
            df,
            scenario,
            "stress_phase_missing_share",
            "Stress-phase missing finalization share",
            f"{scenario_title} vs Stress-Phase Missing Finalization Share",
            os.path.join(out_dir, f"{scenario}_stress_missing_finalization_share_scatter.pdf"),
            bw_order,
            reference_line_y=0.48,
            reference_line_label="Stalled threshold (0.48)",
        )

    if "stress_phase_stall_share" in df.columns:
        save_single_metric_scatter_only(
            df,
            scenario,
            "stress_phase_stall_share",
            "Stress-phase stall share",
            f"{scenario_title} vs Stress-Phase Stall Share",
            os.path.join(out_dir, f"{scenario}_stress_stall_share_scatter.pdf"),
            bw_order,
            reference_line_y=1.0 / 3.0,
            reference_line_label="Stalled threshold (1/3)",
        )

    save_regime_distribution_area_plot(
        df,
        scenario,
        os.path.join(out_dir, f"{scenario}_regime_distribution_area_percent.pdf"),
        bw_order,
        normalize=True,
    )

    save_regime_distribution_bar_plot(
        df,
        scenario,
        os.path.join(out_dir, f"{scenario}_regime_distribution_bar_counts.pdf"),
        bw_order,
        normalize=False,
    )