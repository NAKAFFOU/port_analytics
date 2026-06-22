# src/pipeline/kpi.py
import sqlite3, pandas as pd
from pathlib import Path
from src.pipeline.aggregate import get_occ_direct_costs, get_occ_budgets, get_psl_revenues, get_psl_budgets
from src.pipeline.allocate_phase1 import compute_phase1
from src.pipeline.allocate_phase2 import compute_phase2
DB_PATH = Path('data/port_analytics.db')

def compute_and_store_kpis():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')

    direct   = get_occ_direct_costs(conn)
    budgets  = get_occ_budgets(conn)
    phase1   = compute_phase1(conn)

    # ── OCC indicators (Tier 2) ──
    occ = direct.merge(budgets, on=['centre_code','period_id'], how='left')
    occ = occ.merge(phase1,    on=['centre_code','period_id'], how='left').fillna(0)
    occ['total_occ_cost']     = occ['total_direct_cost'] + occ['allocated_ssc_cost']
    occ['cost_variance_abs']  = occ['total_direct_cost'] - occ['budget_direct']
    occ['cost_variance_pct']  = occ['cost_variance_abs'] / occ['budget_direct'].replace(0,1) * 100
    occ['overhead_share_pct'] = occ['allocated_ssc_cost'] / occ['total_occ_cost'].replace(0,1) * 100
    occ['budget_consumption'] = occ['total_direct_cost'] / occ['budget_direct'].replace(0,1)

    conn.execute('DELETE FROM occ_indicators')
    occ[['centre_code','period_id','total_direct_cost','allocated_ssc_cost',
         'total_occ_cost','budget_direct','cost_variance_abs','cost_variance_pct',
         'overhead_share_pct','budget_consumption']].to_sql('occ_indicators', conn, if_exists='append', index=False)

    # ── PSL indicators (Tier 3 — primary executive output) ──
    phase2    = compute_phase2(conn, occ)
    revenues  = get_psl_revenues(conn)
    revbud    = get_psl_budgets(conn)
    psl = phase2.merge(revenues, on=['service_code','period_id'], how='left')
    psl = psl.merge(revbud,      on=['service_code','period_id'], how='left').fillna(0)
    psl['service_net_position']  = psl['actual_revenue'] - psl['total_attributed_cost']
    psl['cost_recovery_ratio']   = psl['actual_revenue'] / psl['total_attributed_cost'].replace(0,1)
    psl['revenue_variance_pct']  = (psl['actual_revenue'] - psl['budgeted_revenue']) / psl['budgeted_revenue'].replace(0,1) * 100
    psl['budget_consumption']    = psl['actual_revenue'] / psl['budgeted_revenue'].replace(0,1)
    psl['cost_efficiency_index'] = psl['total_attributed_cost'] / psl['budgeted_revenue'].replace(0,1)

    conn.execute('DELETE FROM psl_indicators')
    psl[['service_code','period_id','total_attributed_cost','actual_revenue',
         'budgeted_revenue','service_net_position','cost_recovery_ratio',
         'revenue_variance_pct','cost_efficiency_index','budget_consumption']].to_sql('psl_indicators', conn, if_exists='append', index=False)

    conn.commit()
    conn.close()
    print(f'KPIs stored — OCC: {len(occ)} rows | PSL: {len(psl)} rows')
