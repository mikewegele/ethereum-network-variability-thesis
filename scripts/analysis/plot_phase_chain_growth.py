import argparse
import json
import re
from dataclasses import dataclass
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


NOMINAL_RATE = 0.5
STALLED_GROWTH_THRESHOLD = 0.25


@dataclass(frozen=True)
class PhaseConfig:
    warmup_s: float
    baseline_s: float
    stress_s: float
    recovery_s: float
    plot_start_s: float

    @property
    def stress_start_s(self) -> float:
        return self.warmup_s + self.baseline_s

    @property
    def stress_end_s(self) -> float:
        return self.stress_start_s + self.stress_s

    @property
    def run_end_s(self) -> float:
        return self.stress_end_s + self.recovery_s


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def read_jsonl(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()

    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return pd.DataFrame(rows)


def infer_level_from_name(run_name: str, scenario: str):
    name = run_name.lower()

    if scenario == "latency":
        match = re.search(r"lat_(\d+)ms", name)
        return int(match.group(1)) if match else None

    if scenario == "bandwidth":
        match = re.search(r"bw_([^_]+)_rep", name)
        return match.group(1).lower() if match else None

    if scenario == "partition":
        match = re.search(r"partition_([0-9]+[-_][0-9]+)_rep", name)
        return match.group(1).replace("_", "-") if match else None

    return None


def list_run_dirs(root: Path, scenario: str, level) -> list[Path]:
    scenario_dir = root / scenario

    if not scenario_dir.exists():
        raise FileNotFoundError(f"Scenario directory not found: {scenario_dir}")

    run_dirs = []

    for run_dir in sorted(scenario_dir.iterdir()):
        if not run_dir.is_dir():
            continue

        inferred_level = infer_level_from_name(run_dir.name, scenario)

        if str(inferred_level).lower() != str(level).lower():
            continue

        has_blocks = (run_dir / "rpc" / "blocks.jsonl").exists()
        has_head = (run_dir / "rpc" / "head.jsonl").exists()

        if has_blocks or has_head:
            run_dirs.append(run_dir)

    return run_dirs


def get_run_start(run_dir: Path) -> float:
    run_meta = read_json(run_dir / "rpc" / "run_meta.json")
    ts_start = run_meta.get("ts_start_local")

    if ts_start is None:
        raise ValueError(f"Missing ts_start_local in {run_dir / 'rpc' / 'run_meta.json'}")

    return float(ts_start)


def extract_block_observations(run_dir: Path, phase_config: PhaseConfig) -> pd.DataFrame | None:
    ts_start = get_run_start(run_dir)

    blocks = read_jsonl(run_dir / "rpc" / "blocks.jsonl")

    if not blocks.empty and {"blockTimestamp", "blockNumber"}.issubset(blocks.columns):
        df = blocks[["blockTimestamp", "blockNumber"]].copy()
        df["blockTimestamp"] = pd.to_numeric(df["blockTimestamp"], errors="coerce")
        df["blockNumber"] = pd.to_numeric(df["blockNumber"], errors="coerce")
        df = df.dropna().sort_values("blockTimestamp")
        df["t_rel"] = df["blockTimestamp"] - ts_start
        df = df.drop_duplicates(subset=["blockNumber"], keep="first")
        df = df[(df["t_rel"] >= 0) & (df["t_rel"] <= phase_config.run_end_s + 10)]

        if not df.empty:
            return df[["t_rel", "blockNumber"]]

    head = read_jsonl(run_dir / "rpc" / "head.jsonl")

    if not head.empty and {"ts_local", "blockNumber"}.issubset(head.columns):
        df = head[["ts_local", "blockNumber"]].copy()
        df["ts_local"] = pd.to_numeric(df["ts_local"], errors="coerce")
        df["blockNumber"] = pd.to_numeric(df["blockNumber"], errors="coerce")
        df = df.dropna().sort_values("ts_local")
        df["t_rel"] = df["ts_local"] - ts_start
        df = df.drop_duplicates(subset=["blockNumber"], keep="first")
        df = df[(df["t_rel"] >= 0) & (df["t_rel"] <= phase_config.run_end_s + 10)]

        if not df.empty:
            return df[["t_rel", "blockNumber"]]

    return None


def compute_windowed_chain_growth(
    df: pd.DataFrame | None,
    grid: np.ndarray,
    window_s: float,
) -> np.ndarray:
    values = np.full_like(grid, np.nan, dtype=float)

    if df is None or df.empty:
        return values

    t = df["t_rel"].to_numpy(dtype=float)
    block = df["blockNumber"].to_numpy(dtype=float)

    order = np.argsort(t)
    t = t[order]
    block = block[order]

    for i, current_t in enumerate(grid):
        if current_t < window_s:
            continue

        left_t = current_t - window_s

        right_idx = np.searchsorted(t, current_t, side="right") - 1
        left_idx = np.searchsorted(t, left_t, side="right") - 1

        if right_idx < 0:
            continue

        right_block = block[right_idx]
        left_block = block[left_idx] if left_idx >= 0 else block[0]

        values[i] = max(0.0, right_block - left_block) / window_s

    return values


def aggregate_scenario(
    root: Path,
    scenario: str,
    level,
    step_s: float,
    window_s: float,
    phase_config: PhaseConfig,
):
    run_dirs = list_run_dirs(root, scenario, level)

    if not run_dirs:
        raise ValueError(f"No runs found for {scenario} level {level}")

    grid = np.arange(0.0, phase_config.run_end_s + step_s, step_s)

    series = []
    used_runs = []

    for run_dir in run_dirs:
        df = extract_block_observations(run_dir, phase_config)
        growth = compute_windowed_chain_growth(df, grid, window_s)

        if np.all(np.isnan(growth)):
            continue

        series.append(growth)
        used_runs.append(run_dir.name)

    if not series:
        raise ValueError(f"No usable runs found for {scenario} level {level}")

    arr = np.vstack(series)

    median = np.nanmedian(arr, axis=0)
    q1 = np.nanquantile(arr, 0.25, axis=0)
    q3 = np.nanquantile(arr, 0.75, axis=0)

    return grid, arr, median, q1, q3, used_runs


def add_phase_background(ax, phase_config: PhaseConfig):
    phases = [
        ("Baseline", phase_config.warmup_s, phase_config.stress_start_s, "#e8f0fe"),
        ("Stress", phase_config.stress_start_s, phase_config.stress_end_s, "#fff1df"),
        ("Recovery", phase_config.stress_end_s, phase_config.run_end_s, "#e9f7e9"),
    ]

    for _, start, end, color in phases:
        ax.axvspan(start, end, color=color, alpha=0.65, linewidth=0)

    for x in [phase_config.stress_start_s, phase_config.stress_end_s]:
        ax.axvline(x, color="#333333", linestyle="--", linewidth=1.0, alpha=0.75)

    y0, y1 = ax.get_ylim()
    y = y1 - 0.055 * (y1 - y0)

    for label, start, end, _ in phases:
        ax.text(
            (start + end) / 2,
            y,
            label,
            ha="center",
            va="top",
            fontsize=9,
            color="#333333",
        )


def get_plot_title(scenario: str, level) -> str:
    if scenario == "latency":
        return f"Phase-level chain growth at {level} ms latency"

    if scenario == "bandwidth":
        return f"Phase-level chain growth at {level} bandwidth"

    if scenario == "partition":
        return f"Phase-level chain growth under {level} network partition"

    return f"Phase-level chain growth for {scenario} {level}"


def get_output_name(scenario: str, level) -> str:
    if scenario == "latency":
        return f"latency_{level}ms_phase_chain_growth_median_iqr.pdf"

    if scenario == "bandwidth":
        return f"bandwidth_{level}_phase_chain_growth_median_iqr.pdf"

    if scenario == "partition":
        return f"partition_{level}_phase_chain_growth_median_iqr.pdf"

    return f"{scenario}_{level}_phase_chain_growth_median_iqr.pdf"


def get_xtick_step(run_end_s: float) -> float:
    if run_end_s <= 420:
        return 60.0

    if run_end_s <= 1200:
        return 120.0

    return 300.0


def get_plot_phase_config(phase_config: PhaseConfig) -> PhaseConfig:
    return PhaseConfig(
        warmup_s=0.0,
        baseline_s=phase_config.baseline_s,
        stress_s=phase_config.stress_s,
        recovery_s=phase_config.recovery_s,
        plot_start_s=0.0,
    )


def plot_scenario(
    root: Path,
    scenario: str,
    level,
    out_path: Path,
    step_s: float,
    window_s: float,
    show_individual: bool,
    phase_config: PhaseConfig,
):
    grid, arr, median, q1, q3, used_runs = aggregate_scenario(
        root=root,
        scenario=scenario,
        level=level,
        step_s=step_s,
        window_s=window_s,
        phase_config=phase_config,
    )

    fig, ax = plt.subplots(figsize=(12.0, 4.8))

    x_offset = phase_config.plot_start_s
    plot_grid = grid - x_offset
    plot_end_s = phase_config.run_end_s - x_offset
    plot_phase_config = get_plot_phase_config(phase_config)

    ax.set_xlim(0.0, plot_end_s)
    ax.set_ylim(0, 0.62)
    ax.set_xticks(np.arange(0.0, plot_end_s + 1, get_xtick_step(plot_end_s)))

    add_phase_background(ax, plot_phase_config)

    if show_individual:
        for row in arr:
            ax.plot(
                plot_grid,
                row,
                color="#8a8a8a",
                linewidth=0.55,
                alpha=0.18,
                zorder=2,
            )

    ax.fill_between(
        plot_grid,
        q1,
        q3,
        color="#4c78a8",
        alpha=0.22,
        linewidth=0,
        label="IQR",
        zorder=3,
    )

    ax.plot(
        plot_grid,
        median,
        color="#1f4e79",
        linewidth=2.5,
        label=f"Median (n={len(used_runs)})",
        zorder=4,
    )

    ax.axhline(
        NOMINAL_RATE,
        color="#222222",
        linestyle=":",
        linewidth=1.2,
        label="Nominal rate (0.5 blocks/s)",
        zorder=1,
    )

    ax.axhline(
        STALLED_GROWTH_THRESHOLD,
        color="#9a3412",
        linestyle="-.",
        linewidth=1.1,
        label="Stalled-growth threshold (0.25 blocks/s)",
        zorder=1,
    )

    ax.set_title(get_plot_title(scenario, level))
    ax.set_xlabel("Time since analysis start (s)")
    ax.set_ylabel(f"{int(window_s)} s windowed chain growth rate (blocks/s)")

    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=4,
        frameon=False,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0.08, 1, 1])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)

    print(f"Wrote: {out_path}")
    print(f"Scenario: {scenario}, level: {level}")
    print(f"Used runs: {len(used_runs)}")


