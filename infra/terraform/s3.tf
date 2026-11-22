resource "aws_s3_bucket" "media" {
  bucket = var.bucket_name

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_public_access_block" "media" {
  bucket                  = aws_s3_bucket.media.id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_ownership_controls" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    object_ownership = "BucketOwnerEnforced"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_versioning" "media" {
  bucket = aws_s3_bucket.media.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_cors_configuration" "media" {
  bucket = aws_s3_bucket.media.id
  cors_rule {
    allowed_headers = ["*"]
    allowed_methods = ["PUT", "GET", "HEAD"]
    allowed_origins = var.cors_allowed_origins
    expose_headers  = ["ETag"]
    max_age_seconds = 3000
  }
}

resource "aws_s3_bucket_policy" "media" {
  bucket     = aws_s3_bucket.media.id
  depends_on = [aws_s3_bucket_public_access_block.media]
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "TlsOnly"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource  = [aws_s3_bucket.media.arn, "${aws_s3_bucket.media.arn}/*"]
        Condition = { Bool = { "aws:SecureTransport" = "false" } }
      },
      {
        Sid       = "ApiKeyNeverTouchesBackupsOrDeploys"
        Effect    = "Deny"
        Principal = { AWS = aws_iam_user.media.arn }
        Action    = "s3:*"
        Resource = [
          "${aws_s3_bucket.media.arn}/backups/*",
          "${aws_s3_bucket.media.arn}/deploy/*",
        ]
      },
    ]
  })
}

resource "aws_s3_bucket_lifecycle_configuration" "media" {
  bucket     = aws_s3_bucket.media.id
  depends_on = [aws_s3_bucket_versioning.media]

  rule {
    id     = "expire-nightly-dumps"
    status = "Enabled"
    filter {
      prefix = "backups/${var.repo_slug}/20"
    }
    expiration {
      days = var.nightly_dump_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "keep-weekly-dumps"
    status = "Enabled"
    filter {
      prefix = "backups/${var.repo_slug}/weekly/"
    }
    expiration {
      days = var.weekly_dump_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "abort-abandoned-media-uploads"
    status = "Enabled"
    filter {
      prefix = "media/"
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }

  rule {
    id     = "expire-narration"
    status = "Enabled"
    filter {
      prefix = "media/narration/"
    }
    expiration {
      days = var.narration_days
    }
  }

  rule {
    id     = "expire-voice-replies"
    status = "Enabled"
    filter {
      prefix = "media/voice-replies/"
    }
    expiration {
      days = var.voice_reply_days
    }
  }

  rule {
    id     = "expire-exports"
    status = "Enabled"
    filter {
      prefix = "exports/"
    }
    expiration {
      days = var.export_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 2
    }
  }

  rule {
    id     = "expire-deploy-artifacts"
    status = "Enabled"
    filter {
      prefix = "deploy/"
    }
    expiration {
      days = var.deploy_artifact_days
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 1
    }
  }

  rule {
    id     = "noncurrent-versions"
    status = "Enabled"
    filter {}
    noncurrent_version_expiration {
      noncurrent_days = var.noncurrent_version_days
    }
    expiration {
      expired_object_delete_marker = true
    }
  }
}
