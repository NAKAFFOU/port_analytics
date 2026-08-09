SELECT
    TO_CHAR(GLUKID)                         AS source_row_id,
    TRIM(GLCO)                              AS company_code,
    TRIM(TO_CHAR(GLDOC))                    AS document_number,
    TRIM(GLDCT)                             AS document_type,
    TRIM(GLMCU)                             AS business_unit,
    TRIM(GLOBJ)                             AS object_account,
    TRIM(GLSUB)                             AS subsidiary,
    GLDGJ                                   AS transaction_jde_date,
    GLAA                                    AS amount_source,
    NULLIF(TRIM(GLCRCD), '')                AS source_currency,
    TRIM(GLLT)                              AS ledger_type,
    TRIM(GLEXA)                             AS description
FROM {{DATA_SCHEMA}}.F0911
WHERE GLDGJ BETWEEN :start_jde_date AND :end_jde_date
  AND TRIM(GLLT) = :ledger_type
