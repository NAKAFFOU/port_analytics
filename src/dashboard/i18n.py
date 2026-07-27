TEXT = {
    "en": {
        # --- Navigation ---
        # Exactly six pages, kept identical in both languages by design
        # (see docs/DASHBOARD_DESIGN.md) — these are the six page names
        # required verbatim, not translated labels.
        "pages": {
            "executive": "01_Vue Exécutive_Synthèse",
            "services": "02_Résultat_Net",
            "revenue": "03_Analyse des recettes",
            "charges": "04_Analyses des charges",
            "trend_result": "05_Evolution du résultat de 2020 à 2026",
            "trend_charges": "06_Evolution des charges de 2020 à 2026",
        },
        # --- Sidebar shared ---
        "year": "YEAR",
        "period": "PERIOD",
        "all_year": "Full year",
        "currency": "DISPLAY CURRENCY",
        "category": "CATEGORY",
        "service": "SERVICE LINE",
        "all": "All",
        "language": "Language",
        "base_info": "Analytical base: {} · Display: {} · FX date: {}",
        # --- Executive view ---
        "executive": {
            "title": "ANALYTICAL PERFORMANCE",
            "subtitle": (
                "Consolidated view of revenue, attributed costs, "
                "results and alerts"
            ),
            "all_categories": "All categories",
            "all_services": "All service lines",
            "filter_category": "Category",
            "filter_service": "Service line",
            "no_data": "No analytical data for the selection.",
            "no_match": "No data matches the selected filters.",
            "negative_costs": (
                "Negative costs were detected. Check the "
                "amount_multiplier settings in "
                "config/sources/oracle_pbi_views.yaml and "
                "rerun the Oracle ingestion."
            ),
            "kpi_revenue": "Revenue",
            "kpi_direct": "Direct charges",
            "kpi_indirect": "Indirect charges",
            "kpi_total_cost": "Total attributed cost",
            "kpi_net": "Net result",
            "kpi_margin": "Analytical margin",
            "chart_cat_title": "Revenue, cost and result by category",
            "chart_revenue_share": "Revenue share by category",
            "chart_no_revenue": "No positive revenue to display.",
            "chart_top_services": "Leading service lines by revenue",
            "chart_trend_title": "12-month revenue trend",
            "trend_group_label": "Trend breakdown",
            "trend_group_category": "By category",
            "trend_group_service": "By service line",
            "trend_other": "Other",
            "col_category": "Category",
            "col_indicator": "Indicator",
            "col_amount": "Amount",
            "col_revenue": "Revenue",
            "col_total_cost": "Total cost",
            "col_net": "Net result",
            "col_service": "Service line",
            "col_period": "Period",
            "priority_alerts": "Priority alerts",
            "no_alerts": "No alert for the selection.",
            "alert_col_priority": "Priority",
            "alert_col_category": "Category",
            "alert_col_service": "Service line",
            "alert_col_period": "Period",
            "alert_col_finding": "Finding",
            "alert_col_action": "Recommended action",
            "alert_col_timeframe": "Response timeframe",
            "alert_uncategorised": "Uncategorised",
            "severity_critical": "Critical",
            "severity_priority_review": "Priority review",
            "severity_warning": "Warning",
            "severity_data_quality": "Data quality",
            "rule_critical_deficit": "Critical deficit",
            "rule_service_deficit": "Negative net result",
            "rule_negative_margin": "Negative analytical margin",
            "rule_low_cost_recovery": "Low cost recovery",
            "rule_high_indirect_share": "High indirect cost share",
            "rule_missing_revenue": "Revenue missing",
            "rule_data_quality": "Required data missing",
            "action_critical_deficit": (
                "Immediately review pricing, costs and explicit funding options."
            ),
            "action_service_deficit": (
                "Review cost structure, pricing and public service justification."
            ),
            "action_negative_margin": (
                "Identify the drivers of the negative margin and "
                "prepare corrective measures."
            ),
            "action_low_cost_recovery": (
                "Revisit pricing and cost-recovery conditions for this service."
            ),
            "action_high_indirect_share": (
                "Analyse the composition of indirect costs attributed to this service."
            ),
            "action_missing_revenue": (
                "Verify revenue completeness and the mapping between "
                "services and revenue lines."
            ),
            "action_data_quality": (
                "Correct the missing data or mapping, then rerun the pipeline."
            ),
        },
        # --- Services view ---
        "services": {
            "title": "DETAILED NET RESULT ANALYSIS",
            "kpi_revenue": "Revenue",
            "kpi_total_alloc": "Total charges",
            "kpi_net": "Net result",
            "kpi_count": "No. of services",
            "kpi_margin": "Analytical margin",
            "family_filter": "Family",
            "subfamily_filter": "Sub-family",
            "no_data": "No data for the current selection.",
            "total_row": "Total",
            "matrix_title": "Net result matrix — family / sub-family",
            "treemap_title": "Net result breakdown — family → sub-family",
            "col_category": "Category",
            "col_service": "Service line",
            "col_revenue": "Assigned revenue",
            "col_direct": "Direct charges",
            "col_indirect": "Indirect charges",
            "col_total": "Total charges",
            "col_net": "Net result",
            "col_margin": "Analytical margin %",
            "col_recovery": "Recovery ratio",
            "account_breakdown_title": "Revenue by account (Oracle source)",
            "account_filter": "Account",
            "col_account": "Account",
            "col_amount": "Amount",
            "chart_account_bar": "Revenue by account",
            "waterfall_title": "Revenue to net result — waterfall",
            "waterfall_revenue": "Revenue",
            "waterfall_direct": "Direct charges",
            "waterfall_indirect": "Indirect charges",
            "waterfall_net": "Net result",
        },
        # --- Centres view ---
        "centres": {
            "title": "COST CENTRE ANALYSIS",
            "kpi_total": "Centre costs",
            "kpi_count": "No. of cost centres",
            "kpi_avg": "Average cost per centre",
            "chart_pie": "Cost distribution by centre",
            "chart_bar": "Centre costs by description",
            "col_code": "CC Code",
            "col_name": "Description",
            "col_direct": "Direct costs",
            "col_indirect": "Indirect costs",
            "col_total": "Centre costs",
            "col_pct": "% Total",
            "family_breakdown_title": "Cost breakdown by family / sub-family (Oracle source)",
            "family_filter": "Family",
            "subfamily_filter": "Sub-family",
            "col_family": "Family",
            "col_subfamily": "Sub-family",
            "col_amount": "Amount",
            "chart_family_bar": "Cost by family",
        },
        # --- Allocations view ---
        "allocations": {
            "title": "ALLOCATION ANALYSIS",
            "chart_stacked_title": "Stacked allocation chart by service",
            "direct_pct": "Direct base %",
            "indirect_pct": "Indirect base %",
            "alloc_type": "Allocation type",
            "percentage": "Percentage",
            "matrix_title": "#### Allocation matrix",
            "col_category": "Category",
            "col_service": "Service line",
            "col_direct": "Direct base",
            "col_indirect": "Indirect base",
            "flow_title": "#### Allocation flow: centres → categories → services",
        },
        # --- Budgets view ---
        "budgets": {
            "title": "BUDGET MONITORING",
            "no_budget": (
                "The Oracle PBI_JDE views currently connected do not contain "
                "budget data. This page will be activated once a budget view "
                "or import is connected."
            ),
            "kpi_actual": "Actual",
            "kpi_budget": "Budget",
            "kpi_variance": "Variance",
            "kpi_consumption": "Consumption rate",
            "chart_vs_title": "Actual vs budget by centre",
            "chart_variance_title": "Budget variance by centre",
            "measure": "Measure",
            "amount": "Amount",
        },
        # --- Alerts view ---
        "alerts": {
            "title": "DECISION ALERTS AND GUIDANCE",
            "no_alerts": "No alerts for the selection.",
            "chart_title": "Alerts by severity level",
            "count": "Count",
            "data_quality_title": "#### Data quality",
            "no_issues": "No data quality issues recorded.",
            "batches_title": "#### Extraction history",
            "no_batches": "No external extractions run.",
        },
        # --- Revenue analysis view ---
        "revenue": {
            "title": "DETAILED REVENUE ANALYSIS",
            "family_filter": "FAMILIES",
            "subfamily_filter": "SUB-FAMILIES",
            "kpi_revenue": "Revenue",
            "kpi_allocations": "Total allocations",
            "kpi_net": "Net result",
            "kpi_count": "Number of products",
            "other_label": "Others",
            "not_specified": "Not specified",
            "no_data": "No data available for the selected filters.",
            "chart_donut_title": "Revenue share by category",
            "chart_stacked100_title": "Product mix within each category (100%)",
            "col_category": "Category",
            "col_product": "Finished product",
            "axis_share": "Share of category revenue",
            "consistency_warning": (
                "Inconsistent totals were detected between the KPI card "
                "and the category/product breakdown — see the application logs."
            ),
        },
        # --- Charges analysis view (04) ---
        "charges": {
            "title": "COST ANALYSIS",
            "kpi_total": "Total charges",
            "kpi_direct": "Direct charges",
            "kpi_indirect": "Indirect charges",
            "kpi_count": "No. of cost centres",
            "no_data": "No data available for the selected filters.",
            "chart_grouped_title": "Direct vs indirect charges by cost centre",
            "chart_donut_title": "Direct vs indirect share of total charges",
            "col_centre": "Cost centre",
            "col_amount": "Amount",
            "cost_type": "Cost type",
            "direct": "Direct",
            "indirect": "Indirect",
        },
        # --- Net result evolution view (05) ---
        "trend_result": {
            "title": "NET RESULT EVOLUTION 2020-2026",
            "no_data": "No historical data available.",
            "kpi_total_period": "Total net result (period)",
            "kpi_variation_pct": "Change over the period",
            "kpi_best_year": "Best year",
            "kpi_worst_year": "Worst year",
            "chart_title": "Net result by category — annual evolution",
            "family_filter": "Family",
            "subfamily_filter": "Sub-family",
            "axis_year": "Year",
            "axis_net_result": "Net result",
            "other_label": "Others",
            "not_specified": "Not specified",
            "reference_line": "Period average",
        },
        # --- Charges evolution view (06) ---
        "trend_charges": {
            "title": "CHARGES EVOLUTION 2020-2026",
            "no_data": "No historical data available.",
            "kpi_total_period": "Total charges (period)",
            "kpi_variation_pct": "Change over the period",
            "kpi_best_year": "Lowest-charge year",
            "kpi_worst_year": "Highest-charge year",
            "chart_title": "Charges by family — annual evolution",
            "family_filter": "Family",
            "subfamily_filter": "Sub-family",
            "axis_year": "Year",
            "axis_charges": "Charges",
            "other_label": "Others",
            "not_specified": "Not specified",
            "total_label": "Total charges",
        },
    },
    "fr": {
        # --- Navigation ---
        "pages": {
            "executive": "01_Vue Exécutive_Synthèse",
            "services": "02_Résultat_Net",
            "revenue": "03_Analyse des recettes",
            "charges": "04_Analyses des charges",
            "trend_result": "05_Evolution du résultat de 2020 à 2026",
            "trend_charges": "06_Evolution des charges de 2020 à 2026",
        },
        # --- Sidebar shared ---
        "year": "ANNÉE",
        "period": "PÉRIODE",
        "all_year": "Année complète",
        "currency": "DEVISE D'AFFICHAGE",
        "category": "CATÉGORIE",
        "service": "PRODUIT FINI / SERVICE",
        "all": "Tout",
        "language": "Langue",
        "base_info": "Base analytique : {} · Affichage : {} · Date FX : {}",
        # --- Executive view ---
        "executive": {
            "title": "PERFORMANCE ANALYTIQUE",
            "subtitle": (
                "Vue consolidée des recettes, des coûts attribués, "
                "des résultats et des alertes"
            ),
            "all_categories": "Toutes les catégories",
            "all_services": "Tous les produits finis",
            "filter_category": "Catégorie",
            "filter_service": "Produit fini",
            "no_data": "Aucune donnée analytique pour la sélection.",
            "no_match": "Aucune donnée ne correspond aux filtres sélectionnés.",
            "negative_costs": (
                "Des coûts négatifs ont été détectés. "
                "Vérifiez les paramètres amount_multiplier dans "
                "config/sources/oracle_pbi_views.yaml, puis "
                "relancez l'ingéstion Oracle."
            ),
            "kpi_revenue": "Recettes",
            "kpi_direct": "Charges directes",
            "kpi_indirect": "Charges indirectes",
            "kpi_total_cost": "Coût total attribué",
            "kpi_net": "Résultat net",
            "kpi_margin": "Marge analytique",
            "chart_cat_title": "Recettes, coûts et résultat par catégorie",
            "chart_revenue_share": "Poids des recettes par catégorie",
            "chart_no_revenue": "Aucune recette positive à représenter.",
            "chart_top_services": "Principaux produits finis par recettes",
            "chart_trend_title": "Évolution des recettes sur 12 mois",
            "trend_group_label": "Ventilation de la courbe",
            "trend_group_category": "Par catégorie",
            "trend_group_service": "Par produit fini",
            "trend_other": "Autres",
            "col_category": "Catégorie",
            "col_indicator": "Indicateur",
            "col_amount": "Montant",
            "col_revenue": "Recettes",
            "col_total_cost": "Coût total",
            "col_net": "Résultat net",
            "col_service": "Produit fini",
            "col_period": "Période",
            "priority_alerts": "Alertes prioritaires",
            "no_alerts": "Aucune alerte pour la sélection.",
            "alert_col_priority": "Priorité",
            "alert_col_category": "Catégorie",
            "alert_col_service": "Produit fini",
            "alert_col_period": "Période",
            "alert_col_finding": "Constat",
            "alert_col_action": "Action recommandée",
            "alert_col_timeframe": "Délai de traitement",
            "alert_uncategorised": "Non catégorisé",
            "severity_critical": "Critique",
            "severity_priority_review": "Revue prioritaire",
            "severity_warning": "Avertissement",
            "severity_data_quality": "Qualité des données",
            "rule_critical_deficit": "Déficit critique",
            "rule_service_deficit": "Résultat net négatif",
            "rule_negative_margin": "Marge analytique négative",
            "rule_low_cost_recovery": "Faible couverture des coûts",
            "rule_high_indirect_share": "Poids élevé des coûts indirects",
            "rule_missing_revenue": "Recette absente",
            "rule_data_quality": "Donnée requise manquante",
            "action_critical_deficit": (
                "Analyser immédiatement les tarifs, les coûts et "
                "les options de financement explicite."
            ),
            "action_service_deficit": (
                "Examiner la structure des coûts, la tarification "
                "et la justification de service public."
            ),
            "action_negative_margin": (
                "Identifier les facteurs expliquant la marge négative "
                "et préparer des mesures correctives."
            ),
            "action_low_cost_recovery": (
                "Réexaminer la tarification et les conditions de "
                "couverture des coûts du produit."
            ),
            "action_high_indirect_share": (
                "Analyser la composition des coûts indirects attribués "
                "au produit fini."
            ),
            "action_missing_revenue": (
                "Vérifier l’exhaustivité des recettes et la correspondance "
                "entre produits et revenus."
            ),
            "action_data_quality": (
                "Corriger la donnée ou le mapping manquant, puis "
                "relancer le pipeline."
            ),
        },
        # --- Services view ---
        "services": {
            "title": "ANALYSE DÉTAILLÉE DU RÉSULTAT NET",
            "kpi_revenue": "Recettes",
            "kpi_total_alloc": "Charges totales",
            "kpi_net": "Résultat net",
            "kpi_count": "Nb Produits",
            "kpi_margin": "Marge analytique",
            "family_filter": "Famille",
            "subfamily_filter": "Sous-famille",
            "no_data": "Aucune donnée pour la sélection en cours.",
            "total_row": "Total",
            "matrix_title": "Matrice du résultat net — famille / sous-famille",
            "treemap_title": "Décomposition du résultat net — famille → sous-famille",
            "col_category": "Catégorie",
            "col_service": "Produit fini",
            "col_revenue": "Recettes affectées",
            "col_direct": "Charges directes",
            "col_indirect": "Charges indirectes",
            "col_total": "Charges totales",
            "col_net": "Résultat net",
            "col_margin": "Marge analytique %",
            "col_recovery": "Taux de couverture",
            "account_breakdown_title": "Recettes par compte (source Oracle)",
            "account_filter": "Compte",
            "col_account": "Compte",
            "col_amount": "Montant",
            "chart_account_bar": "Recettes par compte",
            "waterfall_title": "Des recettes au résultat net — waterfall",
            "waterfall_revenue": "Recettes",
            "waterfall_direct": "Charges directes",
            "waterfall_indirect": "Charges indirectes",
            "waterfall_net": "Résultat net",
        },
        # --- Centres view ---
        "centres": {
            "title": "ANALYSE DES CENTRES DE COÛTS",
            "kpi_total": "Coûts centres",
            "kpi_count": "Nb Centres de coûts",
            "kpi_avg": "Coût moyen par centre",
            "chart_pie": "Répartition des coûts par centre",
            "chart_bar": "Coûts centres par description",
            "col_code": "Code CC",
            "col_name": "Description",
            "col_direct": "Coûts directs",
            "col_indirect": "Coûts indirects",
            "col_total": "Coûts centres",
            "col_pct": "% Total",
            "family_breakdown_title": "Répartition des coûts par famille / sous-famille (source Oracle)",
            "family_filter": "Famille",
            "subfamily_filter": "Sous-famille",
            "col_family": "Famille",
            "col_subfamily": "Sous-famille",
            "col_amount": "Montant",
            "chart_family_bar": "Coûts par famille",
        },
        # --- Allocations view ---
        "allocations": {
            "title": "VENTILATION DES ALLOCATIONS",
            "chart_stacked_title": "Graphique empilé des allocations par produit",
            "direct_pct": "Directes base %",
            "indirect_pct": "Indirectes base %",
            "alloc_type": "Type d’allocation",
            "percentage": "Pourcentage",
            "matrix_title": "#### Matrice de ventilation",
            "col_category": "Catégorie",
            "col_service": "Produit fini",
            "col_direct": "Directes base",
            "col_indirect": "Indirectes base",
            "flow_title": "#### Flux de ventilation : centres → catégories → produits finis",
        },
        # --- Budgets view ---
        "budgets": {
            "title": "SUIVI BUDGÉTAIRE",
            "no_budget": (
                "Les vues Oracle PBI_JDE actuellement connectées ne contiennent "
                "pas de données budgétaires. Cette page sera activée lorsqu’une "
                "vue ou un fichier de budget sera ajouté."
            ),
            "kpi_actual": "Réalisé",
            "kpi_budget": "Budget",
            "kpi_variance": "Écart",
            "kpi_consumption": "Taux de consommation",
            "chart_vs_title": "Réalisé vs budget par centre",
            "chart_variance_title": "Écart budgétaire par centre",
            "measure": "Mesure",
            "amount": "Montant",
        },
        # --- Alerts view ---
        "alerts": {
            "title": "ALERTES ET AIDE À LA DÉCISION",
            "no_alerts": "Aucune alerte pour la sélection.",
            "chart_title": "Alertes par niveau de sévérité",
            "count": "Nombre",
            "data_quality_title": "#### Qualité des données",
            "no_issues": "Aucun problème de qualité enregistré.",
            "batches_title": "#### Historique des extractions",
            "no_batches": "Aucune extraction externe exécutée.",
        },
        # --- Revenue analysis view ---
        "revenue": {
            "title": "ANALYSE DÉTAILLÉE DES RECETTES",
            "family_filter": "FAMILLES",
            "subfamily_filter": "SOUS-FAMILLES",
            "kpi_revenue": "Recettes",
            "kpi_allocations": "Allocations totales",
            "kpi_net": "Résultat net",
            "kpi_count": "Nb Produits",
            "other_label": "Autres",
            "not_specified": "Non renseigné",
            "no_data": "Aucune donnée disponible pour les filtres sélectionnés.",
            "chart_donut_title": "Répartition des recettes par catégorie",
            "chart_stacked100_title": "Mix produits au sein de chaque catégorie (100%)",
            "col_category": "Catégorie",
            "col_product": "Produit fini",
            "axis_share": "Part des recettes de la catégorie",
            "consistency_warning": (
                "Une incohérence de totaux a été détectée entre la carte "
                "KPI et la décomposition catégorie/produit — voir les "
                "journaux de l'application."
            ),
        },
        # --- Vue Analyses des charges (04) ---
        "charges": {
            "title": "ANALYSE DES CHARGES",
            "kpi_total": "Charges totales",
            "kpi_direct": "Charges directes",
            "kpi_indirect": "Charges indirectes",
            "kpi_count": "Nb Centres de coûts",
            "no_data": "Aucune donnée disponible pour les filtres sélectionnés.",
            "chart_grouped_title": "Charges directes vs indirectes par centre de coûts",
            "chart_donut_title": "Part directes/indirectes dans les charges totales",
            "col_centre": "Centre de coûts",
            "col_amount": "Montant",
            "cost_type": "Type de charge",
            "direct": "Directes",
            "indirect": "Indirectes",
        },
        # --- Vue Evolution du résultat (05) ---
        "trend_result": {
            "title": "ÉVOLUTION DU RÉSULTAT 2020-2026",
            "no_data": "Aucune donnée historique disponible.",
            "kpi_total_period": "Résultat net cumulé (période)",
            "kpi_variation_pct": "Variation sur la période",
            "kpi_best_year": "Meilleure année",
            "kpi_worst_year": "Pire année",
            "chart_title": "Résultat net par catégorie — évolution annuelle",
            "family_filter": "Famille",
            "subfamily_filter": "Sous-famille",
            "axis_year": "Année",
            "axis_net_result": "Résultat net",
            "other_label": "Autres",
            "not_specified": "Non renseigné",
            "reference_line": "Moyenne de la période",
        },
        # --- Vue Evolution des charges (06) ---
        "trend_charges": {
            "title": "ÉVOLUTION DES CHARGES 2020-2026",
            "no_data": "Aucune donnée historique disponible.",
            "kpi_total_period": "Charges cumulées (période)",
            "kpi_variation_pct": "Variation sur la période",
            "kpi_best_year": "Année la plus basse",
            "kpi_worst_year": "Année la plus haute",
            "chart_title": "Charges par famille — évolution annuelle",
            "family_filter": "Famille",
            "subfamily_filter": "Sous-famille",
            "axis_year": "Année",
            "axis_charges": "Charges",
            "other_label": "Autres",
            "not_specified": "Non renseigné",
            "total_label": "Charges totales",
        },
    },
}


def tr(language: str) -> dict:
    return TEXT.get(language, TEXT["en"])
