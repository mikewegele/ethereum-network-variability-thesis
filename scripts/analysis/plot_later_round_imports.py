import re
from pathlib import Path

import pandas as pd
import matplotlib.pyplot as plt

PROJECT_ROOT = Path(__file__).resolve().parents[2]

IMPORTS_CSV = PROJECT_ROOT / "experiments" / "analysis" / "qbft_logs" / "qbft_import_rounds.csv"
SUMMARY_CSV = PROJECT_ROOT / "experiments" / "analysis" / "qbft_logs" / "qbft_log_summary.csv"

OUT_DIR = PROJECT_ROOT / "experiments" / "plots"
OUT_DIR.mkdir(parents=True, exist_ok=True)

OUT_PDF = OUT_DIR / "figure_5_19_later_round_imports.pdf"
OUT_PNG = OUT_DIR / "figure_5_19_later_round_imports.png"


def classify_run(run):
    m = re.search(r"_lat_(\d+)ms_", run)
    if m:
        value = int(m.group(1))
        return "Latency", value, f"{value} ms"

    m = re.search(r"_loss_(\d+)pct_", run)
    if m:
        value = int(m.group(1))
        return "Packet Loss", value, f"{value}%"

    m = re.search(r"_bw_(unlimited|\d+kbit)_", run)
    if m:
        raw = m.group(1)
        if raw == "unlimited":
            return "Bandwidth", 10**9, "unlimited"
        value = int(re.search(r"\d+", raw).group())
        return "Bandwidth", value, f"{value} kbit/s"

    m = re.search(r"_partition_(\d-\d)_", run)
    if m:
        raw = m.group(1)
        order = {"3-1": 0, "2-2": 1}
        return "Partitions", order[raw], raw.replace("-", " | ")

    return None, None, None


def resolve_round(rounds):
    """
    Reduce validator-local observations to one logical import per run+sequence.
    If validators disagree, use the modal round; on a tie, use the higher round.
    """
    counts = rounds.value_counts()
    modes = counts[counts == counts.max()].index.tolist()
    return int(max(modes))


def build_counts(imports, summary):
    # Besu starts with Round 0. Therefore Round >= 1 is a later-round import.
    stress = imports[
        imports["phase"].eq("stress_phase")
        & imports["round"].ge(1)
    ].copy()

    # The same finalized block can appear in several validator logs.
    logical = (
        stress.groupby(["run", "sequence"], as_index=False)
        .agg(round=("round", resolve_round))
    )

    parsed = logical["run"].map(classify_run)
    logical[["family", "sort_value", "level"]] = pd.DataFrame(
        parsed.tolist(), index=logical.index
    )

    logical["round_group"] = logical["round"].map(
        lambda r: "Round 1"
        if r == 1
        else ("Round 2" if r == 2 else "Round 3+")
    )

    # Keep scenario levels with zero observed later-round imports.
    levels = []
    for run in summary["run"].drop_duplicates():
        family, sort_value, level = classify_run(run)
        if family is not None:
            levels.append((family, sort_value, level))

    levels = pd.DataFrame(
        levels,
        columns=["family", "sort_value", "level"],
    ).drop_duplicates()

    counts = (
        logical.groupby(
            ["family", "sort_value", "level", "round_group"]
        )
        .size()
        .unstack(fill_value=0)
        .reset_index()
    )

    data = levels.merge(
        counts,
        on=["family", "sort_value", "level"],
        how="left",
    ).fillna(0)

    for column in ["Round 1", "Round 2", "Round 3+"]:
        if column not in data.columns:
            data[column] = 0
        data[column] = data[column].astype(int)

    family_order = {
        "Latency": 0,
        "Packet Loss": 1,
        "Bandwidth": 2,
        "Partitions": 3,
    }
    data["family_order"] = data["family"].map(family_order)

    # Display bandwidth from high capacity to low capacity.
    is_bandwidth = data["family"].eq("Bandwidth")
    data.loc[is_bandwidth, "sort_value"] = -data.loc[
        is_bandwidth, "sort_value"
    ]
    data.loc[
        is_bandwidth & data["level"].eq("unlimited"),
        "sort_value",
    ] = -10**9

    return data.sort_values(
        ["family_order", "sort_value"]
    ).reset_index(drop=True)


def plot_counts(data):
    x_positions = []
    labels = []
    family_centers = {}
    separators = []

    x = 0.0
    family_gap = 1.0

    for family in [
        "Latency",
        "Packet Loss",
        "Bandwidth",
        "Partitions",
    ]:
        group = data[data["family"].eq(family)]
        start = x

        for _, row in group.iterrows():
            x_positions.append(x)
            labels.append(row["level"])
            x += 1.0

        end = x - 1.0
        family_centers[family] = (start + end) / 2
        separators.append(x - 0.5 + family_gap / 2)
        x += family_gap

    fig, ax = plt.subplots(figsize=(10, 4.2))

    bottom = [0] * len(data)

    for column in ["Round 1", "Round 2", "Round 3+"]:
        values = data[column].tolist()

        ax.bar(
            x_positions,
            values,
            bottom=bottom,
            width=0.72,
            label=column,
            edgecolor="none",
        )

        bottom = [
            previous + value
            for previous, value in zip(bottom, values)
        ]

    ax.set_title(
        "Later-Round Imports Across Network Impairments",
        fontsize=10,
    )

    ax.set_ylabel(
        "Number of later-round imports",
        fontsize=9,
    )

    ax.set_xticks(x_positions)
    ax.set_xticklabels(
        labels,
        rotation=45,
        ha="right",
        fontsize=8,
    )

    ax.tick_params(axis="y", labelsize=8)

    # Same restrained horizontal grid style as the other result plots.
    ax.grid(
        axis="y",
        linestyle="-",
        linewidth=0.5,
        alpha=0.25,
    )
    ax.set_axisbelow(True)

    # Light separation between impairment families.
    for separator in separators[:-1]:
        ax.axvline(
            separator,
            color="0.75",
            linewidth=0.7,
        )

    # Family names: subtle, not large/bold.
    for family, center in family_centers.items():
        ax.text(
            center,
            -0.28,
            family,
            ha="center",
            va="top",
            transform=ax.get_xaxis_transform(),
            fontsize=8,
        )

    ax.legend(
        title="Import round",
        fontsize=8,
        title_fontsize=8,
        loc="upper left",
        frameon=True,
    )

    ax.set_ylim(bottom=0)

    fig.subplots_adjust(bottom=0.29)
    fig.tight_layout()

    fig.savefig(
        OUT_PDF,
        bbox_inches="tight",
    )

    fig.savefig(
        OUT_PNG,
        dpi=300,
        bbox_inches="tight",
    )

    plt.close(fig)


def main():
    imports = pd.read_csv(IMPORTS_CSV)
    summary = pd.read_csv(SUMMARY_CSV)

    data = build_counts(imports, summary)

    print(
        data[
            ["family", "level", "Round 1", "Round 2", "Round 3+"]
        ].to_string(index=False)
    )

    plot_counts(data)

    print(f"\nSaved: {OUT_PDF}")
    print(f"Saved: {OUT_PNG}")


if __name__ == "__main__":
    main()
