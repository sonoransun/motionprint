variable "domain_name" {
  type        = string
  description = "Root domain for the service (e.g., motionprint.example.com)"
}

variable "image_tag" {
  type        = string
  description = "Container image tag to deploy"
  default     = "latest"
}

variable "gcp_project_id" {
  type        = string
  description = "GCP project ID"
}

variable "aws_certificate_arn_us_east_1" {
  type        = string
  description = "ACM certificate ARN in us-east-1"
}

variable "aws_certificate_arn_us_west_2" {
  type        = string
  description = "ACM certificate ARN in us-west-2"
}
