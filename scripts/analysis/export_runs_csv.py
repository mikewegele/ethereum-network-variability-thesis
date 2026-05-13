import argparse
import csv
import glob
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


def eprint(*args):
    print(*args, file=sys.stderr)


def safe_int(x) -> Optional[int]:
    try:
        if x is None or isinstance(x, bool):
            return None
        if isinstance(x, int):
            return x
        if isinstance(x, float):
            return int(x)
        s = str(x).strip()
        if s == "" or s.lower() == "none":
            return None
        return int(float(s))
    except Exception:
        return None


def safe_float(x) -> Optional[float]:
    try:
        if x is None or isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return float(x)
        s = str(x).strip()
        if s == "" or s.lower() == "none":
            return None
        return float(s)
    except Exception:
        return None


def load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            obj = json.load(f)
        return obj if isinstance(obj, dict) else None
    except Exception as ex:
        eprint(f"WARN: failed to parse json: {path} ({ex})")
        return None


def basename(p: str) -> str:
    return os.path.basename(os.path.normpath(p))


def normalize_run_id(run_dir: str) -> str:
    name = basename(run_dir)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}[_-]\d{2}-\d{2}-\d{2}[_-]?", "", name)
    return name


def parse_rep(run_name: str) -> Optional[int]:
    m = re.search(r"rep[_-]?(\d+)", run_name, re.IGNORECASE)
    return safe_int(m.group(1)) if m else None


def parse_latency_ms(run_name: str) -> Optional[int]:
    patterns = [
        r"lat[_-]?(\d+)ms",
        r"latency[_-]?(\d+)ms",
        r"delay[_-]?(\d+)ms",
    ]
    for p in patterns:
        m = re.search(p, run_name, re.IGNORECASE)
        if m:
            return safe_int(m.group(1))
    return None


def parse_bandwidth(run_name: str) -> Optional[str]:
    patterns = [
        r"bw[_-]?([0-9]+(?:kbit|mbit|gbit)|unlimited)",
        r"bandwidth[_-]?([0-9]+(?:kbit|mbit|gbit)|unlimited)",
        r"rate[_-]?([0-9]+(?:kbit|mbit|gbit)|unlimited)",
    ]
    for p in patterns:
        m = re.search(p, run_name, re.IGNORECASE)
        if m:
            return m.group(1).lower()
    return None


def parse_offline_n(run_name: str) -> Optional[int]:
    patterns = [
        r"offline[_-]?(\d+)",
        r"off[_-]?(\d+)",
    ]
    for p in patterns:
        m = re.search(p, run_name, re.IGNORECASE)
        if m:
            return safe_int(m.group(1))
    return None


def parse_packet_loss_pct(run_name: str) -> Optional[float]:
    patterns = [
        r"loss[_-]?([0-9]+(?:\.[0-9]+)?)pct",
        r"loss[_-]?([0-9]+(?:\.[0-9]+)?)",
        r"packetloss[_-]?([0-9]+(?:\.[0-9]+)?)",
    ]
    for p in patterns:
        m = re.search(p, run_name, re.IGNORECASE)
        if m:
            return safe_float(m.group(1))
    return None


def parse_combined(run_name: str) -> Tuple[Optional[int], Optional[str]]:
    m = re.search(
        r"(?:combined|combo|cmb)[_-]?(\d+)ms[_-]?([0-9]+(?:kbit|mbit|gbit)|unlimited)",
        run_name,
        re.IGNORECASE,
    )
    if m:
        return safe_int(m.group(1)), m.group(2).lower()

    m2 = re.search(
        r"lat[_-]?(\d+)ms[_-]?bw[_-]?([0-9]+(?:kbit|mbit|gbit)|unlimited)",
        run_name,
        re.IGNORECASE,
    )
    if m2:
        return safe_int(m2.group(1)), m2.group(2).lower()

    return None, None


