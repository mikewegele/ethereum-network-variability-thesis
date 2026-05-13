import argparse
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def read_jsonl(path: Path) -> pd.DataFrame:
    rows = []
    if not path.exists():
        return pd.DataFrame()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return pd.DataFrame(rows)


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def infer_level_from_name(run_name: str, scenario: str):
    s = run_name.lower()

    if scenario == "latency":
        m = re.search(r"lat_(\d+)ms", s)
        return int(m.group(1)) if m else None

    if scenario == "packetloss":
        m = re.search(r"loss_(\d+)pct", s)
        return int(m.group(1)) if m else None

    if scenario == "bandwidth":
        m = re.search(r"bw_([^_]+)_rep", s)
        return m.group(1).lower() if m else None

    if scenario == "offline":
        m = re.search(r"(?:off|offline)_(\d+)", s)
        return int(m.group(1)) if m else None

    return None


def infer_rep_from_name(run_name: str):
    m = re.search(r"rep(\d+)", run_name.lower())
    return int(m.group(1)) if m else None


def list_run_dirs(root: Path, scenario: str, level=None, rep=None):
    scenario_dir = root / scenario
    if not scenario_dir.exists():
        return []

    runs = []
    for p in sorted(scenario_dir.iterdir()):
        if not p.is_dir():
            continue

        lvl = infer_level_from_name(p.name, scenario)
        r = infer_rep_from_name(p.name)

        if level is not None:
            if scenario in {"latency", "packetloss", "offline"}:
                if lvl != int(level):
                    continue
            else:
                if str(lvl).lower() != str(level).lower():
                    continue

        if rep is not None and r != int(rep):
            continue

        runs.append(p)

    return runs


def normalize_run(run_dir: Path):
    rpc_dir = run_dir / "rpc"

    run_meta = read_json(rpc_dir / "run_meta.json")
    scenario_meta = read_json(run_dir / "scenario_meta.json")

    blocks = read_jsonl(rpc_dir / "blocks.jsonl")
    head = read_jsonl(rpc_dir / "head.jsonl")
    peers = read_jsonl(rpc_dir / "peers.jsonl")

    ts0 = run_meta.get("ts_start_local")
    if ts0 is None:
        raise ValueError(f"Missing ts_start_local in {run_dir}")
    ts0 = float(ts0)

    if not blocks.empty:
        if "blockTimestamp" in blocks.columns:
            blocks["blockTimestamp"] = pd.to_numeric(blocks["blockTimestamp"], errors="coerce")
            blocks["t_rel"] = blocks["blockTimestamp"] - ts0
        if "blockNumber" in blocks.columns:
            blocks["blockNumber"] = pd.to_numeric(blocks["blockNumber"], errors="coerce")
        if "txCount" in blocks.columns:
            blocks["txCount"] = pd.to_numeric(blocks["txCount"], errors="coerce")
        blocks = blocks.sort_values("blockNumber").reset_index(drop=True)
        if "blockTimestamp" in blocks.columns:
            blocks["interblock_gap_s"] = blocks["blockTimestamp"].diff()
        else:
            blocks["interblock_gap_s"] = np.nan
    else:
        blocks["t_rel"] = pd.Series(dtype=float)
        blocks["interblock_gap_s"] = pd.Series(dtype=float)

    if not head.empty:
        if "ts_local" in head.columns:
            head["ts_local"] = pd.to_numeric(head["ts_local"], errors="coerce")
            head["t_rel"] = head["ts_local"] - ts0
        if "blockNumber" in head.columns:
            head["blockNumber"] = pd.to_numeric(head["blockNumber"], errors="coerce")
        head = head.sort_values("t_rel").reset_index(drop=True)
    else:
        head["t_rel"] = pd.Series(dtype=float)

    if not peers.empty:
        if "ts_local" in peers.columns:
            peers["ts_local"] = pd.to_numeric(peers["ts_local"], errors="coerce")
            peers["t_rel"] = peers["ts_local"] - ts0
        if "peerCount" in peers.columns:
            peers["peerCount"] = pd.to_numeric(peers["peerCount"], errors="coerce")
        peers = peers.sort_values("t_rel").reset_index(drop=True)
    else:
        peers["t_rel"] = pd.Series(dtype=float)

    return {
        "run_dir": run_dir,
        "run_meta": run_meta,
        "scenario_meta": scenario_meta,
        "blocks": blocks,
        "head": head,
        "peers": peers,
    }


