import os
import re
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CSV_PATH = "experiments/summary_all_runs.csv"
OUT_DIR = "experiments/plots"


RATE_ORDER = [
    "unlimited",
    "10mbit",
    "1mbit",
    "512kbit",
    "256kbit",
    "128kbit",
    "64kbit",
]


def parse_delay_ms(run_dir: str):
    m = re.search(r"delay(\d+)ms", str(run_dir))
    return int(m.group(1)) if m else np.nan


def safe_std(x):
    return 0.0 if (x is None or (isinstance(x, float) and np.isnan(x))) else float(x)


def rate_sort_key(rate: str):
    if rate is None or (isinstance(rate, float) and np.isnan(rate)):
        return 10**9
    rate = str(rate).lower()
    if rate in RATE_ORDER:
        return RATE_ORDER.index(rate)
    m = re.search(r"(\d+)\s*(kbit|mbit)", rate)
    if m:
        n = int(m.group(1))
        unit = m.group(2)
        # Convert to kbit for ordering
        kbit = n * 1000 if unit == "mbit" else n
        return 100000 - kbit
    return 999999


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


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    df = pd.read_csv(CSV_PATH)

    # Basic cleanup
    df["run_dir"] = df["run_dir"].astype(str)
    df = df[~df["run_dir"].str.contains("_v2_", regex=False)].copy()

    if "status" in df.columns:
        df = df[df["status"].astype(str).str.lower() == "ok"].copy()

    # Coerce numeric columns that we care about
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
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Ensure delay_ms exists / numeric (backward compat)
    if "delay_ms" not in df.columns:
        df["delay_ms"] = df["run_dir"].apply(parse_delay_ms)
    df["delay_ms"] = pd.to_numeric(df["delay_ms"], errors="coerce")

    # ----------------------------
    # Delay plots (as before)
    # ----------------------------
    delay_df = df[~df["delay_ms"].isna()].copy()

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
                blocks_mean=("blocks_observed", "mean"),
                blocks_std=("blocks_observed", "std"),
            )
            .reset_index()
            .sort_values("delay_ms")
        )

        x = agg_delay["delay_ms"].to_numpy()

        errorbar_plot(
            x=x,
            y=agg_delay["cgr_mean"].to_numpy(),
            yerr=np.array([safe_std(v) for v in agg_delay["cgr_std"].to_numpy()]),
            xlabel="Symmetric delay (ms)",
            ylabel="Chain growth rate (blocks/s), window=60s",
            title="IBFT2: Delay vs Chain Growth Rate",
            out_path=os.path.join(OUT_DIR, "delay_vs_cgr.pdf"),
        )

        errorbar_plot(
            x=x,
            y=agg_delay["maxgap_mean"].to_numpy(),
            yerr=np.array([safe_std(v) for v in agg_delay["maxgap_std"].to_numpy()]),
            xlabel="Symmetric delay (ms)",
            ylabel="Max interblock gap (s)",
            title="IBFT2: Delay vs Max Interblock Gap",
            out_path=os.path.join(OUT_DIR, "delay_vs_max_gap.pdf"),
        )

        errorbar_plot(
            x=x,
            y=agg_delay["stallratio_mean"].to_numpy(),
            yerr=np.array([safe_std(v) for v in agg_delay["stallratio_std"].to_numpy()]),
            xlabel="Symmetric delay (ms)",
            ylabel="Stall ratio (stall_events / (blocks-1))",
            title="IBFT2: Delay vs Stall Ratio (k=5, baseline-median threshold)",
            out_path=os.path.join(OUT_DIR, "delay_vs_stall_ratio.pdf"),
        )

        agg_delay_out = os.path.join(OUT_DIR, "aggregated_by_delay.csv")
        agg_delay.to_csv(agg_delay_out, index=False)
    else:
        agg_delay_out = None

    # ----------------------------
    # Rate plots (new)
    # Requires columns: scenario=rate OR rate not null
    # Uses load_tag to split conditions.
    # ----------------------------
    if "rate" in df.columns:
        rate_df = df[df["rate"].notna()].copy()
    else:
        rate_df = df[df["run_dir"].str.contains("rate_", regex=False)].copy()
        rate_df["rate"] = rate_df["run_dir"].str.extract(r"rate_([^_]+)", expand=False)

    if "load_tag" not in rate_df.columns:
        rate_df["load_tag"] = np.where(rate_df["run_dir"].str.lower().str.contains("load"), "load", "no_load")

    # Normalize load_tag
    rate_df["load_tag"] = rate_df["load_tag"].fillna("no_load").astype(str)
    rate_df["rate"] = rate_df["rate"].astype(str).str.lower()

    if len(rate_df) > 0:
        agg_rate = (
            rate_df.groupby(["load_tag", "rate"])
            .agg(
                n=("run_dir", "count"),
                mean_bt_mean=("block_time_mean_s", "mean"),
                mean_bt_std=("block_time_mean_s", "std"),
                maxgap_mean=("max_interblock_gap_s", "mean"),
                maxgap_std=("max_interblock_gap_s", "std"),
                stallratio_mean=("stall_ratio", "mean"),
                stallratio_std=("stall_ratio", "std"),
                cgr_mean=("cgr_blocks_per_s", "mean"),
                cgr_std=("cgr_blocks_per_s", "std"),
                txpb_mean=("tx_per_block_mean", "mean"),
                txpb_std=("tx_per_block_mean", "std"),
            )
            .reset_index()
        )

        # order rates
        agg_rate["rate_order"] = agg_rate["rate"].apply(rate_sort_key)
        agg_rate = agg_rate.sort_values(["load_tag", "rate_order", "rate"]).reset_index(drop=True)

        # Save table for appendix
        agg_rate_out = os.path.join(OUT_DIR, "aggregated_by_rate_and_load.csv")
        agg_rate.to_csv(agg_rate_out, index=False)

        # One plot per metric, with one line per load_tag (we keep it simple)
        load_tags = list(agg_rate["load_tag"].unique())

        def plot_metric(metric_mean, metric_std, ylabel, title, filename):
            plt.figure()
            for tag in load_tags:
                sub = agg_rate[agg_rate["load_tag"] == tag].copy()
                x = np.arange(len(sub))
                labels = sub["rate"].tolist()
                y = sub[metric_mean].to_numpy()
                yerr = np.array([safe_std(v) for v in sub[metric_std].to_numpy()])
                plt.errorbar(x, y, yerr=yerr, fmt="o-", capsize=3, label=tag)
                plt.xticks(x, labels, rotation=25, ha="right")
            plt.xlabel("Rate limit")
            plt.ylabel(ylabel)
            plt.title(title)
            plt.grid(True, linestyle="--", linewidth=0.5, alpha=0.5)
            plt.legend()
            plt.tight_layout()
            plt.savefig(os.path.join(OUT_DIR, filename))
            plt.close()

        plot_metric(
            metric_mean="mean_bt_mean",
            metric_std="mean_bt_std",
            ylabel="Mean interblock time (s)",
            title="IBFT2: Rate limit vs Mean Block Time (split by load_tag)",
            filename="rate_vs_block_time_mean_by_load.pdf",
        )

        plot_metric(
            metric_mean="maxgap_mean",
            metric_std="maxgap_std",
            ylabel="Max interblock gap (s)",
            title="IBFT2: Rate limit vs Max Interblock Gap (split by load_tag)",
            filename="rate_vs_max_gap_by_load.pdf",
        )

        plot_metric(
            metric_mean="stallratio_mean",
            metric_std="stallratio_std",
            ylabel="Stall ratio",
            title="IBFT2: Rate limit vs Stall Ratio (split by load_tag)",
            filename="rate_vs_stall_ratio_by_load.pdf",
        )

        plot_metric(
            metric_mean="txpb_mean",
            metric_std="txpb_std",
            ylabel="TX per block (mean)",
            title="Load sanity: Rate limit vs TX per block (split by load_tag)",
            filename="rate_vs_tx_per_block_mean_by_load.pdf",
        )
    else:
        agg_rate_out = None

    print("Wrote plots to:", OUT_DIR)
    if agg_delay_out:
        print(" -", os.path.join(OUT_DIR, "delay_vs_cgr.pdf"))
        print(" -", os.path.join(OUT_DIR, "delay_vs_max_gap.pdf"))
        print(" -", os.path.join(OUT_DIR, "delay_vs_stall_ratio.pdf"))
        print(" -", agg_delay_out)
    if agg_rate_out:
        print(" -", os.path.join(OUT_DIR, "rate_vs_block_time_mean_by_load.pdf"))
        print(" -", os.path.join(OUT_DIR, "rate_vs_max_gap_by_load.pdf"))
        print(" -", os.path.join(OUT_DIR, "rate_vs_stall_ratio_by_load.pdf"))
        print(" -", os.path.join(OUT_DIR, "rate_vs_tx_per_block_mean_by_load.pdf"))
        print(" -", agg_rate_out)


if __name__ == "__main__":
    main()