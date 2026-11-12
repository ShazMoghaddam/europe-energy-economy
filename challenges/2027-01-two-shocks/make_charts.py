"""How the charts in this brief were made. They're a snapshot of the data at launch, so the brief and its
numbers always agree. Run from the repository root:

    python challenges/2027-01-two-shocks/make_charts.py
"""

import math
import random
from pathlib import Path

import pandas as pd

import bezel_charts as bc

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

random.seed(2026)  # stable gradient ids, so rerunning gives identical files
prices = pd.read_csv(ROOT / "data" / "world_prices.csv").set_index("month")


def normal(column: str) -> float:
    """The 2015 to 2019 average, added up exactly so every computer draws the same chart."""
    values = [float(v) for v in prices.loc["2015-01":"2019-12", column].dropna()]
    return math.fsum(values) / len(values)


rel = pd.DataFrame({"Oil": prices["brent_usd_per_barrel"] / normal("brent_usd_per_barrel"),
                    "Gas": prices["eu_gas_usd_per_mmbtu"] / normal("eu_gas_usd_per_mmbtu")})
peaks = {
    "2022": [round(float(rel.loc["2022-01":"2022-12", c].max()), 1) for c in rel.columns],
    "2026": [round(float(rel.loc["2026-01":"2026-12", c].max()), 1) for c in rel.columns],
}
bc.bars(peaks, labels=["Oil (Brent)", "European gas"], heading="The worst month of each shock, times the normal price",
        suffix="×", decimals=1, show_values=True, color=["#E07A3F", "#E8B92F"], patterns=["solid", "stripes"],
        theme="light", width=760, height=240).save(HERE / "two-shocks.svg")

both = rel.loc["2021-01":].dropna().round(2)
labels = [pd.Timestamp(m + "-01").strftime("%b %Y") for m in both.index]
bc.line(both, labels=[""] + labels[1:], heading="Oil and gas prices since 2021, times normal", suffix="×", decimals=1,
        goal=1, goal_label="Normal:", color=["#1F2937", "#E07A3F"], zero=True, theme="light", width=760,
        height=240).save(HERE / "since-2021.svg")

print("Saved the brief's charts to", HERE)