def parse_levels(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--root", default="experiments/runs")
    parser.add_argument("--out-dir", default="experiments/plots/phase_level")
    parser.add_argument("--step-s", type=float, default=2.0)
    parser.add_argument("--window-s", type=float, default=60.0)
    parser.add_argument("--show-individual", action="store_true")

    parser.add_argument("--warmup-s", type=float, default=60.0)
    parser.add_argument("--baseline-s", type=float, default=60.0)
    parser.add_argument("--stress-s", type=float, default=180.0)
    parser.add_argument("--recovery-s", type=float, default=60.0)
    parser.add_argument("--plot-start-s", type=float, default=60.0)

    parser.add_argument("--latency-levels", default="")
    parser.add_argument("--bandwidth-levels", default="")
    parser.add_argument("--partition-levels", default="")

    args = parser.parse_args()

    root = Path(args.root)
    out_dir = Path(args.out_dir)

    phase_config = PhaseConfig(
        warmup_s=args.warmup_s,
        baseline_s=args.baseline_s,
        stress_s=args.stress_s,
        recovery_s=args.recovery_s,
        plot_start_s=args.plot_start_s,
    )

    latency_levels = [int(level) for level in parse_levels(args.latency_levels)]
    bandwidth_levels = parse_levels(args.bandwidth_levels)
    partition_levels = parse_levels(args.partition_levels)

    jobs = []

    for level in latency_levels:
        jobs.append(("latency", level))

    for level in bandwidth_levels:
        jobs.append(("bandwidth", level))

    for level in partition_levels:
        jobs.append(("partition", level))

    if not jobs:
        raise ValueError(
            "No levels selected. Use at least one of "
            "--latency-levels, --bandwidth-levels, or --partition-levels."
        )

    for scenario, level in jobs:
        plot_scenario(
            root=root,
            scenario=scenario,
            level=level,
            out_path=out_dir / get_output_name(scenario, level),
            step_s=args.step_s,
            window_s=args.window_s,
            show_individual=args.show_individual,
            phase_config=phase_config,
        )


if __name__ == "__main__":
    main()