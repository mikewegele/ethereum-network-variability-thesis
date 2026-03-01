import csv
import glob
import json
import os
import re

def parse_delay_ms(run_dir: str):
    name = os.path.basename(run_dir)
    m = re.search(r"delay(\d+)ms", name)
    return int(m.group(1)) if m else None

rows = []
for path in glob.glob("experiments/runs/**/summary.json", recursive=True):
    run_dir = os.path.dirname(path)
    with open(path, "r", encoding="utf-8") as f:
        s = json.load(f)

    blocks = s.get("blocks_observed")
    stalls = s.get("stall_event_count")
    stall_ratio = None
    if isinstance(blocks, int) and blocks and blocks > 1 and isinstance(stalls, int):
        stall_ratio = stalls / (blocks - 1)

    rows.append({
        "run_dir": run_dir,
        "delay_ms": parse_delay_ms(run_dir),
        "blocks_observed": blocks,
        "block_time_mean_s": s.get("block_time_mean_s"),
        "block_time_variance": s.get("block_time_variance"),
        "max_interblock_gap_s": s.get("max_interblock_gap_s"),
        "stall_threshold_s": s.get("stall_threshold_s"),
        "stall_event_count": stalls,
        "stall_ratio": stall_ratio,
        "cgr_blocks_per_s": s.get("chain_growth_rate_blocks_per_s_windowed"),
        "baseline_median_s": s.get("baseline_median_block_time_s"),
        "k": s.get("k"),
        "window_s": s.get("chain_growth_window_s"),
    })

rows.sort(key=lambda r: (r["delay_ms"] if r["delay_ms"] is not None else 10**9, r["run_dir"]))

out_csv = "experiments/summary_all_runs.csv"
os.makedirs("experiments", exist_ok=True)
with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else [])
    w.writeheader()
    for r in rows:
        w.writerow(r)

print(out_csv)