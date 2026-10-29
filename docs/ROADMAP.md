# A learning path with concrete exit checks

## Stage 1 — local foundation

Built: pure Python file contract, accepted/review/skipped/summary exports, replay-safe job identity, source receipts, manifest-last publication, integrity checks, recovery tests, local CLI/browser lab, fictional fixtures and sample deliverables.

Prepared: S3/SQS/Lambda Terraform, private buckets and execution role, retries/DLQ, logs/alarms, budget threshold and a credential-free GitHub checks workflow.

Your exit check: trace the sample, explain its 14-row reconciliation, identify the conflicting ID and describe why a second run does not add to the total. Read FIRST_SESSION.md.

## Stage 2 — first AWS deployment

Create your account, choose an eligible plan/region, set up temporary authentication and review the actual Terraform plan/costs. Deploy in an isolated learning project. Complete every live smoke check in DEPLOYMENT.md, including alert delivery and a controlled failure/redrive. Keep honest evidence of what worked and what did not.

Exit check: explain what S3, SQS, Lambda, IAM and CloudWatch each do, locate a failed message and recover it without editing generated totals.

## Stage 3 — delivery and operations

Create the GitHub repository when the foundation is ready to share. Verify hosted CI, then add a restricted deployment role with GitHub OIDC, an approval environment and a remote state backend with locking. Demonstrate deploying a change and rolling it back. Do not count a workflow YAML file as a successful deployment demonstration.

Exit check: rebuild the same infrastructure from source, explain the permissions and know how to remove the deployment and inspect remaining costs.

## Stage 4 — connect it to analytics engineering

Agree a cross-file data model before adding cumulative reports. Introduce Parquet, an Athena catalog/query layer or a separate SQL warehouse only when its purpose is clear. Add dbt where it fits that model. Preserve grain, late-arriving corrections and repeat-file behavior. A dashboard should read a defined published snapshot rather than add all job folders together.

Exit check: demonstrate a source correction flowing through a reproducible model into a reconciled report.

These stages are learning milestones, not a promise of employability or a fixed calendar. Repeat unfamiliar concepts until you can explain and operate them.
