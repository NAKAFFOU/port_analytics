# src/db/seed.py
import sqlite3, random
from pathlib import Path
DB_PATH = Path('data/port_analytics.db')
random.seed(42)  # reproducibility

COST_CENTRES = [
    # Tier 1 — Shared Service Centres
    ('SSC-ADM','General Administration',          'SSC','SUPPORT',     None),
    ('SSC-IT', 'Information Technology & Systems','SSC','SUPPORT',     None),
    ('SSC-FAC','Facilities & Maintenance',        'SSC','SUPPORT',     None),
    # Tier 2 — Operational Cost Centres
    ('OCC-NAV',  'Marine & Navigation Operations',  'OCC','OPERATIONAL',None),
    ('OCC-CARGO','Cargo Handling & Terminal',        'OCC','OPERATIONAL',None),
    ('OCC-INFRA','Port Infrastructure & Engineering','OCC','OPERATIONAL',None),
    ('OCC-SEC',  'Port Security & Safety',           'OCC','OPERATIONAL',None),
    ('OCC-COMM', 'Commercial & Port Domain',         'OCC','OPERATIONAL',None),
]

ACCOUNT_CATEGORIES = [
    ('AC-PAY',  'Payroll & Staff Costs',   'DIRECT_COST'),
    ('AC-EQUIP','Equipment & Assets',      'DIRECT_COST'),
    ('AC-ENRG', 'Energy & Utilities',      'DIRECT_COST'),
    ('AC-OPS',  'Operational Supplies',    'DIRECT_COST'),
    ('AC-IADM', 'Administration Overhead', 'INDIRECT_COST'),
    ('AC-IMNT', 'Maintenance Overhead',    'INDIRECT_COST'),
    ('AC-ISEC', 'Security Overhead',       'INDIRECT_COST'),
    ('AC-IIT',  'IT Overhead',             'INDIRECT_COST'),
    ('AC-IFAC', 'Facilities Overhead',     'INDIRECT_COST'),
    ('RV-DUES', 'Port Dues & Vessel Fees', 'REVENUE'),
    ('RV-CARGO','Cargo Handling Fees',     'REVENUE'),
    ('RV-MISC', 'Ancillary Revenue',       'REVENUE'),
]

SERVICE_LINES = [
    ('PSL-PIL',  'Pilotage Services',         'Port dues — pilotage',  'Vessel calls'),
    ('PSL-TOW',  'Towage Services',           'Port dues — towage',    'Vessel calls'),
    ('PSL-CARGO','Cargo Handling Services',   'Cargo handling fees',   'Cargo throughput (tonnes)'),
    ('PSL-NACC', 'Nautical Access & Channel', 'Port dues — vessel',    'Vessel gross tonnage'),
    ('PSL-STOR', 'Storage & Yard Services',   'Storage fees',          'Tonne-days in storage'),
    ('PSL-DOM',  'Port Domain Concessions',   'Concession & rental',   'Leased area (m2)'),
]

def gen_periods():
    labels = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
    return [(f'2025-{m:02d}',2025,m,f'{labels[m-1]} 2025',1 if m<7 else 0) for m in range(1,13)]

ALLOC_PHASE1 = [
    ('SSC-ADM','OCC-NAV',  'DRV-HEAD',25.0),('SSC-ADM','OCC-CARGO','DRV-HEAD',30.0),
    ('SSC-ADM','OCC-INFRA','DRV-HEAD',20.0),('SSC-ADM','OCC-SEC',  'DRV-HEAD',18.0),('SSC-ADM','OCC-COMM','DRV-HEAD', 7.0),
    ('SSC-IT', 'OCC-NAV',  'DRV-OPEX',20.0),('SSC-IT', 'OCC-CARGO','DRV-OPEX',35.0),
    ('SSC-IT', 'OCC-INFRA','DRV-OPEX',22.0),('SSC-IT', 'OCC-SEC',  'DRV-OPEX',15.0),('SSC-IT', 'OCC-COMM','DRV-OPEX', 8.0),
    ('SSC-FAC','OCC-NAV',  'DRV-OPEX',18.0),('SSC-FAC','OCC-CARGO','DRV-OPEX',32.0),
    ('SSC-FAC','OCC-INFRA','DRV-OPEX',28.0),('SSC-FAC','OCC-SEC',  'DRV-OPEX',16.0),('SSC-FAC','OCC-COMM','DRV-OPEX', 6.0),
]

