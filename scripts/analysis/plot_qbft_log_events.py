import argparse
import csv
import json
import re
from pathlib import Path
from datetime import datetime, timezone

import matplotlib.pyplot as plt
import numpy as np


TS_RE = re.compile(r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?Z)")
MOVED_RE = re.compile(r"Moved to round (?P<round>\d+)")
IMPORT_RE = re.compile(
    r"Importing proposed block to chain\. round=ConsensusRoundIdentifier\{Sequence=(?P<sequence>\d+), Round=(?P<round>\d+)\}"
)
ROUND_SUMMARY_RE = re.compile(r"BFT round summary \(quorum = (?P<quorum>\d+)\)")

PHASE_COLORS = {
    "baseline_phase": "#e8f0fe",
    "stress_phase": "#fff1df",
    "recovery_phase": "#e9f7e9",
}

MAIN_BLUE = "#1f4e79"
LIGHT_BLUE = "#4c78a8"
DARK = "#222222"
ORANGE = "#9a3412"


def parse_ts(value):
    value = value.rstrip("Z")

    if "." in value:
        base, frac = value.split(".", 1)
        frac = frac[:6].ljust(6, "0")
        value = f"{base}.{frac}Z"
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc).timestamp()

    value = f"{value}Z"
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()


def load_json(path):
    if not path.exists():
        return None

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_jsonl(path):
    if not path.exists():
        return []

    rows = []

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            if line:
                rows.append(json.loads(line))

    return rows


def run_name(run_dir):
    return run_dir.name


def format_run_title(run: str) -> str:
    latency = re.search(r"lat_(\d+)ms_rep(\d+)", run)
    if latency:
        level = latency.group(1)
        rep = latency.group(2)
        return f"Latency {level} ms"

    loss = re.search(r"loss_(\d+)pct_rep(\d+)", run)
    if loss:
        level = loss.group(1)
        rep = loss.group(2)
        return f"Packet loss {level}%"

    bandwidth = re.search(r"bw_([^_]+)_rep(\d+)", run)
    if bandwidth:
        level = bandwidth.group(1)
        rep = bandwidth.group(2)
        return f"Bandwidth {level}"

    partition = re.search(r"partition_([0-9]+[-_][0-9]+)_rep(\d+)", run)
    if partition:
        level = partition.group(1).replace("_", "-")
        rep = partition.group(2)
        return f"Partition {level}"

    return run

def parse_log_file(path, run):
    validator = path.name.split("_")[0].replace(".log", "")
    events = []

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            ts_match = TS_RE.search(line)

            if not ts_match:
                continue

            ts = parse_ts(ts_match.group("ts"))

            moved = MOVED_RE.search(line)
            if moved:
                events.append(
                    {
                        "run": run,
                        "validator": validator,
                        "timestamp": ts,
                        "event": "moved_to_round",
                        "round": int(moved.group("round")),
                        "sequence": "",
                        "quorum": "",
                        "line": line.strip(),
                    }
                )
                continue

            imported = IMPORT_RE.search(line)
            if imported:
                events.append(
                    {
                        "run": run,
                        "validator": validator,
                        "timestamp": ts,
                        "event": "imported_proposed_block",
                        "round": int(imported.group("round")),
                        "sequence": int(imported.group("sequence")),
                        "quorum": "",
                        "line": line.strip(),
                    }
                )
                continue

            summary = ROUND_SUMMARY_RE.search(line)
            if summary:
                events.append(
                    {
                        "run": run,
                        "validator": validator,
                        "timestamp": ts,
                        "event": "bft_round_summary",
                        "round": "",
                        "sequence": "",
                        "quorum": int(summary.group("quorum")),
                        "line": line.strip(),
                    }
                )
                continue

    return events


def parse_events(run_dir):
    run = run_name(run_dir)

    log_files = sorted((run_dir / "logs").glob("validator*.log"))

    if not log_files:
        log_files = sorted(run_dir.glob("*_current.log"))

    if not log_files:
        log_files = sorted(run_dir.glob("validator*.log"))

    if not log_files:
        log_files = sorted(run_dir.rglob("*.log"))

    events = []

    for path in log_files:
        events.extend(parse_log_file(path, run))

    return sorted(events, key=lambda x: x["timestamp"])


