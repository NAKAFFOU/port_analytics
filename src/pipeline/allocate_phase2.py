# src/pipeline/allocate_phase2.py
import pandas as pd

def compute_phase2(conn, occ_df):
    '''Phase 2: attribute total OCC costs to PSLs via allocation_rules_phase2.'''
    rules = pd.read_sql_query(
        'SELECT source_occ, destination_psl, allocation_pct FROM allocation_rules_phase2', conn)
    merged = occ_df[['centre_code','period_id','total_occ_cost']].merge(
        rules, left_on='centre_code', right_on='source_occ', how='inner')
    merged['attributed_cost'] = merged['total_occ_cost'] * (merged['allocation_pct'] / 100)
    result = merged.groupby(['destination_psl','period_id'], as_index=False)['attributed_cost'].sum()
    return result.rename(columns={'destination_psl':'service_code','attributed_cost':'total_attributed_cost'})
