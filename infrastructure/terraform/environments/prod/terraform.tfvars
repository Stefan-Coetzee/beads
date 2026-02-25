# ECR URLs — copy from: terraform -chdir=environments/shared output -raw ecr_backend_url
ecr_backend_url  = "FILL_IN_FROM_SHARED_OUTPUT"
ecr_frontend_url = "FILL_IN_FROM_SHARED_OUTPUT"

alarm_email = "FILL_IN_OPS_EMAIL"

# Sensitive values — set via environment variables:
#   export TF_VAR_db_master_password='...'
#   export TF_VAR_redis_auth_token='...'
