import argparse
import math
import pandas as pd


def required_n(std_value: float, error_margin: float) -> int:
    if pd.isna(std_value):
        return 0
    return max(1, math.ceil((1.96 * float(std_value) / float(error_margin)) ** 2))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--latency-ref", type=float, default=3000)
    ap.add_argument("--packetloss-ref", type=float, default=55)
    ap.add_argument("--bandwidth-ref", default="24kbit")
    ap.add_argument("--partition-ref", default="3|1")
    ap.add_argument("--blocktime-error", type=float, default=0.5)
    ap.add_argument("--stall-error", type=float, default=30.0)
    args = ap.parse_args()

    df = pd.read_csv(args.csv)
    df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    # Ensure optional columns exist
    for col in [
        "latency_ms",
        "packet_loss_pct",
        "bandwidth",
        "partition",
        "stress_phase_block_time_mean_s",
        "stress_phase_stall_duration_total_s",
    ]:
        if col not in df.columns:
            df[col] = pd.NA

    df["latency_ms"] = pd.to_numeric(df["latency_ms"], errors="coerce")
    df["packet_loss_pct"] = pd.to_numeric(df["packet_loss_pct"], errors="coerce")
    df["stress_phase_block_time_mean_s"] = pd.to_numeric(
        df["stress_phase_block_time_mean_s"], errors="coerce"
    )
    df["stress_phase_stall_duration_total_s"] = pd.to_numeric(
        df["stress_phase_stall_duration_total_s"], errors="coerce"
    )

    df["bandwidth"] = df["bandwidth"].astype(str).str.lower()
    df["partition"] = df["partition"].astype(str).str.replace(" ", "", regex=False)

    partition_ref = str(args.partition_ref).replace(" ", "")

    cases = [
        {
            "scenario_family": "latency",
            "mask": (df["scenario"] == "latency") & (df["latency_ms"] == args.latency_ref),
            "reference_case": f"{int(args.latency_ref)} ms",
            "metric": "stress_phase_block_time_mean_s",
            "error_margin": args.blocktime_error,
        },
        {
            "scenario_family": "packetloss",
            "mask": (df["scenario"] == "packetloss") & (df["packet_loss_pct"] == args.packetloss_ref),
            "reference_case": f"{int(args.packetloss_ref)} %",
            "metric": "stress_phase_block_time_mean_s",
            "error_margin": args.blocktime_error,
        },
        {
            "scenario_family": "bandwidth",
            "mask": (df["scenario"] == "bandwidth") & (df["bandwidth"] == str(args.bandwidth_ref).lower()),
            "reference_case": str(args.bandwidth_ref).lower(),
            "metric": "stress_phase_block_time_mean_s",
            "error_margin": args.blocktime_error,
        },
        {
            "scenario_family": "partition",
            "mask": (df["scenario"] == "partition") & (df["partition"] == partition_ref),
            "reference_case": partition_ref,
            "metric": "stress_phase_stall_duration_total_s",
            "error_margin": args.stall_error,
        },
    ]

    rows = []

    for case in cases:
        sub = df.loc[case["mask"], case["metric"]].dropna()
        sigma = float(sub.std(ddof=1)) if len(sub) >= 2 else float("nan")
        n = required_n(sigma, case["error_margin"]) if len(sub) >= 2 else 0

        rows.append(
            {
                "scenario_family": case["scenario_family"],
                "reference_case": case["reference_case"],
                "metric": case["metric"],
                "pilot_n": len(sub),
                "mean": float(sub.mean()) if len(sub) else float("nan"),
                "std": sigma,
                "error_margin": case["error_margin"],
                "required_n": n,
            }
        )

    out = pd.DataFrame(rows)
    print(out.to_string(index=False))
    print()
    print(f"uniform_required_n = {int(out['required_n'].max())}")


if __name__ == "__main__":
    main()