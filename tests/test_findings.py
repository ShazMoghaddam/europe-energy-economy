"""Checks that the data is complete and the report says nothing silly.

Run from the repository root with `pytest`. The refresh workflow runs these before opening a pull request,
so a broken download or an odd release never reaches the README unnoticed.
"""

import csv
import json
import re
from pathlib import Path
from urllib.parse import unquote

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CODES = {"keep_default_na": False, "na_values": [""]}  # Eurostat's code for Namibia is NA


@pytest.fixture(scope="module")
def report() -> str:
    return (ROOT / "findings" / "README.md").read_text(encoding="utf-8")


def test_every_data_file_is_listed_in_sources():
    files = json.loads((DATA / "sources.json").read_text(encoding="utf-8"))["files"]
    downloaded = {"energy_mix.csv", "household_prices.csv", "gas_imports.csv", "gas_imports_by_country.csv",
                  "gas_consumption.csv", "world_prices.csv", "brent_daily.csv"}
    assert downloaded <= set(files)
    for name in downloaded:
        assert (DATA / name).exists(), name


def test_prices_are_recent_and_sensible():
    prices = pd.read_csv(DATA / "world_prices.csv").set_index("month")
    assert prices.index.is_monotonic_increasing and prices.index.is_unique
    last = pd.Timestamp(prices["brent_usd_per_barrel"].dropna().index[-1] + "-01")
    assert last >= pd.Timestamp(json.loads((DATA / "sources.json").read_text())["fetched"][:7] + "-01") - pd.DateOffset(months=4)
    assert prices["brent_usd_per_barrel"].dropna().between(10, 250).all()
    assert prices["eu_gas_usd_per_mmbtu"].dropna().between(1, 120).all()
    daily = pd.read_csv(DATA / "brent_daily.csv")
    assert daily["brent_usd_per_barrel"].between(5, 300).all()


def test_household_prices_are_per_kwh():
    hh = pd.read_csv(DATA / "household_prices.csv", **CODES)
    assert set(hh["fuel"]) == {"electricity", "gas"}
    # Euros per kWh: a few cents to well under a euro. A mix-up with GJ or MWh would be far outside this.
    assert hh["eur_per_kwh"].dropna().between(0.0, 1.0).all()
    eu = hh[hh["geo"] == "EU27_2020"]
    assert eu["eur_per_kwh"].notna().sum() >= 30


def test_gas_figures_add_up():
    imp = pd.read_csv(DATA / "gas_imports_by_country.csv", **CODES)
    both = imp.dropna(subset=["imports_total_mio_m3", "imports_from_russia_mio_m3"])
    # Russia can't supply more than all imports, give or take rounding
    assert (both["imports_from_russia_mio_m3"] <= both["imports_total_mio_m3"] * 1.001 + 1).all()
    eu = both[both["geo"] == "EU27_2020"].set_index("year")
    assert eu["imports_total_mio_m3"].between(200_000, 600_000).all()
    use = pd.read_csv(DATA / "gas_consumption.csv", **CODES)
    eu_use = use[use["geo"] == "EU27_2020"]["mio_m3"]
    assert eu_use.between(10_000, 70_000).all()  # a month of EU gas use, in million cubic metres


def test_energy_mix_shares_add_up():
    mix = pd.read_csv(DATA / "energy_mix.csv")
    eu = mix[mix["country"] == "European Union (27)"].dropna(subset=["renewables_share_elec", "fossil_share_elec"])
    total = eu["renewables_share_elec"] + eu["fossil_share_elec"] + eu["nuclear_share_elec"]
    assert total.between(99, 101).all()


def test_hand_entered_figures_have_sources():
    with open(DATA / "company_profits.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            assert row["source"].startswith("https://"), row
    with open(DATA / "timeline.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert all(r["source"].startswith("https://") for r in rows)
    assert [r["date"] for r in rows] == sorted(r["date"] for r in rows), "keep the timeline in date order"
    facts = json.loads((DATA / "facts.json").read_text(encoding="utf-8"))
    for name, block in facts.items():
        if isinstance(block, dict):
            assert block.get("source") or block.get("sources"), f"{name} in facts.json has no source"


def test_report_is_fully_filled_in(report):
    assert "{" not in report and "}" not in report, "a placeholder was left unfilled"
    for bad in ("nan", "NaN", "None", "inf", "NaT"):
        assert not re.search(rf"\b{bad}\b", report), f"report contains {bad!r}"


def test_no_em_dashes_anywhere():
    for path in [*ROOT.glob("*.md"), *ROOT.glob("findings/*.md"), *ROOT.glob("challenges/*/*.md")]:
        assert "—" not in path.read_text(encoding="utf-8"), f"em dash in {path.relative_to(ROOT)}"


def test_every_chart_in_the_report_exists(report):
    charts = re.findall(r"\.\./charts/([\w-]+\.svg)", report)
    assert len(charts) >= 20
    for name in charts:
        svg = (ROOT / "charts" / name).read_text(encoding="utf-8")
        assert svg.startswith("<svg") and "No data yet" not in svg, name


def test_readme_generated_blocks_are_filled_in():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for name in ("tiles", "key-findings"):
        block = readme.split(f"<!-- {name}:start -->")[1].split(f"<!-- {name}:end -->")[0]
        assert len(block.strip()) > 100, f"the {name} block in README.md is empty"
        assert "{" not in block and not re.search(r"\b(nan|None|NaT)\b", block), name


MD_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?\s*\)")
HTML_LINK = re.compile(r"""(?:src|href)\s*=\s*["']([^"']+)["']""")


@pytest.mark.parametrize("path", sorted(p.relative_to(ROOT).as_posix() for p in ROOT.rglob("*.md")
                                        if ".pytest_cache" not in p.parts and p.name != "SUBMISSION_TEMPLATE.md"))
def test_every_local_link_works(path):
    text = re.sub(r"```.*?```", "", (ROOT / path).read_text(encoding="utf-8"), flags=re.DOTALL)
    for target in MD_LINK.findall(text) + HTML_LINK.findall(text):
        if re.match(r"^(https?:|mailto:|#)", target):
            continue
        file = unquote(target.split("#")[0])
        assert ((ROOT / path).parent / file).exists(), f"{path} links to {target}, which doesn't exist"
