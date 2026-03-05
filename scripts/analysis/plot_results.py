import argparse
import os
import re
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt


DEFAULT_RATE_ORDER = ["unlimited", "10mbit", "1mbit", "512kbit", "256kbit", "128kbit", "64kbit", "32kbit"]


def safe_std(x):
    if x is None:
        return 0.0
    if isinstance(x, float) and np.isnan(x):
        return 0.0
    try:
        return float(x)
    except Exception:
        return 0.0


def rate_to_kbit(rate: str):
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return None
    s = str(rate).strip().lower()
    if s == "unlimited":
        return 10**12
    m = re.match(r"^(\d+)\s*(kbit|mbit|gbit)$", s)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2)
    mul = {"kbit": 1, "mbit": 1000, "gbit": 1000_000}.get(unit, 1)
    return n * mul


def rate_sort_key(rate: str, explicit_order):
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return 10**15
    s = str(rate).strip().lower()
    if explicit_order and s in explicit_order:
        return explicit_order.index(s)
    kbit = rate_to_kbit(s)
    if kbit is None:
        return 10**14
    return 10**13 - kbit


def errorbar_plot(x, y, yerr, xlabel, ylabel, title, out_path, x_tick_labels=None):
    plt.figure()
    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3)
    plt.xlabel(xlabel)
    plt.ylabel(ylabel)
    plt.title(title)
    if x_tick_labels is not None:
        plt.xticks(x, x_tick_labels, rotation=25, ha="right")
    plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
    plt.tight_layout()
    plt.savefig(out_path)
    plt.close()


def coerce_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def ensure_load_tag(df: pd.DataFrame, mode: str):
    if mode == "none":
        df["load_tag"] = "all"
        return df

    if "load_tag" in df.columns:
        df["load_tag"] = df["load_tag"].fillna("no_load").astype(str)
        return df

    low = df["run_dir"].astype(str).str.lower()
    df["load_tag"] = np.where(low.str.contains("load"), "load", "no_load")
    return df


def resolve_out_dir(out: str, dataset: str, scenario: str):
    return os.path.join(out, dataset, scenario)


