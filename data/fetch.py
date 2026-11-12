"""Download the European energy data this project uses, straight from the people who publish it.

Run from the repository root:

    python data/fetch.py

It writes these files into data/:

    energy_mix.csv          one row per country and year: how electricity is made and how much
                            gas, oil and coal is used (Our World in Data, from Ember and the Energy Institute)
    world_prices.csv        one row per month: the price of Brent crude oil and of natural gas in Europe
    brent_daily.csv         one row per trading day: the price of Brent crude oil
    household_prices.csv    one row per country and half-year: what households pay for electricity and gas
    gas_imports.csv         one row per month and supplier: where the EU's imported gas comes from
    gas_imports_by_country.csv  one row per country and year: total gas imports and imports from Russia
    gas_consumption.csv     one row per country and month: how much gas each country used
    sources.json            what each file is, where it came from and when it was downloaded

Every source is free and open. Only the Python standard library and pandas are needed.

Each source is downloaded on its own, so if one website is busy the others still save. The raw
downloads are kept in data/raw/ (not committed) in case you want to check a number against the
original.
"""

from __future__ import annotations

import io
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RAW = HERE / "raw"
USER_AGENT = "europe-energy-economy (+https://github.com/ShazMoghaddam/europe-energy-economy)"
START_YEAR = 2010

EUROSTAT = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"
FRED = "https://fred.stlouisfed.org/graph/fredgraph.csv?id="
OWID = "https://raw.githubusercontent.com/owid/energy-data/master/owid-energy-data.csv"
# A mirror of the same EIA Brent series, used only if FRED can't be reached.
EIA_MIRROR = "https://raw.githubusercontent.com/datasets/oil-prices/main/data/"

# The EU as it is now, plus the UK, Norway and a few neighbours that matter for energy.
# Codes are Eurostat's (Greece is EL). Our World in Data uses country names, so both are listed.
COUNTRIES = {
    "EU27_2020": "European Union (27)",
    "AT": "Austria", "BE": "Belgium", "BG": "Bulgaria", "HR": "Croatia", "CY": "Cyprus",
    "CZ": "Czechia", "DK": "Denmark", "EE": "Estonia", "FI": "Finland", "FR": "France",
    "DE": "Germany", "EL": "Greece", "HU": "Hungary", "IE": "Ireland", "IT": "Italy",
    "LV": "Latvia", "LT": "Lithuania", "LU": "Luxembourg", "MT": "Malta", "NL": "Netherlands",
    "PL": "Poland", "PT": "Portugal", "RO": "Romania", "SK": "Slovakia", "SI": "Slovenia",
    "ES": "Spain", "SE": "Sweden",
    "UK": "United Kingdom", "NO": "Norway",
}
OWID_PLACES = list(COUNTRIES.values()) + ["Europe"]

OWID_COLUMNS = [
    "country", "year", "iso_code", "population",
    "electricity_generation", "electricity_demand", "per_capita_electricity", "net_elec_imports",
    "coal_electricity", "gas_electricity", "oil_electricity", "nuclear_electricity", "hydro_electricity",
    "wind_electricity", "solar_electricity", "biofuel_electricity", "other_renewable_exc_biofuel_electricity",
    "renewables_share_elec", "low_carbon_share_elec", "fossil_share_elec", "gas_share_elec", "coal_share_elec",
    "wind_share_elec", "solar_share_elec", "nuclear_share_elec",
    "primary_energy_consumption", "gas_consumption", "oil_consumption", "coal_consumption",
    "renewables_share_energy", "fossil_share_energy", "gas_production", "carbon_intensity_elec",
]


# Downloading ---------------------------------------------------------------------------------

def get(url: str, retries: int = 3) -> bytes:
    """Fetch a URL politely, retrying a couple of times if the site is busy."""
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as resp:
                return resp.read()
        except urllib.error.HTTPError as err:
            if 400 <= err.code < 500 and err.code != 429:  # a bad request won't fix itself
                raise
            if attempt == retries - 1:
                raise
        except Exception:  # noqa: BLE001 - any other network hiccup gets a retry
            if attempt == retries - 1:
                raise
        time.sleep(3 * (attempt + 1))
    raise RuntimeError("unreachable")


