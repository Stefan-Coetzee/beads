#!/usr/bin/env bash
# gen-nginx-config.sh — generate nginx bastion instructions for LTT
#
# Queries AWS for the current ALB DNS names, then outputs markdown-formatted
# step-by-step instructions for updating the nginx reverse proxy at the bastion.
#
# Usage:
#   ./tools/scripts/gen-nginx-config.sh            # writes to stdout
#   ./tools/scripts/gen-nginx-config.sh >> "$GITHUB_STEP_SUMMARY"  # CI
#
# Requires: AWS CLI with elbv2:DescribeLoadBalancers permission.

set -euo pipefail

BASTION="52.30.100.225"
CONF="/etc/nginx/conf.d/ltt.conf"

# ── Query ALB DNS names ────────────────────────────────────────────────────────

get_alb_dns() {
  aws elbv2 describe-load-balancers \
    --names "$1" \
    --query 'LoadBalancers[0].DNSName' \
    --output text 2>/dev/null || echo "<run terraform apply first>"
}

NONPROD_DNS=$(get_alb_dns "ltt-nonprod")
PROD_DNS=$(get_alb_dns "ltt-prod")

# ── Build nginx config string ──────────────────────────────────────────────────
# Use printf with single-quoted format strings so nginx variables ($host etc.)
# remain as literal text in the output rather than being shell-expanded.

nginx_config() {
  printf 'upstream ltt_nonprod_alb {\n'
  printf '    server %s:80;\n' "$NONPROD_DNS"
  printf '    keepalive 32;\n'
  printf '}\n'
  printf '\n'
  printf 'upstream ltt_prod_alb {\n'
  printf '    server %s:80;\n' "$PROD_DNS"
  printf '    keepalive 32;\n'
  printf '}\n'
  printf '\n'
  printf 'server {\n'
  printf '    listen 443 ssl;\n'
  printf '    server_name dev-mwongozo.alx-ai-tools.com staging-mwongozo.alx-ai-tools.com;\n'
  printf '\n'
  printf '    ssl_certificate     /etc/letsencrypt/live/dev-mwongozo.alx-ai-tools.com/fullchain.pem;\n'
  printf '    ssl_certificate_key /etc/letsencrypt/live/dev-mwongozo.alx-ai-tools.com/privkey.pem;\n'
  printf '\n'
  printf '    location / {\n'
  printf '        proxy_pass         http://ltt_nonprod_alb;\n'
  printf '        proxy_set_header   Host              $host;\n'
  printf '        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;\n'
  printf '        proxy_set_header   X-Forwarded-Proto $scheme;\n'
  printf '        proxy_http_version 1.1;\n'
  printf '        proxy_buffering    off;\n'
  printf '        proxy_read_timeout 300s;\n'
  printf '    }\n'
  printf '}\n'
  printf '\n'
  printf 'server {\n'
  printf '    listen 443 ssl;\n'
  printf '    server_name mwongozo.alx-ai-tools.com;\n'
  printf '\n'
  printf '    ssl_certificate     /etc/letsencrypt/live/mwongozo.alx-ai-tools.com/fullchain.pem;\n'
  printf '    ssl_certificate_key /etc/letsencrypt/live/mwongozo.alx-ai-tools.com/privkey.pem;\n'
  printf '\n'
  printf '    location / {\n'
  printf '        proxy_pass         http://ltt_prod_alb;\n'
  printf '        proxy_set_header   Host              $host;\n'
  printf '        proxy_set_header   X-Forwarded-For   $proxy_add_x_forwarded_for;\n'
  printf '        proxy_set_header   X-Forwarded-Proto $scheme;\n'
  printf '        proxy_http_version 1.1;\n'
  printf '        proxy_buffering    off;\n'
  printf '        proxy_read_timeout 300s;\n'
  printf '    }\n'
  printf '}\n'
}

NGINX_CONFIG=$(nginx_config)

# ── Output markdown instructions ───────────────────────────────────────────────

cat << MARKDOWN
## Nginx bastion — route configuration

SSH into \`$BASTION\` and run the steps below.
This is **idempotent** — safe to re-run on every deploy.

### Current ALB DNS names

| ALB | DNS name |
|-----|----------|
| \`ltt-nonprod\` (dev + staging) | \`$NONPROD_DNS\` |
| \`ltt-prod\` | \`$PROD_DNS\` |

---

### Step 1 — write nginx config

\`\`\`bash
sudo tee $CONF > /dev/null << 'NGINX_EOF'
$NGINX_CONFIG
NGINX_EOF
\`\`\`

---

### Step 2 — SSL certificates *(first deploy only — skip if certs already exist)*

\`\`\`bash
sudo certbot --nginx \\
  -d dev-mwongozo.alx-ai-tools.com \\
  -d staging-mwongozo.alx-ai-tools.com \\
  -d mwongozo.alx-ai-tools.com
\`\`\`

---

### Step 3 — reload nginx

\`\`\`bash
sudo nginx -t && sudo systemctl reload nginx
\`\`\`

---

### Verify

\`\`\`bash
curl -sI https://dev-mwongozo.alx-ai-tools.com/health | head -5
curl -sI https://staging-mwongozo.alx-ai-tools.com/health | head -5
curl -sI https://mwongozo.alx-ai-tools.com/health | head -5
\`\`\`
MARKDOWN