ALLOC_PHASE2 = [
    ('OCC-NAV',  'PSL-PIL',  'DRV-CALL',35.0),('OCC-NAV',  'PSL-TOW',  'DRV-CALL',30.0),
    ('OCC-NAV',  'PSL-CARGO','DRV-CALL',15.0),('OCC-NAV',  'PSL-NACC', 'DRV-CALL',20.0),
    ('OCC-CARGO','PSL-TOW',  'DRV-VOL', 5.0), ('OCC-CARGO','PSL-CARGO','DRV-VOL', 60.0),
    ('OCC-CARGO','PSL-STOR', 'DRV-VOL', 30.0),('OCC-CARGO','PSL-DOM',  'DRV-VOL',  5.0),
    ('OCC-INFRA','PSL-PIL',  'DRV-OPEX',10.0),('OCC-INFRA','PSL-TOW',  'DRV-OPEX',10.0),
    ('OCC-INFRA','PSL-CARGO','DRV-OPEX',20.0),('OCC-INFRA','PSL-NACC', 'DRV-OPEX',40.0),
    ('OCC-INFRA','PSL-STOR', 'DRV-OPEX',15.0),('OCC-INFRA','PSL-DOM',  'DRV-OPEX', 5.0),
    ('OCC-SEC',  'PSL-PIL',  'DRV-HEAD',15.0),('OCC-SEC',  'PSL-TOW',  'DRV-HEAD',10.0),
    ('OCC-SEC',  'PSL-CARGO','DRV-HEAD',30.0),('OCC-SEC',  'PSL-NACC', 'DRV-HEAD',10.0),
    ('OCC-SEC',  'PSL-STOR', 'DRV-HEAD',20.0),('OCC-SEC',  'PSL-DOM',  'DRV-HEAD',15.0),
    ('OCC-COMM', 'PSL-CARGO','DRV-OPEX',10.0),('OCC-COMM', 'PSL-NACC', 'DRV-OPEX', 5.0),
    ('OCC-COMM', 'PSL-STOR', 'DRV-OPEX',10.0),('OCC-COMM', 'PSL-DOM',  'DRV-OPEX',75.0),
]

ALERT_THRESHOLDS = [
    ('cost_overrun',      'cost_variance_abs',    0.0, 'WARNING',        'Expenditure above budget'),
    ('material_variance', 'cost_variance_pct',   10.0, 'PRIORITY_REVIEW','Cost variance exceeds 10% of budget'),
    ('revenue_shortfall', 'revenue_variance_pct',-5.0, 'WARNING',        'Revenue more than 5% below budget'),
    ('low_cost_recovery', 'cost_recovery_ratio',  0.85,'PRIORITY_REVIEW','Cost recovery ratio below 85%'),
    ('critical_deficit',  'cost_recovery_ratio',  0.70,'CRITICAL',       'Service in critical deficit (< 70% recovery)'),
    ('budget_ahead',      'budget_consumption',   1.15,'WARNING',        'Budget consumption 15% ahead of time-adjusted plan'),
    ('high_overhead',     'overhead_share_pct',  45.0, 'WARNING',        'Overhead allocation exceeds 45% of total OCC cost'),
    ('data_quality',      'missing_kpi',          0.0, 'DATA_QUALITY',   'Required KPI value is missing or zero'),
]

DECISION_SUPPORT_ACTIONS = [
    ('cost_overrun',     'Review expenditure commitments. Prepare variance explanation for Finance Controller. Assess whether overrun is one-off or structural.', 'Finance Controller notified', 'Monitor', '5 working days'),
    ('material_variance','Investigate account category driving the variance. Request written explanation from Operational Manager. Reassess year-end forecast.', 'Finance Director informed; Operational Manager must respond', 'Investigate', '3 working days'),
    ('revenue_shortfall','Assess whether shortfall is demand-driven, pricing-related, or a data error. Review throughput data for the period.', 'Commercial Manager alerted; Finance Director copied', 'Monitor', '5 working days'),
    ('low_cost_recovery','Review pricing structure for the service. Confirm allocation rules are correct. Assess whether recovery level is acceptable given public mandate.', 'Finance Director informed; Board summary if < 90% for 3 months', 'Review', '10 working days'),
    ('critical_deficit', 'ESCALATE IMMEDIATELY to Port Director and Finance Director. Prepare service cost review. Options: increase tariffs, reduce cost, or approve as explicit public subsidy.', 'Port Director immediate notification; Board agenda if persists beyond 2 months', 'Escalate', 'Same day'),
    ('budget_ahead',     'Project full-year expenditure. If overshoot confirmed, initiate budget review meeting. Consider budget transfer between cost centres.', 'Finance Controller initiates review meeting', 'Monitor', '5 working days'),
    ('high_overhead',    'Review efficiency of the Shared Service Centre(s) allocating to this unit. Assess whether allocation percentages reflect actual consumption.', 'Finance Director reviews SSC efficiency annually', 'Review', 'Next quarterly SSC review'),
    ('data_quality',     'Identify missing source transaction or budget entry. Correct data and re-run pipeline. Document issue in audit log.', 'Finance Controller informed if affects closed period', 'Fix', '2 working days'),
]

