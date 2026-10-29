# AWS developer setup

This project was deployed in **us-east-2** on October 29, 2026, using temporary local-development credentials under profile `zak-aws`. See [LIVE_VERIFICATION.md](LIVE_VERIFICATION.md) for the checks actually completed.

## Authenticate

Install AWS CLI v2 from the [official guide](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html). For supported local identities, use a temporary browser session:

```powershell
aws configure set region us-east-2 --profile zak-aws
aws login --profile zak-aws
aws sts get-caller-identity --profile zak-aws
$env:AWS_PROFILE = 'zak-aws'
$env:AWS_REGION = 'us-east-2'
```

The login flow requires AWS CLI 2.32.0 or later. IAM Identity Center users should retain their established SSO flow. Do not create root access keys or store credentials in this repository. [Local-development sign-in](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html).

## Review your own environment

A fork of this repository does not grant access to the original deployment. Confirm your project's Region in AWS Settings and review its plan, credits, supported services, quotas and permissions before provisioning anything. Regional resources must use the project's assigned Region.

The deployment uses S3, SQS, Lambda, IAM, CloudWatch, SNS and Budgets. Check [supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html) for your actual plan. A successful Terraform plan does not prove runtime or alert delivery behavior.

Keep private variables, full plans, state and logs outside shared folders. See [DEPLOYMENT.md](DEPLOYMENT.md) for the prepared workflow. The sample USD 5 budget is an alert threshold, not a spending cap. It excludes credits and refunds so they do not conceal underlying usage.
