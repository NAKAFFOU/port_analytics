from __future__ import annotations

import csv
import uuid
from datetime import date
from pathlib import Path

from src.common.config import base_currency, project_path
from src.currency.converter import CurrencyConverter
from src.db.schema import connect
from src.ingestion.mapping import find_account, find_cost_centre, find_service


def load_budget_csv(path_value: str | Path) -> tuple[int, int]:
    path = project_path(path_value)
    converter = CurrencyConverter()
    cost_count = 0
    revenue_count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("source_row_id"):
                continue
            period_id = row["period_id"]
            rate_date = date.fromisoformat(f"{period_id}-01")
            account_map = find_account(row["source_system"], row["company_code"], row["object_account"], row.get("subsidiary") or "", rate_date.isoformat())
            if account_map is None:
                raise ValueError(f"Unmapped budget account: {row}")
            amount_source = abs(float(row["amount_source"]) * float(account_map["sign_multiplier"]))
            converted = converter.convert(amount_source, row["source_currency"], base_currency(), rate_date)
            if account_map["target_nature"] == "COST":
                centre_map = find_cost_centre(row["source_system"], row["company_code"], row["business_unit"], rate_date.isoformat())
                if centre_map is None:
                    raise ValueError(f"Unmapped budget cost centre: {row}")
                with connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO budgets(source_system,source_row_id,centre_code,category_code,period_id,
                            amount_source,source_currency,fx_rate_to_base,fx_rate_date,amount_base,base_currency)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?)
                        ON CONFLICT(source_system,source_row_id) DO UPDATE SET amount_base=excluded.amount_base,
                            fx_rate_to_base=excluded.fx_rate_to_base,fx_rate_date=excluded.fx_rate_date
                        """,
                        (row["source_system"], row["source_row_id"], centre_map["target_code"], account_map["target_category"], period_id, amount_source, row["source_currency"], converted.rate, converted.rate_date.isoformat(), converted.amount, base_currency()),
                    )
                cost_count += 1
            else:
                service_map = find_service(row["source_system"], row["company_code"], row["business_unit"], row["object_account"], row.get("subsidiary") or "", rate_date.isoformat())
                if service_map is None:
                    raise ValueError(f"Unmapped budget service: {row}")
                with connect() as conn:
                    conn.execute(
                        """
                        INSERT INTO service_budgets(source_system,source_row_id,service_code,period_id,
                            budgeted_revenue_source,source_currency,fx_rate_to_base,fx_rate_date,
                            budgeted_revenue_base,base_currency,budgeted_volume)
                        VALUES(?,?,?,?,?,?,?,?,?,?,NULL)
                        ON CONFLICT(source_system,source_row_id) DO UPDATE SET budgeted_revenue_base=excluded.budgeted_revenue_base,
                            fx_rate_to_base=excluded.fx_rate_to_base,fx_rate_date=excluded.fx_rate_date
                        """,
                        (row["source_system"], row["source_row_id"], service_map["target_service_code"], period_id, amount_source, row["source_currency"], converted.rate, converted.rate_date.isoformat(), converted.amount, base_currency()),
                    )
                revenue_count += 1
    return cost_count, revenue_count


def load_activity_csv(path_value: str | Path) -> int:
    path = project_path(path_value)
    count = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if not row.get("source_row_id"):
                continue
            with connect() as conn:
                conn.execute(
                    """
                    INSERT INTO activity_volumes(source_system,source_row_id,service_code,period_id,volume_units,unit_name)
                    VALUES(?,?,?,?,?,?)
                    ON CONFLICT(source_system,source_row_id) DO UPDATE SET volume_units=excluded.volume_units,unit_name=excluded.unit_name
                    """,
                    (row["source_system"], row["source_row_id"], row["service_code"], row["period_id"], float(row["volume_units"]), row.get("unit_name")),
                )
            count += 1
    return count
