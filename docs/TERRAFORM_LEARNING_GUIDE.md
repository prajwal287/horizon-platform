# Terraform — Learn the Top 20% Fast

A short, Pareto-style guide: **what Terraform is**, **why use it**, **the 20% that gives 80% of the value**, **how it differs from other tools**, and **core concepts with real examples from this repo**.

---

## 1. What is Terraform?

**Terraform** is an **Infrastructure as Code (IaC)** tool by HashiCorp. You describe infrastructure (buckets, databases, service accounts, networks) in **declarative config files** (`.tf`). Terraform talks to cloud providers (GCP, AWS, Azure) via **providers** and **creates, updates, or destroys** resources so the real world matches your code.

- **Official**: [terraform.io](https://www.terraform.io)  
- **Docs**: [developer.hashicorp.com/terraform](https://developer.hashicorp.com/terraform)

**In one sentence**: *“You declare what you want in `.tf`; Terraform makes the cloud match it (and remembers what it created in state).”*

---

## 2. Why study Terraform?

| Reason | Why it matters |
|--------|----------------|
| **Infrastructure as Code** | No more “click in the console and hope everyone did the same”; one codebase, consistent environments. |
| **Plan before apply** | `terraform plan` shows exactly what will change; no surprise deletions or config drift. |
| **State** | Terraform tracks what it created so it can update or destroy the right resources later. |
| **Documentation** | Your `.tf` files are the source of truth; onboarding and audits are easier. |
| **Automation** | CI/CD can run `terraform apply`; infra changes become repeatable and reviewable. |
| **Multi-cloud / ecosystem** | Same workflow for GCP, AWS, Azure, Kubernetes, etc., via providers. |

---

## 3. Pareto: the top 20% you need

If you learn **only** these, you’ll cover most day-to-day use:

1. **Provider** — Plugin that talks to a cloud (e.g. `google`). You declare it in `terraform { required_providers { ... } }` and configure it with `provider "google" { ... }`.
2. **Resource** — One block that describes **one** real thing (a bucket, a dataset, a service account). Terraform creates/updates/destroys it.
3. **Variable** — Input to your config (e.g. `project_id`, `region`). Defined in `variables.tf`; values come from defaults, `terraform.tfvars`, or `-var`.
4. **Output** — Value you want after apply (bucket name, dataset ID, service account email). Defined in `outputs.tf`; read with `terraform output`.
5. **Init / Plan / Apply** — `terraform init` (download providers), `terraform plan` (preview changes), `terraform apply` (make changes). State is stored in `terraform.tfstate`.

Everything else (modules, data sources, lifecycle rules, workspaces) builds on these five.

---

## 4. How Terraform differs from other tools

| Tool | Model | Best for | Terraform difference |
|------|--------|----------|----------------------|
| **GCP Console (clickops)** | Manual UI | One-off experiments | Terraform = **reproducible and reviewable**; same config for dev/stage/prod. |
| **Pulumi** | General-purpose languages (TypeScript, Python) | Teams that want code over HCL | Terraform = **HCL** (and JSON); larger ecosystem, more examples and jobs. |
| **CloudFormation / Bicep** | AWS / Azure native | All-in on one cloud | Terraform = **cloud-agnostic**; one tool and workflow across GCP, AWS, Azure. |
| **Ansible** | Imperative “do this, then that” | Config and app deploy | Terraform = **declarative** “desired state”; better for long-lived infra. |

**When to choose Terraform**: You want **declarative IaC**, **plan before apply**, **state tracking**, and a **single workflow** across clouds or many GCP resources.

---

## 5. Core concepts with examples (from this repo)

### 5.1 Provider = “how Terraform talks to GCP”

You require the **Google provider** and set **project** and **region**. Terraform uses this for every GCP resource in the config.

**From** `terraform/main.tf`:

```hcl
terraform {
  required_version = ">= 1.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
```

- `required_providers` → which provider and version (e.g. Google ~5.x).
- `provider "google"` → use `var.project_id` and `var.region` for all Google resources.

**Real-world idea**: Change `project_id` (e.g. via `terraform.tfvars`) and re-apply to target another project; no code change.

---

### 5.2 Resource = “one thing in the cloud”

Each **resource** block has a **type** (e.g. `google_storage_bucket`), a **local name** (e.g. `raw`), and **arguments** (name, location, labels, etc.). Terraform creates or updates that one thing.

**GCS bucket** — `terraform/main.tf`:

```hcl
resource "google_storage_bucket" "raw" {
  name          = "${var.project_id}-${var.gcs_bucket_name}"
  location      = var.region
  storage_class = "STANDARD"

  lifecycle_rule {
    condition {
      age = var.lifecycle_nearline_days
    }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = {
    project = lower(var.project_name)
  }

  uniform_bucket_level_access = true
}
```

- **Type**: `google_storage_bucket` (provider resource type).
- **Local name**: `raw` — you refer to it elsewhere as `google_storage_bucket.raw`.
- **Arguments**: name, location, storage_class, lifecycle_rule, labels. These map to GCP bucket settings.

**BigQuery dataset** — same file:

```hcl
resource "google_bigquery_dataset" "job_market_analysis" {
  dataset_id = var.bigquery_dataset_id
  location   = var.region
  project    = var.project_id

  labels = {
    project = lower(var.project_name)
  }
}
```

**Real-world idea**: Adding a new bucket or dataset = add a new `resource` block and run `plan` / `apply`.

---

### 5.3 Variable = input to your config

**Variables** let you change behavior without editing resource blocks. Define them in `variables.tf`; set values in `terraform.tfvars` or via CLI.

**From** `terraform/variables.tf`:

```hcl
variable "project_id" {
  description = "GCP Project ID"
  type        = string
  default     = "horizon-platform-488122"
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "gcs_bucket_name" {
  description = "Name of the GCS bucket for raw data"
  type        = string
  default     = "job-lakehouse-raw"
}
```

- Use in config as `var.project_id`, `var.region`, `var.gcs_bucket_name`.
- Override: create `terraform.tfvars` with `project_id = "my-other-project"` or run `terraform apply -var "project_id=my-other-project"`.

**Real-world idea**: One set of `.tf` files; different `terraform.tfvars` per environment (or use a backend + workspaces).

---

### 5.4 Output = value you need after apply

**Outputs** expose important values (bucket name, dataset ID, service account email) so other systems or humans can use them without opening the console.

**From** `terraform/outputs.tf`:

```hcl
output "gcs_bucket_name" {
  description = "Name of the GCS raw bucket"
  value       = google_storage_bucket.raw.name
}

output "bigquery_dataset_id" {
  description = "BigQuery dataset ID for job market analysis"
  value       = google_bigquery_dataset.job_market_analysis.dataset_id
}

output "service_account_email" {
  description = "Email of the lakehouse service account"
  value       = google_service_account.lakehouse.email
}
```

- **Reference resources**: `google_storage_bucket.raw.name` — attribute of the resource you created.
- **Use in app**: From project root:  
  `export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)`  
  `export BIGQUERY_DATASET=$(terraform -chdir=terraform output -raw bigquery_dataset_id)`

**Real-world idea**: Your README and ingestion scripts get bucket/dataset from Terraform outputs; no hardcoding.

---

### 5.5 Init, Plan, Apply, State

| Command | What it does |
|---------|----------------|
| **`terraform init`** | Downloads providers (e.g. Google), initializes backend; run once per directory (or when you add a provider). |
| **`terraform plan`** | Compares desired state (your `.tf`) to current state (from `terraform.tfstate`); prints what would be added, changed, or destroyed. **No changes applied.** |
| **`terraform apply`** | Applies the plan (after you confirm, or with `-auto-approve`). Creates/updates/destroys resources and writes new state. |
| **`terraform output`** | Prints output values; `-raw` for one value (e.g. for scripts). |
| **`terraform destroy`** | Destroys resources tracked in state (use with care). |

**State** (`terraform.tfstate`): JSON file that records which real resource corresponds to each block. Terraform uses it so the next `plan`/`apply` only applies the **diff**. Don’t edit state by hand; for teams, use a **remote backend** (e.g. GCS) so state is shared and locked.

**Real-world idea**: Always run `terraform plan` before `apply`; use outputs to wire app config (e.g. `GCS_BUCKET`, `BIGQUERY_DATASET`).

---

## 6. End-to-end flow in Horizon (recap)

1. **Variables** (`terraform/variables.tf`): `project_id`, `region`, `gcs_bucket_name`, `bigquery_dataset_id`, etc., with defaults.
2. **Optional overrides** (`terraform/terraform.tfvars`): Copy from `terraform.tfvars.example`, set your `project_id` (and optionally region, names).
3. **Resources** (`terraform/main.tf`): GCS bucket, BigQuery dataset, Pub/Sub topic, service account, IAM bindings. All use `var.*`.
4. **Outputs** (`terraform/outputs.tf`): Bucket name, dataset ID, topic name, service account email for use in dlt and scripts.
5. **Workflow**:  
   `cd terraform` → `terraform init` → `terraform plan` → `terraform apply`  
   Then from project root:  
   `export GCS_BUCKET=$(terraform -chdir=terraform output -raw gcs_bucket_name)` and run ingestion.

So: **Terraform = “create and maintain GCP resources”; your app = “use those resources (bucket, dataset, SA).”**

---

## 7. Quick learning path

1. **Read the Terraform files in order**  
   `terraform/variables.tf` → `terraform/main.tf` → `terraform/outputs.tf`. Follow where `var.*` is used and where outputs get their values from resources.

2. **Run init and plan (no apply yet)**  
   `cd terraform` → `terraform init` → `terraform plan`. See how Terraform interprets your config (and, if state exists, what it would change).

3. **Apply (if you have a GCP project)**  
   Copy `terraform.tfvars.example` to `terraform.tfvars`, set `project_id`, then `terraform apply`. Check GCP Console: bucket, dataset, topic, service account should exist.

4. **Use outputs**  
   From project root:  
   `terraform -chdir=terraform output`  
   `terraform -chdir=terraform output -raw gcs_bucket_name`  
   Export these and run `run_ingestion.py` so ingestion uses Terraform-managed resources.

5. **Change one thing**  
   e.g. add a label to the bucket in `main.tf` or change `lifecycle_nearline_days` in `variables.tf`. Run `plan` again and then `apply` to see the diff and update.

6. **Optional**  
   Skim [Terraform docs](https://developer.hashicorp.com/terraform/docs) for: **data sources** (read existing resources), **modules** (reusable stacks), **remote backends** (GCS for state).

---

## 8. Summary

| Concept | One-line takeaway |
|--------|--------------------|
| **Terraform** | Declarative IaC: you describe infra in `.tf`; Terraform makes the cloud match and tracks state. |
| **Provider** | Plugin for a cloud (e.g. `google`); declared in `terraform { required_providers }` and configured in `provider "google" { ... }`. |
| **Resource** | One block = one cloud thing (bucket, dataset, SA); type + local name + arguments. |
| **Variable** | Input (e.g. `project_id`, `region`); defined in `variables.tf`, set in `terraform.tfvars` or `-var`. |
| **Output** | Exposed value after apply (e.g. bucket name, dataset ID); defined in `outputs.tf`, read with `terraform output`. |
| **Init / Plan / Apply** | Init = get providers; Plan = preview diff; Apply = apply diff. State = what Terraform created. |

Master these and you’re in the top 20% of what you need to use Terraform effectively for GCP (and other clouds) in projects like Horizon.

---

## 9. Related in this repo

- **terraform/README.md** — How to install Terraform and run init/plan/apply for this project.
- **terraform/TERRAFORM-EXPLAINED.md** — Deeper walkthrough of the same Terraform layout and workflow.
- **.env.example** — Documents using Terraform outputs for `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET`, etc.
