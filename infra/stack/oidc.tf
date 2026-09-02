# GitHub Actions OIDC federation — no long-lived AWS keys in GitHub secrets.
#
# All resources here are conditional on var.create_github_oidc: the flag
# exists ONLY because Floci cannot emulate CreateOpenIDConnectProvider; the
# production root never sets it to false.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  github_repository = "${var.github_org}/${local.service_name}"

  # Two exact forms of the OIDC `sub` claim, both pinned in the trust policy.
  #
  # GitHub currently emits the IMMUTABLE-IDENTIFIER form: owner and repository
  # names each carry an `@<numeric id>` suffix (confirmed via CloudTrail — the
  # `userName` of an AssumeRoleWithWebIdentity event IS the `sub` claim). The
  # plain-name form is kept so the deploy does not break if the emitted format
  # changes back. Both are exact strings under StringEquals (arrays are
  # evaluated as OR), so the trust boundary is unchanged — no wildcards.
  github_subject_by_name = "repo:${local.github_repository}:ref:refs/heads/main"
  github_subject_by_id   = "repo:${var.github_org}@${var.github_owner_id}/${local.service_name}@${var.github_repository_id}:ref:refs/heads/main"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]

  # SHARED, ACCOUNT-WIDE RESOURCE. AWS allows exactly one OIDC provider per
  # URL per account, so vehicle-sales-service does NOT create its own — its
  # stack reads this one with a data source and its deploy role trusts it.
  # Destroying it here would silently break that service's CD; prevent_destroy
  # turns that into a loud plan-time error naming this resource.
  # Tearing the whole account down therefore requires a DELIBERATE
  # `terraform state rm aws_iam_openid_connect_provider.github` (after the
  # sales stack is gone), or temporarily removing this block.
  #
  # >>> TEMPORARILY DISABLED FOR A FULL-ACCOUNT TEARDOWN <<<
  # The vehicle-sales-service stack must already be destroyed. RESTORE THIS
  # BLOCK before the next apply, otherwise the guard is gone for good.
  # lifecycle {
  #   prevent_destroy = true
  # }
}

# Deploy role: assumable ONLY by this repo's main branch (security item 2 —
# exact StringEquals on aud and sub, no wildcards).
resource "aws_iam_role" "deploy" {
  count = var.create_github_oidc ? 1 : 0

  name = "${local.service_name}-deploy"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Federated = aws_iam_openid_connect_provider.github[0].arn }
        Action    = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
            "token.actions.githubusercontent.com:sub" = [
              local.github_subject_by_name,
              local.github_subject_by_id,
            ]
          }
        }
      }
    ]
  })
}

# Least-privilege deploy policy (security item 5 + ECR push):
# - ssm:SendCommand restricted to the AWS-RunShellScript document AND to
#   instances carrying the Service tag;
# - ssm:GetCommandInvocation to read command results;
# - ec2:DescribeInstances so CD can resolve the instance id by tag
#   (read-only; not resource-scopable, by AWS design);
# - ECR auth + push limited to the app repository;
# - nothing else.
resource "aws_iam_role_policy" "deploy" {
  count = var.create_github_oidc ? 1 : 0

  name = "${local.service_name}-deploy-policy"
  role = aws_iam_role.deploy[0].id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "SendCommandDocument"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ssm:${data.aws_region.current.name}::document/AWS-RunShellScript"
      },
      {
        Sid      = "SendCommandTaggedInstance"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = "arn:aws:ec2:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:instance/*"
        Condition = {
          StringEquals = {
            "ssm:resourceTag/Service" = local.service_name
          }
        }
      },
      {
        Sid      = "ReadCommandResult"
        Effect   = "Allow"
        Action   = "ssm:GetCommandInvocation"
        Resource = "arn:aws:ssm:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:*"
      },
      {
        Sid      = "ResolveInstanceByTag"
        Effect   = "Allow"
        Action   = "ec2:DescribeInstances"
        Resource = "*" # read-only; not resource-scopable, by AWS design
      },
      {
        Sid      = "EcrAuthToken"
        Effect   = "Allow"
        Action   = "ecr:GetAuthorizationToken"
        Resource = "*" # not resource-scopable, by AWS design
      },
      {
        Sid    = "EcrPushAppRepo"
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = aws_ecr_repository.app.arn
      }
    ]
  })
}
