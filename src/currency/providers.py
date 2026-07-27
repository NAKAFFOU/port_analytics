from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path

import requests

from src.common.config import base_currency, project_path
from src.common.errors import PortAnalyticsError
from src.currency.repository import FxRate, FxRateRepository

ECB_LATEST_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
ECB_90_DAY_URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist-90d.xml"


def load_manual_csv(path_value: str | Path) -> int:
    path = project_path(path_value)
    repository = FxRateRepository()
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            repository.upsert(
                FxRate(
                    rate_date=date.fromisoformat(row["rate_date"]),
                    from_currency=row["from_currency"],
                    to_currency=row["to_currency"],
                    rate=float(row["rate"]),
                    provider=row.get("provider") or "MANUAL_CSV",
                    is_estimated=str(row.get("is_estimated", "0")).strip() in {"1", "true", "TRUE"},
                )
            )
            count += 1
    return count


def _parse_ecb_xml(content: bytes) -> list[tuple[date, dict[str, float]]]:
    root = ET.fromstring(content)
    result: list[tuple[date, dict[str, float]]] = []
    for cube_time in root.findall(".//{*}Cube[@time]"):
        rates = {"EUR": 1.0}
        for cube_rate in cube_time.findall("{*}Cube[@currency]"):
            rates[cube_rate.attrib["currency"].upper()] = float(cube_rate.attrib["rate"])
        result.append((date.fromisoformat(cube_time.attrib["time"]), rates))
    return result


def refresh_ecb(use_90_days: bool = True) -> int:
    target_base = base_currency()
    response = requests.get(ECB_90_DAY_URL if use_90_days else ECB_LATEST_URL, timeout=30)
    response.raise_for_status()
    observations = _parse_ecb_xml(response.content)
    repository = FxRateRepository()
    count = 0

    for rate_date, ecb_rates in observations:
        if target_base not in ecb_rates:
            raise PortAnalyticsError(f"ECB data do not contain configured base currency {target_base}")
        base_per_eur = ecb_rates[target_base]
        for currency, units_per_eur in ecb_rates.items():
            rate_to_base = base_per_eur / units_per_eur
            repository.upsert(FxRate(rate_date, currency, target_base, rate_to_base, "ECB", False))
            count += 1
    return count