def get_phase_boundaries(run_meta: dict, scenario_meta: dict):
    duration_s_observed = float(run_meta.get("duration_s_observed", 0.0))
    warmup_s = float(scenario_meta.get("warmup_s", 0.0))
    baseline_s = float(scenario_meta.get("baseline_s", 0.0))
    stress_s = float(scenario_meta.get("stress_s", 0.0))
    recovery_s = float(scenario_meta.get("recovery_s", 0.0))

    t0 = 0.0
    t1 = warmup_s
    t2 = t1 + baseline_s
    t3 = t2 + stress_s
    t4 = t3 + recovery_s

    if duration_s_observed > 0:
        t4 = min(t4, duration_s_observed)

    return {
        "warmup": (t0, t1),
        "baseline": (t1, t2),
        "stress": (t2, t3),
        "recovery": (t3, t4),
    }


def draw_phase_background(ax, phases, show_warmup=False):
    phase_specs = [
        ("warmup", "#eeeeee"),
        ("baseline", "#dbe9ff"),
        ("stress", "#ffe3c2"),
        ("recovery", "#dff5df"),
    ]

    for name, color in phase_specs:
        if name not in phases:
            continue
        if name == "warmup" and not show_warmup:
            continue
        a, b = phases[name]
        ax.axvspan(a, b, color=color, alpha=0.22, linewidth=0)

    boundaries = []
    for name in ["baseline", "stress", "recovery"]:
        if name in phases:
            boundaries.append(phases[name][0])

    for x in boundaries[1:]:
        ax.axvline(x, color="black", linestyle="--", linewidth=1.0, alpha=0.8)


def add_phase_labels(ax, phases, show_warmup=False):
    y0, y1 = ax.get_ylim()
    y = y1 - 0.04 * (y1 - y0)

    for name in ["warmup", "baseline", "stress", "recovery"]:
        if name not in phases:
            continue
        if name == "warmup" and not show_warmup:
            continue
        a, b = phases[name]
        mid = (a + b) / 2.0
        ax.text(
            mid,
            y,
            name.capitalize(),
            ha="center",
            va="top",
            fontsize=10,
            fontweight="bold",
            alpha=0.9,
        )


def sample_step(xs, ys, grid):
    if len(xs) == 0 or len(ys) == 0:
        return np.full_like(grid, np.nan, dtype=float)

    xs = np.asarray(xs, dtype=float)
    ys = np.asarray(ys, dtype=float)

    order = np.argsort(xs)
    xs = xs[order]
    ys = ys[order]

    idx = np.searchsorted(xs, grid, side="right") - 1
    out = np.full_like(grid, np.nan, dtype=float)
    valid = idx >= 0
    out[valid] = ys[idx[valid]]
    return out


def aggregate_series(series_list):
    if not series_list:
        return None

    arr = np.vstack(series_list)
    valid_cols = ~np.all(np.isnan(arr), axis=0)
    if not np.any(valid_cols):
        return None

    median = np.full(arr.shape[1], np.nan, dtype=float)
    q1 = np.full(arr.shape[1], np.nan, dtype=float)
    q3 = np.full(arr.shape[1], np.nan, dtype=float)

    median[valid_cols] = np.nanmedian(arr[:, valid_cols], axis=0)
    q1[valid_cols] = np.nanquantile(arr[:, valid_cols], 0.25, axis=0)
    q3[valid_cols] = np.nanquantile(arr[:, valid_cols], 0.75, axis=0)

    return {"median": median, "q1": q1, "q3": q3, "n": arr.shape[0]}


