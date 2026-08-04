# GitHub Actions OIDC federation — no long-lived AWS keys in GitHub secrets.
#
# All resources here are conditional on var.create_github_oidc: the flag
# exists ONLY because Floci cannot emulate CreateOpenIDConnectProvider; the
# production root never sets it to false.

data "aws_caller_identity" "current" {}

data "aws_region" "current" {}

locals {
  github_repository = "${var.github_org}/${local.service_name}"
}

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
  thumbprint_list = [
    "6938fd4d98bab03faadb97b34396831e3780aea1",
    "1c58a3a8518e8759bf075b76b750d4f2df264fcd",
  ]
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
            "token.actions.githubusercontent.com:sub" = "repo:${local.github_repository}:ref:refs/heads/main"
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
