# src/dashboard/app.py
import streamlit as st
import sqlite3, pandas as pd
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
DB_PATH = Path('data/port_analytics.db')

# Business-friendly label dictionary
LABELS = {
    'SSC-ADM':'General Administration','SSC-IT':'Information Technology & Systems',
    'SSC-FAC':'Facilities & Maintenance','OCC-NAV':'Marine & Navigation Operations',
    'OCC-CARGO':'Cargo Handling & Terminal','OCC-INFRA':'Port Infrastructure & Engineering',
    'OCC-SEC':'Port Security & Safety','OCC-COMM':'Commercial & Port Domain',
    'PSL-PIL':'Pilotage Services','PSL-TOW':'Towage Services',
    'PSL-CARGO':'Cargo Handling Services','PSL-NACC':'Nautical Access & Channel',
    'PSL-STOR':'Storage & Yard Services','PSL-DOM':'Port Domain Concessions',
    'CRITICAL':'⛔ Critical — Immediate Action Required',
    'PRIORITY_REVIEW':'⚠ Priority Review',
    'WARNING':'⚠ Warning — Monitor Closely',
    'DATA_QUALITY':'ℹ Data Quality Issue',
}

st.set_page_config(page_title='Port Analytics', page_icon='⚓', layout='wide')

@st.cache_data(ttl=300)
def load_data():
    conn = sqlite3.connect(DB_PATH)
    occ_kpis = pd.read_sql_query('SELECT * FROM occ_indicators', conn)
    psl_kpis = pd.read_sql_query('SELECT * FROM psl_indicators', conn)
    alerts   = pd.read_sql_query('SELECT * FROM decision_alerts', conn)
    dsa      = pd.read_sql_query('SELECT * FROM decision_support_actions', conn)
    centres  = pd.read_sql_query('SELECT * FROM cost_centres', conn)
    services = pd.read_sql_query('SELECT * FROM service_lines', conn)
    periods  = pd.read_sql_query('SELECT * FROM reporting_periods ORDER BY period_id', conn)
    conn.close()
    return occ_kpis, psl_kpis, alerts, dsa, centres, services, periods

occ_kpis, psl_kpis, alerts, dsa, centres, services, periods = load_data()

# ── GLOBAL SIDEBAR FILTERS ──
st.sidebar.title('Filters')
selected_period = st.sidebar.selectbox('Reporting Period',
    periods['period_id'].tolist(), index=len(periods)-1)
view = st.sidebar.radio('Analysis Level', ['Service Lines (PSL)','Cost Centres (OCC)'])

filt_psl = psl_kpis[psl_kpis['period_id']==selected_period]
filt_occ = occ_kpis[occ_kpis['period_id']==selected_period]
filt_alerts = alerts[alerts['period_id']==selected_period]

# ── PAGE 1: EXECUTIVE OVERVIEW ──
st.title('⚓ Port Analytics — Executive Overview')

total_rev  = filt_psl['actual_revenue'].sum()
total_cost = filt_psl['total_attributed_cost'].sum()
recovery   = total_rev / total_cost if total_cost > 0 else 0

c1,c2,c3,c4 = st.columns(4)
c1.metric('Total Revenue (£)', f'£{total_rev:,.0f}')
c2.metric('Total Attributed Cost (£)', f'£{total_cost:,.0f}')
c3.metric('Portfolio Cost Recovery', f'{recovery:.2f}')
c4.metric('Active Alerts', len(filt_alerts))

import plotly.express as px
filt_psl_lab = filt_psl.copy()
filt_psl_lab['Service Line'] = filt_psl_lab['service_code'].map(LABELS)
fig = px.bar(filt_psl_lab, x='Service Line', y='service_net_position',
    color='service_net_position', color_continuous_scale=['red','orange','green'],
    title='Service Line Net Position (£) — Revenue minus Total Attributed Cost',
    labels={'service_net_position':'Net Position (£)'})
st.plotly_chart(fig, use_container_width=True)

# Priority alert panel
if not filt_alerts.empty:
    st.subheader('Priority Alerts')
    sev_ord = {'CRITICAL':0,'PRIORITY_REVIEW':1,'WARNING':2,'DATA_QUALITY':3}
    al = filt_alerts.copy()
    al['sev_rank'] = al['severity'].map(sev_ord)
    al['Severity Label'] = al['severity'].map(LABELS)
    al['Entity Name'] = al['entity_code'].map(LABELS).fillna(al['entity_code'])
    al = al.sort_values('sev_rank')
    # Merge recommended action from decision_support_actions
    al = al.merge(dsa[['rule_name','recommended_action']], on='rule_name', how='left')
    st.dataframe(al[['entity_type','Entity Name','rule_name','Severity Label',
                      'indicator_value','threshold_value','recommended_action']]
        .rename(columns={'entity_type':'Level','Entity Name':'Entity','rule_name':'Rule',
                         'Severity Label':'Severity','indicator_value':'Value',
                         'threshold_value':'Threshold','recommended_action':'Recommended Action'}),
        use_container_width=True)
