from __future__ import annotations

import logging
from datetime import date

from src.adapters.jde_oracle import JDEOracleAdapter
from src.common.config import get_settings, load_yaml
from src.ingestion.loader import complete_batch, fail_batch, load_accounting_staging, start_batch
from src.ingestion.mapping import load_mapping_files
from src.ingestion.transform import transform_batch_to_core
from src.ingestion.validator import validate_accounting_frame

LOGGER = logging.getLogger(__name__)


def run_jde_ingestion(date_from: date, date_to: date) -> str:
    settings = get_settings()
    profile_path = settings["source"]["active_profile"]
    profile = load_yaml(profile_path)
    adapter = JDEOracleAdapter(profile_path)
    source_system = profile["source_system"]
    batch_id = start_batch(source_system, date_from, date_to)

    try:
        mapping_counts = load_mapping_files(profile)
        LOGGER.info("Mappings loaded: %s", mapping_counts)
        frame = adapter.extract_accounting_transactions(date_from, date_to)
        validate_accounting_frame(frame)
        staged = load_accounting_staging(batch_id, source_system, frame)
        loaded, rejected = transform_batch_to_core(batch_id)
        complete_batch(batch_id, len(frame), loaded, rejected)
        LOGGER.info("Batch %s completed: extracted=%d staged=%d loaded=%d rejected=%d", batch_id, len(frame), staged, loaded, rejected)
        return batch_id
    except Exception as exc:
        fail_batch(batch_id, str(exc))
        raise
