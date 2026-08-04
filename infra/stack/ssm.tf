# Runtime configuration for the app. deploy/deploy.sh materializes these
# into /opt/vehicle-core-service/.env on the instance at deploy time.
#
# Two groups:
# 1. app_env — SecureString placeholders; REAL values are set out-of-band
#    with `aws ssm put-parameter --overwrite` and never overwritten back by
#    Terraform (lifecycle.ignore_changes on value — security item 7).
# 2. db_config — plain String values OWNED by Terraform (derived from the
#    RDS instance; not secrets). DATABASE_PASSWORD itself is NOT in SSM:
#    it lives in the RDS-managed Secrets Manager secret, referenced by
#    DATABASE_PASSWORD_SECRET_ARN.

locals {
  app_env_keys = [
    "SALES_SERVICE_BASE_URL",
    "SALES_SERVICE_TIMEOUT_SECONDS",
    "INTERNAL_API_TOKEN",
    "SERVICE_NAME",
    "DEBUG",
    "LOG_LEVEL",
  ]

  db_config = {
    DATABASE_HOST                = aws_db_instance.app.address
    DATABASE_PORT                = tostring(aws_db_instance.app.port)
    DATABASE_USER                = aws_db_instance.app.username
    DATABASE_NAME                = aws_db_instance.app.db_name
    DATABASE_PASSWORD_SECRET_ARN = aws_db_instance.app.master_user_secret[0].secret_arn
  }

  ssm_parameter_prefix = "/${local.service_name}"
}

resource "aws_ssm_parameter" "app_env" {
  for_each = toset(local.app_env_keys)

  name   = "${local.ssm_parameter_prefix}/${each.key}"
  type   = "SecureString"
  key_id = aws_kms_key.ssm.arn # dedicated CMK, not alias/aws/ssm (item M3)
  value  = "CHANGE_ME"         # placeholder — set the real value out-of-band

  lifecycle {
    ignore_changes = [value]
  }
}

resource "aws_ssm_parameter" "db_config" {
  for_each = local.db_config

  name  = "${local.ssm_parameter_prefix}/${each.key}"
  type  = "String"
  value = each.value
}
