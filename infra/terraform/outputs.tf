output "api_base_url" {
  description = "HTTPS base URL of the API (NEXT_PUBLIC_API_URL)."
  value       = "https://${aws_cloudfront_distribution.api.domain_name}"
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution in front of the box."
  value       = aws_cloudfront_distribution.api.id
}

output "instance_id" {
  description = "API box, reached through SSM only."
  value       = aws_instance.api.id
}

output "api_public_ip" {
  description = "Elastic IP of the box. Port 80 answers CloudFront only."
  value       = aws_eip.api.public_ip
}

output "api_public_dns" {
  description = "CloudFront origin host name."
  value       = aws_eip.api.public_dns
}

output "security_group_id" {
  description = "Security group on the box."
  value       = aws_security_group.api.id
}

output "media_bucket" {
  description = "Private media bucket (S3_BUCKET)."
  value       = aws_s3_bucket.media.bucket
}

output "deploy_role_arn" {
  description = "Role GitHub Actions assumes through OIDC to deploy."
  value       = aws_iam_role.deploy.arn
}

output "river_load_role_arn" {
  description = "Role the Geo ETL assumes through OIDC to upload river topologies (AWS_RIVER_LOAD_ROLE_ARN)."
  value       = aws_iam_role.river_load.arn
}

output "box_role_name" {
  description = "Instance role of the box."
  value       = aws_iam_role.box.name
}

output "env_parameter_path" {
  description = "SSM Parameter Store path holding the box environment."
  value       = local.env_param_path
}

output "ssm_session_command" {
  description = "Shell on the box without SSH."
  value       = "aws ssm start-session --target ${aws_instance.api.id} --region ${var.aws_region}"
}

output "log_groups" {
  description = "CloudWatch Logs groups the box ships its services' and nginx's logs to."
  value       = sort([for group in aws_cloudwatch_log_group.box : group.name])
}

output "media_access_key_id" {
  description = "Access key id of the API's media user (AWS_ACCESS_KEY_ID)."
  value       = aws_iam_access_key.media.id
}

output "media_secret_access_key" {
  description = "Secret of the API's media user (AWS_SECRET_ACCESS_KEY)."
  value       = aws_iam_access_key.media.secret
  sensitive   = true
}

output "origin_verify_secret" {
  description = "Header value CloudFront sends to nginx (ORIGIN_VERIFY_SECRET)."
  value       = random_password.origin_verify.result
  sensitive   = true
}
