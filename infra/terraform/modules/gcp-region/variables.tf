variable "project_id" {
  type = string
}

variable "project_name" {
  type    = string
  default = "motionprint"
}

variable "environment" {
  type    = string
  default = "production"
}

variable "gcp_region" {
  type = string
}

variable "container_image" {
  type        = string
  description = "Full Artifact Registry image URI with tag"
}

variable "container_port" {
  type    = number
  default = 3000
}

variable "cpu_limit" {
  type    = string
  default = "4"
}

variable "memory_limit" {
  type    = string
  default = "8Gi"
}

variable "max_concurrent_renders" {
  type    = number
  default = 4
}

variable "cache_max_bytes" {
  type    = number
  default = 2147483648
}

variable "min_instances" {
  type    = number
  default = 1
}

variable "max_instances" {
  type    = number
  default = 20
}

variable "concurrency" {
  type    = number
  default = 10
}

variable "timeout_seconds" {
  type    = number
  default = 60
}