def get_phase_bounds(summary, meta):
    bounds = {}

    if summary and summary.get("phase_metrics"):
        for phase, data in summary["phase_metrics"].items():
            start = data.get("phase_start_ts")
            end = data.get("phase_end_ts")

            if start is not None and end is not None:
                bounds[phase] = (float(start), float(end))

    if not bounds and meta:
        start = meta.get("ts_start_local")

        if start is not None:
            start = float(start)
            bounds = {
                "warmup_phase": (start, start + 60),
                "baseline_phase": (start + 60, start + 120),
                "stress_phase": (start + 120, start + 300),
                "recovery_phase": (start + 300, start + 360),
            }

    return bounds


def phase_for_ts(ts, bounds):
    for phase, (start, end) in bounds.items():
        if start <= ts < end:
            return phase

    return "outside"


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in rows:
            writer.writerow(row)


def summarize_run(run_dir, events, bounds):
    run = run_name(run_dir)
    rows = []

    phases = ["warmup_phase", "baseline_phase", "stress_phase", "recovery_phase", "outside"]

    for phase in phases:
        phase_events = [e for e in events if phase_for_ts(e["timestamp"], bounds) == phase]
        moved = [e for e in phase_events if e["event"] == "moved_to_round"]
        imports = [e for e in phase_events if e["event"] == "imported_proposed_block"]
        later_imports = [e for e in imports if isinstance(e["round"], int) and e["round"] > 1]

        rounds = [e["round"] for e in moved if isinstance(e["round"], int)]
        import_rounds = [e["round"] for e in imports if isinstance(e["round"], int)]

        rows.append(
            {
                "run": run,
                "phase": phase,
                "moved_to_round_count": len(moved),
                "max_moved_round": max(rounds) if rounds else "",
                "imported_proposed_block_count": len(imports),
                "imported_later_round_count": len(later_imports),
                "max_import_round": max(import_rounds) if import_rounds else "",
                "bft_round_summary_count": sum(1 for e in phase_events if e["event"] == "bft_round_summary"),
            }
        )

    return rows


def blocks_intervals(blocks):
    rows = []
    sorted_blocks = sorted(blocks, key=lambda x: x["blockTimestamp"])

    for prev, cur in zip(sorted_blocks, sorted_blocks[1:]):
        rows.append(
            {
                "timestamp": cur["blockTimestamp"],
                "block": cur["blockNumber"],
                "interblock_s": cur["blockTimestamp"] - prev["blockTimestamp"],
            }
        )

    return rows


def get_analysis_t0(bounds, fallback_t0):
    if "baseline_phase" in bounds:
        return bounds["baseline_phase"][0]

    return fallback_t0


def get_analysis_plot_end(bounds, t0):
    if "recovery_phase" in bounds:
        return bounds["recovery_phase"][1] - t0

    if "stress_phase" in bounds:
        return bounds["stress_phase"][1] - t0

    return 300.0


def get_tick_end(plot_end):
    return int(np.ceil(plot_end / 60.0) * 60)


def add_phase_background(ax, bounds, t0, y_position=0.945):
    phase_labels = {
        "baseline_phase": "Baseline",
        "stress_phase": "Stress",
        "recovery_phase": "Recovery",
    }

    for phase in ["baseline_phase", "stress_phase", "recovery_phase"]:
        if phase not in bounds:
            continue

        start, end = bounds[phase]
        ax.axvspan(
            start - t0,
            end - t0,
            color=PHASE_COLORS[phase],
            alpha=0.65,
            linewidth=0,
            zorder=0,
        )

    for phase in ["stress_phase", "recovery_phase"]:
        if phase in bounds:
            ax.axvline(
                bounds[phase][0] - t0,
                color="#333333",
                linestyle="--",
                linewidth=1.0,
                alpha=0.75,
                zorder=1,
            )

    y0, y1 = ax.get_ylim()
    y = y1 - (1.0 - y_position) * (y1 - y0)

    for phase, label in phase_labels.items():
        if phase not in bounds:
            continue

        start, end = bounds[phase]
        x = (start + end) / 2 - t0

        ax.text(
            x,
            y,
            label,
            ha="center",
            va="top",
            fontsize=10,
            color="#333333",
            zorder=5,
        )


