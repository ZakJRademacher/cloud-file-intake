# Live AWS verification - October 29, 2026

The Terraform deployment created 29 resources/configuration objects in us-east-2. Lambda is active and its SQS event source mapping is enabled. Source/result buckets block all public access and have versioning enabled. Full state, resource identifiers, source-version receipts and provider logs remain private.

## Completed live checks

| Check | Evidence and result |
| --- | --- |
| Upload to processing | An actual signed S3 upload reached SQS, invoked Lambda and produced an S3 manifest plus four CSV files. |
| Row reconciliation | 14 inputs = 6 accepted + 7 for review + 1 skipped; net accepted amount 2,050 cents. |
| Output integrity | Manifest, all four output files, sizes and SHA-256 hashes match the independent local expected artifacts. |
| Safe replay | A second S3 object version with identical bytes points to the same content job; separate source receipts retain both versions. |
| Exact source version | Two versions of the same key were queued while the mapping was paused, then processed after re-enabling it. Their respective totals are 100 and 300 cents. |
| Bad schema | An incomplete file contract produces a quarantined manifest and diagnosis. |
| Partial failure monitoring | A deliberately corrupt test manifest caused a native failed-message log and the custom MessageFailures alarm entered ALARM. |
| Operational alert delivery | SNS email subscription is confirmed and actual CloudWatch failure-alert emails arrived in the authorized inbox. |
| Hosted CI | GitHub Actions passed all checks for publication commit bdaa73f3a6270c6c36bdf7b65f0fa87cdb2953ae. |

[Initial check record](../evidence/live-initial-check.json) · [Replay/version record](../evidence/live-replay-and-versions.json)

## Controlled recovery drill

A deliberately corrupt completion marker was written for one fictional recovery fixture. The real Lambda consumer logged five native failed attempts for the same message, using the normal 180-second visibility timeout. SQS then moved the message to its dead-letter queue.

The corrupted marker was masked with a recoverable versioned delete marker. AWS native message redrive moved the one message back to the source queue. Lambda then processed the source afresh (`reused=false`), producing one accepted row and 250 net cents. All four outputs and their hashes matched the independent expected result. The dead-letter queue was empty afterward. No client data or real operating workload was used.

[Recovery evidence](../evidence/live-recovery-check.json). The post-deployment Terraform plan found **no infrastructure changes required** after testing; the mapping pause was restored. [Configuration check](../evidence/post-deployment-configuration.json).

[Hosted checks](https://github.com/ZakJRademacher/cloud-file-intake/actions/runs/40919114761) verify tests, package build/smoke check and Terraform validation/mocked plan. They do not deploy to AWS.

## Limits of the evidence

These checks do not establish production availability, throughput, arbitrary-file safety, multi-file business deduplication or a warehouse. The local browser lab makes no AWS requests. The budget configuration and threshold were read back successfully, but a real spending-threshold email was not forced. Large-scale performance, disaster recovery, code rollback and automated cloud deployment are not established by these results.

The earlier October 28 local-foundation evidence is retained as historical evidence; its undeployed status describes that stage. Current cloud claims use this record and the later live evidence.
