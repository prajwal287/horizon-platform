# Horizon documentation

Start here. Older scattered pages were merged into a few guides.

| Guide | Who it's for |
|-------|----------------|
| **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** | Peers, reviewers, or anyone who wants the *story*: problem, pipeline type, tools, dashboard, how this maps to a capstone rubric. |
| **[GUIDE_END_TO_END.md](GUIDE_END_TO_END.md)** | Anyone running the stack: Terraform → ingest → BigQuery → optional dbt → Streamlit. |
| **[GUIDE_GCP_HOSTING.md](GUIDE_GCP_HOSTING.md)** | Hosting Streamlit on **Cloud Run**, **ingress**, IAM, Docker/`amd64`, Terraform vs `gcloud`. |
| **[GUIDE_DLT_DBT.md](GUIDE_DLT_DBT.md)** | Why **dlt** and **dbt** exist here, how they connect, and short scenario walkthroughs. |

**Reference (narrow topics)**

- [MASTER_TABLE_SPEC.md](MASTER_TABLE_SPEC.md) — `master_jobs` columns, clean view, completeness.
- [EVALUATE_SKILLS_EXTRACTION.md](EVALUATE_SKILLS_EXTRACTION.md) — Comparing taxonomy vs LLM skill extraction.

**Terraform** (repo root): [../terraform/README.md](../terraform/README.md) · [../terraform/TERRAFORM-EXPLAINED.md](../terraform/TERRAFORM-EXPLAINED.md)
