data "aws_caller_identity" "current" {}

locals {
  account_id      = data.aws_caller_identity.current.account_id
  env_param_path  = "/${var.project}/env"
  env_param_arn   = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter${local.env_param_path}"
  e2e_param_path  = "/${var.project}/e2e"
  e2e_param_arn   = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter${local.e2e_param_path}"
  ci_param_arn    = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project}/ci"
  config_arn      = "arn:aws:ssm:${var.aws_region}:${local.account_id}:parameter/${var.project}/config"
  run_shell_doc   = "arn:aws:ssm:${var.aws_region}::document/AWS-RunShellScript"
  oidc_provider   = "token.actions.githubusercontent.com"
  oidc_provider_a = "arn:aws:iam::${local.account_id}:oidc-provider/${local.oidc_provider}"
}

resource "aws_iam_user" "media" {
  name = "${var.project}-media"
}

resource "aws_iam_user_policy" "media" {
  name = "${var.project}-media-s3"
  user = aws_iam_user.media.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AppMediaObjects"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:AbortMultipartUpload",
        ]
        Resource = "${aws_s3_bucket.media.arn}/media/*"
      },
      {
        Sid      = "AppExports"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.media.arn}/exports/*"
      },
      {
        Sid      = "AppStoppedShareFiles"
        Effect   = "Allow"
        Action   = "s3:DeleteObject"
        Resource = "${aws_s3_bucket.media.arn}/exports/00000000-0000-0000-0000-000000000000/*"
      },
      {
        Sid      = "AppListOwnPrefixes"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.media.arn
        Condition = {
          StringLike = { "s3:prefix" = ["media/*", "exports/*"] }
        }
      },
    ]
  })
}

resource "aws_iam_access_key" "media" {
  user = aws_iam_user.media.name
}

resource "aws_iam_role" "box" {
  name        = "${var.project}-box"
  description = "Instance role for ${var.project}-api: SSM, its release tarballs and its environment parameters."
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ec2.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "box_ssm_core" {
  role       = aws_iam_role.box.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy" "box" {
  name = "${var.project}-box-release"
  role = aws_iam_role.box.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "ReadReleaseTarballs"
        Effect   = "Allow"
        Action   = "s3:GetObject"
        Resource = "${aws_s3_bucket.media.arn}/deploy/backend/*"
      },
      {
        Sid      = "WriteDeployLogs"
        Effect   = "Allow"
        Action   = "s3:PutObject"
        Resource = "${aws_s3_bucket.media.arn}/deploy/logs/*"
      },
      {
        Sid    = "ReadEnvironmentParameters"
        Effect = "Allow"
        Action = [
          "ssm:GetParametersByPath",
          "ssm:GetParameters",
          "ssm:GetParameter",
        ]
        Resource = [local.env_param_arn, "${local.env_param_arn}/*"]
      },
      {
        Sid      = "ReadE2EAccountParameters"
        Effect   = "Allow"
        Action   = "ssm:GetParameters"
        Resource = "${local.e2e_param_arn}/*"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "box" {
  name = "${var.project}-box"
  role = aws_iam_role.box.name
}

resource "aws_iam_role" "deploy" {
  name                 = "${var.project}-deploy"
  description          = "Assumed by GitHub Actions in ${var.github_repo} on ${var.github_deploy_ref} to ship the backend."
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_provider_a }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider}:aud" = "sts.amazonaws.com"
          "${local.oidc_provider}:sub" = "repo:${var.github_oidc_subject_repo}:ref:${var.github_deploy_ref}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "deploy" {
  name = "${var.project}-deploy"
  role = aws_iam_role.deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "UploadReleaseTarballs"
        Effect   = "Allow"
        Action   = ["s3:PutObject"]
        Resource = "${aws_s3_bucket.media.arn}/deploy/backend/*"
      },
      {
        Sid      = "ReadDeployLogs"
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.media.arn}/deploy/logs/*"
      },
      {
        Sid      = "ListDeployLogs"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.media.arn
        Condition = {
          StringLike = { "s3:prefix" = ["deploy/logs/*"] }
        }
      },
      {
        Sid      = "RunOnTheBoxOnly"
        Effect   = "Allow"
        Action   = "ssm:SendCommand"
        Resource = [aws_instance.api.arn, local.run_shell_doc]
      },
      {
        Sid    = "FollowCommands"
        Effect = "Allow"
        Action = [
          "ssm:GetCommandInvocation",
          "ssm:ListCommandInvocations",
          "ssm:ListCommands",
          "ssm:DescribeInstanceInformation",
        ]
        Resource = "*"
      },
      {
        Sid    = "SyncEnvironmentParameters"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:GetParameter",
          "ssm:GetParameters",
          "ssm:GetParametersByPath",
          "ssm:AddTagsToResource",
        ]
        Resource = [local.env_param_arn, "${local.env_param_arn}/*"]
      },
      {
        Sid    = "MirrorRepositorySettings"
        Effect = "Allow"
        Action = [
          "ssm:PutParameter",
          "ssm:GetParameter",
          "ssm:AddTagsToResource",
        ]
        Resource = ["${local.e2e_param_arn}/*", "${local.ci_param_arn}/*", "${local.config_arn}/*"]
      },
    ]
  })
}

resource "aws_iam_role" "river_load" {
  name                 = "${var.project}-river-load"
  description          = "Assumed by the Geo ETL in ${var.github_repo} on ${var.github_deploy_ref} to upload river topologies."
  max_session_duration = 3600
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = local.oidc_provider_a }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = {
          "${local.oidc_provider}:aud" = "sts.amazonaws.com"
          "${local.oidc_provider}:sub" = "repo:${var.github_oidc_subject_repo}:ref:${var.github_deploy_ref}"
        }
      }
    }]
  })
}

resource "aws_iam_role_policy" "river_load" {
  name = "${var.project}-river-load"
  role = aws_iam_role.river_load.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid      = "WriteAndHeadRiverTopologies"
        Effect   = "Allow"
        Action   = ["s3:PutObject", "s3:GetObject"]
        Resource = "${aws_s3_bucket.media.arn}/media/rivers/*"
      },
      {
        Sid      = "TellMissingRiverTopologies"
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.media.arn
        Condition = {
          StringLike = { "s3:prefix" = ["media/rivers/*"] }
        }
      },
    ]
  })
}
