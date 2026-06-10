import argparse
import os

from plot_result_figures import make_scenario_plots
from plot_utils import DEFAULT_BW_ORDER, prepare_df


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-root", default="experiments/plots/final_series/results")
    ap.add_argument(
        "--scenario",
        default="all",
        choices=["all", "latency", "packetloss", "bandwidth", "partition"],
    )
    ap.add_argument("--bw-order", default=",".join(DEFAULT_BW_ORDER))

    args = ap.parse_args()

    df = prepare_df(args.csv)
    bw_order = [s.strip().lower() for s in args.bw_order.split(",") if s.strip()]

    scenarios = (
        ["latency", "packetloss", "bandwidth", "partition"]
        if args.scenario == "all"
        else [args.scenario]
    )

    for scenario in scenarios:
        make_scenario_plots(
            df=df,
            scenario=scenario,
            out_dir=os.path.join(args.out_root, scenario),
            bw_order=bw_order,
        )

    print(args.out_root)


if __name__ == "__main__":
    main()