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
        return int(s)
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


def parse_delay_ms(run_name: str) -> Optional[int]:
    m = re.search(r"delay[_-]?(\d+)\s*ms", run_name, re.IGNORECASE)
    return safe_int(m.group(1)) if m else None


def parse_rate(run_name: str) -> Optional[str]:
    m = re.search(r"rate[_-]([^_]+?)(?:_|$)", run_name, re.IGNORECASE)
    if m:
        return m.group(1)
    m2 = re.search(r"\brate\s*([0-9]+(?:kbit|mbit|gbit))\b", run_name, re.IGNORECASE)
    return m2.group(1) if m2 else None


def parse_offline(run_name: str) -> Optional[int]:
    m = re.search(r"offline[_-]?(\d+)", run_name, re.IGNORECASE)
    return safe_int(m.group(1)) if m else None


def parse_rep(run_name: str) -> Optional[int]:
    m = re.search(r"rep[_-]?(\d+)", run_name, re.IGNORECASE)
    if m:
        return safe_int(m.group(1))
    m2 = re.search(r"(?:^|[_-])(\d{2})(?:$|[_-])", run_name)
    return safe_int(m2.group(1)) if m2 else None


def parse_load_tag(run_name: str) -> Optional[str]:
    low = run_name.lower()
    if "load" not in low:
        return None
    m = re.search(r"load[_-]?(\d+)", low)
    if m:
        return f"load{m.group(1)}"
    return "load"


def infer_scenario(delay_ms: Optional[int], rate: Optional[str], offline_n: Optional[int], run_path: str) -> str:
    parts = os.path.normpath(run_path).split(os.sep)
    if "runs" in parts:
        i = parts.index("runs")
        if i + 1 < len(parts):
            kind = parts[i + 1].lower()
            if kind in ("rate", "delay", "offline", "baseline"):
                return kind
    if offline_n is not None:
        return "offline"
    if rate is not None:
        return "rate"
    if delay_ms is not None:
        return "delay"
    return "baseline_or_other"


def compute_stall_ratio(blocks, stalls) -> Optional[float]:
    b = safe_int(blocks)
    s = safe_int(stalls)
    if b is None or s is None or b <= 1:
        return None
    return s / float(b - 1)


def normalize_run_id(run_dir: str) -> str:
    name = basename(run_dir)
    name = re.sub(r"^\d{4}-\d{2}-\d{2}[_-]+", "", name)
    return name


def rate_to_kbit(rate: str) -> Optional[int]:
    if rate is None:
        return None
    r = str(rate).strip().lower()
    if r == "unlimited":
        return 10**12
    m = re.match(r"^(\d+)\s*(kbit|mbit|gbit)$", r)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    mul = {"kbit": 1, "mbit": 1000, "gbit": 1000_000}.get(unit, 1)
    return n * mul


def sort_key(r: Dict[str, Any]) -> Tuple:
    scenario = r.get("scenario") or ""
    delay_key = safe_int(r.get("delay_ms"))
    delay_key = delay_key if delay_key is not None else 10**9

    rate = r.get("rate") or ""
    rate_num = rate_to_kbit(rate)
    rate_num_key = rate_num if rate_num is not None else 10**12

    offline_key = safe_int(r.get("offline_n"))
    offline_key = offline_key if offline_key is not None else -1

    load_tag = r.get("load_tag") or ""
    rep_key = safe_int(r.get("rep"))
    rep_key = rep_key if rep_key is not None else 10**9

    return (scenario, delay_key, rate_num_key, rate, offline_key, load_tag, rep_key, r.get("run_dir") or "")


FIELDNAMES = [
    "run_dir",
    "run_id",
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


def resolve_out_path(out: Optional[str], out_root: str, dataset: Optional[str], scenario: Optional[str]) -> str:
    if out:
        return out
    ds = dataset or "dataset"
    sc = scenario or "all"
    return os.path.join(out_root, ds, sc, "summary.csv")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="experiments/runs")
    ap.add_argument("--glob", default="**/summary.json")
    ap.add_argument("--scenario", default=None, help="rate|delay|offline|baseline|baseline_or_other")
    ap.add_argument("--dataset", default=None, help="e.g. 2026-03-05 (used for default out path)")
    ap.add_argument("--out", default=None, help="explicit output csv path (overrides default)")
    ap.add_argument("--out-root", default="experiments/exports", help="base dir for default output")
    ap.add_argument("--only-ok", action="store_true")
    ap.add_argument("--fail-on-missing", action="store_true")
    ap.add_argument("--normalize-run-id", action="store_true", default=True)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    pattern = os.path.join(root, args.glob)

    paths = glob.glob(pattern, recursive=True)
    if not paths:
        msg = f"no files matched: {pattern}"
        if args.fail_on_missing:
            raise SystemExit(msg)
        eprint(f"WARN: {msg}")

    rows: List[Dict[str, Any]] = []
    for path in paths:
        run_dir = os.path.dirname(path)
        run_name = basename(run_dir)

        s = load_json(path)
        if s is None:
            continue

        delay_ms = parse_delay_ms(run_name)
        rate = parse_rate(run_name)
        offline_n = parse_offline(run_name)
        rep = parse_rep(run_name)
        load_tag = parse_load_tag(run_name)

        scenario = infer_scenario(delay_ms, rate, offline_n, run_dir)
        if args.scenario and scenario != args.scenario:
            continue

        status = s.get("status", "ok")
        if args.only_ok and str(status).lower() != "ok":
            continue

        blocks = s.get("blocks_observed")
        stalls = s.get("stall_event_count")

        rows.append({
            "run_dir": os.path.relpath(run_dir, os.getcwd()),
            "run_id": normalize_run_id(run_dir) if args.normalize_run_id else run_name,
            "scenario": scenario,
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
            "stall_ratio": compute_stall_ratio(blocks, stalls),
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

    rows.sort(key=sort_key)

    out_path = resolve_out_path(args.out, args.out_root, args.dataset, args.scenario)
    out_path = os.path.abspath(out_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k) for k in FIELDNAMES})

    print(out_path)


if __name__ == "__main__":
    main()