KPI_DEFINITIONS = [
    ('KPI-01','Service Net Position','Revenue - Attributed Cost','Positive=surplus; Negative=deficit','Executive: assess financial viability of each service','Net position < £0','ALT-05'),
    ('KPI-02','Cost Recovery Ratio','Revenue / Attributed Cost','1.0=full cost recovery; <1.0=net subsidy','Exec/Finance: assess subsidy level and pricing policy','< 0.85','ALT-04'),
    ('KPI-03','Cost Variance (£)','Actual Cost - Budget Cost','Positive=overrun; Negative=underspend','Finance Controller: monitor budget adherence','> £0','ALT-01'),
    ('KPI-04','Cost Variance (%)','(Actual-Budget)/Budget*100','Normalised variance for cross-centre comparison','Finance Manager: prioritise by materiality','> +10%','ALT-02'),
    ('KPI-05','Revenue Variance (%)','(Actual Rev-Budget Rev)/Budget*100','Negative=income below plan','Commercial Manager: assess income performance','< -5%','ALT-03'),
    ('KPI-06','Budget Consumption Rate','Actual YTD/(Budget*Months/12)','Values>1.0 = spending ahead of plan profile','Finance Controller: detect in-year budget drift','> 1.15','ALT-06'),
    ('KPI-07','Overhead Allocation Share','Allocated SSC/Total OCC Cost*100','High values = heavy overhead burden','Finance: assess SSC efficiency; Ops: understand true cost','> 45%','ALT-07'),
    ('KPI-08','Top Cost Category Share','Largest Category/Total Direct*100','High concentration = limited cost flexibility','Finance: assess cost structure resilience','> 60% (secondary)','None'),
    ('KPI-09','Cost Efficiency Index','Attributed Cost/Activity Volume','Rising=declining productivity or cost inflation','Operations: track unit cost trend; Executive: benchmark','Trend only','None'),
]

BASE_BUDGETS_GBP = {
    'SSC-ADM':  {'AC-PAY':185000,'AC-EQUIP':12000,'AC-ENRG':8000, 'AC-OPS':22000},
    'SSC-IT':   {'AC-PAY':120000,'AC-EQUIP':45000,'AC-ENRG':18000,'AC-OPS':15000},
    'SSC-FAC':  {'AC-PAY':95000, 'AC-EQUIP':38000,'AC-ENRG':28000,'AC-OPS':12000},
    'OCC-NAV':  {'AC-PAY':310000,'AC-EQUIP':85000,'AC-ENRG':92000,'AC-OPS':45000},
    'OCC-CARGO':{'AC-PAY':420000,'AC-EQUIP':180000,'AC-ENRG':145000,'AC-OPS':88000},
    'OCC-INFRA':{'AC-PAY':195000,'AC-EQUIP':95000,'AC-ENRG':48000,'AC-OPS':35000},
    'OCC-SEC':  {'AC-PAY':245000,'AC-EQUIP':32000,'AC-ENRG':22000,'AC-OPS':28000},
    'OCC-COMM': {'AC-PAY':88000, 'AC-EQUIP':18000,'AC-ENRG':9000, 'AC-OPS':32000},
}

BASE_SERVICE_BUDGETS_GBP = {
    'PSL-PIL':480000,'PSL-TOW':360000,'PSL-CARGO':1200000,
    'PSL-NACC':650000,'PSL-STOR':420000,'PSL-DOM':280000,
}

