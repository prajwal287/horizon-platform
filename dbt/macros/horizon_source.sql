{# True when this raw_* table should be modeled (must match BigQuery). Uses var — not adapter.get_relation — because get_relation is unreliable during dbt parse. #}
{# Discover actual tables: python scripts/dbt_raw_tables_vars.py --json   then   dbt run --vars "$(python ...)" #}

{% macro horizon_raw_table_exists(identifier) %}
  {{ return(identifier in var('raw_tables_present')) }}
{% endmacro %}
