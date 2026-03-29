# Horizon documentation

**New here?** Read the **[../README.md](../README.md)** first — problem statement, **how project criteria are covered**, **quick links** (local + Cloud Run URL), and architecture in one place.

---

## Quick links

| Need | Link / command |
|------|----------------|
| **Hosted Streamlit URL** | `terraform -chdir=../terraform output -raw streamlit_service_uri` (after Cloud Run deploy). Example demo URL in root README. |
| **Full runbook** | [GUIDE_END_TO_END.md](GUIDE_END_TO_END.md) |
| **Criteria + narrative** | [PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md) |

---

## Guides

| Guide | Who it's for |
|-------|----------------|
| **[PROJECT_OVERVIEW.md](PROJECT_OVERVIEW.md)** | Story, tools, dashboard, **how each criterion is met** |
| **[GUIDE_END_TO_END.md](GUIDE_END_TO_END.md)** | Terraform → ingest → BigQuery → dbt → Streamlit |
| **[GUIDE_GCP_HOSTING.md](GUIDE_GCP_HOSTING.md)** | Cloud Run, ingress, Docker `amd64`, redeploy after code changes |
| **[GUIDE_DLT_DBT.md](GUIDE_DLT_DBT.md)** | dlt + dbt, partitions/clusters |

**Reference**

- [MASTER_TABLE_SPEC.md](MASTER_TABLE_SPEC.md) — `master_jobs`, skills
- [EVALUATE_SKILLS_EXTRACTION.md](EVALUATE_SKILLS_EXTRACTION.md) — skills eval

**Terraform:** [../terraform/README.md](../terraform/README.md) · [../terraform/TERRAFORM-EXPLAINED.md](../terraform/TERRAFORM-EXPLAINED.md)