def style_axis(ax):
    ax.grid(True, linestyle="--", linewidth=0.5, alpha=0.35)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)


def plot_round_events_timeline(run_dir, events, bounds, out_dir):
    run = run_name(run_dir)
    selected = [e for e in events if e["event"] in {"moved_to_round", "imported_proposed_block"}]

    if not selected:
        return

    fallback_t0 = min(e["timestamp"] for e in selected)
    t0 = get_analysis_t0(bounds, fallback_t0)
    plot_end = get_analysis_plot_end(bounds, t0)
    tick_end = get_tick_end(plot_end)

    validators = sorted(set(e["validator"] for e in selected))
    ymap = {v: i for i, v in enumerate(validators)}

    fig, ax = plt.subplots(figsize=(12.0, 4.8))

    ax.set_xlim(0, tick_end)
    ax.set_xticks(np.arange(0, tick_end + 1, 60))
    ax.set_ylim(-0.6, len(validators) - 0.4)

    if bounds:
        add_phase_background(ax, bounds, t0)

    moved = [e for e in selected if e["event"] == "moved_to_round"]
    imported = [e for e in selected if e["event"] == "imported_proposed_block"]

    ax.scatter(
        [e["timestamp"] - t0 for e in moved],
        [ymap[e["validator"]] for e in moved],
        s=42,
        marker="o",
        color=ORANGE,
        alpha=0.9,
        label="Moved to later round",
        zorder=4,
    )

    ax.scatter(
        [e["timestamp"] - t0 for e in imported],
        [ymap[e["validator"]] for e in imported],
        s=42,
        marker="x",
        color=MAIN_BLUE,
        alpha=0.9,
        label="Imported proposed block",
        zorder=4,
    )

    for e in selected:
        if isinstance(e["round"], int):
            ax.text(
                e["timestamp"] - t0,
                ymap[e["validator"]] + 0.09,
                str(e["round"]),
                fontsize=7,
                ha="center",
                color="#333333",
                zorder=5,
            )

    ax.set_title(f"{format_run_title(run)}: QBFT round-related log events")
    ax.set_xlabel("Time since analysis start (s)")
    ax.set_ylabel("Validator")
    ax.set_yticks(list(ymap.values()))
    ax.set_yticklabels(validators)

    style_axis(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        frameon=False,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0.08, 1, 1])

    fig.savefig(out_dir / f"{run}_round_events_timeline.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{run}_round_events_timeline.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_import_rounds(run_dir, events, out_dir):
    run = run_name(run_dir)
    imports = [
        e for e in events
        if e["event"] == "imported_proposed_block" and isinstance(e["sequence"], int)
    ]

    if not imports:
        return

    fig, ax = plt.subplots(figsize=(12.0, 4.8))

    ax.scatter(
        [e["sequence"] for e in imports],
        [e["round"] for e in imports],
        s=34,
        color=MAIN_BLUE,
        alpha=0.9,
        label="Imported proposed block",
        zorder=3,
    )

    ax.axhline(
        1,
        color=DARK,
        linestyle=":",
        linewidth=1.2,
        label="Round 1",
        zorder=1,
    )

    ax.set_title(f"{format_run_title(run)}: Imported proposed blocks by QBFT round")
    ax.set_xlabel("Consensus sequence")
    ax.set_ylabel("QBFT round")

    style_axis(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        frameon=False,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0.08, 1, 1])

    fig.savefig(out_dir / f"{run}_import_round_by_sequence.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{run}_import_round_by_sequence.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_interblock_with_round_events(run_dir, events, blocks, bounds, out_dir):
    run = run_name(run_dir)
    intervals = blocks_intervals(blocks)

    if not intervals:
        return

    meta = load_run_meta(run_dir)
    fallback_t0 = (
        float(meta["ts_start_local"])
        if meta and meta.get("ts_start_local") is not None
        else min(row["timestamp"] for row in intervals)
    )

    t0 = get_analysis_t0(bounds, fallback_t0)
    plot_end = get_analysis_plot_end(bounds, t0)
    tick_end = get_tick_end(plot_end)

    fig, ax = plt.subplots(figsize=(12.0, 4.8))

    x = [row["timestamp"] - t0 for row in intervals]
    y = [row["interblock_s"] for row in intervals]

    filtered = [(xi, yi) for xi, yi in zip(x, y) if 0 <= xi <= tick_end]

    if not filtered:
        return

    x_filtered = [xi for xi, _ in filtered]
    y_filtered = [yi for _, yi in filtered]

    ax.set_xlim(0, tick_end)
    ax.set_xticks(np.arange(0, tick_end + 1, 60))

    ymax = max(max(y_filtered) * 1.12, 4.0)
    ax.set_ylim(0, ymax)

    if bounds:
        add_phase_background(ax, bounds, t0)

    ax.plot(
        x_filtered,
        y_filtered,
        marker="o",
        markersize=4.2,
        linewidth=2.2,
        color=MAIN_BLUE,
        label="Inter-block time",
        zorder=4,
    )

    moved = [e for e in events if e["event"] == "moved_to_round"]

    round_change_x = sorted(
        {
            round(e["timestamp"] - t0, 1)
            for e in moved
            if 0 <= e["timestamp"] - t0 <= tick_end
        }
    )

    for x_event in round_change_x:
        ax.axvline(
            x_event,
            color=ORANGE,
            alpha=0.32,
            linewidth=1.1,
            linestyle="-",
            zorder=2,
        )

    if round_change_x:
        ax.plot(
            [],
            [],
            color=ORANGE,
            alpha=0.32,
            linewidth=1.1,
            label="Moved to later round",
        )

    ax.axhline(
        2.0,
        color=DARK,
        linestyle=":",
        linewidth=1.2,
        label="Configured block period (2s)",
        zorder=1,
    )

    ax.set_title(f"{format_run_title(run)}: Inter-block time with QBFT round-change markers")
    ax.set_xlabel("Time since analysis start (s)")
    ax.set_ylabel("Inter-block time (s)")

    style_axis(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=3,
        frameon=False,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0.08, 1, 1])

    fig.savefig(out_dir / f"{run}_interblock_with_round_events.pdf", bbox_inches="tight")
    fig.savefig(out_dir / f"{run}_interblock_with_round_events.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def plot_summary(summary_rows, out_dir):
    stress_rows = [r for r in summary_rows if r["phase"] == "stress_phase"]

    if not stress_rows:
        return

    labels = [r["run"] for r in stress_rows]
    moved = [int(r["moved_to_round_count"]) for r in stress_rows]
    later = [int(r["imported_later_round_count"]) for r in stress_rows]

    fig, ax = plt.subplots(figsize=(max(10, len(labels) * 0.55), 4.8))

    x = np.arange(len(labels))
    width = 0.38

    ax.bar(
        x - width / 2,
        moved,
        width=width,
        color=LIGHT_BLUE,
        alpha=0.85,
        label="Moved to later round",
        zorder=3,
    )

    ax.bar(
        x + width / 2,
        later,
        width=width,
        color=ORANGE,
        alpha=0.85,
        label="Imported in round > 1",
        zorder=3,
    )

    ax.set_title("Stress-phase QBFT log-event counts by run")
    ax.set_xlabel("Run")
    ax.set_ylabel("Event count")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=90, fontsize=7)

    style_axis(ax)

    ax.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.22),
        ncol=2,
        frameon=False,
        fontsize=8.5,
    )

    fig.tight_layout(rect=[0, 0.08, 1, 1])

    fig.savefig(out_dir / "summary_stress_phase_round_event_counts.pdf", bbox_inches="tight")
    fig.savefig(out_dir / "summary_stress_phase_round_event_counts.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def collect_run_dirs(args):
    run_dirs = []

    for value in args.run:
        p = Path(value)

        if p.exists() and p.is_dir():
            run_dirs.append(p)

    for value in args.glob:
        for p in sorted(Path().glob(value)):
            if p.is_dir():
                run_dirs.append(p)

    seen = set()
    unique = []

    for p in run_dirs:
        r = p.resolve()

        if r not in seen:
            unique.append(p)
            seen.add(r)

    return unique


def load_run_blocks(run_dir):
    blocks = load_jsonl(run_dir / "blocks.jsonl")

    if blocks:
        return blocks

    return load_jsonl(run_dir / "rpc" / "blocks.jsonl")


def load_run_summary(run_dir):
    summary = load_json(run_dir / "summary.json")

    if summary:
        return summary

    return load_json(run_dir / "rpc" / "summary.json")


def load_run_meta(run_dir):
    meta = load_json(run_dir / "run_meta.json")

    if meta:
        return meta

    return load_json(run_dir / "rpc" / "run_meta.json")


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument("--run", action="append", default=[])
    parser.add_argument("--glob", action="append", default=[])
    parser.add_argument("--analysis-dir", default="experiments/analysis/qbft_logs")
    parser.add_argument("--plots-dir", default="experiments/plots/qbft_logs")

    args = parser.parse_args()

    analysis_dir = Path(args.analysis_dir)
    plots_dir = Path(args.plots_dir)

    analysis_dir.mkdir(parents=True, exist_ok=True)
    plots_dir.mkdir(parents=True, exist_ok=True)

    run_dirs = collect_run_dirs(args)

    if not run_dirs:
        raise SystemExit("No run directories found.")

    all_events = []
    all_summary = []
    all_imports = []

    for run_dir in run_dirs:
        events = parse_events(run_dir)
        summary = load_run_summary(run_dir)
        meta = load_run_meta(run_dir)
        blocks = load_run_blocks(run_dir)
        bounds = get_phase_bounds(summary, meta)

        for e in events:
            e["phase"] = phase_for_ts(e["timestamp"], bounds)
            all_events.append(e)

        all_summary.extend(summarize_run(run_dir, events, bounds))

        for e in events:
            if e["event"] == "imported_proposed_block":
                all_imports.append(
                    {
                        "run": e["run"],
                        "validator": e["validator"],
                        "timestamp": e["timestamp"],
                        "phase": phase_for_ts(e["timestamp"], bounds),
                        "sequence": e["sequence"],
                        "round": e["round"],
                    }
                )

        run_plot_dir = plots_dir / run_name(run_dir)
        run_plot_dir.mkdir(parents=True, exist_ok=True)

        plot_round_events_timeline(run_dir, events, bounds, run_plot_dir)
        plot_import_rounds(run_dir, events, run_plot_dir)
        plot_interblock_with_round_events(run_dir, events, blocks, bounds, run_plot_dir)

    write_csv(
        analysis_dir / "qbft_log_events.csv",
        all_events,
        ["run", "validator", "timestamp", "phase", "event", "round", "sequence", "quorum", "line"],
    )

    write_csv(
        analysis_dir / "qbft_log_summary.csv",
        all_summary,
        [
            "run",
            "phase",
            "moved_to_round_count",
            "max_moved_round",
            "imported_proposed_block_count",
            "imported_later_round_count",
            "max_import_round",
            "bft_round_summary_count",
        ],
    )

    write_csv(
        analysis_dir / "qbft_import_rounds.csv",
        all_imports,
        ["run", "validator", "timestamp", "phase", "sequence", "round"],
    )

    plot_summary(all_summary, plots_dir)

    print(f"runs: {len(run_dirs)}")
    print(f"events: {len(all_events)}")
    print(f"analysis: {analysis_dir}")
    print(f"plots: {plots_dir}")


if __name__ == "__main__":
    main()