def run_to_grid_series(run_data, step_s: float):
    run_meta = run_data["run_meta"]
    scenario_meta = run_data["scenario_meta"]
    blocks = run_data["blocks"]
    head = run_data["head"]
    peers = run_data["peers"]

    duration = float(run_meta.get("duration_s_observed", 0.0))
    if duration <= 0:
        duration = float(
            scenario_meta.get("warmup_s", 0)
            + scenario_meta.get("baseline_s", 0)
            + scenario_meta.get("stress_s", 0)
            + scenario_meta.get("recovery_s", 0)
        )
    grid = np.arange(0.0, duration + step_s, step_s)

    block_period_s = float(scenario_meta.get("block_period_s", 2.0))
    window_s = float(scenario_meta.get("window_s", 60.0))
    missing_threshold_s = 2.0 * block_period_s
    stall_threshold_s = 5.0 * block_period_s

    series = {}

    if not head.empty:
        series["head_block_number"] = sample_step(head["t_rel"].to_numpy(dtype=float), head["blockNumber"].to_numpy(dtype=float), grid)
    else:
        series["head_block_number"] = np.full_like(grid, np.nan, dtype=float)

    if not peers.empty:
        series["peer_count"] = sample_step(peers["t_rel"].to_numpy(dtype=float), peers["peerCount"].to_numpy(dtype=float), grid)
    else:
        series["peer_count"] = np.full_like(grid, np.nan, dtype=float)

    if not head.empty and "blockNumber" in head.columns:
        head_clean = head.dropna(subset=["t_rel", "blockNumber"]).copy()
        head_clean["delta_bn"] = head_clean["blockNumber"].diff().fillna(0)
        finalized_times = head_clean.loc[head_clean["delta_bn"] > 0, "t_rel"].to_numpy(dtype=float)
    elif not blocks.empty:
        finalized_times = blocks["t_rel"].dropna().to_numpy(dtype=float)
    else:
        finalized_times = np.array([], dtype=float)

    if len(finalized_times) >= 2:
        gaps = np.diff(finalized_times)
        gap_times = finalized_times[1:]
        series["interblock_gap_s"] = sample_step(gap_times, gaps, grid)
    else:
        series["interblock_gap_s"] = np.full_like(grid, np.nan, dtype=float)

    if len(finalized_times) > 0:
        idx = np.searchsorted(finalized_times, grid, side="right") - 1
        time_since_last = np.full_like(grid, np.nan, dtype=float)
        valid = idx >= 0
        time_since_last[valid] = grid[valid] - finalized_times[idx[valid]]
    else:
        time_since_last = np.full_like(grid, np.nan, dtype=float)

    series["time_since_last_finalization_s"] = time_since_last
    series["missing_finalization_state"] = np.where(np.isnan(time_since_last), np.nan, (time_since_last >= missing_threshold_s).astype(float))
    series["stall_state"] = np.where(np.isnan(time_since_last), np.nan, (time_since_last >= stall_threshold_s).astype(float))

    stall_state = np.nan_to_num(series["stall_state"], nan=0.0)
    series["cumulative_stall_duration_s"] = np.cumsum(stall_state * step_s)

    miss_count = np.zeros_like(grid, dtype=float)
    current = 0.0
    next_mark = missing_threshold_s
    for i, _t in enumerate(grid):
        if np.isnan(time_since_last[i]):
            miss_count[i] = current
            continue
        if time_since_last[i] >= next_mark:
            current += 1.0
            next_mark += missing_threshold_s
        if time_since_last[i] < missing_threshold_s:
            next_mark = missing_threshold_s
        miss_count[i] = current
    series["cumulative_missing_finalization_intervals"] = miss_count

    if not np.all(np.isnan(series["head_block_number"])):
        head_vals = np.nan_to_num(series["head_block_number"], nan=np.nan)
        growth = np.full_like(grid, np.nan, dtype=float)
        window_steps = max(1, int(round(window_s / step_s)))
        for i in range(window_steps, len(grid)):
            a = head_vals[i - window_steps]
            b = head_vals[i]
            if np.isnan(a) or np.isnan(b):
                continue
            growth[i] = (b - a) / (window_steps * step_s)
        series["chain_growth_rate_blocks_per_s_windowed"] = growth
    else:
        series["chain_growth_rate_blocks_per_s_windowed"] = np.full_like(grid, np.nan, dtype=float)

    if not blocks.empty and "txCount" in blocks.columns and "t_rel" in blocks.columns:
        tx_blocks = blocks.dropna(subset=["t_rel", "txCount"]).copy()
        if not tx_blocks.empty:
            series["tx_per_block"] = sample_step(
                tx_blocks["t_rel"].to_numpy(dtype=float),
                tx_blocks["txCount"].to_numpy(dtype=float),
                grid,
            )
        else:
            series["tx_per_block"] = np.full_like(grid, np.nan, dtype=float)
    else:
        series["tx_per_block"] = np.full_like(grid, np.nan, dtype=float)

    if not blocks.empty and "txCount" in blocks.columns and "t_rel" in blocks.columns:
        tx_blocks = blocks.dropna(subset=["t_rel", "txCount"]).copy()
        t_arr = tx_blocks["t_rel"].to_numpy(dtype=float)
        tx_arr = tx_blocks["txCount"].to_numpy(dtype=float)
        throughput = np.full_like(grid, np.nan, dtype=float)
        for i, t in enumerate(grid):
            lo = t - window_s
            mask = (t_arr > lo) & (t_arr <= t)
            throughput[i] = tx_arr[mask].sum() / window_s if np.any(mask) else 0.0
        series["throughput_txs_per_s_windowed"] = throughput
    else:
        series["throughput_txs_per_s_windowed"] = np.full_like(grid, np.nan, dtype=float)

    baseline_p95 = 2.0 * block_period_s
    if len(finalized_times) >= 2:
        delayed_gap_times = finalized_times[1:]
        delayed_flags = (np.diff(finalized_times) > baseline_p95).astype(float)
        delayed_state = sample_step(delayed_gap_times, delayed_flags, grid)
        delayed_cum = sample_step(delayed_gap_times, np.cumsum(delayed_flags), grid)
        series["delayed_finalization_state"] = delayed_state
        series["cumulative_delayed_finalization_events"] = delayed_cum
    else:
        series["delayed_finalization_state"] = np.full_like(grid, np.nan, dtype=float)
        series["cumulative_delayed_finalization_events"] = np.full_like(grid, np.nan, dtype=float)

    return grid, series


