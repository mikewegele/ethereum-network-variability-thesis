import argparse
import json
import os
import statistics

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
    blocks = sorted(blocks, key=lambda x: x["blockNumber"])
    return blocks

def interblock_times(blocks):
    dts = []
    for i in range(1, len(blocks)):
        prev = blocks[i - 1]
        cur = blocks[i]
        dt = cur["blockTimestamp"] - prev["blockTimestamp"]
        if dt >= 0:
            dts.append(dt)
    return dts

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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--baseline_run", default=None)
    ap.add_argument("--k", type=float, default=5.0)
    ap.add_argument("--stall_threshold_s", type=float, default=None)
    ap.add_argument("--window_s", type=float, default=60.0)
    ap.add_argument("--block_period_s", type=float, default=2.0)
    args = ap.parse_args()

    blocks = load_blocks(args.run)
    if len(blocks) < 2:
        print(json.dumps({"status": "insufficient_blocks", "count": len(blocks)}))
        return

    dts = interblock_times(blocks)
    mean = statistics.mean(dts) if dts else None
    variance = statistics.pvariance(dts) if len(dts) > 1 else 0.0
    max_gap = max(dts) if dts else None

    baseline_median = None
    if args.baseline_run:
        baseline_blocks = load_blocks(args.baseline_run)
        baseline_dts = interblock_times(baseline_blocks)
        if len(baseline_dts) >= 2:
            baseline_median = statistics.median(baseline_dts)

    if args.stall_threshold_s is not None:
        stall_threshold = float(args.stall_threshold_s)
        threshold_source = "explicit"
    else:
        if baseline_median is not None and baseline_median > 0:
            stall_threshold = args.k * baseline_median
            threshold_source = "baseline_median"
        else:
            stall_threshold = args.k * args.block_period_s
            threshold_source = "block_period_fallback"

    stalls = []
    for i in range(1, len(blocks)):
        prev = blocks[i - 1]
        cur = blocks[i]
        dt = cur["blockTimestamp"] - prev["blockTimestamp"]
        if dt >= stall_threshold:
            stalls.append({
                "from_block": prev["blockNumber"],
                "to_block": cur["blockNumber"],
                "dt_s": dt
            })

    cgr = chain_growth_rate(blocks, args.window_s)

    summary = {
        "status": "ok",
        "blocks_observed": len(blocks),
        "block_time_mean_s": mean,
        "block_time_variance": variance,
        "max_interblock_gap_s": max_gap,
        "stall_threshold_s": stall_threshold,
        "stall_threshold_source": threshold_source,
        "baseline_median_block_time_s": baseline_median,
        "k": args.k,
        "block_period_s": args.block_period_s,
        "stall_event_count": len(stalls),
        "stall_events": stalls,
        "chain_growth_rate_blocks_per_s_windowed": cgr,
        "chain_growth_window_s": args.window_s
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()