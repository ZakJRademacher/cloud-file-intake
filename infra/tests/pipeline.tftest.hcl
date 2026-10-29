mock_provider "aws" {
  mock_data "aws_caller_identity" {
    defaults = { account_id = "123456789012" }
  }
}

override_resource {
  target          = aws_sqs_queue.dead_letter
  override_during = plan
  values          = { arn = "arn:aws:sqs:us-east-2:123456789012:mock-dead-letter" }
}

run "private_replay_safe_pipeline" {
  command = plan
  assert {
    condition     = aws_s3_bucket.raw.force_destroy == false && aws_s3_bucket.results.force_destroy == false
    error_message = "Demo teardown must not silently delete uploaded data."
  }
  assert {
    condition     = alltrue([for bucket in aws_s3_bucket_public_access_block.private : bucket.block_public_acls && bucket.block_public_policy && bucket.ignore_public_acls && bucket.restrict_public_buckets])
    error_message = "Both data buckets must block public access."
  }
  assert {
    condition     = aws_s3_bucket_versioning.versioned["raw"].versioning_configuration[0].status == "Enabled"
    error_message = "The processor requires versioned raw uploads."
  }
  assert {
    condition     = aws_sqs_queue.uploads.visibility_timeout_seconds >= 6 * aws_lambda_function.processor.timeout
    error_message = "The retry visibility interval must cover six function timeouts."
  }
  assert {
    condition     = contains(aws_lambda_event_source_mapping.uploads.function_response_types, "ReportBatchItemFailures")
    error_message = "Individual failed messages must be retried without replaying a successful batch."
  }
  assert {
    condition     = jsondecode(aws_sqs_queue.uploads.redrive_policy).maxReceiveCount == 5
    error_message = "Repeated operational failures must have a dead-letter destination."
  }
  assert {
    condition     = aws_lambda_event_source_mapping.uploads.scaling_config[0].maximum_concurrency == 2
    error_message = "The upload trigger must not run more than two jobs concurrently."
  }
  assert {
    condition     = aws_lambda_function.processor.reserved_concurrent_executions == -1
    error_message = "Use the shared pool so the learning deployment supports new-project quotas."
  }
  assert {
    condition     = aws_budgets_budget.learning.cost_types[0].include_credit == false
    error_message = "Credits must not hide usage from the learning budget alert."
  }
}
