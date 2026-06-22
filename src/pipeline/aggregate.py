# src/pipeline/aggregate.py
import sqlite3, pandas as pd
from pathlib import Path
DB_PATH = Path('data/port_analytics.db')

def get_occ_direct_costs(conn):
    return pd.read_sql_query('''
        SELECT at.centre_code, at.period_id, SUM(at.amount) AS total_direct_cost
        FROM actual_transactions at
        JOIN cost_centres cc ON at.centre_code=cc.centre_code
        JOIN account_categories ac ON at.category_code=ac.category_code
        WHERE cc.tier='OCC' AND ac.category_type='DIRECT_COST'
        GROUP BY at.centre_code, at.period_id''', conn)

def get_ssc_total_costs(conn):
    return pd.read_sql_query('''
        SELECT at.centre_code AS ssc_code, at.period_id, SUM(at.amount) AS ssc_total_cost
        FROM actual_transactions at
        JOIN cost_centres cc ON at.centre_code=cc.centre_code
        WHERE cc.tier='SSC'
        GROUP BY at.centre_code, at.period_id''', conn)

def get_occ_budgets(conn):
    return pd.read_sql_query('''
        SELECT b.centre_code, b.period_id, SUM(b.amount) AS budget_direct
        FROM budgets b
        JOIN cost_centres cc ON b.centre_code=cc.centre_code
        JOIN account_categories ac ON b.category_code=ac.category_code
        WHERE cc.tier='OCC' AND ac.category_type='DIRECT_COST'
        GROUP BY b.centre_code, b.period_id''', conn)

def get_psl_revenues(conn):
    return pd.read_sql_query('''
        SELECT service_code, period_id, SUM(amount) AS actual_revenue
        FROM revenue_transactions GROUP BY service_code, period_id''', conn)

def get_psl_budgets(conn):
    return pd.read_sql_query('SELECT service_code, period_id, budgeted_revenue FROM service_budgets', conn)
