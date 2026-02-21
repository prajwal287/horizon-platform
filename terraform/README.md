# Terraform + GCP – Step-by-Step Guide

This guide walks you through provisioning your GCP lakehouse (GCS, BigQuery, Pub/Sub, Service Account) using Terraform. No prior Terraform or GCP experience assumed.

---

## Prerequisites

You need two things installed and one GCP project.

### 1. Install Google Cloud CLI (gcloud)

**macOS (Homebrew):**
```bash
brew install google-cloud-sdk
```

**Or download:** https://cloud.google.com/sdk/docs/install

Check it works:
```bash
gcloud --version
```

### 2. Install Terraform

**macOS (Homebrew):**
```bash
brew install terraform
```

**Or download:** https://developer.hashicorp.com/terraform/downloads

Check it works:
```bash
terraform version
```

### 3. Have a GCP project (or create one)

- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Sign in with your Google account
- Create a new project (or pick an existing one)
- Note the **Project ID** (e.g. `my-lakehouse-123`) – you’ll need it below

---

## Step 1: Log in to GCP and pick your project

Open a terminal and run:

```bash
# Log in (opens a browser)
gcloud auth login

# Set your default project (use YOUR project ID)
gcloud config set project YOUR_PROJECT_ID
```

Example:
```bash
gcloud config set project my-lakehouse-123
```

### Optional: Create a new project from the CLI

```bash
# Create project (replace with your desired ID and name)
gcloud projects create my-lakehouse-123 --name="My Lakehouse"

# Set it as default
gcloud config set project my-lakehouse-123

# Link billing (required for real resources)
# Do this in Console: Billing → Link a billing account to your project
```

---

## Step 2: Authenticate Terraform with GCP

Terraform uses “Application Default Credentials.” One-time setup:

```bash
gcloud auth application-default login
```

A browser window opens; sign in with the same Google account. After that, Terraform can create resources in your project.

---

## Step 3: Enable required APIs

These APIs must be enabled for the resources we create (GCS, BigQuery, Pub/Sub, IAM):

```bash
# Replace YOUR_PROJECT_ID with your actual project ID
export PROJECT_ID=YOUR_PROJECT_ID

gcloud services enable storage.googleapis.com --project=$PROJECT_ID
gcloud services enable bigquery.googleapis.com --project=$PROJECT_ID
gcloud services enable pubsub.googleapis.com --project=$PROJECT_ID
gcloud services enable iam.googleapis.com --project=$PROJECT_ID
```

Example:
```bash
export PROJECT_ID=my-lakehouse-123
gcloud services enable storage.googleapis.com bigquery.googleapis.com pubsub.googleapis.com iam.googleapis.com --project=$PROJECT_ID
```

---

## Step 4: Set your project in Terraform

From the **project root** (parent of `terraform/`), go into the Terraform folder and create a variable file.

```bash
cd terraform
```

Create a file named `terraform.tfvars` with your project ID (and optional region):

```hcl
# terraform/terraform.tfvars
project_id = "my-lakehouse-123"
region     = "us-central1"
```

Use your real **Project ID** from the GCP Console. Do not commit this file if it contains sensitive data; add `terraform.tfvars` to `.gitignore` if needed.

---

## Step 5: Initialize Terraform

This downloads the Google provider and prepares Terraform:

```bash
terraform init
```

You should see something like:

```
Initializing the backend...
Initializing provider plugins...
- Finding hashicorp/google versions matching "~> 5.0"...
- Installing hashicorp/google v5.x.x...
Terraform has been successfully initialized!
```

---

## Step 6: Plan (preview changes)

See what Terraform will create **without** creating it yet:

```bash
terraform plan
```

You’ll see a list of resources to be added (GCS bucket, BigQuery dataset, Pub/Sub topic, service account, IAM bindings). Read through it to confirm.

Example snippet:

```
Plan: 7 to add, 0 to change, 0 to destroy.
```

---

## Step 7: Apply (create the resources)

Create the resources in GCP:

```bash
terraform apply
```

Terraform will show the plan again and ask:

```
Do you want to perform these actions?
  Terraform will perform the actions described above.
  Only 'yes' will be accepted to approve.

  Enter a value:
```

Type **yes** and press Enter. After a minute or two you should see:

```
Apply complete! Resources: 7 added, 0 changed, 0 destroyed.
```

---

## Step 8: View outputs

Terraform prints useful values at the end of `apply`. To see them again anytime:

```bash
terraform output
```

Example:

```
bigquery_dataset_id     = "job_market_analysis"
gcs_bucket_name         = "my-lakehouse-123-job-lakehouse-raw"
pubsub_topic_name       = "job-stream-input"
service_account_email   = "lakehouse-sa@my-lakehouse-123.iam.gserviceaccount.com"
```

Use these values in your ingestion scripts and applications.

---

## Quick reference: usual workflow

| Step   | Command             | Purpose                    |
|--------|---------------------|----------------------------|
| Once   | `terraform init`    | Download providers         |
| Change | `terraform plan`    | Preview changes            |
| Change | `terraform apply`   | Create/update resources    |
| Anytime| `terraform output`  | Show outputs               |

---

## If something goes wrong

### “Error: Could not load plugin”
- Run `terraform init` again from inside the `terraform/` directory.

### “Error: 403 – Permission denied” or “API not enabled”
- Run Step 2 again: `gcloud auth application-default login`
- Run Step 3 again to enable the four APIs for your project.

### “Error: Bucket name already exists”
- GCS bucket names are global. Use a different `project_id` or change `gcs_bucket_name` in `terraform.tfvars` to something unique.

### “Error: Billing not enabled”
- In GCP Console: **Billing** → link a billing account to your project.

---

## Tearing down (optional)

To delete all resources created by this Terraform config:

```bash
terraform destroy
```

Type **yes** when prompted. This removes the bucket, dataset, topic, service account, and IAM bindings. Only do this when you no longer need the environment.

---

## Next steps

- Use **service_account_email** from `terraform output` when running pipelines (e.g. grant it access to other systems or use Workload Identity).
- Write data to the **GCS bucket** and **Pub/Sub topic**; query tables in the **BigQuery dataset** `job_market_analysis`.
- To change region or names, edit `terraform.tfvars` and run `terraform plan` then `terraform apply` again.
