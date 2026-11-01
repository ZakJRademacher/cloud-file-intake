# Architecture and operating limits

## Core first

`src/processor.py` takes the bounded CSV bytes and returns accepted/review/skipped records, category totals, and repeatable outputs. It does not read files or make network requests. `src/jobs.py` adds content identity, storage, integrity checks and the final manifest. `src/storage.py` provides local and S3 adapters. The local CLI and browser run the same core as the deployed Lambda adapter.

The browser console executes files synchronously on this computer. It does not emulate queue timing, AWS permissions, network behavior, pricing or service availability. Fake S3 in unit tests verifies adapter calls and response handling, not AWS itself.

## Cloud path

1. Upload a lowercase .csv filename under incoming/ in a private S3 raw bucket.
2. S3 sends an ObjectCreated notification to a standard SQS queue. The queue policy accepts only that bucket and AWS account.
3. Lambda receives one message per invocation, reads the exact version from the notification and applies the same file contract.
4. Valid files produce accepted/review/skipped/summary CSVs; malformed files produce a quarantine diagnosis. The private results bucket stores each result under jobs/<content-id>/.
5. The manifest is written last. Receipts map individual upload object versions to the result.
6. Transient/operational failures return their SQS message ID as failed. SQS redrives repeated failures to a dead-letter queue after five receives.

AWS documents at-least-once delivery for [S3 notifications](https://docs.aws.amazon.com/AmazonS3/latest/userguide/EventNotifications.html) and [Lambda SQS event sources](https://docs.aws.amazon.com/lambda/latest/dg/with-sqs.html). This design expects duplication and out-of-order delivery. Reading the notified version avoids processing a newer overwritten object by mistake.

## Publication and concurrency

Outputs depend only on the complete source bytes and sales-v1 contract. Two identical concurrent jobs write identical bytes to identical keys; neither increments a shared total. The manifest is the only completed-job marker. Reuse verifies its expected file set, hashes and byte sizes. A missing or corrupt output under a completed manifest raises an operational failure rather than silently serving it.

Local writes use a temporary file and atomic replacement. S3 object writes are separate objects; there is no multi-object transaction. A consumer must require the manifest and should verify its hashes. This is a small content-addressed artifact workflow, not a distributed database or exactly-once queue.

## Permissions and observability

Both buckets block public access, require TLS by bucket policy and use S3-managed encryption. Raw access is GetObjectVersion under incoming/. The function can read/write only result/receipt prefixes, list the results bucket to distinguish missing objects from denied access, read its queue and write its log streams. It does not delete source data or manage infrastructure.

Versioning preserves source identity. Raw current/noncurrent versions have 21-day demonstration retention, covering the 4-day source queue plus 14-day dead-letter retention window. Result objects have 30-day retention and noncurrent versions 7 days. Lifecycle expiry can remove data; set retention intentionally before any real use.

The function has a 30-second timeout and 256 MB memory. Its SQS mapping limits this trigger to two simultaneous jobs. The function uses the shared concurrency pool because the verified new-project quota is 10, below the buffer required to reserve capacity. This trigger limit does not cap direct or future unrelated invocations. Queue visibility is 180 seconds, matching AWS's six-timeout recommendation. Partial batch responses are enabled even though the initial batch size is one. [AWS queue configuration guidance](https://docs.aws.amazon.com/lambda/latest/dg/services-sqs-configure.html).

Structured JSON logs contain job/message IDs, statuses and error types, not rows or full source keys. Alarms cover unhandled Lambda errors, individual message failures and visible dead-letter messages. Optional SNS email requires confirmation. A separate account-wide budget is an alert threshold, not an enforced cap. Operational failure-alert email delivery was verified on October 29, 2026. Budget-threshold email delivery is a separate check; a real cost threshold was not forced.

## Later additions

Athena/Parquet, cross-file aggregation, a public authenticated intake portal, deploy-role OIDC and a managed Terraform state backend are later stages. No VPC, NAT gateway, always-on database or Kubernetes cluster is needed for this first workflow. Network engineering and container operations would be separate learning exercises.
