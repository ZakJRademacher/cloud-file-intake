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
| SNS subscription | The authorized alert email subscription is confirmed. Email arrival is checked separately from subscription status. |

[Initial check record](../evidence/live-initial-check.json) · [Replay/version record](../evidence/live-replay-and-versions.json)

## Controlled recovery drill

A fictional recovery fixture is being tested through native queue retries. Dead-letter handling, repair and redrive will be recorded here after verification. No client data or real operating workload is involved. The queue retains its normal 180-second visibility timeout during the drill.

## Limits of the evidence

These checks do not establish production availability, throughput, arbitrary-file safety, multi-file business deduplication or a warehouse. The local browser lab makes no AWS requests. Budget-alert delivery, large-scale performance, disaster recovery, code rollback and automated cloud deployment are not established by these results.

The earlier October 28 local-foundation evidence is retained as historical evidence; its undeployed status describes that stage. Current cloud claims use this record and the later live evidence.