def keep_raw(name: str, content: bytes) -> None:
    RAW.mkdir(exist_ok=True)
    (RAW / name).write_bytes(content)


# Eurostat ------------------------------------------------------------------------------------

def jsonstat(js: dict) -> pd.DataFrame:
    """Turn Eurostat's JSON-stat answer into a long table: one column per dimension, plus value and flag."""
    ids, sizes = js["id"], js["size"]
    codes = []
    for dim in ids:
        index = js["dimension"][dim]["category"]["index"]
        codes.append(index if isinstance(index, list) else sorted(index, key=index.get))
    values = js.get("value", {})
    status = js.get("status", {})
    items = values.items() if isinstance(values, dict) else enumerate(values)
    rows = []
    for key, value in items:
        if value is None:
            continue
        pos, place = int(key), []
        for size, cats in zip(reversed(sizes), reversed(codes)):
            place.append(cats[pos % size])
            pos //= size
        flags = status.get(str(key), "") if isinstance(status, dict) else (status[int(key)] or "")
        rows.append({**dict(zip(ids, reversed(place))), "value": float(value), "flag": flags})
    return pd.DataFrame(rows)


def eurostat(code: str, since: str, **filters: str | list[str]) -> tuple[pd.DataFrame, dict]:
    """Download one Eurostat dataset, filtered by dimension.

    If Eurostat rejects a filter (they occasionally rename one), it tries again with fewer filters and the
    table is narrowed down here instead, so a small change on their side doesn't stop the download.
    """
    attempts = [dict(filters, sinceTimePeriod=since), dict(filters), {"geo": filters.get("geo", [])}]
    last_error: Exception | None = None
    for params in attempts:
        query = [("format", "JSON"), ("lang", "EN")]
        for name, value in params.items():
            for v in ([value] if isinstance(value, str) else value):
                query.append((name, v))
        url = f"{EUROSTAT}/{code}?{urllib.parse.urlencode(query)}"
        try:
            content = get(url)
        except urllib.error.HTTPError as err:
            last_error = err
            continue
        keep_raw(f"eurostat_{code}.json", content)
        js = json.loads(content)
        frame = jsonstat(js)
        for name, value in filters.items():
            if name in frame.columns:
                frame = frame[frame[name].isin([value] if isinstance(value, str) else value)]
        meta = {
            "publisher": "Eurostat",
            "dataset": code,
            "title": js.get("label", code),
            "url": f"https://ec.europa.eu/eurostat/databrowser/view/{code}/default/table?lang=en",
            "updated": str(js.get("updated", ""))[:10],
            "licence": "CC BY 4.0, (c) European Union",
        }
        return frame.reset_index(drop=True), meta
    raise RuntimeError(f"Eurostat would not send {code}: {last_error}")


def household_prices() -> tuple[pd.DataFrame, dict]:
    """What a typical household pays per kWh, including all taxes and levies, every half-year since 2010.

    Electricity: band DC, 2,500 to 5,000 kWh a year. Gas: band D2, 20 to 200 GJ a year (about 5,600 to
    56,000 kWh). These are the bands Eurostat uses for its headline figures.
    """
    geo = list(COUNTRIES)
    elec, elec_meta = eurostat("nrg_pc_204", f"{START_YEAR}-S1", geo=geo, nrg_cons="KWH2500-4999",
                               unit="KWH", tax="I_TAX", currency="EUR")
    gas, gas_meta = eurostat("nrg_pc_202", f"{START_YEAR}-S1", geo=geo, nrg_cons="GJ20-199",
                             unit="KWH", tax="I_TAX", currency="EUR")
    frame = pd.concat([
        elec.assign(fuel="electricity")[["geo", "time", "fuel", "value", "flag"]],
        gas.assign(fuel="gas")[["geo", "time", "fuel", "value", "flag"]],
    ])
    frame = frame.rename(columns={"time": "period", "value": "eur_per_kwh"})
    frame["country"] = frame["geo"].map(COUNTRIES)
    frame = frame.sort_values(["fuel", "geo", "period"])
    return frame[["fuel", "geo", "country", "period", "eur_per_kwh", "flag"]].reset_index(drop=True), {
        "electricity": elec_meta, "gas": gas_meta,
        "description": "Household prices including all taxes and levies, euros per kWh. Electricity band DC "
                       "(2,500 to 5,000 kWh a year), gas band D2 (20 to 200 GJ a year). S1 is January to June, "
                       "S2 is July to December.",
    }


