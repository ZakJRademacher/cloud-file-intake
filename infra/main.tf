data "aws_caller_identity" "current" {}

locals {
  prefix = "${var.project_name}-${data.aws_caller_identity.current.account_id}-${var.aws_region}"
}

resource "aws_s3_bucket" "raw" {
  bucket        = "${local.prefix}-raw"
  force_destroy = false
}

resource "aws_s3_bucket" "results" {
  bucket        = "${local.prefix}-results"
  force_destroy = false
}

resource "aws_s3_bucket_public_access_block" "private" {
  for_each                = { raw = aws_s3_bucket.raw.id, results = aws_s3_bucket.results.id }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "encrypted" {
  for_each = { raw = aws_s3_bucket.raw.id, results = aws_s3_bucket.results.id }
  bucket   = each.value
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

resource "aws_s3_bucket_versioning" "versioned" {
  for_each = { raw = aws_s3_bucket.raw.id, results = aws_s3_bucket.results.id }
  bucket   = each.value
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_policy" "tls_only" {
  for_each = { raw = aws_s3_bucket.raw, results = aws_s3_bucket.results }
  bucket   = each.value.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid      = "DenyInsecureTransport", Effect = "Deny", Principal = "*", Action = "s3:*",
    Resource = [each.value.arn, "${each.value.arn}/*"], Condition = { Bool = { "aws:SecureTransport" = "false" } }
  }] })
}

resource "aws_s3_bucket_lifecycle_configuration" "raw_retention" {
  bucket     = aws_s3_bucket.raw.id
  depends_on = [aws_s3_bucket_versioning.versioned]
  rule {
    id     = "demo-upload-retention"
    status = "Enabled"
    filter { prefix = "incoming/" }
    expiration { days = 21 }
    noncurrent_version_expiration { noncurrent_days = 21 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "results_retention" {
  bucket     = aws_s3_bucket.results.id
  depends_on = [aws_s3_bucket_versioning.versioned]
  rule {
    id     = "demo-results-retention"
    status = "Enabled"
    filter {}
    expiration { days = 30 }
    noncurrent_version_expiration { noncurrent_days = 7 }
    abort_incomplete_multipart_upload { days_after_initiation = 1 }
  }
}

resource "aws_sqs_queue" "dead_letter" {
  name                      = "${var.project_name}-dead-letter"
  message_retention_seconds = 1209600
  sqs_managed_sse_enabled   = true
}

resource "aws_sqs_queue" "uploads" {
  name                       = "${var.project_name}-uploads"
  visibility_timeout_seconds = 180
  message_retention_seconds  = 345600
  sqs_managed_sse_enabled    = true
  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.dead_letter.arn, maxReceiveCount = 5
  })
}

resource "aws_sqs_queue_redrive_allow_policy" "only_uploads" {
  queue_url = aws_sqs_queue.dead_letter.id
  redrive_allow_policy = jsonencode({
    redrivePermission = "byQueue", sourceQueueArns = [aws_sqs_queue.uploads.arn]
  })
}

resource "aws_sqs_queue_policy" "allow_bucket" {
  queue_url = aws_sqs_queue.uploads.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Sid    = "S3UploadsOnly", Effect = "Allow", Principal = { Service = "s3.amazonaws.com" },
    Action = "sqs:SendMessage", Resource = aws_sqs_queue.uploads.arn,
    Condition = {
      ArnEquals    = { "aws:SourceArn" = aws_s3_bucket.raw.arn },
      StringEquals = { "aws:SourceAccount" = data.aws_caller_identity.current.account_id }
    }
  }] })
}

resource "aws_s3_bucket_notification" "uploads" {
  bucket = aws_s3_bucket.raw.id
  queue {
    queue_arn     = aws_sqs_queue.uploads.arn
    events        = ["s3:ObjectCreated:*"]
    filter_prefix = "incoming/"
    filter_suffix = ".csv"
  }
  depends_on = [aws_sqs_queue_policy.allow_bucket, aws_s3_bucket_versioning.versioned]
}

resource "aws_cloudwatch_log_group" "processor" {
  name              = "/aws/lambda/${var.project_name}"
  retention_in_days = 7
}

resource "aws_iam_role" "processor" {
  name = "${var.project_name}-processor"
  assume_role_policy = jsonencode({ Version = "2012-10-17", Statement = [{
    Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" }
  }] })
}

resource "aws_iam_role_policy" "processor" {
  role = aws_iam_role.processor.id
  policy = jsonencode({ Version = "2012-10-17", Statement = [
    { Effect = "Allow", Action = ["s3:GetObjectVersion"], Resource = "${aws_s3_bucket.raw.arn}/incoming/*" },
    { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = ["${aws_s3_bucket.results.arn}/jobs/*", "${aws_s3_bucket.results.arn}/receipts/*"] },
    # A missing GetObject needs ListBucket permission to produce 404 rather than 403.
    { Effect = "Allow", Action = ["s3:ListBucket"], Resource = aws_s3_bucket.results.arn },
    { Effect = "Allow", Action = ["sqs:ReceiveMessage", "sqs:DeleteMessage", "sqs:GetQueueAttributes", "sqs:ChangeMessageVisibility"], Resource = aws_sqs_queue.uploads.arn },
    { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.processor.arn}:*" }
  ] })
}

resource "aws_lambda_function" "processor" {
  function_name    = var.project_name
  filename         = var.lambda_zip_path
  source_code_hash = filebase64sha256(var.lambda_zip_path)
  handler          = "src.lambda_handler.handler"
  runtime          = "python3.12"
  architectures    = ["x86_64"]
  role             = aws_iam_role.processor.arn
  timeout          = 30
  memory_size      = 256
  # New projects can have a concurrency quota below Lambda's unreserved buffer.
  # Use the shared pool; the SQS mapping below limits this trigger to two jobs.
  reserved_concurrent_executions = -1
  environment {
    variables = { RAW_BUCKET = aws_s3_bucket.raw.id, RESULTS_BUCKET = aws_s3_bucket.results.id }
  }
  depends_on = [aws_cloudwatch_log_group.processor, aws_iam_role_policy.processor]
}

resource "aws_lambda_event_source_mapping" "uploads" {
  event_source_arn        = aws_sqs_queue.uploads.arn
  function_name           = aws_lambda_function.processor.arn
  batch_size              = 1
  function_response_types = ["ReportBatchItemFailures"]
  scaling_config { maximum_concurrency = 2 }
}
