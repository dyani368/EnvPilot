variable "environment_id" {
  type = string
  validation {
    condition     = can(regex("^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", var.environment_id))
    error_message = "environment_id must be a lowercase UUID."
  }
}

variable "expires_at" {
  type = string
  validation {
    condition     = can(formatdate("YYYY-MM-DD'T'hh:mm:ss'Z'", var.expires_at))
    error_message = "expires_at must be a timestamp."
  }
}

variable "aws_region" {
  type    = string
  default = "ap-southeast-2"
  validation {
    condition     = var.aws_region == "ap-southeast-2"
    error_message = "Only the reviewed Sydney region is allowed."
  }
}

variable "vpc_id" { type = string }
variable "subnet_id" { type = string }
