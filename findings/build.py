"""Draw every chart and write the State of Europe's energy report from the latest data.

Run from the repository root after data/fetch.py:

    python findings/build.py

Charts go into charts/ as SVG files, made with bezel-charts (https://pypi.org/project/bezel-charts/).
The report is written to findings/README.md, and the headline tiles and key findings in the main README
are rewritten between their marker comments. Every number is worked out from the data files, so it stays
true when new figures come out. The few figures that don't come from a data series (company profits, gas
storage, government spending) live in data/company_profits.csv and data/facts.json, each with its source.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path

import pandas as pd

import bezel_charts as bc

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CHARTS = ROOT / "charts"
REPORT = ROOT / "findings" / "README.md"
README = ROOT / "README.md"

THEME = {"theme": "light"}
WIDE = 760
EU = "EU27_2020"
EU_NAME = "European Union (27)"
NORMAL = ("2015-01", "2019-12")  # the "normal" years prices are compared with

# Colours for energy sources, used the same way on every chart so readers learn them once.
SOURCE_COLOURS = {
    "Coal": "#5B5B66", "Gas": "#E07A3F", "Oil": "#9C6B4E", "Nuclear": "#8E6CD8",
    "Hydro": "#3D8FD1", "Wind": "#2BB3A3", "Solar": "#E8B92F", "Bioenergy and other": "#7CB45C",
}
BRENT_COLOUR, GAS_COLOUR = "#1F2937", "#E07A3F"

SHORT = {"Czechia": "Czechia", "Netherlands": "Netherlands", "European Union (27)": "EU average",
         "United Kingdom": "UK"}


# Loading -------------------------------------------------------------------------------------

def load() -> dict:
    read = lambda name, **kw: pd.read_csv(DATA / name, **kw)  # noqa: E731
    # Eurostat's code for Namibia is NA, so pandas mustn't read it as a missing value.
    codes = {"keep_default_na": False, "na_values": [""]}
    return {
        "mix": read("energy_mix.csv"),
        "prices": read("world_prices.csv").set_index("month"),
        "brent_daily": read("brent_daily.csv", parse_dates=["date"]).set_index("date")["brent_usd_per_barrel"],
        "household": read("household_prices.csv", **codes),
        "imports": read("gas_imports.csv", **codes),
        "imports_by_country": read("gas_imports_by_country.csv", **codes),
        "consumption": read("gas_consumption.csv", **codes),
        "companies": read("company_profits.csv"),
        "timeline": read("timeline.csv"),
        "facts": json.loads((DATA / "facts.json").read_text(encoding="utf-8")),
        "sources": json.loads((DATA / "sources.json").read_text(encoding="utf-8")),
    }


# Words for numbers and dates -------------------------------------------------------------------

def month_name(label: str) -> str:
    """'2026-10' -> 'Oct 2026'."""
    return pd.Timestamp(label + "-01").strftime("%b %Y")


def half(label: str) -> str:
    """Eurostat's half-years in words: '2026-S1' -> 'Jan to Jun 2026'."""
    year, h = label.split("-S")
    return f"{'Jan to Jun' if h == '1' else 'Jul to Dec'} {year}"


def half_short(label: str) -> str:
    """'2026-S1' -> 'H1 2026', for chart axes where space is tight."""
    year, h = label.split("-S")
    return f"H{h} {year}"


def pct(x: float, decimals: int = 0) -> str:
    return f"{x:.{decimals}f}%"


def change(x: float, decimals: int = 0) -> str:
    """A % change in words: 34.2 -> 'up 34%', -12 -> 'down 12%'."""
    if round(x, decimals) == 0:
        return "unchanged"
    return f"{'up' if x > 0 else 'down'} {abs(x):.{decimals}f}%"


def cents(eur_per_kwh: float) -> str:
    return f"{eur_per_kwh * 100:.1f} cents"


def times(x: float) -> str:
    """How many times bigger, in words people use: 1.5 -> '1.5 times', 11.75 -> '11.8 times'."""
    return f"{x:.1f} times"


def bcm(mio_m3: float) -> str:
    """Million cubic metres to billion cubic metres, the unit used in news reports."""
    return f"{mio_m3 / 1000:.0f} billion cubic metres"


def usd_bn(million: float) -> str:
    return f"${million / 1000:.1f} billion"


def save(chart: bc.Chart, name: str) -> str:
    CHARTS.mkdir(exist_ok=True)
    chart.save(CHARTS / f"{name}.svg")
    return f"../charts/{name}.svg"


def img(path: str, chart_alt: str) -> str:
    return f"![{chart_alt}]({path})"


def fsum_mean(values) -> float:
    """An exact average, so the result is the same whatever version of pandas or NumPy is installed."""
    values = [float(v) for v in values]
    return math.fsum(values) / len(values)


def axis(labels: list[str]) -> list[str]:
    """Labels for a long line chart. The first is left blank so it can't run into the next one."""
    return [""] + labels[1:]


# The headline tiles --------------------------------------------------------------------------

def tiles(d: dict) -> dict:
    """Six small tiles: the latest figure with the story behind it."""
    prices = d["prices"]
    mix = d["mix"][d["mix"]["country"] == EU_NAME].set_index("year")
    hh = d["household"][d["household"]["geo"] == EU]
    rus = d["imports_by_country"][d["imports_by_country"]["geo"] == EU].set_index("year")
    rus_share = (rus["imports_from_russia_mio_m3"] / rus["imports_total_mio_m3"] * 100).round(1)

    out = {}
    last36 = lambda s: s.dropna().iloc[-36:]  # noqa: E731
    brent = last36(prices["brent_usd_per_barrel"])
    out["oil"] = save(bc.spark(brent.tolist(), labels=[month_name(m) for m in brent.index], heading="Brent oil, $ a barrel",
                               prefix="$", decimals=0, delta_label=f"since {month_name(brent.index[0])}", delta="inverse", width=300, **THEME), "tile-oil")
    normal = fsum_mean(prices.loc[NORMAL[0]:NORMAL[1], "eu_gas_usd_per_mmbtu"].dropna())
    gas = (last36(prices["eu_gas_usd_per_mmbtu"]) / normal).round(2)
    out["gas"] = save(bc.spark(gas.tolist(), labels=[month_name(m) for m in gas.index], heading="European gas, times normal",
                               suffix="×", decimals=1, delta="none", width=300, **THEME), "tile-gas")
    for fuel, slug, heading in [("electricity", "electricity-bill", "Home electricity, cents per kWh"),
                                ("gas", "gas-bill", "Home gas, cents per kWh")]:
        s = hh[hh["fuel"] == fuel].set_index("period")["eur_per_kwh"].dropna()
        s = s[s.index >= "2019-S1"]
        out[slug] = save(bc.spark((s * 100).round(1).tolist(), labels=[half(p) for p in s.index], heading=heading, suffix="c",
                                  decimals=1, delta_label=f"since {s.index[0][:4]}", delta="inverse", width=300, **THEME), f"tile-{slug}")
    ren = mix["renewables_share_elec"].dropna()
    out["renewables"] = save(bc.spark(ren.round(1).tolist(), labels=[str(y) for y in ren.index], heading="EU power from renewables",
                                      suffix="%", decimals=1, delta="none", width=300, **THEME), "tile-renewables")
    out["russia"] = save(bc.spark(rus_share.tolist(), labels=[str(y) for y in rus_share.index], heading="EU gas imports from Russia",
                                  suffix="%", decimals=0, delta="none",
                                  width=300, **THEME), "tile-russia")
    return out