def finalize_plot(ax, phases, xlabel, ylabel, title, show_warmup=False):
    draw_phase_background(ax, phases, show_warmup=show_warmup)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    add_phase_labels(ax, phases, show_warmup=show_warmup)
    plt.tight_layout()


def plot_single_series(grid, y, phases, out_path: Path, ylabel: str, title: str, step=False, hlines=None):
    fig, ax = plt.subplots(figsize=(12, 4.8))
    if step:
        ax.step(grid, y, where="post", linewidth=2)
    else:
        ax.plot(grid, y, linewidth=2)
    if hlines:
        for yv, style, label in hlines:
            ax.axhline(yv, linestyle=style, linewidth=1, label=label)
        ax.legend()
    finalize_plot(ax, phases, "Time since run start (s)", ylabel, title)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


def plot_aggregate_series(grid, agg, phases, out_path: Path, ylabel: str, title: str, hlines=None):
    fig, ax = plt.subplots(figsize=(12, 4.8))
    ax.plot(grid, agg["median"], linewidth=2, label=f"Median (n={agg['n']})")
    ax.fill_between(grid, agg["q1"], agg["q3"], alpha=0.2, label="IQR")
    if hlines:
        for yv, style, label in hlines:
            ax.axhline(yv, linestyle=style, linewidth=1, label=label)
    ax.legend()
    finalize_plot(ax, phases, "Time since run start (s)", ylabel, title)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out_path)
    plt.close()


