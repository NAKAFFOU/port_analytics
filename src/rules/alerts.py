# src/rules/alerts.py
import sqlite3, pandas as pd
from pathlib import Path
from datetime import datetime
DB_PATH = Path('data/port_analytics.db')

def generate_alerts():
    conn = sqlite3.connect(DB_PATH)
    occ  = pd.read_sql_query('SELECT * FROM occ_indicators', conn)
    psl  = pd.read_sql_query('SELECT * FROM psl_indicators', conn)
    thresh_df = pd.read_sql_query('SELECT * FROM alert_thresholds', conn)
    thresh = {r['rule_name']: r for _, r in thresh_df.iterrows()}
    ts = datetime.now().isoformat()
    alerts = []

    # ── OCC rules ──
    for _, row in occ.iterrows():
        c, p = row['centre_code'], row['period_id']
        if row['cost_variance_abs'] > thresh['cost_overrun']['threshold_val']:
            alerts.append(('OCC',c,p,'cost_overrun',row['cost_variance_abs'],
                thresh['cost_overrun']['threshold_val'],thresh['cost_overrun']['severity'],
                thresh['cost_overrun']['description'],ts))
        if row['cost_variance_pct'] > thresh['material_variance']['threshold_val']:
            alerts.append(('OCC',c,p,'material_variance',row['cost_variance_pct'],
                thresh['material_variance']['threshold_val'],thresh['material_variance']['severity'],
                thresh['material_variance']['description'],ts))
        if row['budget_consumption'] > thresh['budget_ahead']['threshold_val']:
            alerts.append(('OCC',c,p,'budget_ahead',row['budget_consumption'],
                thresh['budget_ahead']['threshold_val'],thresh['budget_ahead']['severity'],
                thresh['budget_ahead']['description'],ts))
        if (row['overhead_share_pct'] or 0) > thresh['high_overhead']['threshold_val']:
            alerts.append(('OCC',c,p,'high_overhead',row['overhead_share_pct'],
                thresh['high_overhead']['threshold_val'],thresh['high_overhead']['severity'],
                thresh['high_overhead']['description'],ts))

    # ── PSL rules ──
    for _, row in psl.iterrows():
        s, p = row['service_code'], row['period_id']
        if row['revenue_variance_pct'] < thresh['revenue_shortfall']['threshold_val']:
            alerts.append(('PSL',s,p,'revenue_shortfall',row['revenue_variance_pct'],
                thresh['revenue_shortfall']['threshold_val'],thresh['revenue_shortfall']['severity'],
                thresh['revenue_shortfall']['description'],ts))
        if row['cost_recovery_ratio'] < thresh['low_cost_recovery']['threshold_val']:
            alerts.append(('PSL',s,p,'low_cost_recovery',row['cost_recovery_ratio'],
                thresh['low_cost_recovery']['threshold_val'],thresh['low_cost_recovery']['severity'],
                thresh['low_cost_recovery']['description'],ts))
        if row['cost_recovery_ratio'] < thresh['critical_deficit']['threshold_val']:
            alerts.append(('PSL',s,p,'critical_deficit',row['cost_recovery_ratio'],
                thresh['critical_deficit']['threshold_val'],thresh['critical_deficit']['severity'],
                thresh['critical_deficit']['description'],ts))

    conn.execute('DELETE FROM decision_alerts')
    conn.executemany('''INSERT INTO decision_alerts
        (entity_type,entity_code,period_id,rule_name,indicator_value,
         threshold_value,severity,description,generated_at) VALUES(?,?,?,?,?,?,?,?,?)''', alerts)
    conn.commit()
    conn.close()
    print(f'{len(alerts)} alerts generated.')
    return len(alerts)
