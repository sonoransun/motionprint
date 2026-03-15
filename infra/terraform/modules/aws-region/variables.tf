variable "project_name" {
  type    = string
  default = "motionprint"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "aws_region" {
  type = string
}

variable "vpc_cidr" {
  type    = string
  default = "10.0.0.0/16"
}

variable "container_image" {
  type        = string
  description = "Full ECR image URI with tag"
}

variable "container_port" {
  type    = number
  default = 3000
}

variable "task_cpu" {
  type    = number
  default = 4096
}

variable "task_memory" {
  type    = number
  default = 8192
}

variable "max_concurrent_renders" {
  type    = number
  default = 4
}

variable "cache_max_bytes" {
  type    = number
  default = 2147483648
}

variable "desired_count" {
  type    = number
  default = 2
}

variable "min_capacity" {
  type    = number
  default = 2
}

variable "max_capacity" {
  type    = number
  default = 20
}

variable "cpu_target_value" {
  type    = number
  default = 65
}

variable "certificate_arn" {
  type        = string
  description = "ACM certificate ARN for HTTPS"
}

variable "ephemeral_storage_gib" {
  type    = number
  default = 30
}

variable "tags" {
  type    = map(string)
  default = {}
}