# 1. What normal looked like -------------------------------------------------------------------

def electricity_mix(d: dict) -> dict:
    mix = d["mix"][d["mix"]["country"] == EU_NAME].set_index("year")
    parts = pd.DataFrame({
        "Coal": mix["coal_electricity"], "Gas": mix["gas_electricity"], "Oil": mix["oil_electricity"],
        "Nuclear": mix["nuclear_electricity"], "Hydro": mix["hydro_electricity"], "Wind": mix["wind_electricity"],
        "Solar": mix["solar_electricity"],
        "Bioenergy and other": mix["biofuel_electricity"] + mix["other_renewable_exc_biofuel_electricity"],
    }).dropna()
    chart = bc.area(parts.round(1), stacked="percent", heading="Where the EU's electricity comes from, share of the total",
                    color=[SOURCE_COLOURS[c] for c in parts.columns], labels=axis([str(y) for y in parts.index]),
                    max=100, width=WIDE, height=300, **THEME)
    first, last = parts.index[0], parts.index[-1]
    share = parts.div(parts.sum(axis=1), axis=0) * 100
    fossil = share[["Coal", "Gas", "Oil"]].sum(axis=1)
    wind_solar = share[["Wind", "Solar"]].sum(axis=1)
    gas_prod = mix["gas_production"].dropna()
    return {"chart": save(chart, "electricity-mix"), "first": first, "last": last, "fossil": fossil, "wind_solar": wind_solar,
            "share": share, "parts": parts, "gas_prod": gas_prod}


# 2. Russia's gas ------------------------------------------------------------------------------

def russian_gas(d: dict) -> dict:
    imp = d["imports_by_country"]
    eu = imp[imp["geo"] == EU].set_index("year")
    share = eu["imports_from_russia_mio_m3"] / eu["imports_total_mio_m3"] * 100
    combo = bc.combo(bars=(eu["imports_from_russia_mio_m3"] / 1000).round(1).tolist(), line=share.round(1).tolist(),
                     labels=[str(y) for y in eu.index], series=["Gas from Russia, billion cubic metres"], line_series=["Russia's share of all gas imports (right)"],
                     heading="EU gas imports from Russia", line_suffix="%", line_decimals=0, decimals=0, width=WIDE, height=260, **THEME)

    y21 = imp[(imp["year"] == 2021) & (imp["geo"] != EU) & (imp["imports_from_russia_mio_m3"] > 0)].copy()
    y21["share"] = y21["imports_from_russia_mio_m3"] / y21["imports_total_mio_m3"] * 100
    y21 = y21[y21["imports_total_mio_m3"] >= 500]  # leave out tiny importers, where one cargo swings the share
    top = y21.set_index("country")["share"].sort_values(ascending=False).round(0)
    eu21 = float(share.loc[2021])
    bars = bc.bars(top, horizontal=True, heading="Share of each country's gas imports that came from Russia, 2021",
                   suffix="%", decimals=0, goal=round(eu21), goal_label="EU:", width=WIDE, **THEME)

    peak_year = int(eu["imports_from_russia_mio_m3"].idxmax())
    latest_year = int(eu.index[-1])
    replaced = (1 - eu.loc[latest_year, "imports_from_russia_mio_m3"] / eu.loc[2021, "imports_from_russia_mio_m3"]) * 100
    progress = bc.progress({f"Cut by {latest_year}": round(replaced)}, max=100, goal=100, goal_label="Full ban, autumn 2027",
                           heading="How much of the EU's Russian gas has gone since 2021", suffix="%", width=WIDE, **THEME)

    us = d["imports"][d["imports"]["partner"] == "US"].copy()
    us["year"] = us["month"].str[:4].astype(int)
    us_year = us.groupby("year")["mio_m3"].agg(["sum", "count"])
    us_year = us_year[us_year["count"] == 12]["sum"]
    return {"combo": save(combo, "russian-gas"), "bars": save(bars, "russian-gas-by-country"),
            "progress": save(progress, "russian-gas-cut"), "share": share, "eu": eu, "peak_year": peak_year,
            "latest_year": latest_year, "replaced": replaced, "top": top, "us": us_year}


# 3. The 2022 price shock ----------------------------------------------------------------------

