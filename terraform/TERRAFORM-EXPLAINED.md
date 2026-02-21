# What is Terraform? And What Did We Just Do?

A beginner-friendly explanation of Terraform and a walkthrough of everything we did in this project.

---

## Part 1: What is Terraform?

### In one sentence

**Terraform is a tool that lets you describe your cloud infrastructure in code (files), and then creates or updates that infrastructure for you in a repeatable way.**

Instead of clicking through the GCP Console to create a bucket, a dataset, and a service account, you write those things in `.tf` files. When you run Terraform, it talks to GCP and makes the real resources match what you wrote.

### The old way vs. the Terraform way

| Without Terraform | With Terraform |
|-------------------|----------------|
| You create a bucket in the Console. Your teammate creates one manually too, with slightly different settings. | You and your teammate use the same `main.tf`. Everyone gets the same bucket. |
| Someone deletes a resource by mistake. Figuring out what to recreate is guesswork. | Your code is the “source of truth.” You can recreate from the same files. |
| “How did we set up prod?” → Someone has to remember or dig through screenshots. | The answer is in the repo: `terraform/` shows exactly what exists. |
| Creating dev, staging, and prod means repeating the same manual steps three times. | You run Terraform three times with different `project_id` or workspace; the same code provisions each environment. |

So: **Terraform = Infrastructure as Code (IaC)**. Your infrastructure is defined in version-controlled files and applied consistently.

### Why Terraform matters

1. **Reproducibility** – Same code → same infrastructure every time (and across environments).
2. **Version control** – Changes to infrastructure are in Git: you see who changed what and when.
3. **Documentation** – The `.tf` files describe exactly what you have; no need to reverse‑engineer from the console.
4. **Automation** – CI/CD can run `terraform apply` so deployments and infra changes are automated.
5. **Safety** – `terraform plan` shows what will change before you apply; no surprise deletions or changes.

### How Terraform works (big picture)

1. You write **configuration** in `.tf` files (resources, variables, outputs).
2. You run **`terraform init`** – Terraform downloads the right “provider” (e.g. Google) so it can talk to GCP.
3. You run **`terraform plan`** – Terraform compares your code to what actually exists in GCP and prints what it would add, change, or destroy.
4. You run **`terraform apply`** – Terraform creates or updates resources in GCP to match your code.

Terraform keeps a **state file** (e.g. `terraform.tfstate`) that records what it created. Later runs use that state so Terraform knows what already exists and only applies the difference.

---

## Part 2: The Files We Created and What They Do

Our Terraform setup has three main code files plus optional variable files.

### 1. `variables.tf` – Inputs and defaults

**What it is:** Defines the inputs your configuration can take (project ID, region, names, etc.). You can give them default values so you don’t have to type them every time.

**Why it’s useful:**  
- Change one place (e.g. `project_id`) and it updates everywhere.  
- Different environments (dev/staging/prod) can use different values without changing the main logic.

