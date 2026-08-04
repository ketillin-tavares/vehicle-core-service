variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "github_org" {
  description = "GitHub organization/user that owns the vehicle-core-service repository. Used to pin the OIDC trust policy (no wildcards)."
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the application host."
  type        = string
  default     = "t3.micro"
}

variable "create_github_oidc" {
  description = "Create the GitHub OIDC provider + deploy role. Set to false ONLY in the Floci local root (the emulator does not support CreateOpenIDConnectProvider)."
  type        = bool
  default     = true
}

variable "aws_endpoint_url" {
  description = "Custom AWS API endpoint (Floci local emulator, e.g. http://localhost:4566). Leave null for real AWS."
  type        = string
  default     = null
}
