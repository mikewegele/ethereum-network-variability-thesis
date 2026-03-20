import argparse
import math
import os
from itertools import combinations
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import kruskal, mannwhitneyu


METRICS = [
    "block_time_mean_s",
    "max_interblock_gap_s",
    "stall_event_count",
    "stall_ratio",
    "chain_growth_rate_blocks_per_s_windowed",
    "tx_per_block_mean",
    "tx_per_block_median",
    "tx_per_block_p95",
    "tx_per_block_max",
]


def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)


def cliffs_delta(x: np.ndarray, y: np.ndarray) -> float:
    if len(x) == 0 or len(y) == 0:
        return float("nan")
    gt = 0
    lt = 0
    for xi in x:
        gt += np.sum(xi > y)
        lt += np.sum(xi < y)
    return (gt - lt) / (len(x) * len(y))


def cliffs_delta_label(d: float) -> str:
    ad = abs(d)
    if math.isnan(ad):
        return "nan"
    if ad < 0.147:
        return "negligible"
    if ad < 0.33:
        return "small"
    if ad < 0.474:
        return "medium"
    return "large"


def holm_correction(p_values: List[float]) -> List[float]:
    n = len(p_values)
    order = np.argsort(p_values)
    adjusted = np.empty(n, dtype=float)

    prev = 0.0
    for rank, idx in enumerate(order):
        adj = (n - rank) * p_values[idx]
        adj = max(adj, prev)
        prev = adj
        adjusted[idx] = min(adj, 1.0)

    return adjusted.tolist()


def coerce_numeric(df: pd.DataFrame, cols: List[str]) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def get_group_columns(df: pd.DataFrame) -> List[str]:
    cols = []
    if "scenario" in df.columns:
        cols.append("scenario")
    if "latency_ms" in df.columns:
        cols.append("latency_ms")
    if "bandwidth" in df.columns:
        cols.append("bandwidth")
    if "offline_n" in df.columns:
        cols.append("offline_n")
    return cols


def level_label(row: pd.Series) -> str:
    scenario = str(row.get("scenario", "unknown"))

    if scenario == "baseline":
        return "baseline"

    if scenario == "latency":
        return f"latency_{int(row['latency_ms'])}ms"

    if scenario == "bandwidth":
        return f"bandwidth_{row['bandwidth']}"

    if scenario == "offline":
        return f"offline_{int(row['offline_n'])}"

    if scenario == "combined":
        return f"combined_{int(row['latency_ms'])}ms_{row['bandwidth']}"

    return scenario