def price_shock(d: dict) -> dict:
    p = d["prices"]
    base = {c: fsum_mean(p.loc[NORMAL[0]:NORMAL[1], c].dropna()) for c in p.columns}
    rel = pd.DataFrame({c: (p[c] / base[c]).round(2) for c in p.columns})
    rel.columns = ["Brent oil", "European gas"]
    labels = [month_name(m) for m in rel.index]
    notes = {"Mar 2022": "Russia invades Ukraine", "Mar 2026": "War in the Gulf"}
    notes = {k: v for k, v in notes.items() if k in labels}
    # Oil prices often come out a month before gas prices, so the gas line can stop one point early.
    span = rel.dropna(how="all")
    series = {name: span[name].loc[:span[name].last_valid_index()].tolist() for name in span.columns}
    labels = [month_name(m) for m in span.index]
    notes = {k: v for k, v in notes.items() if k in labels}
    chart = bc.line(series, labels=axis(labels),
                    heading="Oil and gas prices, compared with normal (1 = the 2015 to 2019 average)",
                    suffix="×", decimals=1, goal=1, goal_label="Normal:", notes=notes, color=[BRENT_COLOUR, GAS_COLOUR],
                    dash=["solid", "solid"], zero=True, width=WIDE, height=280, **THEME)
    gas = rel["European gas"].dropna()
    oil = rel["Brent oil"].dropna()
    raw_oil = p["brent_usd_per_barrel"].dropna()
    oil_now_month = raw_oil.index[-1]
    earlier_higher = raw_oil[(raw_oil.index < oil_now_month) & (raw_oil >= raw_oil.iloc[-1])]
    return {"chart": save(chart, "oil-and-gas-prices"), "gas": gas, "oil": oil, "base": base, "raw": p,
            "gas_peak": (gas.idxmax(), float(gas.max())), "oil_now": (oil_now_month, float(raw_oil.iloc[-1])),
            "oil_last_higher": earlier_higher.index[-1] if len(earlier_higher) else None}


# 4. The 2026 shock --------------------------------------------------------------------------

def gulf_shock(d: dict) -> dict:
    daily = d["brent_daily"]
    year = daily[daily.index >= "2026-01-01"]
    # Markets are shut at weekends and holidays. Those days show the last price before them, so the
    # calendar has no blank squares that could be mistaken for a low price.
    days = pd.date_range(year.index.min(), year.index.max(), freq="D")
    filled = year.reindex(days).ffill()
    over = (filled > 100).astype(int)
    heat = bc.heatmap(over, heading="Days in 2026 when Brent oil cost more than $100 a barrel", stat="total", suffix=" days",
                      width=WIDE, **THEME)
    f = d["facts"]["storage"]
    gauge = bc.gauge(f["march_2026_percent_full"], min=0, max=100, zones=[40, 70], suffix="%", goal=f["march_2026_ten_year_average"],
                     label="Full, March 2026", heading="EU gas storage in March 2026, against the 10-year average for the time of year",
                     color=["#D9534F", "#E8B92F", "#2BB3A3"], width=WIDE, **THEME)
    before = year[year.index < "2026-02-28"]
    peak_day = year.idxmax()
    return {"heat": save(heat, "oil-2026-calendar"), "gauge": save(gauge, "gas-storage-2026"), "year": year,
            "before": float(before.iloc[-1]), "before_day": before.index[-1], "peak": (peak_day, float(year.max())),
            "over_100": int(over.sum()), "last_100_before": daily[(daily.index < "2026-01-01") & (daily > 100)].index.max(), "days": len(over), "first_over": over[over == 1].index.min(),
            "latest": (year.index[-1], float(year.iloc[-1]))}


# 5. What households pay --------------------------------------------------------------------

def household(d: dict) -> dict:
    hh = d["household"]
    eu = hh[hh["geo"] == EU].pivot(index="period", columns="fuel", values="eur_per_kwh").dropna()
    line = bc.line((eu * 100).round(1).rename(columns={"electricity": "Electricity", "gas": "Gas"}),
                   labels=axis([half_short(p) for p in eu.index]), heading="What EU households pay, cents per kWh, all taxes included",
                   suffix="c", decimals=1, color=["#3D8FD1", GAS_COLOUR], zero=True, width=WIDE, height=260, **THEME)

    elec = hh[hh["fuel"] == "electricity"].pivot(index="country", columns="period", values="eur_per_kwh")
    latest = elec.columns[-1]
    now = (elec[latest].dropna() * 100).round(1)
    now = now.drop(EU_NAME).sort_values(ascending=False)
    bars = bc.bars(now, horizontal=True, heading=f"Household electricity, cents per kWh, {half(latest)}", suffix="c", decimals=1,
                   goal=round(float(elec.loc[EU_NAME, latest]) * 100, 1), goal_label="EU average:", width=WIDE, **THEME)

    years = ["2019-S1", "2021-S1", "2022-S2", "2023-S1", latest]
    years = list(dict.fromkeys(y for y in years if y in elec.columns))
    countries = elec.drop(index=[EU_NAME], errors="ignore")
    # Only countries with a price in every period, so each box compares the same group of countries.
    spread = pd.DataFrame({half_short(y): (countries[y] * 100).round(1) for y in years}).dropna()
    box = bc.boxplot(spread, heading="How much household electricity costs across Europe, cents per kWh", suffix="c", decimals=0,
                     mark="mean", width=WIDE, height=260, **THEME)
    gas = hh[hh["fuel"] == "gas"].pivot(index="country", columns="period", values="eur_per_kwh")
    return {"line": save(line, "household-prices"), "bars": save(bars, "electricity-by-country"),
            "box": save(box, "electricity-spread"), "eu": eu, "latest": latest, "now": now, "elec": elec, "gas": gas,
            "spread": spread}


# 6. Did Russian gas decide who paid most? ----------------------------------------------------

def dependence(d: dict) -> dict:
    imp = d["imports_by_country"]
    y21 = imp[(imp["year"] == 2021) & (imp["geo"] != EU) & (imp["imports_from_russia_mio_m3"] > 0)
              & (imp["imports_total_mio_m3"] >= 500)].set_index("geo")
    share = y21["imports_from_russia_mio_m3"] / y21["imports_total_mio_m3"] * 100
    gas = d["household"][d["household"]["fuel"] == "gas"].pivot(index="geo", columns="period", values="eur_per_kwh")
    rise = (gas["2023-S1"] / gas["2021-S1"] - 1) * 100
    df = pd.concat({"Gas from Russia in 2021, %": share.round(1), "Rise in household gas prices, %": rise.round(1)}, axis=1).dropna()
    names = imp.drop_duplicates("geo").set_index("geo")["country"]
    df["country"] = [names[g] for g in df.index]
    chart = bc.scatter(df, x="Gas from Russia in 2021, %", y="Rise in household gas prices, %", label="country", trend=True,
                       heading="Russian gas and household gas bills, by country (Jan to Jun 2021 against Jan to Jun 2023)",
                       width=WIDE, height=320, **THEME)
    xs, ys = df.iloc[:, 0].tolist(), df.iloc[:, 1].tolist()
    mx, my = fsum_mean(xs), fsum_mean(ys)
    cov = math.fsum((x - mx) * (y - my) for x, y in zip(xs, ys))
    r = cov / math.sqrt(math.fsum((x - mx) ** 2 for x in xs) * math.fsum((y - my) ** 2 for y in ys))
    df = df.set_index("country")
    biggest = df.iloc[:, 1].idxmax()
    rest = df.drop(biggest)
    r_rest = float(rest.corr().iloc[0, 1])
    return {"chart": save(chart, "russian-gas-and-bills"), "r": r, "n": len(df), "df": df, "biggest": biggest,
            "biggest_rise": float(df.loc[biggest].iloc[1]), "r_rest": r_rest}


