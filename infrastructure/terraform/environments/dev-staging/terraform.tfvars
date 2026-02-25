# ECR URLs — copy from: terraform -chdir=environments/shared output -raw ecr_backend_url
ecr_backend_url  = "FILL_IN_FROM_SHARED_OUTPUT"
ecr_frontend_url = "FILL_IN_FROM_SHARED_OUTPUT"

# Sensitive values — set via environment variables instead:
#   export TF_VAR_db_master_password='...'
#   export TF_VAR_redis_auth_token='...'