def add_level_label(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["level_label"] = df.apply(level_label, axis=1)
    return df


def descriptive_stats(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []
    for lvl, sub in df.groupby("level_label"):
        base = {"level_label": lvl}
        if "scenario" in sub.columns:
            base["scenario"] = sub["scenario"].iloc[0]

        for m in metrics:
            vals = sub[m].dropna().to_numpy()
            base[f"{m}_n"] = len(vals)
            base[f"{m}_mean"] = np.mean(vals) if len(vals) else np.nan
            base[f"{m}_std"] = np.std(vals, ddof=1) if len(vals) > 1 else np.nan
            base[f"{m}_median"] = np.median(vals) if len(vals) else np.nan
            base[f"{m}_p25"] = np.percentile(vals, 25) if len(vals) else np.nan
            base[f"{m}_p75"] = np.percentile(vals, 75) if len(vals) else np.nan
            base[f"{m}_min"] = np.min(vals) if len(vals) else np.nan
            base[f"{m}_max"] = np.max(vals) if len(vals) else np.nan
        rows.append(base)

    return pd.DataFrame(rows).sort_values("level_label")


def kruskal_by_metric(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []
    groups = list(df.groupby("level_label"))

    for metric in metrics:
        samples = []
        labels = []
        for lvl, sub in groups:
            vals = sub[metric].dropna().to_numpy()
            if len(vals) > 0:
                samples.append(vals)
                labels.append(lvl)

        if len(samples) < 2:
            rows.append({
                "metric": metric,
                "group_count": len(samples),
                "kruskal_H": np.nan,
                "p_value": np.nan,
            })
            continue

        try:
            stat, p = kruskal(*samples)
        except Exception:
            stat, p = np.nan, np.nan

        rows.append({
            "metric": metric,
            "group_count": len(samples),
            "kruskal_H": stat,
            "p_value": p,
        })

    return pd.DataFrame(rows)


def pairwise_vs_baseline(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []

    if "baseline" not in set(df["level_label"]):
        return pd.DataFrame(columns=[
            "metric", "baseline_level", "compare_level",
            "n_baseline", "n_compare",
            "u_stat", "p_value", "p_holm",
            "median_baseline", "median_compare",
            "delta", "delta_label"
        ])

    baseline_df = df[df["level_label"] == "baseline"].copy()
    compare_levels = [x for x in df["level_label"].unique() if x != "baseline"]

    for metric in metrics:
        tmp_rows = []
        base_vals = baseline_df[metric].dropna().to_numpy()

        for lvl in compare_levels:
            comp_vals = df[df["level_label"] == lvl][metric].dropna().to_numpy()

            if len(base_vals) == 0 or len(comp_vals) == 0:
                tmp_rows.append({
                    "metric": metric,
                    "baseline_level": "baseline",
                    "compare_level": lvl,
                    "n_baseline": len(base_vals),
                    "n_compare": len(comp_vals),
                    "u_stat": np.nan,
                    "p_value": np.nan,
                    "median_baseline": np.nan,
                    "median_compare": np.nan,
                    "delta": np.nan,
                    "delta_label": "nan",
                })
                continue

            try:
                u_stat, p = mannwhitneyu(base_vals, comp_vals, alternative="two-sided")
            except Exception:
                u_stat, p = np.nan, np.nan

            d = cliffs_delta(comp_vals, base_vals)

            tmp_rows.append({
                "metric": metric,
                "baseline_level": "baseline",
                "compare_level": lvl,
                "n_baseline": len(base_vals),
                "n_compare": len(comp_vals),
                "u_stat": u_stat,
                "p_value": p,
                "median_baseline": np.median(base_vals),
                "median_compare": np.median(comp_vals),
                "delta": d,
                "delta_label": cliffs_delta_label(d),
            })

        valid_ps = [r["p_value"] for r in tmp_rows if pd.notna(r["p_value"])]
        if valid_ps:
            corrected = holm_correction(valid_ps)
            j = 0
            for r in tmp_rows:
                if pd.notna(r["p_value"]):
                    r["p_holm"] = corrected[j]
                    j += 1
                else:
                    r["p_holm"] = np.nan
        else:
            for r in tmp_rows:
                r["p_holm"] = np.nan

        rows.extend(tmp_rows)

    return pd.DataFrame(rows)


def pairwise_within_scenario(df: pd.DataFrame, metrics: List[str]) -> pd.DataFrame:
    rows = []

    for scenario, sub_s in df.groupby("scenario"):
        levels = list(sub_s["level_label"].unique())
        if len(levels) < 2:
            continue

        for metric in metrics:
            tmp_rows = []
            for a, b in combinations(levels, 2):
                xa = sub_s[sub_s["level_label"] == a][metric].dropna().to_numpy()
                xb = sub_s[sub_s["level_label"] == b][metric].dropna().to_numpy()

                if len(xa) == 0 or len(xb) == 0:
                    tmp_rows.append({
                        "scenario": scenario,
                        "metric": metric,
                        "group_a": a,
                        "group_b": b,
                        "n_a": len(xa),
                        "n_b": len(xb),
                        "u_stat": np.nan,
                        "p_value": np.nan,
                        "median_a": np.nan,
                        "median_b": np.nan,
                        "delta": np.nan,
                        "delta_label": "nan",
                    })
                    continue

                try:
                    u_stat, p = mannwhitneyu(xa, xb, alternative="two-sided")
                except Exception:
                    u_stat, p = np.nan, np.nan

                d = cliffs_delta(xa, xb)

                tmp_rows.append({
                    "scenario": scenario,
                    "metric": metric,
                    "group_a": a,
                    "group_b": b,
                    "n_a": len(xa),
                    "n_b": len(xb),
                    "u_stat": u_stat,
                    "p_value": p,
                    "median_a": np.median(xa),
                    "median_b": np.median(xb),
                    "delta": d,
                    "delta_label": cliffs_delta_label(d),
                })

            valid_ps = [r["p_value"] for r in tmp_rows if pd.notna(r["p_value"])]
            if valid_ps:
                corrected = holm_correction(valid_ps)
                j = 0
                for r in tmp_rows:
                    if pd.notna(r["p_value"]):
                        r["p_holm"] = corrected[j]
                        j += 1
                    else:
                        r["p_holm"] = np.nan
            else:
                for r in tmp_rows:
                    r["p_holm"] = np.nan

            rows.extend(tmp_rows)

    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--include-nonok", action="store_true")
    args = ap.parse_args()

    ensure_dir(args.out_dir)

    df = pd.read_csv(args.csv)
    df = coerce_numeric(df, METRICS + ["rep", "latency_ms", "offline_n"])

    if not args.include_nonok and "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    if "scenario" not in df.columns:
        raise SystemExit("CSV needs a 'scenario' column")

    if "bandwidth" not in df.columns:
        df["bandwidth"] = np.nan
    else:
        df["bandwidth"] = df["bandwidth"].astype(str)

    df = add_level_label(df)

    desc = descriptive_stats(df, METRICS)
    desc.to_csv(os.path.join(args.out_dir, "descriptive_stats.csv"), index=False)

    kw = kruskal_by_metric(df, METRICS)
    kw.to_csv(os.path.join(args.out_dir, "kruskal_all_levels.csv"), index=False)

    vs_base = pairwise_vs_baseline(df, METRICS)
    vs_base.to_csv(os.path.join(args.out_dir, "pairwise_vs_baseline.csv"), index=False)

    within = pairwise_within_scenario(df, METRICS)
    within.to_csv(os.path.join(args.out_dir, "pairwise_within_scenario.csv"), index=False)

    summary_lines = []
    summary_lines.append("Statistical summary")
    summary_lines.append("===================")
    summary_lines.append(f"Rows analyzed: {len(df)}")
    summary_lines.append(f"Scenarios: {', '.join(sorted(df['scenario'].astype(str).unique()))}")
    summary_lines.append("")

    if not kw.empty:
        summary_lines.append("Kruskal-Wallis (global differences):")
        for _, row in kw.iterrows():
            summary_lines.append(
                f"- {row['metric']}: H={row['kruskal_H']}, p={row['p_value']}"
            )
        summary_lines.append("")

    with open(os.path.join(args.out_dir, "stats_summary.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(summary_lines))

    print(args.out_dir)


if __name__ == "__main__":
    main()