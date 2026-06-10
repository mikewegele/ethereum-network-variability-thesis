import argparse
import json
import math
import os
import statistics
from typing import Optional


def read_jsonl(path: str):
    out = []
    if not os.path.exists(path):
        return out
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if "error" in obj:
                continue
            out.append(obj)
    return out


def load_blocks(run_dir: str):
    blocks_path = os.path.join(run_dir, "rpc", "blocks.jsonl")
    blocks = read_jsonl(blocks_path)
    blocks = [b for b in blocks if isinstance(b.get("blockNumber"), int)]
    blocks = sorted(blocks, key=lambda x: x["blockNumber"])
    return blocks


def load_head_samples(run_dir: str):
    head_path = os.path.join(run_dir, "rpc", "head.jsonl")
    heads = read_jsonl(head_path)
    out = []
    for h in heads:
        ts_local = h.get("ts_local")
        bn = h.get("blockNumber")
        if isinstance(ts_local, (int, float)) and isinstance(bn, int):
            out.append({"ts_local": float(ts_local), "blockNumber": bn})
    out.sort(key=lambda x: x["ts_local"])
    return out


def load_run_meta(run_dir: str):
    meta_path = os.path.join(run_dir, "rpc", "run_meta.json")
    if not os.path.exists(meta_path):
        return {}
    with open(meta_path, "r", encoding="utf-8") as f:
        return json.load(f)


def drop_genesis_outlier(blocks, block_period_s: float):
    if len(blocks) < 2:
        return blocks, False

    first = blocks[0]
    second = blocks[1]
    if first.get("blockNumber") != 0:
        return blocks, False

    first_ts = first.get("blockTimestamp")
    second_ts = second.get("blockTimestamp")
    if not isinstance(first_ts, int) or not isinstance(second_ts, int):
        return blocks, False

    if (second_ts - first_ts) >= max(60.0, 10.0 * float(block_period_s)):
        return blocks[1:], True

    return blocks, False


def find_block_at_offset(run_dir: str, offset_s: float) -> Optional[int]:
    if offset_s <= 0:
        return None

    meta = load_run_meta(run_dir)
    ts_start_local = meta.get("ts_start_local")
    if not isinstance(ts_start_local, (int, float)):
        return None

    target_ts = float(ts_start_local) + float(offset_s)
    heads = load_head_samples(run_dir)
    if not heads:
        return None

    for h in heads:
        if h["ts_local"] >= target_ts:
            return h["blockNumber"]

    return heads[-1]["blockNumber"]


def filter_blocks_between(blocks, start_block: Optional[int], end_block_exclusive: Optional[int]):
    out = []
    for b in blocks:
        bn = b["blockNumber"]
        if start_block is not None and bn < start_block:
            continue
        if end_block_exclusive is not None and bn >= end_block_exclusive:
            continue
        out.append(b)
    return out


def interblock_times(blocks):
    dts = []
    for i in range(1, len(blocks)):
        prev = blocks[i - 1]
        cur = blocks[i]
        dt = cur["blockTimestamp"] - prev["blockTimestamp"]
        if dt >= 0:
            dts.append(dt)
    return dts


def percentile(values, p: float):
    if not values:
        return None
    if p <= 0:
        return min(values)
    if p >= 100:
        return max(values)
    xs = sorted(values)
    k = (len(xs) - 1) * (p / 100.0)
    f = int(k)
    c = min(f + 1, len(xs) - 1)
    if f == c:
        return xs[f]
    d0 = xs[f] * (c - k)
    d1 = xs[c] * (k - f)
    return d0 + d1


def chain_growth_rate(blocks, window_s: float):
    if len(blocks) < 2:
        return None
    t0 = blocks[0]["blockTimestamp"]
    t1 = blocks[-1]["blockTimestamp"]
    span = max(0.0, t1 - t0)
    if span == 0:
        return None
    effective_window = min(window_s, span)
    t_start = t1 - effective_window
    count = 0
    for b in blocks:
        if b["blockTimestamp"] >= t_start:
            count += 1
    return count / effective_window


