import csv
import glob
import json
import os
import re


def parse_delay_ms(run_dir: str):
    name = os.path.basename(run_dir)
    m = re.search(r"delay(\d+)ms", name)
    return int(m.group(1)) if m else None


def parse_rate(run_dir: str):
    name = os.path.basename(run_dir)
    m = re.search(r"rate_([^_]+)", name)
    return m.group(1) if m else None


def parse_offline(run_dir: str):
    name = os.path.basename(run_dir)
    m = re.search(r"offline(\d+)", name)
    return int(m.group(1)) if m else None


def parse_rep(run_dir: str):
    name = os.path.basename(run_dir)
    m = re.search(r"rep(\d+)", name, re.IGNORECASE)
    return int(m.group(1)) if m else None


def parse_load_tag(run_dir: str):
    name = os.path.basename(run_dir).lower()
    if "load" not in name:
        return None
    m = re.search(r"load(\d+)", name)  # e.g. load200
    if m:
        return f"load{m.group(1)}"
    return "load"


def infer_scenario(delay_ms, rate, offline_n):
    if offline_n is not None:
        return f"offline{offline_n}"
    if rate is not None:
        return "rate"
    if delay_ms is not None:
        return "delay"
    return "baseline_or_other"


rows = []
for path in glob.glob("experiments/runs/**/summary.json", recursive=True):
    run_dir = os.path.dirname(path)
    with open(path, "r", encoding="utf-8") as f:
        s = json.load(f)

    delay_ms = parse_delay_ms(run_dir)
    rate = parse_rate(run_dir)
    offline_n = parse_offline(run_dir)
    rep = parse_rep(run_dir)
    load_tag = parse_load_tag(run_dir)

    status = s.get("status", "ok")

    blocks = s.get("blocks_observed")
    stalls = s.get("stall_event_count")

    stall_ratio = None
    if isinstance(blocks, int) and blocks and blocks > 1 and isinstance(stalls, int):
        stall_ratio = stalls / (blocks - 1)

    rows.append({
        "run_dir": run_dir,
        "scenario": infer_scenario(delay_ms, rate, offline_n),
        "rep": rep,
        "load_tag": load_tag,

        "delay_ms": delay_ms,
        "rate": rate,
        "offline_n": offline_n,

        "status": status,

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

        "tx_total": s.get("tx_total"),
        "tx_per_block_mean": s.get("tx_per_block_mean"),
        "tx_per_block_median": s.get("tx_per_block_median"),
        "tx_per_block_p95": s.get("tx_per_block_p95"),
        "tx_per_block_max": s.get("tx_per_block_max"),
    })


def sort_key(r):
    scenario = r.get("scenario") or ""
    delay_ms = r.get("delay_ms")
    delay_key = delay_ms if isinstance(delay_ms, int) else 10**9
    rate = r.get("rate") or ""
    offline_n = r.get("offline_n")
    offline_key = offline_n if isinstance(offline_n, int) else -1
    rep = r.get("rep")
    rep_key = rep if isinstance(rep, int) else 10**9
    load_tag = r.get("load_tag") or ""
    return (scenario, delay_key, rate, offline_key, load_tag, rep_key, r.get("run_dir") or "")


rows.sort(key=sort_key)

out_csv = "experiments/summary_all_runs.csv"
os.makedirs("experiments", exist_ok=True)

fieldnames = [
    "run_dir",
    "scenario",
    "rep",
    "load_tag",
    "delay_ms",
    "rate",
    "offline_n",
    "status",
    "blocks_observed",
    "block_time_mean_s",
    "block_time_variance",
    "max_interblock_gap_s",
    "stall_threshold_s",
    "stall_event_count",
    "stall_ratio",
    "cgr_blocks_per_s",
    "baseline_median_s",
    "k",
    "window_s",
    "tx_total",
    "tx_per_block_mean",
    "tx_per_block_median",
    "tx_per_block_p95",
    "tx_per_block_max",
]

with open(out_csv, "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, fieldnames=fieldnames)
    w.writeheader()
    for r in rows:
        w.writerow({k: r.get(k) for k in fieldnames})

print(out_csv)