def gas_imports() -> tuple[pd.DataFrame, dict]:
    """Where the EU's imported gas comes from, month by month, in million cubic metres."""
    frame, meta = eurostat("nrg_ti_gasm", f"{START_YEAR}-01", geo="EU27_2020", siec="G3000", unit="MIO_M3")
    frame = frame.rename(columns={"time": "month", "value": "mio_m3"})
    frame = frame[["month", "partner", "mio_m3", "flag"]].sort_values(["month", "partner"])
    meta["description"] = "EU27 imports of natural gas by partner country, million cubic metres a month."
    return frame.reset_index(drop=True), meta


def gas_imports_by_country() -> tuple[pd.DataFrame, dict]:
    """Each country's total gas imports and the part that came from Russia, year by year."""
    frame, meta = eurostat("nrg_ti_gas", str(START_YEAR), geo=list(COUNTRIES), siec="G3000",
                           unit="MIO_M3", partner=["TOTAL", "RU"])
    frame = frame.rename(columns={"time": "year", "value": "mio_m3"})
    frame = frame.pivot_table(index=["geo", "year"], columns="partner", values="mio_m3").reset_index()
    frame = frame.rename(columns={"TOTAL": "imports_total_mio_m3", "RU": "imports_from_russia_mio_m3"})
    frame["country"] = frame["geo"].map(COUNTRIES)
    meta["description"] = "Imports of natural gas, total and from Russia, million cubic metres a year."
    return frame[["geo", "country", "year", "imports_total_mio_m3", "imports_from_russia_mio_m3"]], meta


def gas_consumption() -> tuple[pd.DataFrame, dict]:
    """How much gas each country used each month (inland consumption, as observed)."""
    frame, meta = eurostat("nrg_cb_gasm", f"{START_YEAR}-01", geo=list(COUNTRIES), siec="G3000",
                           nrg_bal="IC_OBS", unit="MIO_M3")
    frame = frame.rename(columns={"time": "month", "value": "mio_m3"})
    frame["country"] = frame["geo"].map(COUNTRIES)
    meta["description"] = "Inland consumption of natural gas (observed), million cubic metres a month."
    return frame[["geo", "country", "month", "mio_m3", "flag"]].sort_values(["geo", "month"]).reset_index(drop=True), meta


# Prices from FRED, with a GitHub mirror of the EIA Brent series as a fallback -----------------------

def fred(series_id: str) -> pd.Series:
    content = get(FRED + series_id)
    keep_raw(f"fred_{series_id}.csv", content)
    frame = pd.read_csv(io.BytesIO(content), na_values=".")
    date_col = frame.columns[0]  # "observation_date", or "DATE" in older downloads
    return frame.set_index(pd.to_datetime(frame[date_col]))[series_id].dropna()


def world_prices() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    sources = {}
    try:
        brent = fred("MCOILBRENTEU")
        brent_daily = fred("DCOILBRENTEU")
        sources["brent"] = {"publisher": "U.S. Energy Information Administration, via FRED",
                            "series": "MCOILBRENTEU, DCOILBRENTEU",
                            "url": "https://fred.stlouisfed.org/series/MCOILBRENTEU"}
    except Exception:  # noqa: BLE001
        monthly = pd.read_csv(io.BytesIO(get(EIA_MIRROR + "brent-monthly.csv")))
        daily = pd.read_csv(io.BytesIO(get(EIA_MIRROR + "brent-daily.csv")))
        brent = monthly.set_index(pd.to_datetime(monthly["Date"]))["Price"]
        brent_daily = daily.set_index(pd.to_datetime(daily["Date"]))["Price"]
        sources["brent"] = {"publisher": "U.S. Energy Information Administration, via the datasets/oil-prices mirror",
                            "series": "Europe Brent Spot Price FOB",
                            "url": "https://www.eia.gov/dnav/pet/hist/RBRTEd.htm"}
    gas = fred("PNGASEUUSDM")
    sources["gas"] = {"publisher": "International Monetary Fund, Primary Commodity Prices, via FRED",
                      "series": "PNGASEUUSDM", "url": "https://fred.stlouisfed.org/series/PNGASEUUSDM",
                      "note": "Natural gas, EU (Netherlands TTF), US dollars per million British thermal units"}
    month = lambda s: s.groupby(s.index.strftime("%Y-%m")).mean()  # noqa: E731 - monthly labels
    prices = pd.concat({"brent_usd_per_barrel": month(brent), "eu_gas_usd_per_mmbtu": month(gas)}, axis=1)
    prices = prices[prices.index >= f"{START_YEAR}-01"].round(2)
    prices.index.name = "month"
    daily = brent_daily[brent_daily.index >= f"{START_YEAR}-01-01"].rename("brent_usd_per_barrel").round(2)
    daily.index = daily.index.strftime("%Y-%m-%d")
    daily.index.name = "date"
    return prices.reset_index(), daily.reset_index(), sources


