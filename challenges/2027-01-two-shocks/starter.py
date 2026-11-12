"""Starter for Energy & the Economy, January 2027: Two shocks.

Uses the tidy data files in this repo, so there's nothing to download first:

    pip install -r requirements.txt
    python challenges/2027-01-two-shocks/starter.py

Want the very latest figures? Run `python data/fetch.py` first.

It prints a short summary and saves two charts, drawn with bezel-charts:

    oil-2022-vs-2026.svg   the Brent oil price, month by month, in 2022 and in 2026
    gas-2022-vs-2026.svg   the European gas price, month by month, in 2022 and in 2026
"""

from pathlib import Path

import pandas as pd

import bezel_charts as bc

ROOT = Path(__file__).resolve().parents[2]
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def year_by_month(series: pd.Series, year: str) -> list:
    """Twelve monthly values for one year. Months with no figure yet are left out at the end."""
    values = [series.get(f"{year}-{m:02d}") for m in range(1, 13)]
    while values and pd.isna(values[-1]):
        values.pop()
    return values


def main() -> None:
    prices = pd.read_csv(ROOT / "data" / "world_prices.csv").set_index("month")

    for column, name, unit in [("brent_usd_per_barrel", "Brent oil", "$ a barrel"),
                               ("eu_gas_usd_per_mmbtu", "European gas", "$ per million British thermal units")]:
        s = prices[column].dropna()
        print(f"{name} ({unit})")
        for year in ["2022", "2026"]:
            months = s.loc[f"{year}-01":f"{year}-12"]
            print(f"  {year}: highest {months.max():.2f} in {pd.Timestamp(months.idxmax() + '-01'):%B}, "
                  f"average {months.mean():.2f} over {len(months)} months")

    # Beginner: put the two years side by side, month by month.
    for column, slug, heading in [("brent_usd_per_barrel", "oil", "Brent oil, $ a barrel"),
                                  ("eu_gas_usd_per_mmbtu", "gas", "European gas, $ per MMBtu")]:
        s = prices[column]
        y22, y26 = year_by_month(s, "2022"), year_by_month(s, "2026")
        # The 2026 line is shorter: it simply stops at the latest month with a figure.
        bc.line({"2022": y22, "2026": y26}, labels=MONTHS[:len(y22)], heading=f"{heading}: 2022 against 2026",
                dash=["solid", "dashed"],
                theme="light", width=720).save(f"{slug}-2022-vs-2026.svg")

    print("Saved oil-2022-vs-2026.svg and gas-2022-vs-2026.svg. Open them in your browser.")


if __name__ == "__main__":
    main()