def level_to_dirname(level) -> str:
    return str(level).replace("/", "_")


def build_run_output_dir(base: Path, run_data) -> Path:
    scenario = run_data["scenario_meta"].get("mode")
    if scenario is None:
        run_name = run_data["run_dir"].name
        for s in ["latency", "packetloss", "bandwidth", "offline"]:
            if infer_level_from_name(run_name, s) is not None:
                scenario = s
                break
    if scenario is None:
        scenario = "unknown"

    level = infer_level_from_name(run_data["run_dir"].name, scenario)
    level_dir = level_to_dirname(level if level is not None else "unknown")
    return base / "run" / scenario / level_dir


def build_aggregate_output_dir(base: Path, scenario: str, level) -> Path:
    return base / "aggregate" / scenario / level_to_dirname(level)


def plot_run_outputs(run_data, out_dir: Path, step_s: float):
    phases = get_phase_boundaries(run_data["run_meta"], run_data["scenario_meta"])
    grid, series = run_to_grid_series(run_data, step_s)
    stem = run_data["run_dir"].name

    outputs = {
        "head_block_number": ("Block number", f"Temporal block progress: {stem}", True, None),
        "peer_count": ("Peer count", f"Temporal peer count: {stem}", True, None),
        "interblock_gap_s": ("Inter-block gap (s)", f"Temporal inter-block gaps: {stem}", False, [(2.0, "--", "Nominal block period"), (10.0, ":", "Stall threshold")]),
        "time_since_last_finalization_s": ("Time since last finalization (s)", f"Temporal time since last finalization: {stem}", False, [(4.0, "--", "Missing-finalization threshold"), (10.0, ":", "Stall threshold")]),
        "missing_finalization_state": ("Missing finalization state", f"Temporal missing finalization state: {stem}", True, None),
        "cumulative_missing_finalization_intervals": ("Cumulative missing-finalization intervals", f"Temporal cumulative missing finalization intervals: {stem}", False, None),
        "stall_state": ("Stall state", f"Temporal stall state: {stem}", True, None),
        "cumulative_stall_duration_s": ("Cumulative stall duration (s)", f"Temporal cumulative stall duration: {stem}", False, None),
        "chain_growth_rate_blocks_per_s_windowed": ("Chain growth rate (blocks/s)", f"Temporal sustained block production: {stem}", False, None),
        "tx_per_block": ("Transactions per block", f"Temporal transactions per block: {stem}", True, None),
        "throughput_txs_per_s_windowed": ("Throughput (tx/s)", f"Temporal throughput: {stem}", False, None),
        "delayed_finalization_state": ("Delayed finalization state", f"Temporal delayed finalization state: {stem}", True, None),
        "cumulative_delayed_finalization_events": ("Cumulative delayed finalization events", f"Temporal cumulative delayed finalization events: {stem}", False, None),
    }

    for key, (ylabel, title, step, hlines) in outputs.items():
        y = series.get(key)
        if y is None:
            continue
        plot_single_series(grid, y, phases, out_dir / f"{stem}_{key}.pdf", ylabel, title, step=step, hlines=hlines)