**Example from our file:**

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
```

- `project_id` is used everywhere we need to say “which GCP project.” Default: your project.  
- `region` is where we create the bucket, dataset, etc. Default: `us-central1`.

You can override these in `terraform.tfvars` or with `-var "project_id=other-project"` without editing `variables.tf`.

---

### 2. `main.tf` – The actual infrastructure

**What it is:** The core file. It declares *what* resources should exist (bucket, dataset, topic, service account, IAM). Terraform (and the Google provider) turn those declarations into real GCP resources.

**Main blocks we use:**

#### A. Terraform and provider block

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

- **`terraform { ... }`** – Requires Terraform 1.0+ and the Google provider ~5.x.  
- **`provider "google"`** – Tells Terraform *how* to talk to GCP: which project and region to use (from variables).

#### B. Resources

Each **`resource "TYPE" "NAME" { ... }`** block is one (or a set of) real thing(s) in GCP.

| Resource in our code | What it creates in GCP |
|----------------------|-------------------------|
| `google_storage_bucket.raw` | A GCS bucket (e.g. `horizon-platform-488122-job-lakehouse-raw`) with Standard storage, a lifecycle rule to move objects to Nearline after 90 days, and a label. |
| `google_bigquery_dataset.job_market_analysis` | A BigQuery dataset named `job_market_analysis` in your project and region. |
| `google_pubsub_topic.job_stream_input` | A Pub/Sub topic named `job-stream-input` for real-time ingestion. |
| `google_service_account.lakehouse` | A service account (e.g. `lakehouse-sa@horizon-platform-488122.iam.gserviceaccount.com`) for pipelines/jobs. |
| `google_storage_bucket_iam_member.lakehouse_storage_admin` | Gives that service account “Storage Object Admin” on the raw bucket. |
| `google_project_iam_member.lakehouse_bigquery_admin` | Gives that service account “BigQuery Admin” on the project. |
| `google_pubsub_topic_iam_member.lakehouse_pubsub_publisher` | Gives that service account “Pub/Sub Publisher” on the topic. |

**Example – GCS bucket:**

```hcl
resource "google_storage_bucket" "raw" {
  name          = "${var.project_id}-${var.gcs_bucket_name}"
  location      = var.region
  storage_class = "STANDARD"

  lifecycle_rule {
    condition { age = var.lifecycle_nearline_days }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }

  labels = { project = lower(var.project_name) }
  uniform_bucket_level_access = true
}
```

- **name** – Unique bucket name (project ID + bucket name).  
- **location** – Region (from variable).  
- **storage_class** – Standard at creation.  
- **lifecycle_rule** – After 90 days, move objects to Nearline to save cost.  
- **labels** – So you can identify the bucket (e.g. in billing or console). GCP requires lowercase, so we use `lower(var.project_name)`.

So: **main.tf = “I want this bucket, this dataset, this topic, this service account, and these permissions.”** Terraform makes GCP match that.

---

### 3. `outputs.tf` – Values you care about after apply

**What it is:** Declares values that Terraform prints after `apply` (and when you run `terraform output`). These are the things other systems or humans need: bucket name, dataset ID, topic name, service account email.

**Example:**

```hcl
output "gcs_bucket_name" {
  description = "Name of the GCS raw bucket"
  value       = google_storage_bucket.raw.name
}

