#!/bin/bash
# Deploy script executed ON the EC2 instance via SSM Run Command
# (AWS-RunShellScript). Expects this file and docker-compose.prod.yml to be
# present in /opt/vehicle-core-service (the CD workflow puts them there).
#
# Usage: deploy.sh <full-image-ref>
#   e.g. deploy.sh <account>.dkr.ecr.<region>.amazonaws.com/vehicle-core-service:<sha>
#
# Contract with cd.yml: this file lives at /opt/vehicle-core-service/deploy.sh
# on the instance and takes the FULL ECR image ref (registry/repo:sha) as $1.
#
# Security notes (items 6/7 of the plan):
# - .env is materialized here from SSM Parameter Store (config) and from the
#   RDS-managed Secrets Manager secret (DATABASE_PASSWORD) using the instance
#   profile — values are NEVER passed through SendCommand parameters and
#   NEVER echoed (no set -x).
# - ECR login uses the instance role (get-login-password piped straight to
#   docker login) — no registry credentials via SSM parameters or SendCommand
#   (resolves security item 6).
# - Seed NEVER runs in production: docker-compose.prod.yml has migrations +
#   app only.
set -euo pipefail

APP_IMAGE="${1:?usage: deploy.sh <full-image-ref>}"
APP_DIR="/opt/vehicle-core-service"
SSM_PREFIX="/vehicle-core-service"
ENV_KEYS=(
  DATABASE_HOST
  DATABASE_PORT
  DATABASE_USER
  DATABASE_NAME
  SALES_SERVICE_BASE_URL
  SALES_SERVICE_TIMEOUT_SECONDS
  INTERNAL_API_TOKEN
  SERVICE_NAME
  DEBUG
  LOG_LEVEL
)

cd "$APP_DIR"

# 1. Materialize .env from SSM (decrypted via instance profile). Region is
#    auto-detected by the AWS CLI through IMDSv2.
echo "[deploy] materializing .env from SSM ($SSM_PREFIX/*)"
umask 077
: >.env.tmp
for key in "${ENV_KEYS[@]}"; do
  value="$(aws ssm get-parameter --name "$SSM_PREFIX/$key" \
    --with-decryption --query 'Parameter.Value' --output text)"
  printf '%s=%s\n' "$key" "$value" >>.env.tmp
done

# 2. DATABASE_PASSWORD from the RDS-managed Secrets Manager secret
#    (secret ARN published by Terraform as an SSM parameter).
secret_arn="$(aws ssm get-parameter --name "$SSM_PREFIX/DATABASE_PASSWORD_SECRET_ARN" \
  --query 'Parameter.Value' --output text)"
db_password="$(aws secretsmanager get-secret-value --secret-id "$secret_arn" \
  --query 'SecretString' --output text |
  python3 -c 'import json, sys; print(json.load(sys.stdin)["password"])')"
printf 'DATABASE_PASSWORD=%s\n' "$db_password" >>.env.tmp
unset db_password

# 2b. Guard: refuse to deploy if any parameter is still the CHANGE_ME
#     placeholder (would silently break the service). Only KEY names are
#     printed — never values.
placeholder_keys="$(grep -E '=CHANGE_ME$' .env.tmp | cut -d= -f1 || true)"
if [ -n "$placeholder_keys" ]; then
  echo "[deploy] ERROR: SSM parameter(s) still set to the CHANGE_ME placeholder:" >&2
  echo "$placeholder_keys" >&2
  echo "[deploy] set real values out-of-band (aws ssm put-parameter --overwrite, see infra/README.md)" >&2
  rm -f .env.tmp
  exit 1
fi
mv -f .env.tmp .env

# 3. Shared network for the platform (sales service joins it later).
docker network create vehicle-platform 2>/dev/null || true

# 4. ECR login via instance role, pull the requested image and roll the
#    stack (migrations -> app, per compose depends_on; NO seed in production).
registry="${APP_IMAGE%%/*}"
echo "[deploy] logging in to ECR ($registry)"
aws ecr get-login-password | docker login --username AWS --password-stdin "$registry"
echo "[deploy] pulling $APP_IMAGE"
docker pull "$APP_IMAGE"
export APP_IMAGE
docker compose -f docker-compose.prod.yml up -d --remove-orphans

# 5. Health check — fail the SSM command (and the CD job) if not healthy.
echo "[deploy] waiting for /health"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null --max-time 3 "http://localhost:8000/health"; then
    echo "[deploy] healthy — deploy OK ($APP_IMAGE)"
    exit 0
  fi
  sleep 3
done

echo "[deploy] ERROR: service did not become healthy" >&2
docker compose -f docker-compose.prod.yml ps >&2
exit 1
