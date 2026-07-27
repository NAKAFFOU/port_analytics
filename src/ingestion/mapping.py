from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path

from src.common.config import project_path
from src.db.schema import connect


def _clean(value: str | None, default: str = "") -> str:
    return (value or default).strip()


def load_mapping_files(profile: dict) -> dict[str, int]:
    mappings = profile["mappings"]
    counts = {
        "cost_centres": _load_cost_centres(project_path(mappings["cost_centres"])),
        "accounts": _load_accounts(project_path(mappings["accounts"])),
        "services": _load_services(project_path(mappings["services"])),
    }
    return counts


def _load_cost_centres(path: Path) -> int:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["source_system"], row["company_code"], row["source_business_unit"], row["target_code"], _clean(row.get("valid_from")) or None, _clean(row.get("valid_to")) or None))
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO source_cost_centre_mapping(source_system,company_code,source_business_unit,target_code,valid_from,valid_to)
            VALUES(?,?,?,?,?,?)
            ON CONFLICT(source_system,company_code,source_business_unit,valid_from)
            DO UPDATE SET target_code=excluded.target_code,valid_to=excluded.valid_to
            """,
            rows,
        )
    return len(rows)


def _load_accounts(path: Path) -> int:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["source_system"], row["company_code"], row["object_account"], _clean(row.get("subsidiary"), "*") or "*", row["target_category"], row["target_nature"].upper(), float(row.get("sign_multiplier") or 1), _clean(row.get("valid_from")) or None, _clean(row.get("valid_to")) or None))
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO source_account_mapping(source_system,company_code,object_account,subsidiary,target_category,target_nature,sign_multiplier,valid_from,valid_to)
            VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(source_system,company_code,object_account,subsidiary,valid_from)
            DO UPDATE SET target_category=excluded.target_category,target_nature=excluded.target_nature,
                          sign_multiplier=excluded.sign_multiplier,valid_to=excluded.valid_to
            """,
            rows,
        )
    return len(rows)


def _load_services(path: Path) -> int:
    rows = []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["source_system"], row["company_code"], _clean(row.get("business_unit"), "*") or "*", row["object_account"], _clean(row.get("subsidiary"), "*") or "*", row["target_service_code"], _clean(row.get("valid_from")) or None, _clean(row.get("valid_to")) or None))
    with connect() as conn:
        conn.executemany(
            """
            INSERT INTO source_service_mapping(source_system,company_code,business_unit,object_account,subsidiary,target_service_code,valid_from,valid_to)
            VALUES(?,?,?,?,?,?,?,?)
            ON CONFLICT(source_system,company_code,business_unit,object_account,subsidiary,valid_from)
            DO UPDATE SET target_service_code=excluded.target_service_code,valid_to=excluded.valid_to
            """,
            rows,
        )
    return len(rows)


def _valid_on(row, transaction_date: str) -> bool:
    current = date.fromisoformat(transaction_date)
    valid_from = date.fromisoformat(row["valid_from"]) if row["valid_from"] else date.min
    valid_to = date.fromisoformat(row["valid_to"]) if row["valid_to"] else date.max
    return valid_from <= current <= valid_to


def find_cost_centre(source_system: str, company: str, business_unit: str, transaction_date: str):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_cost_centre_mapping
            WHERE source_system=? AND company_code IN (?, '*') AND source_business_unit=?
            ORDER BY CASE WHEN company_code=? THEN 0 ELSE 1 END, valid_from DESC
            """,
            (source_system, company, business_unit, company),
        ).fetchall()
    return next((row for row in rows if _valid_on(row, transaction_date)), None)


def find_account(source_system: str, company: str, account: str, subsidiary: str, transaction_date: str):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_account_mapping
            WHERE source_system=? AND company_code IN (?, '*') AND object_account=? AND subsidiary IN (?, '*')
            ORDER BY CASE WHEN company_code=? THEN 0 ELSE 1 END,
                     CASE WHEN subsidiary=? THEN 0 ELSE 1 END,
                     valid_from DESC
            """,
            (source_system, company, account, subsidiary, company, subsidiary),
        ).fetchall()
    return next((row for row in rows if _valid_on(row, transaction_date)), None)


def find_service(source_system: str, company: str, business_unit: str, account: str, subsidiary: str, transaction_date: str):
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM source_service_mapping
            WHERE source_system=? AND company_code IN (?, '*')
              AND business_unit IN (?, '*') AND object_account=? AND subsidiary IN (?, '*')
            ORDER BY CASE WHEN company_code=? THEN 0 ELSE 1 END,
                     CASE WHEN business_unit=? THEN 0 ELSE 1 END,
                     CASE WHEN subsidiary=? THEN 0 ELSE 1 END,
                     valid_from DESC
            """,
            (source_system, company, business_unit, account, subsidiary, company, business_unit, subsidiary),
        ).fetchall()
    return next((row for row in rows if _valid_on(row, transaction_date)), None)
