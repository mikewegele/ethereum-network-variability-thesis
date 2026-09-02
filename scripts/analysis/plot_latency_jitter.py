import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.ticker import MaxNLocator


def load_data(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df[df["scenario"] == "latency_jitter"].copy()

    numeric_cols = [
        "latency_jitter_ms",
        "stress_phase_chain_growth_rate_blocks_per_s_windowed",
        "stress_phase_block_time_mean_s",
        "stress_phase_stall_duration_total_s",
        "stress_phase_missing_finalization_interval_count",
        "stress_phase_missing_share",
        "stress_phase_stall_share",
    ]

    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    return df


def plot_metric(
    df: pd.DataFrame,
    out_dir: Path,
    y_col: str,
    filename_base: str,
    title: str,
    ylabel: str,
    reference_lines: list[tuple[float, str, str]],
) -> None:
    x_col = "latency_jitter_ms"

    fig, ax = plt.subplots(figsize=(8, 4.8))

    for jitter, sub in df.groupby(x_col):
        ax.scatter([jitter] * len(sub), sub[y_col], alpha=0.8)

    med = df.groupby(x_col)[y_col].median().reset_index()
    ax.plot(med[x_col], med[y_col], marker="o", linewidth=1.5, label="median")

    for y, linestyle, label in reference_lines:
        ax.axhline(y, linestyle=linestyle, linewidth=1, label=label)

    ax.set_title(title)
    ax.set_xlabel("Delay variation around 3000 ms mean latency (ms)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(sorted(df[x_col].dropna().unique()))
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    fig.tight_layout()
    fig.savefig(out_dir / f"{filename_base}.pdf")
    fig.savefig(out_dir / f"{filename_base}.png", dpi=200)
    plt.close(fig)


def plot_regime_distribution(df: pd.DataFrame, out_dir: Path) -> None:
    x_col = "latency_jitter_ms"

    if "stress_phase_regime" not in df.columns:
        return

    sub = df.dropna(subset=[x_col, "stress_phase_regime"]).copy()

    if sub.empty:
        return

    counts = (
        sub.groupby([x_col, "stress_phase_regime"])
        .size()
        .unstack(fill_value=0)
    )

    for regime in ["stable", "degraded", "stalled"]:
        if regime not in counts.columns:
            counts[regime] = 0

    counts = counts[["stable", "degraded", "stalled"]]
    counts = counts.sort_index()

    x = range(len(counts))
    labels = [str(int(v)) for v in counts.index]

    stable = counts["stable"]
    degraded = counts["degraded"]
    stalled = counts["stalled"]

    fig, ax = plt.subplots(figsize=(11.5, 6.2))

    ax.bar(x, stable, label="Stable", color="tab:green", alpha=0.82)
    ax.bar(x, degraded, bottom=stable, label="Degraded", color="tab:orange", alpha=0.82)
    ax.bar(
        x,
        stalled,
        bottom=stable + degraded,
        label="Stalled",
        color="tab:red",
        alpha=0.82,
    )

    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right")
    ax.set_xlabel("Delay variation around 3000 ms mean latency (ms)")
    ax.set_ylabel("Number of runs")
    ax.set_title("Latency Variation: Number of Runs by Stability Regime")
    ax.grid(True, axis="y", linestyle="--", linewidth=0.5, alpha=0.5)
    ax.legend(loc="upper left")
    ax.yaxis.set_major_locator(MaxNLocator(integer=True))

    fig.tight_layout()
    fig.savefig(out_dir / "latency_jitter_regime_distribution_bar_counts.pdf")
    fig.savefig(out_dir / "latency_jitter_regime_distribution_bar_counts.png", dpi=200)
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        default="experiments/exports/jitter_series/summary.csv",
    )
    parser.add_argument(
        "--out-dir",
        default="experiments/plots/jitter_series",
    )
    args = parser.parse_args()

    csv_path = Path(args.csv)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = load_data(csv_path)

    plot_metric(
        df=df,
        out_dir=out_dir,
        y_col="stress_phase_chain_growth_rate_blocks_per_s_windowed",
        filename_base="latency_jitter_chain_growth_scatter",
        title="Stress-phase chain growth under latency variation",
        ylabel="60 s windowed chain growth rate (blocks/s)",
        reference_lines=[
            (0.5, "--", "nominal rate"),
            (0.25, ":", "stalled-growth threshold"),
        ],
    )

    plot_metric(
        df=df,
        out_dir=out_dir,
        y_col="stress_phase_block_time_mean_s",
        filename_base="latency_jitter_interblock_time_scatter",
        title="Stress-phase inter-block time under latency variation",
        ylabel="Mean inter-block time (s)",
        reference_lines=[
            (2.0, "--", "configured block period"),
        ],
    )

    plot_regime_distribution(df=df, out_dir=out_dir)

    print(out_dir / "latency_jitter_chain_growth_scatter.pdf")
    print(out_dir / "latency_jitter_interblock_time_scatter.pdf")
    print(out_dir / "latency_jitter_regime_distribution_bar_counts.pdf")


if __name__ == "__main__":
    main()