# Our World in Data -------------------------------------------------------------------------------

def energy_mix() -> tuple[pd.DataFrame, dict]:
    content = get(OWID)
    keep_raw("owid-energy-data.csv", content)
    owid = pd.read_csv(io.BytesIO(content))
    frame = owid[owid["country"].isin(OWID_PLACES) & (owid["year"] >= START_YEAR)][OWID_COLUMNS]
    missing = set(OWID_PLACES) - set(frame["country"])
    if missing:
        raise RuntimeError(f"Our World in Data has no rows for {sorted(missing)}")
    return frame.sort_values(["country", "year"]).reset_index(drop=True), {
        "publisher": "Our World in Data, from Ember and the Energy Institute Statistical Review of World Energy",
        "url": "https://github.com/owid/energy-data",
        "licence": "CC BY 4.0",
        "description": "Electricity in terawatt-hours (TWh) and shares in %. Gas, oil, coal and primary energy "
                       "consumption in TWh of primary energy.",
    }


# Putting it together ------------------------------------------------------------------------

JOBS = {
    "energy_mix": (energy_mix, "energy_mix.csv"),
    "household_prices": (household_prices, "household_prices.csv"),
    "gas_imports": (gas_imports, "gas_imports.csv"),
    "gas_imports_by_country": (gas_imports_by_country, "gas_imports_by_country.csv"),
    "gas_consumption": (gas_consumption, "gas_consumption.csv"),
}


def main() -> int:
    manifest_path = HERE / "sources.json"
    old = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    files = old.get("files", {})
    failed = []

    for i, (name, (job, filename)) in enumerate(JOBS.items(), start=1):
        print(f"[{i}/{len(JOBS) + 1}] {filename}")
        try:
            frame, meta = job()
            frame.to_csv(HERE / filename, index=False)
            files[filename] = {**meta, "rows": len(frame)}
            print(f"      saved {len(frame):,} rows")
        except Exception as exc:  # noqa: BLE001 - keep going, report at the end
            failed.append(f"{filename}: {exc}")
            print(f"      FAILED: {exc}")
        time.sleep(0.5)

    print(f"[{len(JOBS) + 1}/{len(JOBS) + 1}] world_prices.csv and brent_daily.csv")
    try:
        prices, daily, meta = world_prices()
        prices.to_csv(HERE / "world_prices.csv", index=False)
        daily.to_csv(HERE / "brent_daily.csv", index=False)
        files["world_prices.csv"] = {**meta, "rows": len(prices), "last": prices["month"].iloc[-1]}
        files["brent_daily.csv"] = {**meta["brent"], "rows": len(daily), "last": daily["date"].iloc[-1]}
        print(f"      saved {len(prices):,} months and {len(daily):,} days")
    except Exception as exc:  # noqa: BLE001
        failed.append(f"world_prices.csv: {exc}")
        print(f"      FAILED: {exc}")

    manifest = {
        "fetched": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "credit": "Sources: Eurostat (CC BY 4.0); Our World in Data, from Ember and the Energy Institute (CC BY 4.0); "
                  "U.S. Energy Information Administration; International Monetary Fund, via FRED.",
        "files": files,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if failed:
        print("\nSome downloads didn't work:\n  " + "\n  ".join(failed))
        print("The files that did download have been saved. Wait a minute and run it again.")
        return 1
    print(f"\nAll done. Everything is in {HERE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
