{# Reusable logic for silver / gold layers #}

{# skills can be ARRAY<STRING>, STRING (JSON array text), or coerced STRING after UNION — never CAST string -> ARRAY<STRING>. #}
{% macro normalize_skills_array(skills_col) -%}
  IFNULL(
    (
      SELECT ARRAY_AGG(TRIM(s))
      FROM UNNEST(
        IF(
          JSON_TYPE(
            SAFE.PARSE_JSON(
              IF(
                STARTS_WITH(TRIM(IFNULL(SAFE_CAST({{ skills_col }} AS STRING), '')), '['),
                TRIM(SAFE_CAST({{ skills_col }} AS STRING)),
                TO_JSON_STRING({{ skills_col }})
              )
            )
          ) = 'array',
          JSON_VALUE_ARRAY(
            SAFE.PARSE_JSON(
              IF(
                STARTS_WITH(TRIM(IFNULL(SAFE_CAST({{ skills_col }} AS STRING), '')), '['),
                TRIM(SAFE_CAST({{ skills_col }} AS STRING)),
                TO_JSON_STRING({{ skills_col }})
              )
            )
          ),
          ARRAY<STRING>[]
        )
      ) AS s
      WHERE TRIM(s) IS NOT NULL AND TRIM(s) != ''
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
