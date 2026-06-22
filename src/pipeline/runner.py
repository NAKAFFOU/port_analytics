# src/pipeline/runner.py
from src.pipeline.ingest import validate_referential_integrity
from src.pipeline.kpi import compute_and_store_kpis

def run_full_pipeline():
    print('=== Port Analytics Pipeline ===')
    print('[1/2] Validating...')
    if not validate_referential_integrity():
        print('Pipeline aborted — validation errors.')
        return False
    print('[2/2] Calculating KPIs (Phase 1 + Phase 2 allocation)...')
    compute_and_store_kpis()
    print('Pipeline complete.')
    return True

if __name__ == '__main__':
    run_full_pipeline()
