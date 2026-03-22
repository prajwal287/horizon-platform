{# Reusable logic for silver / gold layers #}

{% macro normalize_skills_array(skills_col) -%}
  IFNULL(
    (
      SELECT ARRAY_AGG(TRIM(CAST(s AS STRING)))
      FROM UNNEST(IFNULL(SAFE_CAST({{ skills_col }} AS ARRAY<STRING>), ARRAY<STRING>[])) AS s
      WHERE TRIM(CAST(s AS STRING)) IS NOT NULL AND TRIM(CAST(s AS STRING)) != ''
    ),
    ARRAY<STRING>[]
  )
{%- endmacro %}


{% macro job_dedup_fingerprint() -%}
  farm_fingerprint(
    concat(
      cast(source_id as string), '#',
      coalesce(nullif(trim(job_url), ''), '_nourl_'), '#',
      coalesce(trim(job_title), ''), '#',
      coalesce(trim(company_name), ''), '#',
      cast(posted_date as string), '#',
      coalesce(trim(location), '')
    )
  )
{%- endmacro %}