def seed_database():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA foreign_keys = ON')
    conn.executemany('INSERT OR IGNORE INTO cost_centres VALUES(?,?,?,?,?)', COST_CENTRES)
    conn.executemany('INSERT OR IGNORE INTO account_categories VALUES(?,?,?)', ACCOUNT_CATEGORIES)
    conn.executemany('INSERT OR IGNORE INTO service_lines VALUES(?,?,?,?)', SERVICE_LINES)
    conn.executemany('INSERT OR IGNORE INTO reporting_periods VALUES(?,?,?,?,?)', gen_periods())
    conn.executemany('INSERT OR IGNORE INTO alert_thresholds(rule_name,indicator,threshold_val,severity,description) VALUES(?,?,?,?,?)', ALERT_THRESHOLDS)
    conn.executemany('INSERT OR IGNORE INTO allocation_rules_phase1(source_ssc,destination_occ,driver_code,allocation_pct) VALUES(?,?,?,?)', ALLOC_PHASE1)
    conn.executemany('INSERT OR IGNORE INTO allocation_rules_phase2(source_occ,destination_psl,driver_code,allocation_pct) VALUES(?,?,?,?)', ALLOC_PHASE2)
    conn.executemany('INSERT OR IGNORE INTO decision_support_actions VALUES(?,?,?,?,?)', DECISION_SUPPORT_ACTIONS)
    conn.executemany('INSERT OR IGNORE INTO kpi_definitions VALUES(?,?,?,?,?,?,?)', KPI_DEFINITIONS)

    # Monthly cost budgets (GBP) with seasonal factor
    for centre, cats in BASE_BUDGETS_GBP.items():
        for m in range(1,13):
            pid = f'2025-{m:02d}'
            season = 1.15 if m in (1,2,7,8) else (0.90 if m in (4,5,6) else 1.0)
            for cat, annual in cats.items():
                conn.execute('INSERT OR IGNORE INTO budgets(centre_code,category_code,period_id,amount) VALUES(?,?,?,?)',
                    (centre, cat, pid, round((annual/12)*season, 2)))

    # Monthly service revenue budgets (GBP)
    for svc, annual in BASE_SERVICE_BUDGETS_GBP.items():
        for m in range(1,13):
            pid = f'2025-{m:02d}'
            season = 1.20 if m in (1,2,7,8) else (0.88 if m in (4,5,6) else 1.0)
            conn.execute('INSERT OR IGNORE INTO service_budgets(service_code,period_id,budgeted_revenue) VALUES(?,?,?)',
                (svc, pid, round((annual/12)*season, 2)))

    # Actual cost transactions with structured anomalies
    for centre in BASE_BUDGETS_GBP:
        for m in range(1,13):
            pid = f'2025-{m:02d}'
            for cat in BASE_BUDGETS_GBP[centre]:
                brow = conn.execute('SELECT amount FROM budgets WHERE centre_code=? AND category_code=? AND period_id=?',(centre,cat,pid)).fetchone()
                if not brow: continue
                factor = random.uniform(0.95,1.10)
                # ALT-02: OCC-CARGO energy overrun Jul-Aug
                if centre=='OCC-CARGO' and cat=='AC-ENRG' and m in (7,8): factor=1.28
                # ALT-06: SSC-ADM budget ahead Q3
                if centre=='SSC-ADM' and m in (7,8,9): factor=1.19
                # ALT-07: OCC-SEC structurally higher costs
                if centre=='OCC-SEC': factor=random.uniform(1.02,1.08)
                conn.execute('INSERT INTO actual_transactions(centre_code,category_code,period_id,amount,description) VALUES(?,?,?,?,?)',
                    (centre,cat,pid,round(brow[0]*factor,2),f'{centre} {cat} {pid}'))

    # Actual revenue transactions with structured anomalies
    for svc in BASE_SERVICE_BUDGETS_GBP:
        for m in range(1,13):
            pid = f'2025-{m:02d}'
            brow = conn.execute('SELECT budgeted_revenue FROM service_budgets WHERE service_code=? AND period_id=?',(svc,pid)).fetchone()
            if not brow: continue
            factor = random.uniform(0.92,1.08)
            # ALT-03: PSL-NACC revenue shortfall Mar
            if svc=='PSL-NACC' and m==3: factor=0.87
            # ALT-05: PSL-PIL critical deficit Nov
            if svc=='PSL-PIL' and m==11: factor=0.91
            # ALT-04: PSL-STOR low recovery Sep
            if svc=='PSL-STOR' and m==9: factor=0.85
            conn.execute('INSERT INTO revenue_transactions(service_code,period_id,amount,description) VALUES(?,?,?,?)',
                (svc,pid,round(brow[0]*factor,2),f'{svc} revenue {pid}'))

    conn.commit()
    conn.close()
    print('Database seeded successfully (GBP).')

if __name__ == '__main__':
    seed_database()
