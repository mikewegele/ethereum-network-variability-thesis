import argparse
from pathlib import Path

import numpy as np
import pandas as pd


def classify_regime(row):
    growth = row.get("stress_phase_chain_growth_rate_blocks_per_s_windowed")
    stall = row.get("stress_phase_stall_duration_total_s")
    missing = row.get("stress_phase_missing_finalization_interval_count")

    if pd.notna(stall) and stall >= 60:
        return "stalled"

    if pd.notna(missing) and missing >= 30:
        return "stalled"

    if pd.notna(growth) and growth < 0.25:
        return "stalled"

    if pd.notna(stall) and pd.notna(missing) and stall == 0 and missing == 0:
        return "stable"

    if pd.notna(growth) or pd.notna(stall) or pd.notna(missing):
        return "degraded"

    return None


def scenario_level(row):
    scenario = row.get("scenario")

    if scenario == "latency":
        return row.get("latency_ms")

    if scenario == "packetloss":
        return row.get("packet_loss_pct")

    if scenario == "bandwidth":
        return row.get("bandwidth")

    if scenario == "offline":
        return row.get("offline_n")

    if scenario == "baseline":
        return "baseline"

    return None


def entropy(counts):
    total = counts.sum()
    if total == 0:
        return 0.0
    p = counts[counts > 0] / total
    return float(-(p * np.log2(p)).sum())


def iqr(series):
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return 0.0
    return float(series.quantile(0.75) - series.quantile(0.25))


def safe_mean(series):
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return np.nan
    return float(series.mean())


def safe_median(series):
    series = pd.to_numeric(series, errors="coerce").dropna()
    if series.empty:
        return np.nan
    return float(series.median())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        default="experiments/exports/final_series/summary.csv",
    )
    parser.add_argument(
        "--out",
        default="experiments/exports/interesting_scenarios_ranked.csv",
    )
    args = parser.parse_args()

    df = pd.read_csv(args.csv)

    df["computed_regime"] = df.apply(classify_regime, axis=1)
    df["scenario_level"] = df.apply(scenario_level, axis=1)

    df = df[df["scenario_level"].notna()].copy()

    rows = []

    for (scenario, level), g in df.groupby(["scenario", "scenario_level"], dropna=False):
        counts = g["computed_regime"].value_counts()

        stable = int(counts.get("stable", 0))
        degraded = int(counts.get("degraded", 0))
        stalled = int(counts.get("stalled", 0))
        n = stable + degraded + stalled

        if n == 0:
            continue

        regime_entropy = entropy(counts)
        mixed_regime_score = regime_entropy / np.log2(3)

        non_stable_share = (degraded + stalled) / n
        stalled_share = stalled / n
        degraded_share = degraded / n

        transition_score = 1.0 - abs(non_stable_share - 0.5) * 2.0
        transition_score = max(0.0, transition_score)

        chain_growth_iqr = iqr(g["stress_phase_chain_growth_rate_blocks_per_s_windowed"])
        block_time_iqr = iqr(g["stress_phase_block_time_mean_s"])
        stall_duration_iqr = iqr(g["stress_phase_stall_duration_total_s"])
        missing_intervals_iqr = iqr(g["stress_phase_missing_finalization_interval_count"])

        variability_score = (
            min(chain_growth_iqr / 0.25, 1.0)
            + min(block_time_iqr / 2.0, 1.0)
            + min(stall_duration_iqr / 60.0, 1.0)
            + min(missing_intervals_iqr / 30.0, 1.0)
        ) / 4.0

        structural_stall_score = 1.0 if stalled == n else 0.0

        interestingness_score = (
            0.40 * mixed_regime_score
            + 0.30 * variability_score
            + 0.20 * transition_score
            + 0.10 * structural_stall_score
        )

        if structural_stall_score == 1.0:
            suggested_plot = "phase_chain_growth_structural_stall"
        elif mixed_regime_score >= 0.45:
            suggested_plot = "phase_chain_growth_transition_variability"
        elif degraded > 0 and stalled == 0:
            suggested_plot = "phase_chain_growth_degraded_live"
        elif stalled > 0:
            suggested_plot = "phase_chain_growth_stall_transition"
        else:
            suggested_plot = "not_priority"

        rows.append(
            {
                "scenario": scenario,
                "level": level,
                "n": n,
                "stable": stable,
                "degraded": degraded,
                "stalled": stalled,
                "stable_share": stable / n,
                "degraded_share": degraded_share,
                "stalled_share": stalled_share,
                "interestingness_score": interestingness_score,
                "mixed_regime_score": mixed_regime_score,
                "variability_score": variability_score,
                "transition_score": transition_score,
                "chain_growth_iqr": chain_growth_iqr,
                "block_time_iqr": block_time_iqr,
                "stall_duration_iqr": stall_duration_iqr,
                "missing_intervals_iqr": missing_intervals_iqr,
                "mean_chain_growth": safe_mean(g["stress_phase_chain_growth_rate_blocks_per_s_windowed"]),
                "median_chain_growth": safe_median(g["stress_phase_chain_growth_rate_blocks_per_s_windowed"]),
                "mean_stall_duration": safe_mean(g["stress_phase_stall_duration_total_s"]),
                "median_stall_duration": safe_median(g["stress_phase_stall_duration_total_s"]),
                "suggested_plot": suggested_plot,
            }
        )

    ranked = pd.DataFrame(rows).sort_values(
        ["interestingness_score", "mixed_regime_score", "variability_score"],
        ascending=False,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    ranked.to_csv(out_path, index=False)

    cols = [
        "scenario",
        "level",
        "n",
        "stable",
        "degraded",
        "stalled",
        "interestingness_score",
        "mixed_regime_score",
        "variability_score",
        "transition_score",
        "suggested_plot",
    ]

    print("\nTop 25 most interesting scenario levels:\n")
    print(ranked[cols].head(25).to_string(index=False))
    print(f"\nWrote full ranking to: {out_path}")


if __name__ == "__main__":
    main()