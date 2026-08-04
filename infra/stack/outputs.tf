output "instance_id" {
  description = "EC2 instance id of the application host."
  value       = aws_instance.app.id
}

output "elastic_ip" {
  description = "Public Elastic IP of the application host."
  value       = aws_eip.app.public_ip
}

output "deploy_role_arn" {
  description = "ARN of the GitHub Actions OIDC deploy role (save as AWS_ROLE_ARN repo secret). Null when create_github_oidc = false (Floci local runs only)."
  value       = var.create_github_oidc ? aws_iam_role.deploy[0].arn : null
}

output "ecr_repository_url" {
  description = "URL of the ECR repository holding the app images."
  value       = aws_ecr_repository.app.repository_url
}

output "db_endpoint" {
  description = "RDS PostgreSQL endpoint address."
  value       = aws_db_instance.app.address
}

output "db_port" {
  description = "RDS PostgreSQL port."
  value       = aws_db_instance.app.port
}

output "db_master_secret_arn" {
  description = "ARN of the RDS-managed master password secret in Secrets Manager."
  value       = aws_db_instance.app.master_user_secret[0].secret_arn
}

output "ssm_parameter_prefix" {
  description = "SSM Parameter Store prefix holding the app runtime env."
  value       = local.ssm_parameter_prefix
}