def compute_gap_metrics(blocks, phase_start_ts: Optional[int], phase_end_ts: Optional[int], stall_threshold_s: float, missing_threshold_s: float):
    gaps = []
    if phase_start_ts is None or phase_end_ts is None or phase_end_ts < phase_start_ts:
        return {
            "gaps": [],
            "stall_event_count": 0,
            "stall_events": [],
            "stall_duration_total_s": 0.0,
            "missing_finalization_interval_count": 0,
        }

    if not blocks:
        gaps.append({
            "from_block": None,
            "to_block": None,
            "from_ts": phase_start_ts,
            "to_ts": phase_end_ts,
            "dt_s": phase_end_ts - phase_start_ts,
            "kind": "phase_start_to_phase_end",
        })
    else:
        first = blocks[0]
        if first["blockTimestamp"] > phase_start_ts:
            gaps.append({
                "from_block": None,
                "to_block": first["blockNumber"],
                "from_ts": phase_start_ts,
                "to_ts": first["blockTimestamp"],
                "dt_s": first["blockTimestamp"] - phase_start_ts,
                "kind": "phase_start_to_first_block",
            })

        for i in range(1, len(blocks)):
            prev = blocks[i - 1]
            cur = blocks[i]
            dt = cur["blockTimestamp"] - prev["blockTimestamp"]
            if dt >= 0:
                gaps.append({
                    "from_block": prev["blockNumber"],
                    "to_block": cur["blockNumber"],
                    "from_ts": prev["blockTimestamp"],
                    "to_ts": cur["blockTimestamp"],
                    "dt_s": dt,
                    "kind": "inter_block",
                })

        last = blocks[-1]
        if phase_end_ts > last["blockTimestamp"]:
            gaps.append({
                "from_block": last["blockNumber"],
                "to_block": None,
                "from_ts": last["blockTimestamp"],
                "to_ts": phase_end_ts,
                "dt_s": phase_end_ts - last["blockTimestamp"],
                "kind": "last_block_to_phase_end",
            })

    stall_events = []
    stall_duration_total_s = 0.0
    missing_finalization_interval_count = 0

    for g in gaps:
        dt = g["dt_s"]
        if dt >= stall_threshold_s:
            stall_events.append({
                "from_block": g["from_block"],
                "to_block": g["to_block"],
                "dt_s": dt,
                "kind": g["kind"],
            })
            stall_duration_total_s += dt

        if dt >= missing_threshold_s and missing_threshold_s > 0:
            missing_finalization_interval_count += int(math.floor(dt / missing_threshold_s))

    return {
        "gaps": gaps,
        "stall_event_count": len(stall_events),
        "stall_events": stall_events,
        "stall_duration_total_s": stall_duration_total_s,
        "missing_finalization_interval_count": missing_finalization_interval_count,
    }