def infer_scenario(run_dir: str) -> str:
    parts = os.path.normpath(run_dir).split(os.sep)
    for anchor in ("runs", "runs_pilot", "runs_extended"):
        if anchor in parts:
            i = parts.index(anchor)
            if i + 1 < len(parts):
                kind = parts[i + 1].lower()
                if kind in ("baseline", "latency", "packetloss", "bandwidth", "offline", "combined"):
                    return kind

    return "unknown"


def rate_to_kbit(rate: Optional[str]) -> Optional[int]:
    if rate is None:
        return None
    s = str(rate).strip().lower()
    if s == "unlimited":
        return 10**12
    m = re.match(r"^(\d+)\s*(kbit|mbit|gbit)$", s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    mul = {"kbit": 1, "mbit": 1000, "gbit": 1000_000}[unit]
    return n * mul


def sort_key(row: Dict[str, Any]) -> Tuple:
    scenario_order = {
        "baseline": 0,
        "latency": 1,
        "packetloss": 2,
        "bandwidth": 3,
        "offline": 4,
        "combined": 5,
        "unknown": 9,
    }

    scenario = row.get("scenario", "unknown")
    latency_ms = safe_int(row.get("latency_ms"))
    packet_loss_pct = safe_float(row.get("packet_loss_pct"))
    bandwidth = row.get("bandwidth")
    offline_n = safe_int(row.get("offline_n"))
    rep = safe_int(row.get("rep"))

    bandwidth_num = rate_to_kbit(bandwidth) if bandwidth is not None else None

    return (
        scenario_order.get(scenario, 99),
        latency_ms if latency_ms is not None else 10**9,
        packet_loss_pct if packet_loss_pct is not None else 10**9,
        -(bandwidth_num if bandwidth_num is not None else -1),
        offline_n if offline_n is not None else 10**9,
        rep if rep is not None else 10**9,
        row.get("run_dir", ""),
    )


def compute_stall_ratio(blocks_observed, stall_event_count) -> Optional[float]:
    b = safe_int(blocks_observed)
    s = safe_int(stall_event_count)
    if b is None or s is None or b <= 1:
        return None
    return s / float(b - 1)


def get_phase_metric(summary: Dict[str, Any], phase: str, key: str):
    phase_metrics = summary.get("phase_metrics")
    if not isinstance(phase_metrics, dict):
        return None
    phase_obj = phase_metrics.get(phase)
    if not isinstance(phase_obj, dict):
        return None
    return phase_obj.get(key)


FIELDNAMES = [
    "run_dir",
    "run_id",
    "scenario",
    "rep",
    "status",
    "phase_mode",
    "latency_ms",
    "packet_loss_pct",
    "bandwidth",
    "offline_n",

    "blocks_observed",
    "raw_blocks_observed",
    "genesis_outlier_dropped",
    "analysis_start_offset_s",
    "analysis_start_block",

    "block_time_mean_s",
    "block_time_variance",
    "max_interblock_gap_s",

    "stall_threshold_s",
    "stall_threshold_source",
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

    "baseline_phase_status",
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

    "stress_phase_status",
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

    "recovery_phase_status",
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


def resolve_out_path(out: Optional[str], out_root: str, dataset: Optional[str]) -> str:
    if out:
        return out
    ds = dataset or "dataset"
    return os.path.join(out_root, ds, "summary.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="experiments/runs")
    ap.add_argument("--glob", default="**/summary.json")
    ap.add_argument("--dataset", default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--out-root", default="experiments/exports")
    ap.add_argument(
        "--scenario",
        default=None,
        choices=["baseline", "latency", "packetloss", "bandwidth", "offline", "combined"],
    )
    ap.add_argument("--only-ok", action="store_true")
    ap.add_argument("--normalize-run-id", action="store_true", default=True)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    pattern = os.path.join(root, args.glob)
    paths = glob.glob(pattern, recursive=True)

    if not paths:
        raise SystemExit(f"No files matched: {pattern}")

    rows: List[Dict[str, Any]] = []

    for path in paths:
        run_dir = os.path.dirname(path)
        run_name = basename(run_dir)

        summary = load_json(path)
        if summary is None:
            continue

        scenario = infer_scenario(run_dir)
        if args.scenario and scenario != args.scenario:
            continue

        status = str(summary.get("status", "ok")).lower()
        if args.only_ok and status != "ok":
            continue

        latency_ms = None
        packet_loss_pct = None
        bandwidth = None
        offline_n = None

        if scenario == "latency":
            latency_ms = parse_latency_ms(run_name)
        elif scenario == "packetloss":
            packet_loss_pct = parse_packet_loss_pct(run_name)
        elif scenario == "bandwidth":
            bandwidth = parse_bandwidth(run_name)
        elif scenario == "offline":
            offline_n = parse_offline_n(run_name)
        elif scenario == "combined":
            latency_ms, bandwidth = parse_combined(run_name)

        row = {
            "run_dir": os.path.relpath(run_dir, os.getcwd()),
            "run_id": normalize_run_id(run_dir) if args.normalize_run_id else run_name,
            "scenario": scenario,
            "rep": parse_rep(run_name),
            "status": summary.get("status"),
            "phase_mode": summary.get("phase_mode"),

            "latency_ms": latency_ms,
            "packet_loss_pct": packet_loss_pct,
            "bandwidth": bandwidth,
            "offline_n": offline_n,

            "blocks_observed": summary.get("blocks_observed"),
            "raw_blocks_observed": summary.get("raw_blocks_observed"),
            "genesis_outlier_dropped": summary.get("genesis_outlier_dropped"),
            "analysis_start_offset_s": summary.get("analysis_start_offset_s"),
            "analysis_start_block": summary.get("analysis_start_block"),

            "block_time_mean_s": summary.get("block_time_mean_s"),
            "block_time_variance": summary.get("block_time_variance"),
            "max_interblock_gap_s": summary.get("max_interblock_gap_s"),

            "stall_threshold_s": summary.get("stall_threshold_s"),
            "stall_threshold_source": summary.get("stall_threshold_source"),
            "baseline_median_block_time_s": summary.get("baseline_median_block_time_s"),
            "baseline_p95_block_time_s": summary.get("baseline_p95_block_time_s"),
            "baseline_analysis_start_block": summary.get("baseline_analysis_start_block"),
            "k": summary.get("k"),
            "block_period_s": summary.get("block_period_s"),

            "stall_event_count": summary.get("stall_event_count"),
            "stall_ratio": compute_stall_ratio(
                summary.get("blocks_observed"),
                summary.get("stall_event_count"),
            ),
            "stall_duration_total_s": summary.get("stall_duration_total_s"),
            "missing_finalization_interval_threshold_s": summary.get("missing_finalization_interval_threshold_s"),
            "missing_finalization_interval_count": summary.get("missing_finalization_interval_count"),
            "delayed_finalization_threshold_s": summary.get("delayed_finalization_threshold_s"),
            "delayed_finalization_event_count": summary.get("delayed_finalization_event_count"),

            "chain_growth_rate_blocks_per_s_windowed": summary.get("chain_growth_rate_blocks_per_s_windowed"),
            "chain_growth_window_s": summary.get("chain_growth_window_s"),

            "tx_total": summary.get("tx_total"),
            "tx_per_block_mean": summary.get("tx_per_block_mean"),
            "tx_per_block_median": summary.get("tx_per_block_median"),
            "tx_per_block_p95": summary.get("tx_per_block_p95"),
            "tx_per_block_max": summary.get("tx_per_block_max"),

            "baseline_phase_status": get_phase_metric(summary, "baseline_phase", "status"),
            "baseline_phase_blocks_observed": get_phase_metric(summary, "baseline_phase", "blocks_observed"),
            "baseline_phase_block_time_mean_s": get_phase_metric(summary, "baseline_phase", "block_time_mean_s"),
            "baseline_phase_block_time_median_s": get_phase_metric(summary, "baseline_phase", "block_time_median_s"),
            "baseline_phase_block_time_p95_s": get_phase_metric(summary, "baseline_phase", "block_time_p95_s"),
            "baseline_phase_max_interblock_gap_s": get_phase_metric(summary, "baseline_phase", "max_interblock_gap_s"),
            "baseline_phase_chain_growth_rate_blocks_per_s_windowed": get_phase_metric(summary, "baseline_phase", "chain_growth_rate_blocks_per_s_windowed"),
            "baseline_phase_tx_total": get_phase_metric(summary, "baseline_phase", "tx_total"),
            "baseline_phase_tx_per_block_mean": get_phase_metric(summary, "baseline_phase", "tx_per_block_mean"),
            "baseline_phase_stall_event_count": get_phase_metric(summary, "baseline_phase", "stall_event_count"),
            "baseline_phase_stall_duration_total_s": get_phase_metric(summary, "baseline_phase", "stall_duration_total_s"),
            "baseline_phase_missing_finalization_interval_count": get_phase_metric(summary, "baseline_phase", "missing_finalization_interval_count"),

            "stress_phase_status": get_phase_metric(summary, "stress_phase", "status"),
            "stress_phase_blocks_observed": get_phase_metric(summary, "stress_phase", "blocks_observed"),
            "stress_phase_block_time_mean_s": get_phase_metric(summary, "stress_phase", "block_time_mean_s"),
            "stress_phase_block_time_median_s": get_phase_metric(summary, "stress_phase", "block_time_median_s"),
            "stress_phase_block_time_p95_s": get_phase_metric(summary, "stress_phase", "block_time_p95_s"),
            "stress_phase_max_interblock_gap_s": get_phase_metric(summary, "stress_phase", "max_interblock_gap_s"),
            "stress_phase_chain_growth_rate_blocks_per_s_windowed": get_phase_metric(summary, "stress_phase", "chain_growth_rate_blocks_per_s_windowed"),
            "stress_phase_tx_total": get_phase_metric(summary, "stress_phase", "tx_total"),
            "stress_phase_tx_per_block_mean": get_phase_metric(summary, "stress_phase", "tx_per_block_mean"),
            "stress_phase_stall_event_count": get_phase_metric(summary, "stress_phase", "stall_event_count"),
            "stress_phase_stall_duration_total_s": get_phase_metric(summary, "stress_phase", "stall_duration_total_s"),
            "stress_phase_missing_finalization_interval_count": get_phase_metric(summary, "stress_phase", "missing_finalization_interval_count"),

            "recovery_phase_status": get_phase_metric(summary, "recovery_phase", "status"),
            "recovery_phase_blocks_observed": get_phase_metric(summary, "recovery_phase", "blocks_observed"),
            "recovery_phase_block_time_mean_s": get_phase_metric(summary, "recovery_phase", "block_time_mean_s"),
            "recovery_phase_block_time_median_s": get_phase_metric(summary, "recovery_phase", "block_time_median_s"),
            "recovery_phase_block_time_p95_s": get_phase_metric(summary, "recovery_phase", "block_time_p95_s"),
            "recovery_phase_max_interblock_gap_s": get_phase_metric(summary, "recovery_phase", "max_interblock_gap_s"),
            "recovery_phase_chain_growth_rate_blocks_per_s_windowed": get_phase_metric(summary, "recovery_phase", "chain_growth_rate_blocks_per_s_windowed"),
            "recovery_phase_tx_total": get_phase_metric(summary, "recovery_phase", "tx_total"),
            "recovery_phase_tx_per_block_mean": get_phase_metric(summary, "recovery_phase", "tx_per_block_mean"),
            "recovery_phase_stall_event_count": get_phase_metric(summary, "recovery_phase", "stall_event_count"),
            "recovery_phase_stall_duration_total_s": get_phase_metric(summary, "recovery_phase", "stall_duration_total_s"),
            "recovery_phase_missing_finalization_interval_count": get_phase_metric(summary, "recovery_phase", "missing_finalization_interval_count"),
        }

        rows.append(row)

    rows.sort(key=sort_key)

    out_path = resolve_out_path(args.out, args.out_root, args.dataset)
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k) for k in FIELDNAMES})

    print(out_path)


if __name__ == "__main__":
    main()