# 7. Europe used less gas -------------------------------------------------------------------

def gas_demand(d: dict) -> dict:
    c = d["consumption"].pivot(index="month", columns="geo", values="mio_m3")
    names = d["consumption"].drop_duplicates("geo").set_index("geo")["country"]
    eu = c[EU].dropna()
    years = eu.groupby(eu.index.str[:4]).agg(["sum", "count"])
    full = years[years["count"] == 12]["sum"]
    bars = bc.bars((full / 1000).round(0), heading="How much gas the EU used each year, billion cubic metres", decimals=0,
                   highlight="none", show_values=True, width=WIDE, height=220, **THEME)

    # The EU's 2022 emergency rule asked countries to cut gas use by 15% from August 2022, against the
    # average for the same months over the five years before. It was extended to March 2024.
    months = c.index.to_series()
    ref = c[(months >= "2017-04") & (months <= "2022-03")]
    period = c[(months >= "2022-08") & (months <= "2024-03")]
    ref_by_month = ref.groupby(ref.index.str[5:7]).mean()
    expected = pd.DataFrame([ref_by_month.loc[m[5:7]] for m in period.index], index=period.index)
    cut = ((1 - period.sum() / expected.sum()) * 100).dropna()
    cut = cut[[g for g in cut.index if period[g].notna().all() and g != "UK"]]
    eu_cut = float(cut[EU])
    countries = cut.drop(EU).rename(names).sort_values(ascending=False).round(1)
    cutters = countries[countries > 0]
    top = math.ceil(float(cutters.max()) / 5) * 5
    bullet = bc.bullet({k: v for k, v in cutters.items()}, target=15, zones=[5, 15], max=top, zone_labels=["Small cut", "Some way there", "Hit the 15% goal"],
                       heading="How much each country cut its gas use, Aug 2022 to Mar 2024, against its usual use", suffix="%",
                       decimals=0, width=WIDE, **THEME)
    hist = bc.histogram(countries.tolist(), bin_width=5, mark="median", heading="How many countries cut their gas use by how much",
                        suffix="%", width=WIDE, height=220, **THEME)
    return {"bars": save(bars, "gas-use"), "bullet": save(bullet, "gas-cuts-by-country"), "hist": save(hist, "gas-cuts-spread"),
            "full": full, "eu_cut": eu_cut, "countries": countries, "latest_month": eu.index[-1],
            "used_more": countries[countries <= 0]}


# 8. The switch to clean power --------------------------------------------------------------

def clean_power(d: dict, mix_result: dict) -> dict:
    parts = mix_result["parts"]
    lines = parts[["Wind", "Solar", "Gas", "Coal"]].round(0)
    line = bc.line(lines, labels=axis([str(y) for y in lines.index]), heading="EU electricity made from wind, solar, gas and coal, TWh",
                   color=[SOURCE_COLOURS[c] for c in lines.columns], dash=["solid", "solid", "dashed", "dashed"],
                   markers=["circle", "diamond", "square", "triangle"], width=WIDE, height=270, **THEME)
    a, b = 2021, int(parts.index[-1])
    diff = (parts.loc[b] - parts.loc[a]).round(0)
    order = ["Coal", "Gas", "Oil", "Nuclear", "Hydro", "Bioenergy and other", "Wind", "Solar"]
    short = {"Bioenergy and other": "Bio, other"}
    steps = {short.get(k, k): float(diff[k]) for k in order}
    steps["Overall"] = 0  # a total with no value of its own shows where the steps ended up
    water = bc.waterfall(steps, totals=["Overall"], heading=f"How the EU's electricity changed from {a} to {b}, TWh",
                         decimals=0, angle_labels=True, width=WIDE, height=280, **THEME)
    row = parts.loc[b]
    now = pd.Series({"Coal, gas and oil": row["Coal"] + row["Gas"] + row["Oil"], "Nuclear": row["Nuclear"], "Wind": row["Wind"],
                     "Solar": row["Solar"], "Hydro": row["Hydro"], "Bioenergy and other": row["Bioenergy and other"]}).round(0)
    now = now.sort_values(ascending=False)
    colours = {**SOURCE_COLOURS, "Coal, gas and oil": SOURCE_COLOURS["Coal"]}
    donut = bc.donut(now, heading=f"Where the EU's electricity came from in {b}", center_label="TWh",
                     color=[colours[k] for k in now.index], width=WIDE, height=220, **THEME)
    mix = d["mix"]
    big = ["Germany", "France", "Italy", "Spain", "Poland"]
    rings_data = {c: round(float(mix[(mix["country"] == c) & (mix["year"] == b)]["renewables_share_elec"].iloc[0])) for c in big}
    rings = bc.ring(rings_data, heading=f"Share of electricity from renewables in {b}, the EU's five biggest economies",
                    suffix="%", width=WIDE, **THEME)
    crossings = {}
    for clean, dirty in [("Wind", "Gas"), ("Solar", "Coal"), ("Wind", "Coal")]:
        ahead = parts[clean] > parts[dirty]
        if not ahead.iloc[-1]:
            crossings[(clean, dirty)] = None
            continue
        start = ahead.index[-1]
        for year in reversed(ahead.index):  # step back to the start of the current unbroken run
            if not ahead[year]:
                break
            start = year
        crossings[(clean, dirty)] = int(start)
    return {"line": save(line, "wind-solar-gas-coal"), "water": save(water, "electricity-change"),
            "donut": save(donut, "electricity-today"), "rings": save(rings, "renewables-big-five"),
            "diff": diff, "a": a, "b": b, "crossings": crossings, "now": now, "rings_data": rings_data}


# 9. The big energy companies ---------------------------------------------------------------

