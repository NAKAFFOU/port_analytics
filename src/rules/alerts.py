from __future__ import annotations

import pandas as pd

from src.db.schema import connect


def generate_alerts() -> int:
    with connect() as conn:
        occ = pd.read_sql_query("SELECT * FROM occ_indicators", conn)
        psl = pd.read_sql_query("SELECT * FROM psl_indicators", conn)
        threshold_frame = pd.read_sql_query(
            "SELECT * FROM alert_thresholds", conn
        )
        thresholds = {
            row["rule_name"]: row
            for _, row in threshold_frame.iterrows()
        }
        alerts: list[tuple] = []

        def append(
            entity_type: str,
            entity_code: str,
            period_id: str,
            rule: str,
            value,
        ) -> None:
            if rule not in thresholds:
                return
            threshold = thresholds[rule]
            alerts.append(
                (
                    entity_type,
                    entity_code,
                    period_id,
                    rule,
                    None if pd.isna(value) else float(value),
                    float(threshold["threshold_val"]),
                    threshold["severity"],
                    threshold["description"],
                )
            )

        for _, row in occ.iterrows():
            if pd.isna(row.get("total_occ_cost")):
                append(
                    "OCC", row["centre_code"], row["period_id"],
                    "data_quality", None,
                )
                continue

            if not pd.isna(row.get("budget_direct")) and row["budget_direct"]:
                if row["cost_variance_abs"] > thresholds["cost_overrun"]["threshold_val"]:
                    append("OCC", row["centre_code"], row["period_id"], "cost_overrun", row["cost_variance_abs"])
                if row["cost_variance_pct"] > thresholds["material_variance"]["threshold_val"]:
                    append("OCC", row["centre_code"], row["period_id"], "material_variance", row["cost_variance_pct"])
                if row["budget_consumption_ytd"] > thresholds["budget_ahead"]["threshold_val"]:
                    append("OCC", row["centre_code"], row["period_id"], "budget_ahead", row["budget_consumption_ytd"])

            if not pd.isna(row.get("overhead_share_pct")):
                if row["overhead_share_pct"] > thresholds["high_overhead"]["threshold_val"]:
                    append("OCC", row["centre_code"], row["period_id"], "high_overhead", row["overhead_share_pct"])

        for _, row in psl.iterrows():
            revenue = row.get("actual_revenue")
            total_cost = row.get("total_attributed_cost")
            if pd.isna(total_cost):
                append("PSL", row["service_code"], row["period_id"], "data_quality", None)
                continue

            if (pd.isna(revenue) or float(revenue) == 0.0) and float(total_cost or 0) > 0:
                append("PSL", row["service_code"], row["period_id"], "missing_revenue", revenue)
            if not pd.isna(row.get("service_net_position")) and row["service_net_position"] < 0:
                append("PSL", row["service_code"], row["period_id"], "service_deficit", row["service_net_position"])
            if not pd.isna(row.get("analytical_margin_pct")) and row["analytical_margin_pct"] < 0:
                append("PSL", row["service_code"], row["period_id"], "negative_margin", row["analytical_margin_pct"])
            if not pd.isna(row.get("cost_recovery_ratio")):
                if row["cost_recovery_ratio"] < thresholds["low_cost_recovery"]["threshold_val"]:
                    append("PSL", row["service_code"], row["period_id"], "low_cost_recovery", row["cost_recovery_ratio"])
                if row["cost_recovery_ratio"] < thresholds["critical_deficit"]["threshold_val"]:
                    append("PSL", row["service_code"], row["period_id"], "critical_deficit", row["cost_recovery_ratio"])

            if float(total_cost or 0) > 0 and not pd.isna(row.get("indirect_allocated_cost")):
                indirect_share = float(row["indirect_allocated_cost"]) / float(total_cost) * 100
                if indirect_share > thresholds["high_indirect_share"]["threshold_val"]:
                    append("PSL", row["service_code"], row["period_id"], "high_indirect_share", indirect_share)

            if not pd.isna(row.get("budgeted_revenue")) and row["budgeted_revenue"]:
                if row["revenue_variance_pct"] < thresholds["revenue_shortfall"]["threshold_val"]:
                    append("PSL", row["service_code"], row["period_id"], "revenue_shortfall", row["revenue_variance_pct"])

        conn.execute("DELETE FROM decision_alerts")
        conn.executemany(
            """INSERT INTO decision_alerts
            (entity_type,entity_code,period_id,rule_name,indicator_value,
             threshold_value,severity,description)
            VALUES(?,?,?,?,?,?,?,?)""",
            alerts,
        )
    return len(alerts)
