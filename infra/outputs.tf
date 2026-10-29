output "raw_bucket" { value = aws_s3_bucket.raw.id }
output "results_bucket" { value = aws_s3_bucket.results.id }
output "upload_queue_url" { value = aws_sqs_queue.uploads.id }
output "dead_letter_queue_url" { value = aws_sqs_queue.dead_letter.id }
output "processor_name" { value = aws_lambda_function.processor.function_name }
output "log_group" { value = aws_cloudwatch_log_group.processor.name }
output "alerts_topic_arn" { value = aws_sns_topic.alerts.arn }
