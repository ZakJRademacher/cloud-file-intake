# AWS deployment review - October 29, 2026

**Applied October 29, 2026.** The reviewed Terraform plan created 29 resources/configuration objects with no updates or deletions. Region: **us-east-2**. Profile: **zak-aws**.

## What it creates

| Component | Purpose |
| --- | --- |
| Two private, versioned S3 buckets | Original uploads and checked outputs/receipts |
| Standard SQS queue and dead-letter queue | Buffer uploads, retry failures and isolate repeated failures |
| One Python 3.12 Lambda | Run the existing bounded CSV processor |
| One restricted execution role/policy | Read notified source versions, write results, receive queue messages and log |
| Log group, failure metric and three alarms | Observe failed messages, Lambda errors and dead letters |
| SNS topic and email subscription | Send processing alerts to the authorized recipient |
| Monthly USD 5 budget | Email when actual usage exceeds 80%, excluding credits/refunds |
| Bucket/queue configuration and event mapping | Encryption, public-access blocks, TLS, retention and event delivery |

The 29 objects include configuration and policies; this is not 29 servers. There is no public upload endpoint, VPC, NAT gateway or always-on database in this plan.

## Verified project plan and estimate

The project used an active Free plan at deployment. Private credit balances and billing identifiers are kept outside the public repository. The selected Region's Lambda concurrency quota is 10. The function uses the shared pool; its SQS trigger caps itself at two simultaneous jobs. That cap does not limit direct or future unrelated invocations.

A light-use scenario of 1,000 small uploads per month produces a calculated **USD 1.17 subtotal** before credits or free allowances. Budget roughly **USD 1-2 per month** for this learning workload. This is an estimate, not a maximum. The subtotal excludes SNS delivery/publish fees, archived logs, transfers/downloads and taxes. Actual usage and service pricing determine the total. Full assumptions and rates are in [cost-estimate.json](../evidence/cost-estimate.json).

The USD 5 budget sends its actual-cost alert above **USD 4**, using the user's approved email stored only in the private settings file. **A budget is not a spending cap**, and billing data/alerts can be delayed. SNS operational alerts require the recipient to confirm a subscription after deployment. Delivery has not been tested.

The Free plan has no usage charges unless converted to a Paid plan or paid-only features are activated. Its free period ends at six months or when credits run out, whichever comes first. No plan upgrade was made. [AWS Free Tier](https://aws.amazon.com/free/).

## Validation and artifact handling

- All 20 application tests pass.
- Existing ZIP matches current packaged source and its recorded SHA-256; its SDK smoke check passes with stubbed calls.
- Terraform formatting, validation and mocked plan pass after the quota correction.
- The authenticated plan is complete/applyable with 29 creates, no changes and no destroys. A successful plan does not guarantee every creation permission or live runtime behavior.
- Both buckets block public access. Source versions are retained for 21 days, results for 30 days, noncurrent result versions for 7 days and logs for 7 days.

Private variable file, provider cache, full plan, plan JSON, future state and command logs remain in Windows local application data outside OneDrive. [Sanitized plan summary](../evidence/authenticated-plan-summary.json) retains useful public evidence in this project. Detailed billing and identity preflight results are private.

Run `python tools/prepare_aws_plan.py` to prepare a new authenticated plan without applying it, after creating the private variable file described in [DEPLOYMENT.md](DEPLOYMENT.md). Applying a future reviewed plan consumes AWS credits and may create or change resources. See [LIVE_VERIFICATION.md](LIVE_VERIFICATION.md) for the actual results of this deployment.
