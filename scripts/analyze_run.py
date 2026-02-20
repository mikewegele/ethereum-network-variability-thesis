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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--expected_block_s", type=float, default=2.0)
    ap.add_argument("--stall_threshold_s", type=float, default=10.0)
    args = ap.parse_args()

    blocks_path = os.path.join(args.run, "rpc", "blocks.jsonl")
    blocks = read_jsonl(blocks_path)
    blocks = sorted(blocks, key=lambda x: x["blockNumber"])

    if len(blocks) < 2:
        print(json.dumps({"status": "insufficient_blocks", "count": len(blocks)}))
        return

    block_times = []
    for i in range(1, len(blocks)):
        dt = blocks[i]["blockTimestamp"] - blocks[i-1]["blockTimestamp"]
        if dt >= 0:
            block_times.append(dt)

    variance = statistics.pvariance(block_times) if len(block_times) > 1 else 0.0
    mean = statistics.mean(block_times) if block_times else None

    stalls = []
    last_seen_local = blocks[0]["ts_local"]
    last_bn = blocks[0]["blockNumber"]
    for b in blocks[1:]:
        gap_local = b["ts_local"] - last_seen_local
        if gap_local >= args.stall_threshold_s and b["blockNumber"] == last_bn:
            stalls.append({"from_local": last_seen_local, "to_local": b["ts_local"], "gap_s": gap_local})
        if b["blockNumber"] != last_bn:
            last_bn = b["blockNumber"]
            last_seen_local = b["ts_local"]

    summary = {
        "status": "ok",
        "blocks_observed": len(blocks),
        "block_time_mean_s": mean,
        "block_time_variance": variance,
        "stall_events": stalls,
        "stall_event_count": len(stalls),
        "stall_threshold_s": args.stall_threshold_s
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()