def plot_aggregate_outputs(runs_data, out_dir: Path, step_s: float, stem: str):
    grids = []
    aligned_store = {}

    for rd in runs_data:
        grid, series = run_to_grid_series(rd, step_s)
        grids.append(grid)
        for key, vals in series.items():
            aligned_store.setdefault(key, []).append(vals)

    max_t = max(g[-1] for g in grids)
    grid = np.arange(0.0, max_t + step_s, step_s)

    aligned_store_fixed = {}
    for key, series_list in aligned_store.items():
        fixed = []
        for vals in series_list:
            aligned = np.full_like(grid, np.nan, dtype=float)
            n = min(len(vals), len(aligned))
            aligned[:n] = vals[:n]
            fixed.append(aligned)
        aligned_store_fixed[key] = fixed

    phases = get_phase_boundaries(runs_data[0]["run_meta"], runs_data[0]["scenario_meta"])

    outputs = {
        "head_block_number": ("Block number", f"Aggregate block progress: {stem}", None),
        "peer_count": ("Peer count", f"Aggregate peer count: {stem}", None),
        "interblock_gap_s": ("Inter-block gap (s)", f"Aggregate inter-block gaps: {stem}", [(2.0, "--", "Nominal block period"), (10.0, ":", "Stall threshold")]),
        "time_since_last_finalization_s": ("Time since last finalization (s)", f"Aggregate time since last finalization: {stem}", [(4.0, "--", "Missing-finalization threshold"), (10.0, ":", "Stall threshold")]),
        "missing_finalization_state": ("Missing finalization state", f"Aggregate missing finalization state: {stem}", None),
        "cumulative_missing_finalization_intervals": ("Cumulative missing-finalization intervals", f"Aggregate cumulative missing finalization intervals: {stem}", None),
        "stall_state": ("Stall state", f"Aggregate stall state: {stem}", None),
        "cumulative_stall_duration_s": ("Cumulative stall duration (s)", f"Aggregate cumulative stall duration: {stem}", None),
        "chain_growth_rate_blocks_per_s_windowed": ("Chain growth rate (blocks/s)", f"Aggregate sustained block production: {stem}", None),
        "tx_per_block": ("Transactions per block", f"Aggregate transactions per block: {stem}", None),
        "throughput_txs_per_s_windowed": ("Throughput (tx/s)", f"Aggregate throughput: {stem}", None),
        "delayed_finalization_state": ("Delayed finalization state", f"Aggregate delayed finalization state: {stem}", None),
        "cumulative_delayed_finalization_events": ("Cumulative delayed finalization events", f"Aggregate cumulative delayed finalization events: {stem}", None),
    }

    for key, (ylabel, title, hlines) in outputs.items():
        agg = aggregate_series(aligned_store_fixed.get(key, []))
        if agg is None:
            continue
        plot_aggregate_series(grid, agg, phases, out_dir / f"{stem}_{key}.pdf", ylabel, title, hlines=hlines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="experiments/runs")
    ap.add_argument("--mode", choices=["run", "aggregate"], required=True)
    ap.add_argument("--run-dir", default=None)
    ap.add_argument("--scenario", choices=["latency", "packetloss", "bandwidth", "offline"], default=None)
    ap.add_argument("--level", default=None)
    ap.add_argument("--rep", type=int, default=None)
    ap.add_argument("--step-s", type=float, default=2.0)
    ap.add_argument("--out-dir", default="experiments/plots/temporal")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)

    if args.mode == "run":
        if args.run_dir:
            run_dir = Path(args.run_dir)
        else:
            if args.scenario is None:
                raise ValueError("--scenario is required when --run-dir is not given")
            matches = list_run_dirs(Path(args.root), args.scenario, level=args.level, rep=args.rep)
            if not matches:
                raise ValueError("No matching run found")
            run_dir = matches[0]

        run_data = normalize_run(run_dir)
        target_dir = build_run_output_dir(out_dir, run_data)
        plot_run_outputs(run_data, target_dir, args.step_s)
        print(target_dir)
        return

    if args.mode == "aggregate":
        if args.scenario is None or args.level is None:
            raise ValueError("--scenario and --level are required for aggregate mode")

        run_dirs = list_run_dirs(Path(args.root), args.scenario, level=args.level, rep=args.rep)
        if not run_dirs:
            raise ValueError("No matching runs found")

        runs_data = [normalize_run(p) for p in run_dirs]
        target_dir = build_aggregate_output_dir(out_dir, args.scenario, args.level)
        stem = f"{args.scenario}_{str(args.level).replace('/', '_')}"
        plot_aggregate_outputs(runs_data, target_dir, args.step_s, stem)
        print(target_dir)
        return


if __name__ == "__main__":
    main()