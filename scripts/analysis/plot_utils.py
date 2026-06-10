import re
from typing import Optional

import numpy as np
import pandas as pd


DEFAULT_BW_ORDER = [
    "unlimited",
    "10gbit",
    "1gbit",
    "100mbit",
    "10mbit",
    "1mbit",
    "512kbit",
    "256kbit",
    "128kbit",
    "64kbit",
    "32kbit",
    "24kbit",
    "16kbit",
    "12kbit",
    "8kbit",
]


SCENARIO_LABELS = {
    "latency": "Latency (ms)",
    "packetloss": "Packet loss (%)",
    "bandwidth": "Bandwidth limit",
    "partition": "Network partition",
}


def ensure_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def rate_to_kbit(rate: Optional[str]) -> Optional[int]:
    if rate is None:
        return None

    s = str(rate).strip().lower()

    if s == "" or s == "nan":
        return None

    if s == "unlimited":
        return 10**12

    m = re.match(r"^(\d+)\s*(kbit|mbit|gbit)$", s)
    if not m:
        return None

    n = int(m.group(1))
    unit = m.group(2)
    mul = {"kbit": 1, "mbit": 1000, "gbit": 1_000_000}[unit]

    return n * mul


def bandwidth_sort_key(rate: str, explicit_order):
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return 10**18

    s = str(rate).strip().lower()

    if s in explicit_order:
        return explicit_order.index(s)

    kbit = rate_to_kbit(s)

    if kbit is None:
        return 10**17

    return -kbit


def get_x_config(df: pd.DataFrame, scenario: str, bw_order):
    sub = df[df["scenario"] == scenario].copy()

    if sub.empty:
        return None, None, None

    if scenario == "latency":
        x_col = "latency_ms"
        levels = sorted(sub[x_col].dropna().unique())
        x_positions = {v: v for v in levels}
        tick_positions = levels
        tick_labels = [str(int(v)) for v in levels]
        return x_col, x_positions, (tick_positions, tick_labels)

    if scenario == "packetloss":
        x_col = "packet_loss_pct"
        levels = sorted(sub[x_col].dropna().unique())
        x_positions = {v: v for v in levels}
        tick_positions = levels
        tick_labels = [str(int(v)) for v in levels]
        return x_col, x_positions, (tick_positions, tick_labels)

    if scenario == "partition":
        x_col = "partition"
        preferred_order = ["3-1", "2-2"]

        existing_levels = set(sub[x_col].dropna().astype(str).unique())
        levels = [v for v in preferred_order if v in existing_levels]

        remaining = sorted(existing_levels - set(preferred_order))
        levels.extend(remaining)

        x_positions = {v: i for i, v in enumerate(levels)}
        tick_positions = list(range(len(levels)))
        tick_labels = levels

        return x_col, x_positions, (tick_positions, tick_labels)

    if scenario == "bandwidth":
        x_col = "bandwidth"
        levels = sorted(
            sub[x_col].dropna().astype(str).str.lower().unique(),
            key=lambda v: bandwidth_sort_key(v, bw_order),
        )
        x_positions = {v: i for i, v in enumerate(levels)}
        tick_positions = list(range(len(levels)))
        tick_labels = levels
        return x_col, x_positions, (tick_positions, tick_labels)

    return None, None, None


def aggregate_median_iqr(sub: pd.DataFrame, x_col: str, metric_col: str) -> pd.DataFrame:
    return (
        sub.groupby(x_col)[metric_col]
        .agg(
            median="median",
            q1=lambda s: s.quantile(0.25),
            q3=lambda s: s.quantile(0.75),
            count="count",
        )
        .reset_index()
        .dropna(subset=["median"])
    )


def get_jitter_width(scenario: str, x_positions) -> float:
    if scenario == "bandwidth":
        return 0.12

    if scenario == "partition":
        return 0.035

    levels = sorted([float(v) for v in x_positions.values()])

    if len(levels) > 1:
        min_step = min(abs(b - a) for a, b in zip(levels, levels[1:]))
        return min_step * 0.06

    return 0.1


def prepare_df(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    df = ensure_numeric(
        df,
        [
            "latency_ms",
            "packet_loss_pct",
            "block_period_s",
            "request_timeout_s",
            "stress_phase_block_time_mean_s",
            "baseline_phase_stall_duration_total_s",
            "stress_phase_stall_duration_total_s",
            "recovery_phase_stall_duration_total_s",
            "baseline_phase_missing_finalization_interval_count",
            "stress_phase_missing_finalization_interval_count",
            "recovery_phase_missing_finalization_interval_count",
            "stress_phase_chain_growth_rate_blocks_per_s_windowed",
            "stress_phase_expected_blocks",
            "stress_phase_missing_share",
            "stress_phase_stall_share",
            "delayed_finalization_event_count",
        ],
    )

    if "bandwidth" in df.columns:
        df["bandwidth"] = df["bandwidth"].astype(str).str.lower()

    if "partition" in df.columns:
        df["partition"] = df["partition"].astype("string").str.strip()

    if "stress_phase_regime" in df.columns:
        df["stress_phase_regime"] = df["stress_phase_regime"].astype("string").str.strip()

    return df