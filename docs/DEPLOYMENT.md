# Deploy and verify

Prerequisites: an AWS account/region that supports the resources, an authorized temporary CLI profile, Python 3.12, Terraform 1.17.0 and a reviewed cost plan. The project has passed local tests, a mocked Terraform plan and an authenticated plan. See AWS_PLAN.md for the October 29 preflight and estimate. The reviewed plan was applied October 29, 2026. See LIVE_VERIFICATION.md for the actual results.

## 1. Rebuild and test

From the project root:

```powershell
python -m unittest discover -s tests -v
python tools/build_lambda.py
```

The ZIP includes pinned SDK dependencies from requirements.lock.txt. Its hash is recorded in evidence/lambda-package.json. Core changes require a new build. Preserve a known-good ZIP outside ignored build/ before an actual deployment if you need rollback.

`python tools/bootstrap_terraform.py` can download the official Windows x64 Terraform CLI into a per-user tool cache; the script compares the published SHA-256. It does not change PATH or authenticate. On other platforms, follow the official Terraform installation guide.

## 2. Keep private state and settings outside OneDrive

After signing in as described in AWS_SETUP.md:

```powershell
$env:AWS_PROFILE = 'zak-aws'
$intakePrivate = Join-Path $env:LOCALAPPDATA 'cloud-file-intake-tools'
New-Item -ItemType Directory -Force -Path (Join-Path $intakePrivate 'state') | Out-Null
$env:TF_DATA_DIR = Join-Path $intakePrivate 'terraform-live-data'
cd infra
terraform init -input=false -backend-config="path=$intakePrivate/state/terraform.tfstate"
```

Create a private variable file at `$intakePrivate/private.tfvars.json`, using the fields in infra/terraform.tfvars.example as a guide and JSON syntax. Keep the approved email only in that private file. `python tools/prepare_aws_plan.py` runs initialization and planning with these paths, records a sanitized summary and never applies. Confirm the region and project name; add an email only if you want the notifications. State, plan files and settings may contain private details. They must not be committed or placed in a public artifact.

This starts with one local state owner. Back up that private state securely. Do not run competing Terraform commands from different computers. A managed remote state backend with locking is a later improvement.

## 3. Review the real plan before applying

```powershell
aws sts get-caller-identity
terraform plan -var-file="$intakePrivate/private.tfvars.json" -out="$intakePrivate/review.tfplan"
terraform show "$intakePrivate/review.tfplan"
```

Confirm the target account, region, resource names, permissions, retention and costs. No public buckets or publicly reachable upload API are expected. The budget threshold defaults to USD 5, but does not stop charges. CloudWatch alarms/custom metrics and retained object versions can incur charges even in a tiny workload; check your actual plan/credits and current pricing.

Only when the concrete plan and cost exposure are acceptable:

```powershell
terraform apply "$intakePrivate/review.tfplan"
terraform output -json
```

If an SNS email recipient is configured, confirm the subscription in that inbox. A successful resource creation is not yet proof the pipeline works.

## 4. Live smoke checks for each deployment

Save `terraform output -json` privately and read the raw/results bucket names. From an authorized shell, upload the supplied sample to the raw bucket using a lowercase .csv extension under incoming/:

```powershell
aws s3 cp ../data/samples/weekly-sales.csv "s3://YOUR_RAW_BUCKET/incoming/weekly-sales.csv"
```

Then verify with the console or CLI:

1. Queue receives the notification and Lambda completes a job.
2. Result manifest has 14 inputs, 6 accepted, 7 review, 1 skipped and 2,050 cents.
3. Downloaded artifact hashes match that manifest.
4. Re-upload the identical sample. A new source receipt points to the same content job; totals are unchanged.
5. Upload bad-schema.csv and inspect the quarantined result.
6. Upload a corrected/new object version and verify the notified version is read, even if another upload arrives quickly.
7. In the isolated learning deployment, inject a controlled operational failure; confirm retry, message-failure alarm and dead-letter behavior, restore the configuration, and redrive the message.
8. Test the chosen notification destination and record whether it actually receives an alert.

Keep dated evidence without exposing private raw records or settings. Record which checks actually pass. A configuration readback of retention is not a long-term retention test.

## GitHub automation

The included checks workflow tests the processor, builds the ZIP and runs a mocked Terraform plan without cloud credentials. Hosted checks passed October 29, 2026. Automated deployment remains deferred; the current workflow has no AWS credentials. That later workflow should use a narrowly scoped deployment role, restricted GitHub OIDC trust, an approval environment and locked remote state. [GitHub's AWS OIDC guidance](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws).
