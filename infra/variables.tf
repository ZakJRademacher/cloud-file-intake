variable "aws_region" {
  type        = string
  description = "Use one region for both S3 and SQS/Lambda."
  default     = "us-east-2"
}

variable "project_name" {
  type    = string
  default = "zak-file-intake"
  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,23}$", var.project_name))
    error_message = "Use 3–24 lowercase letters, digits or hyphens, starting with a letter."
  }
}

variable "lambda_zip_path" {
  type    = string
  default = "../build/lambda.zip"
}

variable "notification_email" {
  type        = string
  default     = null
  nullable    = true
  description = "Optional private email; supplied in a git-ignored tfvars file. Requires SNS email confirmation."
}

variable "monthly_budget_usd" {
  type        = number
  default     = 5
  description = "Account-wide notification threshold; this is NOT a spending cap."
  validation {
    condition     = var.monthly_budget_usd > 0
    error_message = "The budget threshold must be positive."
  }
}
