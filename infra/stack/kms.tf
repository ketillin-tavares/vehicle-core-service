# --- KMS CMK for the SSM SecureString parameters (security item M3) -------
#
# With the account-default alias/aws/ssm key, ANY principal allowed to call
# ssm:GetParameter --with-decryption can read every service's SecureStrings.
# A dedicated CMK gates decryption of THIS service's parameters by this key
# policy: only the instance role (and account admins via root delegation)
# can decrypt. Cost: USD 1/mo per CMK + negligible request charges.

resource "aws_kms_key" "ssm" {
  description         = "${local.service_name}: encrypts the service's SSM SecureString parameters"
  enable_key_rotation = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        # Root delegation: key administration via normal IAM policies
        # (TFC run role, human admins). Standard KMS pattern — without it
        # the key becomes unmanageable.
        Sid       = "AccountRootAdmin"
        Effect    = "Allow"
        Principal = { AWS = "arn:aws:iam::${data.aws_caller_identity.current.account_id}:root" }
        Action    = "kms:*"
        Resource  = "*"
      },
      {
        # deploy.sh on the instance: ssm get-parameter --with-decryption.
        # Decrypt only, and only through SSM in this region.
        Sid       = "InstanceRoleDecryptViaSsm"
        Effect    = "Allow"
        Principal = { AWS = aws_iam_role.instance.arn }
        Action    = "kms:Decrypt"
        Resource  = "*"
        Condition = {
          StringEquals = {
            "kms:ViaService" = "ssm.${data.aws_region.current.name}.amazonaws.com"
          }
        }
      }
    ]
  })
}

resource "aws_kms_alias" "ssm" {
  name          = "alias/${local.service_name}-ssm"
  target_key_id = aws_kms_key.ssm.key_id
}
