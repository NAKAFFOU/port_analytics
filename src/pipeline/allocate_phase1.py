# src/pipeline/allocate_phase1.py
import pandas as pd

def compute_phase1(conn):
    '''Phase 1: redistribute SSC total costs to OCCs via allocation_rules_phase1.'''
    from src.pipeline.aggregate import get_ssc_total_costs
    ssc = get_ssc_total_costs(conn)
    rules = pd.read_sql_query(
        'SELECT source_ssc, destination_occ, allocation_pct FROM allocation_rules_phase1', conn)
    merged = ssc.merge(rules, left_on='ssc_code', right_on='source_ssc', how='inner')
    merged['allocated_ssc_cost'] = merged['ssc_total_cost'] * (merged['allocation_pct'] / 100)
    result = merged.groupby(['destination_occ','period_id'], as_index=False)['allocated_ssc_cost'].sum()
    return result.rename(columns={'destination_occ': 'centre_code'})
