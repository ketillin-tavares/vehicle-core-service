# PRODUCTION root — HCP Terraform (CLI-driven: remote execution + state).
# This is what .github/workflows/infra.yml runs.
#
# The `cloud` block does not accept Terraform variables; organization and
# workspace come from environment variables (set locally and in CI):
#
#   TF_CLOUD_ORGANIZATION = <your HCP Terraform organization>
#   TF_WORKSPACE          = vehicle-core-infra
terraform {
  required_version = ">= 1.6.0"

  cloud {}
}

variable "github_org" {
  description = "GitHub organization/user that owns the vehicle-core-service repository."
  type        = string
}

variable "aws_region" {
  description = "AWS region for all resources."
  type        = string
  default     = "us-east-1"
}

variable "instance_type" {
  description = "EC2 instance type for the application host."
  type        = string
  default     = "t3.micro"
}

module "stack" {
  source = "../stack"

  github_org    = var.github_org
  aws_region    = var.aws_region
  instance_type = var.instance_type
}

output "instance_id" {
  description = "EC2 instance id of the application host."
  value       = module.stack.instance_id
}

output "elastic_ip" {
  description = "Public Elastic IP of the application host."
  value       = module.stack.elastic_ip
}

output "deploy_role_arn" {
  description = "ARN of the GitHub Actions OIDC deploy role (save as AWS_ROLE_ARN repo secret)."
  value       = module.stack.deploy_role_arn
}

output "ecr_repository_url" {
  description = "URL of the ECR repository holding the app images."
  value       = module.stack.ecr_repository_url
}

output "db_endpoint" {
  description = "RDS PostgreSQL endpoint address."
  value       = module.stack.db_endpoint
}

output "db_port" {
  description = "RDS PostgreSQL port."
  value       = module.stack.db_port
}

output "db_master_secret_arn" {
  description = "ARN of the RDS-managed master password secret in Secrets Manager."
  value       = module.stack.db_master_secret_arn
}

output "ssm_parameter_prefix" {
  description = "SSM Parameter Store prefix holding the app runtime env."
  value       = module.stack.ssm_parameter_prefix
}