def companies(d: dict) -> dict:
    c = d["companies"].pivot(index="year", columns="company", values="usd_million")[["Shell", "TotalEnergies", "BP"]]
    chart = bc.bars((c / 1000).round(1), labels=[str(y) for y in c.index], heading="Profits of Europe's three biggest oil companies, $ billion",
                    prefix="$", suffix="bn", decimals=0, color=["#E8B92F", "#D9534F", "#2BB3A3"], patterns=["solid", "stripes", "dots"],
                    width=WIDE, height=260, **THEME)
    total = c.sum(axis=1)
    return {"chart": save(chart, "company-profits"), "c": c, "total": total}


# Writing -----------------------------------------------------------------------------------

def timeline_table(tl: pd.DataFrame, shock: str) -> str:
    rows = tl[tl["shock"] == shock]
    lines = ["| When | What happened |", "|---|---|"]
    for _, r in rows.iterrows():
        when = pd.Timestamp(r["date"]).strftime("%-d %b %Y")
        lines.append(f"| {when} | {r['event']} [↗]({r['source']}) |")
    return "\n".join(lines)


def write(d: dict) -> tuple[str, dict]:
    tiles(d)  # draws the six tiles; their paths are fixed, so the block below can name them
    m = electricity_mix(d)
    r = russian_gas(d)
    p = price_shock(d)
    g = gulf_shock(d)
    h = household(d)
    dep = dependence(d)
    dem = gas_demand(d)
    cp = clean_power(d, m)
    co = companies(d)
    facts = d["facts"]
    fetched = d["sources"]["fetched"]

    first, last = m["first"], m["last"]
    fossil, ws = m["fossil"], m["wind_solar"]
    eu_hh = h["eu"]
    elec, gasp = eu_hh["electricity"], eu_hh["gas"]
    e_peak, g_peak = elec.idxmax(), gasp.idxmax()
    latest = h["latest"]
    cheapest, dearest = h["now"].idxmin(), h["now"].idxmax()
    gp_month, gp_x = p["gas_peak"]
    oil_month, oil_usd = p["oil_now"]
    sh = r["share"]
    us = r["us"]
    gas_rise = (gasp.loc["2023-S1"] / gasp.loc["2021-S1"] - 1) * 100
    elec_rise = (elec[e_peak] / elec.loc["2021-S1"] - 1) * 100
    support = facts["government_support"]
    cf = facts["russian_gas_commission"]
    st = facts["storage"]
    epl = facts["uk_energy_profits_levy"]
    ctot = co["total"]
    cr = cp["crossings"]

    tile_block = """<p align="center">
  <img src="{p}charts/tile-oil.svg" width="270" alt="Brent oil price over the last three years">
  <img src="{p}charts/tile-gas.svg" width="270" alt="European gas price compared with normal, over the last three years">
  <img src="{p}charts/tile-russia.svg" width="270" alt="Share of EU gas imports from Russia since 2010">
</p>

<p align="center">
  <img src="{p}charts/tile-electricity-bill.svg" width="270" alt="EU household electricity price since 2019">
  <img src="{p}charts/tile-gas-bill.svg" width="270" alt="EU household gas price since 2019">
  <img src="{p}charts/tile-renewables.svg" width="270" alt="Share of EU electricity from renewables since 2010">
</p>"""

    report = f"""# State of Europe's energy

**From 2010 to {month_name(p['raw'].dropna(how='all').index[-1])}: two wars, two price shocks, and a power system that changed faster than anyone expected.**

Every number and chart on this page is worked out from the data in [`data/`](../data) by [`build.py`](build.py), and
redrawn when new figures come out. Charts are drawn with [bezel-charts](https://pypi.org/project/bezel-charts/), an
open-source Python library created by Shaz Moghaddam, the author of this project.

Data last downloaded: {fetched}.

**In this report:** [1. The headline numbers](#1-the-headline-numbers) ·
[2. What normal looked like](#2-what-normal-looked-like-2010-to-2021) ·
[3. Russia's gas](#3-russias-gas-from-biggest-supplier-to-almost-gone) ·
[4. The 2022 price shock](#4-the-2022-price-shock) ·
[5. The second shock: war in the Gulf](#5-the-second-shock-war-in-the-gulf-2026) ·
[6. What households pay](#6-what-households-pay) ·
[7. Did Russian gas decide who paid most?](#7-did-russian-gas-decide-who-paid-most) ·
[8. Europe used less gas](#8-europe-used-less-gas) ·
[9. The switch to clean power](#9-the-switch-to-clean-power) ·
[10. What governments did](#10-what-governments-and-the-eu-did) ·
[11. The big energy companies](#11-the-big-energy-companies) ·
[About the data](#about-the-data)

## 1. The headline numbers

{tile_block.replace('{p}', '../')}

Each tile shows the latest figure, with the line behind it.

- **Oil** averaged **${oil_usd:.0f}** a barrel in {month_name(oil_month)}, {times(oil_usd / p['base']['brent_usd_per_barrel'])} its 2015 to 2019 average.
- **Russia** supplied **{pct(sh.loc[2021])}** of the gas the EU imported in 2021. By {r['latest_year']} it was **{pct(sh.iloc[-1])}**.
- **Households** paid **{cents(elec.iloc[-1])}** per kWh for electricity in {half(latest)}, {change((elec.iloc[-1] / elec.loc['2021-S1'] - 1) * 100)} on {half('2021-S1')}.
- **Renewables** made **{pct(m['share'].loc[last, ['Hydro', 'Wind', 'Solar', 'Bioenergy and other']].sum())}** of the EU's electricity in {last}, against {pct(m['share'].loc[first, ['Hydro', 'Wind', 'Solar', 'Bioenergy and other']].sum())} in {first}.

## 2. What normal looked like (2010 to 2021)

{img(m['chart'], 'Where the EU gets its electricity, as shares of the total, from ' + str(first) + ' to ' + str(last))}

In {first}, **{pct(fossil.loc[first])}** of the EU's electricity came from burning coal, gas and oil. Wind and solar
together made just **{pct(ws.loc[first], 1)}**. Nuclear power, half of it made in France, provided **{pct(m['share'].loc[first, 'Nuclear'])}**.

For most of the 2010s the picture changed slowly. Wind and solar grew a little every year, coal slipped, and
energy was cheap: oil and gas prices in 2015 to 2019 are the "normal" that the rest of this report compares against.

Underneath, though, a risk was building. The EU's own gas fields were running down. Gas production fell from
**{m['gas_prod'].loc[first]:,.0f} TWh** in {first} to **{m['gas_prod'].loc[2021]:,.0f} TWh** in 2021, as the giant
Groningen field in the Netherlands was wound down after earthquakes. More and more gas had to be bought from abroad,
and the cheapest, closest seller was Russia.

## 3. Russia's gas: from biggest supplier to almost gone

{img(r['combo'], 'EU gas imports from Russia each year, with Russia’s share of all imports')}

- In {r['peak_year']}, the EU bought **{bcm(r['eu'].loc[r['peak_year'], 'imports_from_russia_mio_m3'])}** of gas from Russia.
  In 2021, Russia supplied **{pct(sh.loc[2021])}** of all the gas the EU imported from outside the EU.
- By {r['latest_year']} that share had fallen to **{pct(sh.iloc[-1])}**, and the volume was down
  **{pct(r['replaced'])}** on 2021.
- The European Commission, which also counts Russian gas that reaches Europe through other countries and as
  liquefied natural gas (LNG) shipped by sea, puts the fall at **{cf['share_2021_percent']}% to {cf['share_2024_percent']}%**
  between 2021 and 2024, and about **{cf['share_2025_percent']}%** in 2025.

Some countries were far more exposed than others:

{img(r['bars'], 'Share of each country’s gas imports from Russia in 2021')}

Countries that bought less than 500 million cubic metres of gas from abroad are left out, because a single delivery
can swing their figures. A few countries, including Austria, report no Russian gas at all, even though Austria is
known to have bought most of its gas from Russia. These figures depend on how each country records where its gas
came from, so treat the smaller bars with care.

Who filled the gap? Mostly Norway, through North Sea pipelines, and the United States, by ship. The EU imported
**{bcm(us.loc[2021])}** of American LNG in 2021 and **{bcm(us.iloc[-1])}** in {us.index[-1]}.

{img(r['progress'], 'How much of the EU’s 2021 Russian gas imports have gone')}

The last of it is now being legislated away. In January 2026 EU countries agreed a step-by-step ban: Russian LNG
from the start of 2027 and Russian pipeline gas from autumn 2027.

{timeline_table(d['timeline'], 'Russia')}

## 4. The 2022 price shock

{img(p['chart'], 'Oil and gas prices since 2010, compared with their 2015 to 2019 average')}

The line at 1 is normal: the average price from 2015 to 2019. Anything above it is how many times more expensive
energy was.

- **Gas** was already climbing in late 2021, as economies reopened after Covid and Russia sent less gas than usual.
  After the invasion of Ukraine it went further. In **{month_name(gp_month)}** European gas cost **{times(gp_x)}** its normal
  price, the highest monthly average in this data.
- **Oil** rose too, but much less: about **{times(p['oil'].loc['2022-01':'2022-12'].max())}** normal at its 2022 peak. Oil is
  traded all over the world, so there are many more places to buy it. Most of Europe's gas came through a few
  pipelines.
- By 2024 gas had fallen back, but it never quite returned to normal. Even in 2025 it was about **{times(fsum_mean(p['gas'].loc['2025-01':'2025-12']))}** its 2015 to 2019 level.

## 5. The second shock: war in the Gulf (2026)

On **28 February 2026** the United States and Israel struck Iran, and shipping through the **Strait of Hormuz**
almost stopped. This narrow channel between Iran and Oman carries about **{facts['gulf_2026']['hormuz_share_of_world_oil_percent']}%** of
the world's oil and about **{facts['gulf_2026']['hormuz_share_of_world_lng_percent']}%** of its LNG, including everything Qatar exports.

{img(g['heat'], 'Calendar of 2026 showing the days when Brent oil cost more than $100 a barrel')}

Each square is a day. A dark square means oil cost more than $100 a barrel that day. Markets are closed at weekends,
so weekends take the price from the last weekday before them.

- Oil cost more than $100 a barrel on **{g['over_100']} of the {g['days']} days** so far this year, starting on
  {g['first_over']:%-d %B}. Before the war, the last time it was over $100 was
  {g['last_100_before']:%-d %B %Y}.
- On {g['before_day']:%-d %B}, just before the strikes, Brent oil cost **${g['before']:.0f}** a barrel.
- It peaked at **${g['peak'][1]:.0f}** on {g['peak'][0]:%-d %B}. A ceasefire in April and tankers moving again in June
  brought it back down. Then fighting started again at the end of August.
- In {month_name(oil_month)} oil averaged **${oil_usd:.0f}**, the highest monthly average since
  {month_name(p['oil_last_higher']) if p['oil_last_higher'] else 'records began'}, before allowing for inflation. The latest daily price, on
  {g['latest'][0]:%-d %B %Y}, was **${g['latest'][1]:.0f}**.

This time Europe was hit through its gas storage. Countries fill underground stores over the summer to get through
the winter. They were unusually empty when the war began: at the end of February the EU held
**{st['end_february_bcm']['2026']} billion cubic metres**, against {st['end_february_bcm']['2025']} a year earlier and {st['end_february_bcm']['2024']} in 2024.

{img(g['gauge'], 'EU gas storage in March 2026 against the ten-year average')}

Storage was about **{st['march_2026_percent_full']}%** full in March 2026, against a usual **{st['march_2026_ten_year_average']}%** for the time of year. The
Commission told countries they could aim for {st['eased_target_percent']}% by winter instead of the legal {st['legal_target_percent']}%. By the
end of August, storage had only reached **{st['end_august_2026_percent_full']}%**.

{timeline_table(d['timeline'], 'Gulf')}

## 6. What households pay

{img(h['line'], 'What EU households pay for electricity and gas, every half year since 2010')}

These are the prices households actually pay per kWh, including taxes, for a typical home. They are not adjusted
for inflation.

- Household **gas** rose **{pct(gas_rise)}** between {half('2021-S1')} and {half('2023-S1')}. It peaked at
  **{cents(gasp[g_peak])}** per kWh in {half(g_peak)}, against **{cents(gasp.loc['2021-S1'])}** in {half('2021-S1')}.
- Household **electricity** rose more slowly, but has stayed high: from **{cents(elec.loc['2021-S1'])}** in {half('2021-S1')}
  to a peak of **{cents(elec[e_peak])}** in {half(e_peak)}, {change(elec_rise)}.
- Bills moved much less than wholesale prices. Most homes pay fixed tariffs that change slowly, many governments
  capped prices, and taxes and network charges, which barely changed, make up a big part of every bill.
- The latest figures, for {half(latest)}, only partly cover the war in the Gulf. If gas stays expensive, it will
  reach bills over the coming months.

{img(h['bars'], 'Household electricity prices by country, latest half year')}

In {half(latest)}, electricity was dearest in **{dearest} ({h['now'][dearest]:.1f} cents)** and cheapest in
**{cheapest} ({h['now'][cheapest]:.1f} cents)**. Hungary's government sets household prices well below market rates for
typical use, which is why it sits at the bottom.

{img(h['box'], 'How spread out household electricity prices were across countries in each period')}

Each box shows the middle half of European countries, and the diamond marks the average. In 2022 the spread grew
much wider: some countries passed the shock on to households almost straight away, while others held prices down.

## 7. Did Russian gas decide who paid most?

You might expect the countries that bought the most Russian gas to have seen the biggest rises in bills. The data
says they didn't.

{img(dep['chart'], 'Each country’s reliance on Russian gas in 2021 against the rise in its household gas price')}

Each dot is a country. The dashed line is the best straight-line fit, and **r = {dep['r']:.2f}** says how closely the dots
follow it. 1 would be a perfect upward line, and 0 means no pattern at all. Across these {dep['n']} countries,
there is almost no link.

The dot near the top is **{dep['biggest']}**, where household gas went up **{pct(dep['biggest_rise'])}**, from a very low
regulated price. Leave it out and r is still only **{dep['r_rest']:.2f}**.

Why? Because Europe shares one gas market. When Russian gas disappeared, every country was suddenly bidding for the
same replacement cargoes, so prices rose everywhere, whether or not a country had ever bought from Russia. What
made the real difference to bills was what each government did next: price caps, tax cuts and subsidies.

## 8. Europe used less gas

{img(dem['bars'], 'How much gas the EU used each year')}

In August 2022 EU countries agreed to cut their gas use by 15%, compared with their usual use for the time of year.
It was voluntary, and later extended to March 2024.

- Between August 2022 and March 2024 the EU as a whole used **{pct(dem['eu_cut'])}** less gas than usual. That's our
  calculation from Eurostat's monthly data, following the method set out in the EU rules. For the first winter alone,
  [Eurostat's own figure]({facts['gas_demand_eurostat']['source']}) was {facts['gas_demand_eurostat']['cut_aug_2022_to_mar_2023_percent']}%.
- In {dem['full'].index[-1]} the EU used **{bcm(dem['full'].iloc[-1])}**, against **{bcm(dem['full'].loc['2021'])}** in 2021.
- Some of the cut came from people turning the heating down and from mild winters. A lot came from factories,
  especially chemicals and fertiliser makers, using less or shutting down production. That's a saving, but
  also a cost.

{img(dem['bullet'], 'How much each country cut its gas use against the 15% goal')}

{img(dem['hist'], 'How many countries cut their gas use by how much')}

**{sum(dem['countries'] >= 15)} of {len(dem['countries'])}** countries beat the 15% goal. The typical country cut its use by about
**{pct(dem['countries'].median())}**. {' and '.join(dem['used_more'].index)} used more gas than usual, so {'is' if len(dem['used_more']) == 1 else 'are'} left off the
first chart.

## 9. The switch to clean power

The shocks didn't just raise prices. They sped up a change that was already happening.

{img(cp['line'], 'EU electricity from wind, solar, gas and coal, every year since 2010')}

- **Wind** has made more of the EU's electricity than **gas** every year since **{cr[('Wind', 'Gas')]}**.
- **Solar** overtook **coal** in **{cr[('Solar', 'Coal')]}**. In {first} coal made {times(m['parts'].loc[first, 'Coal'] / m['parts'].loc[first, 'Solar'])} as much electricity as solar.

{img(cp['water'], 'How the EU’s electricity changed by source between 2021 and the latest year')}

Between {cp['a']} and {cp['b']}, coal power fell by **{-cp['diff']['Coal']:.0f} TWh** and gas power by
**{-cp['diff']['Gas']:.0f} TWh**. Solar grew by **{cp['diff']['Solar']:.0f} TWh**, the biggest change of any source.
Overall the EU made **{-cp['diff'].sum():.0f} TWh** less electricity in {cp['b']} than in {cp['a']}, partly because high
prices pushed people and businesses to use less.

{img(cp['donut'], 'Where the EU’s electricity came from in the latest year')}

{img(cp['rings'], 'Share of electricity from renewables in Germany, France, Italy, Spain and Poland')}

France scores lower on renewables than you might expect because most of its electricity comes from nuclear power,
which is low-carbon but not renewable.

## 10. What governments and the EU did

**Governments spent big to protect people.** Between September 2021 and January 2023, European governments set
aside about **€{support['total_eur_bn']} billion** to shield households and businesses from energy prices, according to
[Bruegel]({support['source']}): **€{support['eu_eur_bn']} billion** in the EU, **€{support['uk_eur_bn']} billion** in
the UK and **€{support['norway_eur_bn']} billion** in Norway. Germany alone earmarked **€{support['germany_eur_bn']} billion**.
The help came as price caps, cuts to energy taxes, direct payments and support for businesses.

**The EU acted together**, which it had rarely done on energy:

| What | What it did |
|---|---|
| **Gas storage rules** (2022) | Countries must fill their gas stores to 90% before each winter. In 2026 this was eased to 80% because of the war in the Gulf |
| **15% cut in gas use** (Aug 2022) | A shared, voluntary goal, met overall: see finding 8 |
| **Windfall taxes** (Oct 2022) | A "solidarity contribution" of at least 33% on fossil fuel firms' extra profits, and a cap on some electricity producers' revenues |
| **Gas price cap** (Dec 2022) | A safety brake on the wholesale price at €180 per MWh |
| **REPowerEU** (May 2022) | The plan to end Russian fossil fuels: more renewables, more LNG terminals, saving energy |
| **Ban on Russian gas** (agreed Jan 2026) | No Russian LNG from 2027, no Russian pipeline gas from autumn 2027 |

**The UK** added its own windfall tax, the Energy Profits Levy, on oil and gas producers: {epl['rates'][0][1]}% from
{epl['rates'][0][0]}, raised to {epl['rates'][1][1]}% from {epl['rates'][1][0]} and {epl['rates'][2][1]}% from
{epl['rates'][2][0]}. It runs until {epl['ends']}.

In April 2026, as the war in the Gulf pushed prices up again, the Commission relaxed the rules on state aid so
governments could help again, and said countries could tax windfall profits further.

## 11. The big energy companies

{img(co['chart'], 'Yearly profits of Shell, TotalEnergies and BP since 2019')}

High prices were very good news for the companies that produce and sell oil and gas.

- In 2022 Shell, TotalEnergies and BP together made **{usd_bn(ctot.loc[2022])}** in profit, against
  **{usd_bn(ctot.loc[2019])}** in 2019. Shell's **{usd_bn(co['c'].loc[2022, 'Shell'])}** was the biggest in its history.
- Profits have fallen back since: to **{usd_bn(ctot.loc[2025])}** in 2025, as oil and gas prices eased.
- In 2020, the Covid year, BP made a loss of {usd_bn(-co['c'].loc[2020, 'BP'])}.
- The profits fed the case for windfall taxes, and they shaped strategy. In February 2025 BP cut its yearly spending
  on low-carbon energy to $1.5 to $2 billion and raised its oil and gas spending to about $10 billion. Its chief executive said that "in the
  long run investors will love this".

Each company reports its own headline measure, which leaves out one-off gains and losses, so the figures are close
but not exactly like for like: Shell's adjusted earnings, TotalEnergies' adjusted net income and BP's underlying
replacement cost profit. Norway's Equinor, which sells much of the gas that replaced Russia's, also reported a record profit for 2022.

## About the data

| What | Who publishes it | File |
|---|---|---|
| Electricity by source, energy use | [Our World in Data](https://github.com/owid/energy-data), from Ember and the Energy Institute | [`energy_mix.csv`](../data/energy_mix.csv) |
| Household electricity and gas prices | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_pc_204/default/table?lang=en) | [`household_prices.csv`](../data/household_prices.csv) |
| Gas imports, by supplier | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_ti_gas/default/table?lang=en) | [`gas_imports_by_country.csv`](../data/gas_imports_by_country.csv), [`gas_imports.csv`](../data/gas_imports.csv) |
| Gas use, month by month | [Eurostat](https://ec.europa.eu/eurostat/databrowser/view/nrg_cb_gasm/default/table?lang=en) | [`gas_consumption.csv`](../data/gas_consumption.csv) |
| Oil price (Brent) | [U.S. Energy Information Administration, via FRED](https://fred.stlouisfed.org/series/MCOILBRENTEU) | [`world_prices.csv`](../data/world_prices.csv), [`brent_daily.csv`](../data/brent_daily.csv) |
| European gas price (Dutch TTF) | [International Monetary Fund, via FRED](https://fred.stlouisfed.org/series/PNGASEUUSDM) | [`world_prices.csv`](../data/world_prices.csv) |
| Company profits | Each company's annual results | [`company_profits.csv`](../data/company_profits.csv) |
| Events, storage, government support | Linked next to each figure | [`timeline.csv`](../data/timeline.csv), [`facts.json`](../data/facts.json) |

A few things to know:

- **Prices are not adjusted for inflation.** Everything else got more expensive too, especially in 2022 and 2023.
- **Gas imports by country of origin are only published yearly**, so the latest full year is {r['latest_year']}. Eurostat's
  monthly import figures record the country the gas arrived from, so Russian gas that crossed Ukraine shows up as
  Ukrainian, and Algerian gas as Tunisian. This report only uses them for American LNG, which arrives by ship.
- **The UK** left the EU in 2020, so Eurostat stopped publishing UK prices after that. The UK is included in the
  electricity figures from Our World in Data.
- **Countries sometimes keep figures confidential** or count gas by the neighbour it came through. Where that matters, it's
  said next to the chart.
"""

    key = f"""### Russia went from supplying {pct(sh.loc[2021])} of the EU's imported gas to {pct(sh.iloc[-1])}

In 2021 Russia was the EU's biggest gas supplier. By {r['latest_year']} the volume was down {pct(r['replaced'])}, replaced
mostly by Norway and American LNG, and a full ban starts in 2027.

![EU gas imports from Russia]({r['combo'].replace('../', '')})

### Gas cost {times(gp_x)} its normal price in {month_name(gp_month)}

Then, in 2026, war in the Gulf sent oil to **${g['peak'][1]:.0f}** a barrel on {g['peak'][0]:%-d %B}. It averaged **${oil_usd:.0f}** in {month_name(oil_month)}.

![Oil and gas prices compared with normal]({p['chart'].replace('../', '')})

### Countries that relied on Russian gas didn't see bigger bills

There's almost no link (r = {dep['r']:.2f}) between how much gas a country bought from Russia and how much household gas
prices rose. Europe shares one market, so prices rose everywhere.

![Russian gas and household bills]({dep['chart'].replace('../', '')})

### Wind now makes more of the EU's electricity than gas, and solar more than coal

Renewables made {pct(m['share'].loc[last, ['Hydro', 'Wind', 'Solar', 'Bioenergy and other']].sum())} of the EU's electricity in {last}. Since 2021, solar
power has grown by {cp['diff']['Solar']:.0f} TWh while coal fell by {-cp['diff']['Coal']:.0f} TWh.

![How EU electricity changed]({cp['water'].replace('../', '')})"""

    return report, {"tiles": tile_block.replace("{p}", ""), "key-findings": key}


def fill(readme: str, name: str, block: str) -> str:
    start, end = f"<!-- {name}:start -->", f"<!-- {name}:end -->"
    before, rest = readme.split(start)
    _, after = rest.split(end)
    return f"{before}{start}\n{block}\n{end}{after}"


def main() -> None:
    random.seed(2026)  # bezel-charts gives gradients random ids; a fixed seed draws identical files every time
    d = load()
    report, blocks = write(d)
    REPORT.write_text(report, encoding="utf-8")
    if README.exists():
        text = README.read_text(encoding="utf-8")
        for name, block in blocks.items():
            text = fill(text, name, block)
        README.write_text(text, encoding="utf-8")
    print(f"Wrote {REPORT.relative_to(ROOT)} and {len(list(CHARTS.glob('*.svg')))} charts")


if __name__ == "__main__":
    main()
