# Operate and recover

## Determine whether a result is published

Require jobs/<id>/manifest.json. CSV objects without a manifest may be remnants of an interrupted run. A completed manifest must describe the expected file set and matching hashes. Do not treat the existence of accepted.csv alone as completion.

Normal statuses: completed, completed_with_review, quarantined. Review rows are data-quality exceptions, not an infrastructure outage. A quarantined file has a permanent file-contract error and a diagnosis. Correct the original source and upload a new version; do not edit generated tables in place.

## Operational failure

The AWS adapter returns a failed SQS message ID when storage access, source lookup, integrity verification or processing cannot complete. Successful messages are acknowledged independently. CloudWatch has a custom MessageFailures metric because partial-batch failures can occur in a Lambda invocation that otherwise returns successfully.

After five receives, the queue's redrive policy sends the failed message to its dead-letter queue. Inspect the message privately, the job/message IDs in logs, and the exact source object version. Check permissions, available source versions, object size and the manifest/output integrity. The logs intentionally omit raw rows and full keys.

Fix the cause before redriving. Do not repeatedly redrive an oversized source or invalid notification. A source over the demo limit needs to be split or processed by a separately designed path. Raw versions have 21-day retention; very late redrive after expiry may require restoring an archived source. Alerts and recovery are not live-verified yet.

## Partial output or corrupt completed output

A failed write before the manifest can be retried normally. Deterministic artifacts are overwritten with the same complete values, then the manifest publishes.

If a completed manifest exists but an output fails its hash/size check, processing fails instead of reusing it. Preserve the evidence. In a learning deployment, inspect object versions and determine which content was altered. Restore a consistent previously verified set, or deliberately remove only the corrupted completion marker before an authorized rebuild from the exact source. Never delete objects broadly to clear an error.

The local recovery test injects a write failure before summary.csv, verifies that no completion manifest exists and retries successfully. See evidence/local-verification.json and tests/test_jobs.py. This is distinct from a live AWS failure drill.

## Roll back code

Keep the previous verified Lambda ZIP/hash and matching source revision. Restore that source and ZIP, review the Terraform plan, then apply the code change. Rerun the smoke test. A rollback does not automatically undo previously generated artifacts.

Change CONTRACT_VERSION when business rules or output semantics change. Otherwise a content hash may reuse a result produced by an older rule. A bad contract release requires an explicit version/reprocessing decision, not merely a code rollback.

## Cost and cleanup

- Use one region and fictional small files. Inspect actual billing/credits and alerts after deployment.
- Default retention: raw current/noncurrent versions 21 days; results 30 days; result noncurrent versions 7 days; function logs 7 days. These are demo settings, not client retention commitments.
- A budget notification threshold is not a spending cap. Optional SNS email requires confirmation. No recipient means no email delivery.
- Before teardown, export any desired evidence and inspect both bucket contents and object versions. Buckets have force_destroy=false to prevent silent data removal.
- Review `terraform plan -destroy` with the same private state/variables. Empty/version-delete buckets only after the owner has explicitly decided to remove that data. An apply can otherwise destroy some resources and then stop on nonempty buckets; understand the plan before proceeding.
- After authorized teardown, verify queues, functions, alarms, logs, topics, budgets and all bucket versions are removed or intentionally retained. Check billing again later for delayed usage records.

## First-version limitations

No cross-file warehouse, public intake portal, user accounts, service-level objective, live load test, managed remote Terraform state or automated deployment exists yet. The console binds only to 127.0.0.1. Development tests use fictional files and a fake object store; they do not certify AWS security or production readiness.