output "service_account_email" {
  description = "Email of the lakehouse service account"
  value       = google_service_account.lakehouse.email
}
```

- Other code or docs can use `terraform output -raw service_account_email` to get the email.  
- You don’t have to look it up in the Console.

---

### 4. `terraform.tfvars` (optional) and `terraform.tfvars.example`

- **`terraform.tfvars`** – Where you set variable values for your environment (e.g. `project_id = "horizon-platform-488122"`). Terraform loads this automatically.  
- **`terraform.tfvars.example`** – A template showing which variables exist and example values; you copy it to `terraform.tfvars` and edit.

We set defaults in `variables.tf`, so you can run without `terraform.tfvars` if the defaults (e.g. your project ID) are correct.

---

## Part 3: Every Step We Did (With Meaning)

Here’s what we did, in order, and what each step was for.

### Step 1: Install and log in (gcloud + Terraform)

- **Installed:** `gcloud` (Google Cloud CLI) and `terraform`.  
- **Ran:** `gcloud auth login` and `gcloud config set project horizon-platform-488122`.

**Why:** Terraform doesn’t log you into GCP by itself. It uses your **Application Default Credentials**. So we also ran:

- **`gcloud auth application-default login`**

**Why:** This writes credentials to a file that Terraform (and other tools) use. Without it, Terraform would have no permission to create resources. Doing it again after changing project fixes the “quota project” warning so the right project is used for billing/quota.

---

### Step 2: Enable GCP APIs

We enabled:

- `storage.googleapis.com` – for GCS  
- `bigquery.googleapis.com` – for BigQuery  
- `pubsub.googleapis.com` – for Pub/Sub  
- `iam.googleapis.com` – for service accounts and IAM

**Why:** In GCP, each “product” (Storage, BigQuery, Pub/Sub) is behind an API. Terraform calls those APIs. If the API isn’t enabled, Terraform gets permission errors. Enabling them once per project is a one-time setup.

---

### Step 3: Set variables (optional)

We created/edited `terraform.tfvars` with:

- `project_id   = "horizon-platform-488122"`  
- `project_name = "Horizon-platform"`  
- (optional) `region = "us-central1"`

**Why:** So Terraform knows which project and display name to use. Our `variables.tf` already has these as defaults, so this step was to align with your real project and fix the label value (we later used `lower(project_name)` so GCP accepts the label).

---

### Step 4: `terraform init`

**Command:** `terraform init`

**What it does:**  
- Creates a `.terraform` directory.  
- Downloads the Google provider (the plugin that knows how to create GCS buckets, BigQuery datasets, etc.).  
- Prepares the backend (by default, local state).

**Why:** Terraform needs the provider binaries before it can plan or apply. You run `init` once per directory (and again if you add a new provider or change backend).

---

### Step 5: `terraform plan`

**Command:** `terraform plan`

**What it does:**  
- Reads all `.tf` and variable values.  
- Compares desired state (your code) to current state (from `terraform.tfstate`, or “nothing” on first run).  
- Prints what it would do: “X to add, Y to change, Z to destroy.”  
- Does **not** change any infrastructure.

**Why:** So you can review changes before applying. It’s like a “dry run.”

---

### Step 6: `terraform apply`

**Command:** `terraform apply`  
You type `yes` when prompted.

**What it does:**  
- Does the same comparison as `plan`.  
- Calls GCP APIs to create or update resources so that real infrastructure matches your code.  
- Writes the new state to `terraform.tfstate`.  
- Prints the `output` values (bucket name, dataset ID, topic, service account email).

**Why:** This is the step that actually creates your bucket, dataset, topic, service account, and IAM bindings.

---

### Step 7: Fixing the label error

We got an error that the label value `"Horizon-platform"` is invalid (GCP labels must be lowercase, etc.).

**What we did:** In `main.tf`, we changed every label value from `var.project_name` to `lower(var.project_name)` so the value sent to GCP is `"horizon-platform"`.

**Why:** GCP label rules are strict; Terraform doesn’t fix that for you. Using `lower()` keeps your display name “Horizon-platform” in variables/outputs while making labels valid.

---

### Step 8: `terraform output`

**Command:** `terraform output`

**What it does:** Prints the output values (bucket name, dataset ID, topic name, service account email, etc.) from the last apply.

**Why:** So you can copy-paste these into your apps, pipelines, or docs without hunting in the Console.

---

## Part 4: How It All Fits Together (Example)

1. **You** – Edit `main.tf` or `variables.tf` (e.g. add a new bucket or change region).  
2. **Terraform** – On `plan`, it says: “I will add 1 bucket” or “I will change the lifecycle rule.”  
3. **You** – Run `apply` and say `yes`.  
4. **Terraform** – Calls GCP, creates/updates resources, updates state.  
5. **GCP** – Your project now has the new or updated resources.  
6. **You** – Use `terraform output` or the printed output to get names/IDs and use them in your code.

So: **Code = desired infrastructure. Terraform = the tool that makes GCP match that code.**  
You didn’t “do Terraform” in the abstract – you defined infrastructure in code and used Terraform to create and manage it in GCP. That’s Infrastructure as Code, and that’s what we did step by step.

---

## Quick reference

| Concept | Meaning |
|--------|--------|
| **Infrastructure as Code (IaC)** | Infrastructure defined in version-controlled files and applied by a tool (e.g. Terraform). |
| **Provider** | Plugin that knows how to create/update/delete resources in a cloud (we use the Google provider for GCP). |
| **Resource** | One block in `.tf` that maps to one (or more) real thing in the cloud (bucket, dataset, topic, etc.). |
| **State** | File (`terraform.tfstate`) that records what Terraform created so it can update or destroy the right things later. |
| **Variable** | Input to your config (e.g. `project_id`, `region`); can have defaults or be set in `terraform.tfvars`. |
| **Output** | Value printed after apply (e.g. bucket name, service account email) for use elsewhere. |
| **init** | Download providers and prepare backend; run once (or when config changes). |
| **plan** | Show what would change; no changes applied. |
| **apply** | Apply changes so real infrastructure matches your code. |

If you want to go deeper, the next step is to try a small change (e.g. add a label or change `lifecycle_nearline_days`), run `plan` and then `apply`, and watch Terraform update only what changed.