def infer_dataset_from_csv(csv_path: str):
    b = os.path.basename(csv_path).replace(".csv", "")
    return b


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", required=True)
    ap.add_argument("--out-root", default="experiments/plots")
    ap.add_argument("--scenario", default="all", choices=["all", "delay", "rate", "offline"])
    ap.add_argument("--dataset", default=None, help="folder name for plots (default: inferred from csv filename)")
    ap.add_argument("--only-ok", action="store_true", default=True)
    ap.add_argument("--include-nonok", action="store_true")
    ap.add_argument("--load-tag-mode", default="auto", choices=["auto", "none", "split"])
    ap.add_argument("--rate-order", default=",".join(DEFAULT_RATE_ORDER))
    args = ap.parse_args()

    dataset = args.dataset or infer_dataset_from_csv(args.csv)
    out_dir = resolve_out_dir(args.out_root, dataset, args.scenario)
    os.makedirs(out_dir, exist_ok=True)

    df = pd.read_csv(args.csv)
    df["run_dir"] = df["run_dir"].astype(str)

    only_ok = False if args.include_nonok else bool(args.only_ok)
    if only_ok and "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    num_cols = [
        "blocks_observed",
        "block_time_mean_s",
        "block_time_variance",
        "max_interblock_gap_s",
        "stall_event_count",
        "stall_ratio",
        "cgr_blocks_per_s",
        "delay_ms",
        "tx_total",
        "tx_per_block_mean",
        "tx_per_block_median",
        "tx_per_block_p95",
        "tx_per_block_max",
    ]
    df = coerce_numeric(df, num_cols)

    if args.scenario != "all":
        if "scenario" in df.columns:
            df = df[df["scenario"].astype(str).str.lower() == args.scenario].copy()
        else:
            if args.scenario == "delay":
                df = df[df["run_dir"].str.contains("delay", case=False, regex=False)].copy()
            elif args.scenario == "rate":
                df = df[df["run_dir"].str.contains("rate", case=False, regex=False)].copy()
            elif args.scenario == "offline":
                df = df[df["run_dir"].str.contains("offline", case=False, regex=False)].copy()

    explicit_rate_order = [s.strip().lower() for s in args.rate_order.split(",") if s.strip()]

    # Delay plots
    if args.scenario in ("all", "delay") and "delay_ms" in df.columns:
        delay_df = df[df["delay_ms"].notna()].copy()
        if len(delay_df) > 0:
            agg_delay = (
                delay_df.groupby("delay_ms")
                .agg(
                    n=("run_dir", "count"),
                    cgr_mean=("cgr_blocks_per_s", "mean"),
                    cgr_std=("cgr_blocks_per_s", "std"),
                    maxgap_mean=("max_interblock_gap_s", "mean"),
                    maxgap_std=("max_interblock_gap_s", "std"),
                    stallratio_mean=("stall_ratio", "mean"),
                    stallratio_std=("stall_ratio", "std"),
                )
                .reset_index()
                .sort_values("delay_ms")
            )

            agg_delay.to_csv(os.path.join(out_dir, "aggregated_by_delay.csv"), index=False)
            x = agg_delay["delay_ms"].to_numpy()

            errorbar_plot(
                x=x,
                y=agg_delay["cgr_mean"].to_numpy(),
                yerr=np.array([safe_std(v) for v in agg_delay["cgr_std"].to_numpy()]),
                xlabel="Symmetric delay (ms)",
                ylabel="Chain growth rate (blocks/s), window=60s",
                title="IBFT2: Delay vs Chain Growth Rate",
                out_path=os.path.join(out_dir, "delay_vs_cgr.pdf"),
            )

            errorbar_plot(
                x=x,
                y=agg_delay["maxgap_mean"].to_numpy(),
                yerr=np.array([safe_std(v) for v in agg_delay["maxgap_std"].to_numpy()]),
                xlabel="Symmetric delay (ms)",
                ylabel="Max interblock gap (s)",
                title="IBFT2: Delay vs Max Interblock Gap",
                out_path=os.path.join(out_dir, "delay_vs_max_gap.pdf"),
            )

            errorbar_plot(
                x=x,
                y=agg_delay["stallratio_mean"].to_numpy(),
                yerr=np.array([safe_std(v) for v in agg_delay["stallratio_std"].to_numpy()]),
                xlabel="Symmetric delay (ms)",
                ylabel="Stall ratio",
                title="IBFT2: Delay vs Stall Ratio",
                out_path=os.path.join(out_dir, "delay_vs_stall_ratio.pdf"),
            )

    # Rate plots
    if args.scenario in ("all", "rate"):
        if "rate" in df.columns:
            rate_df = df[df["rate"].notna()].copy()
            rate_df["rate"] = rate_df["rate"].astype(str).str.lower()
        else:
            rate_df = df[df["run_dir"].str.contains("rate_", regex=False, case=False)].copy()
            rate_df["rate"] = rate_df["run_dir"].str.extract(r"rate_([^_]+)", expand=False).astype(str).str.lower()

        if len(rate_df) > 0:
            rate_df = ensure_load_tag(rate_df, args.load_tag_mode)

            agg_rate = (
                rate_df.groupby(["load_tag", "rate"])
                .agg(
                    n=("run_dir", "count"),
                    bt_mean=("block_time_mean_s", "mean"),
                    bt_std=("block_time_mean_s", "std"),
                    maxgap_mean=("max_interblock_gap_s", "mean"),
                    maxgap_std=("max_interblock_gap_s", "std"),
                    stallratio_mean=("stall_ratio", "mean"),
                    stallratio_std=("stall_ratio", "std"),
                    cgr_mean=("cgr_blocks_per_s", "mean"),
                    cgr_std=("cgr_blocks_per_s", "std"),
                )
                .reset_index()
            )

            agg_rate["rate_order"] = agg_rate["rate"].apply(lambda r: rate_sort_key(r, explicit_rate_order))
            agg_rate = agg_rate.sort_values(["load_tag", "rate_order", "rate"]).reset_index(drop=True)
            agg_rate.to_csv(os.path.join(out_dir, "aggregated_by_rate_and_load.csv"), index=False)

            load_tags = list(agg_rate["load_tag"].unique())

            def plot_metric(metric_mean, metric_std, ylabel, title, filename):
                plt.figure()
                for tag in load_tags:
                    sub = agg_rate[agg_rate["load_tag"] == tag].copy()
                    x = np.arange(len(sub))
                    labels = sub["rate"].tolist()
                    y = sub[metric_mean].to_numpy()
                    yerr = np.array([safe_std(v) for v in sub[metric_std].to_numpy()])
                    plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3, label=str(tag))
                    plt.xticks(x, labels, rotation=25, ha="right")
                plt.xlabel("Rate limit")
                plt.ylabel(ylabel)
                plt.title(title)
                plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
                if len(load_tags) > 1:
                    plt.legend()
                plt.tight_layout()
                plt.savefig(os.path.join(out_dir, filename))
                plt.close()

            plot_metric(
                "bt_mean", "bt_std",
                "Mean interblock time (s)",
                "IBFT2: Rate limit vs Mean Block Time",
                "rate_vs_block_time_mean.pdf",
            )

            plot_metric(
                "maxgap_mean", "maxgap_std",
                "Max interblock gap (s)",
                "IBFT2: Rate limit vs Max Interblock Gap",
                "rate_vs_max_gap.pdf",
            )

            plot_metric(
                "stallratio_mean", "stallratio_std",
                "Stall ratio",
                "IBFT2: Rate limit vs Stall Ratio",
                "rate_vs_stall_ratio.pdf",
            )

            plot_metric(
                "cgr_mean", "cgr_std",
                "Chain growth rate (blocks/s)",
                "IBFT2: Rate limit vs Chain Growth Rate",
                "rate_vs_cgr.pdf",
            )

    print(out_dir)


if __name__ == "__main__":
    main()