def summarize_phase(blocks, window_s: float, phase_start_ts: Optional[int] = None, phase_end_ts: Optional[int] = None, stall_threshold_s: Optional[float] = None, missing_threshold_s: Optional[float] = None):
    tx_counts = [b["txCount"] for b in blocks if isinstance(b.get("txCount"), int)]
    dts = interblock_times(blocks)

    summary = {
        "blocks_observed": len(blocks),
        "tx_total": sum(tx_counts) if tx_counts else None,
        "tx_per_block_mean": statistics.mean(tx_counts) if tx_counts else None,
        "tx_per_block_median": statistics.median(tx_counts) if tx_counts else None,
        "tx_per_block_p95": percentile(tx_counts, 95) if tx_counts else None,
        "tx_per_block_max": max(tx_counts) if tx_counts else None,
    }

    if len(blocks) >= 2:
        summary.update({
            "status": "ok",
            "block_time_mean_s": statistics.mean(dts) if dts else None,
            "block_time_median_s": statistics.median(dts) if dts else None,
            "block_time_p95_s": percentile(dts, 95) if dts else None,
            "block_time_variance": statistics.pvariance(dts) if len(dts) > 1 else 0.0,
            "max_interblock_gap_s": max(dts) if dts else None,
            "chain_growth_rate_blocks_per_s_windowed": chain_growth_rate(blocks, window_s),
        })
    else:
        summary.update({
            "status": "insufficient_blocks",
            "block_time_mean_s": None,
            "block_time_median_s": None,
            "block_time_p95_s": None,
            "block_time_variance": None,
            "max_interblock_gap_s": None,
            "chain_growth_rate_blocks_per_s_windowed": None,
        })

    if stall_threshold_s is not None and missing_threshold_s is not None:
        gap_metrics = compute_gap_metrics(
            blocks,
            phase_start_ts,
            phase_end_ts,
            stall_threshold_s,
            missing_threshold_s,
        )
        summary.update({
            "phase_start_ts": phase_start_ts,
            "phase_end_ts": phase_end_ts,
            "stall_event_count": gap_metrics["stall_event_count"],
            "stall_events": gap_metrics["stall_events"],
            "stall_duration_total_s": gap_metrics["stall_duration_total_s"],
            "missing_finalization_interval_count": gap_metrics["missing_finalization_interval_count"],
        })

    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--baseline_run", default=None)
    ap.add_argument("--k", type=float, default=5.0)
    ap.add_argument("--stall_threshold_s", type=float, default=None)
    ap.add_argument("--window_s", type=float, default=60.0)
    ap.add_argument("--block_period_s", type=float, default=2.0)
    ap.add_argument("--request_timeout_s", type=float, default=None)
    ap.add_argument("--analysis_start_offset_s", type=float, default=0.0)

    ap.add_argument("--phase_mode", choices=["steady", "phased"], default="steady")
    ap.add_argument("--warmup_s", type=float, default=0.0)
    ap.add_argument("--baseline_s", type=float, default=0.0)
    ap.add_argument("--stress_s", type=float, default=0.0)
    ap.add_argument("--recovery_s", type=float, default=0.0)

    args = ap.parse_args()

    original_raw_blocks = load_blocks(args.run)
    raw_blocks, genesis_outlier_dropped = drop_genesis_outlier(original_raw_blocks, args.block_period_s)

    analysis_start_block = find_block_at_offset(args.run, args.analysis_start_offset_s)
    blocks = filter_blocks_between(raw_blocks, analysis_start_block, None)

    if len(blocks) < 1:
        print(json.dumps({
            "status": "insufficient_blocks",
            "count": len(blocks),
            "analysis_start_offset_s": args.analysis_start_offset_s,
            "analysis_start_block": analysis_start_block,
        }))
        return

    dts = interblock_times(blocks)
    mean = statistics.mean(dts) if dts else None
    variance = statistics.pvariance(dts) if len(dts) > 1 else 0.0
    max_gap = max(dts) if dts else None

    baseline_median = None
    baseline_p95 = None
    baseline_analysis_start_block = None

    if args.baseline_run:
        baseline_original_raw_blocks = load_blocks(args.baseline_run)
        baseline_raw_blocks, _ = drop_genesis_outlier(baseline_original_raw_blocks, args.block_period_s)
        baseline_analysis_start_block = find_block_at_offset(
            args.baseline_run,
            args.analysis_start_offset_s,
        )
        baseline_blocks = filter_blocks_between(
            baseline_raw_blocks,
            baseline_analysis_start_block,
            None,
        )
        baseline_dts = interblock_times(baseline_blocks)
        if len(baseline_dts) >= 2:
            baseline_median = statistics.median(baseline_dts)
            baseline_p95 = percentile(baseline_dts, 95)

    request_timeout_s = (
        float(args.request_timeout_s)
        if args.request_timeout_s is not None
        else 2.0 * float(args.block_period_s)
    )

    missing_finalization_interval_threshold_s = request_timeout_s

    if args.stall_threshold_s is not None:
        stall_threshold = float(args.stall_threshold_s)
        threshold_source = "explicit"
    else:
        stall_threshold = 3.0 * request_timeout_s
        threshold_source = "request_timeout_x3"

    analysis_meta = load_run_meta(args.run)
    ts_start_local = analysis_meta.get("ts_start_local")
    ts_end_local = analysis_meta.get("ts_end_local")

    analysis_start_ts = None
    analysis_end_ts = None
    if isinstance(ts_start_local, (int, float)):
        analysis_start_ts = int(float(ts_start_local) + float(args.analysis_start_offset_s))
    if isinstance(ts_end_local, (int, float)):
        analysis_end_ts = int(float(ts_end_local))

    overall_gap_metrics = compute_gap_metrics(
        blocks,
        analysis_start_ts,
        analysis_end_ts,
        stall_threshold,
        missing_finalization_interval_threshold_s,
    )

    delayed_finalization_threshold_s = baseline_p95
    delayed_finalization_event_count = 0
    delayed_finalization_events = []
    if delayed_finalization_threshold_s is not None:
        for i in range(1, len(blocks)):
            prev = blocks[i - 1]
            cur = blocks[i]
            dt = cur["blockTimestamp"] - prev["blockTimestamp"]
            if dt > delayed_finalization_threshold_s:
                delayed_finalization_event_count += 1
                delayed_finalization_events.append({
                    "from_block": prev["blockNumber"],
                    "to_block": cur["blockNumber"],
                    "dt_s": dt,
                })

    cgr = chain_growth_rate(blocks, args.window_s)

    tx_counts = []
    for b in blocks:
        if "txCount" in b and isinstance(b["txCount"], int):
            tx_counts.append(b["txCount"])

    tx_total = sum(tx_counts) if tx_counts else None
    tx_mean = statistics.mean(tx_counts) if tx_counts else None
    tx_median = statistics.median(tx_counts) if tx_counts else None
    tx_p95 = percentile(tx_counts, 95) if tx_counts else None
    tx_max = max(tx_counts) if tx_counts else None

    phase_metrics = None
    if args.phase_mode == "phased":
        baseline_phase_start = find_block_at_offset(args.run, args.warmup_s)
        stress_phase_start = find_block_at_offset(args.run, args.warmup_s + args.baseline_s)
        recovery_phase_start = find_block_at_offset(args.run, args.warmup_s + args.baseline_s + args.stress_s)

        baseline_phase_blocks = filter_blocks_between(raw_blocks, baseline_phase_start, stress_phase_start)
        stress_phase_blocks = filter_blocks_between(raw_blocks, stress_phase_start, recovery_phase_start)
        recovery_phase_blocks = filter_blocks_between(raw_blocks, recovery_phase_start, None)

        baseline_phase_start_ts = int(float(ts_start_local) + float(args.warmup_s)) if isinstance(ts_start_local, (int, float)) else None
        stress_phase_start_ts = int(float(ts_start_local) + float(args.warmup_s + args.baseline_s)) if isinstance(ts_start_local, (int, float)) else None
        recovery_phase_start_ts = int(float(ts_start_local) + float(args.warmup_s + args.baseline_s + args.stress_s)) if isinstance(ts_start_local, (int, float)) else None
        recovery_phase_end_ts = int(float(ts_start_local) + float(args.warmup_s + args.baseline_s + args.stress_s + args.recovery_s)) if isinstance(ts_start_local, (int, float)) else None

        phase_metrics = {
            "baseline_phase": {
                "start_block": baseline_phase_start,
                "end_block_exclusive": stress_phase_start,
                **summarize_phase(
                    baseline_phase_blocks,
                    args.window_s,
                    baseline_phase_start_ts,
                    stress_phase_start_ts,
                    stall_threshold,
                    missing_finalization_interval_threshold_s,
                ),
            },
            "stress_phase": {
                "start_block": stress_phase_start,
                "end_block_exclusive": recovery_phase_start,
                **summarize_phase(
                    stress_phase_blocks,
                    args.window_s,
                    stress_phase_start_ts,
                    recovery_phase_start_ts,
                    stall_threshold,
                    missing_finalization_interval_threshold_s,
                ),
            },
            "recovery_phase": {
                "start_block": recovery_phase_start,
                "end_block_exclusive": None,
                **summarize_phase(
                    recovery_phase_blocks,
                    args.window_s,
                    recovery_phase_start_ts,
                    recovery_phase_end_ts,
                    stall_threshold,
                    missing_finalization_interval_threshold_s,
                ),
            },
        }

    summary = {
        "status": "ok",
        "blocks_observed": len(blocks),
        "raw_blocks_observed": len(raw_blocks),
        "genesis_outlier_dropped": genesis_outlier_dropped,

        "analysis_start_offset_s": args.analysis_start_offset_s,
        "analysis_start_block": analysis_start_block,

        "block_time_mean_s": mean,
        "block_time_variance": variance,
        "max_interblock_gap_s": max_gap,

        "stall_threshold_s": stall_threshold,
        "stall_threshold_source": threshold_source,
        "baseline_median_block_time_s": baseline_median,
        "baseline_p95_block_time_s": baseline_p95,
        "baseline_analysis_start_block": baseline_analysis_start_block,
        "k": args.k,
        "block_period_s": args.block_period_s,
        "request_timeout_s": request_timeout_s,

        "stall_event_count": overall_gap_metrics["stall_event_count"],
        "stall_events": overall_gap_metrics["stall_events"],
        "stall_duration_total_s": overall_gap_metrics["stall_duration_total_s"],

        "missing_finalization_interval_threshold_s": missing_finalization_interval_threshold_s,
        "missing_finalization_interval_count": overall_gap_metrics["missing_finalization_interval_count"],

        "delayed_finalization_threshold_s": delayed_finalization_threshold_s,
        "delayed_finalization_event_count": delayed_finalization_event_count,
        "delayed_finalization_events": delayed_finalization_events,

        "chain_growth_rate_blocks_per_s_windowed": cgr,
        "chain_growth_window_s": args.window_s,

        "tx_total": tx_total,
        "tx_per_block_mean": tx_mean,
        "tx_per_block_median": tx_median,
        "tx_per_block_p95": tx_p95,
        "tx_per_block_max": tx_max,
    }

    if phase_metrics is not None:
        summary["phase_mode"] = "phased"
        summary["phase_metrics"] = phase_metrics
    else:
        summary["phase_mode"] = "steady"

    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()