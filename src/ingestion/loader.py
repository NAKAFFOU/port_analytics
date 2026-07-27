from __future__ import annotations

import uuid
from datetime import date

import pandas as pd

from src.db.schema import connect


def start_batch(source_system: str, date_from: date | None, date_to: date | None) -> str:
    batch_id = str(uuid.uuid4())
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO ingestion_batches(batch_id,source_system,date_from,date_to,status)
            VALUES(?,?,?,?, 'STARTED')
            """,
            (
                batch_id,
                source_system,
                date_from.isoformat() if date_from else None,
                date_to.isoformat() if date_to else None,
            ),
        )
    return batch_id


def complete_batch(batch_id: str, rows_extracted: int, rows_loaded: int, rows_rejected: int) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE ingestion_batches
            SET completed_at=datetime('now'),rows_extracted=?,rows_loaded=?,rows_rejected=?,status='COMPLETED'
            WHERE batch_id=?
            """,
            (rows_extracted, rows_loaded, rows_rejected, batch_id),
        )


def fail_batch(batch_id: str, error_message: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE ingestion_batches
            SET completed_at=datetime('now'),status='FAILED',error_message=?
            WHERE batch_id=?
            """,
            (error_message[:4000], batch_id),
        )


def load_accounting_staging(batch_id: str, source_system: str, frame: pd.DataFrame) -> int:
    if frame.empty:
        return 0
    work = frame.copy()
    work.insert(0, "source_system", source_system)
    work.insert(0, "batch_id", batch_id)
    with connect() as conn:
        work.to_sql("_incoming_accounting", conn, if_exists="replace", index=False)
        conn.execute(
            """
            INSERT OR REPLACE INTO stg_accounting_transactions(
                batch_id,source_system,source_row_id,company_code,document_number,document_type,
                business_unit,object_account,subsidiary,transaction_date,amount_source,
                source_currency,ledger_type,description
            )
            SELECT batch_id,source_system,source_row_id,company_code,document_number,document_type,
                   business_unit,object_account,subsidiary,transaction_date,amount_source,
                   source_currency,ledger_type,description
            FROM _incoming_accounting
            """
        )
        conn.execute("DROP TABLE _incoming_accounting")
    return len(work)


def add_quality_issue(
    batch_id: str,
    source_system: str,
    source_row_id: str,
    issue_type: str,
    description: str,
    severity: str = "ERROR",
) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO data_quality_issues(batch_id,source_system,source_row_id,issue_type,severity,description)
            VALUES(?,?,?,?,?,?)
            """,
            (batch_id, source_system, source_row_id, issue_type, severity, description),
        )
