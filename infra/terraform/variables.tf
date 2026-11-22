variable "project" {
  description = "Prefix for every resource name."
  type        = string
  default     = "kalavigyan"
}

variable "aws_region" {
  description = "Region for the box, the bucket and the parameters."
  type        = string
  default     = "ap-south-1"
}

variable "bucket_name" {
  description = "Private media bucket."
  type        = string
  default     = "kalavigyan-media-626159998512"
}

variable "repo_slug" {
  description = "Repository folder name used under backups/."
  type        = string
  default     = "science-behind-craft"
}

variable "github_repo" {
  description = "owner/name of the repository allowed to assume the deploy role."
  type        = string
  default     = "cxacraftecosystem-ui/KalaVigyan"
}

variable "github_oidc_subject_repo" {
  description = "Repository part of the GitHub OIDC sub claim; the cxacraftecosystem-ui organisation issues immutable subjects (owner@id/name@id)."
  type        = string
  default     = "cxacraftecosystem-ui@293924172/KalaVigyan@1459150589"
}

variable "github_deploy_ref" {
  description = "Git ref whose workflows may assume the deploy role."
  type        = string
  default     = "refs/heads/main"
}

variable "cors_allowed_origins" {
  description = "Browser origins allowed to PUT and GET media with presigned URLs."
  type        = list(string)
  default = [
    "https://kalavigyan.vercel.app",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
  ]
}

variable "instance_type" {
  description = "API box size."
  type        = string
  default     = "t3.large"
}

variable "root_volume_gb" {
  description = "Root volume size in GiB."
  type        = number
  default     = 40
}

variable "noncurrent_version_days" {
  description = "Days an overwritten or deleted object version is kept."
  type        = number
  default     = 90
}

variable "nightly_dump_days" {
  description = "Days a nightly database dump is kept."
  type        = number
  default     = 30
}

variable "weekly_dump_days" {
  description = "Days a weekly database dump is kept."
  type        = number
  default     = 365
}

variable "export_days" {
  description = "Days a generated export under exports/ is kept."
  type        = number
  default     = 7
}

variable "narration_days" {
  description = "Days a Listen narration part or manifest under media/narration/ is kept; a block heard again after that is spoken once more."
  type        = number
  default     = 365
}

variable "voice_reply_days" {
  description = "Days a voice call's reply audio under media/voice-replies/ is kept; a reply plays for at most two minutes after its call ends."
  type        = number
  default     = 1
}

variable "deploy_artifact_days" {
  description = "Days a release tarball or deploy log under deploy/ is kept."
  type        = number
  default     = 30
}

variable "cloudfront_price_class" {
  description = "CloudFront edge set. PriceClass_200 includes India."
  type        = string
  default     = "PriceClass_200"
}

variable "log_retention_days" {
  description = "Days CloudWatch Logs keeps each of the box's log groups."
  type        = number
  default     = 30
}
