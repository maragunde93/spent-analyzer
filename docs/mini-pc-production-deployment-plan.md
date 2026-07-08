# Finance App Mini PC Production Deployment

This guide tracks the production deployment work for Spent Analyzer on the `homelab` Mini PC.

## Target Runtime

- Public LAN path: `/finance/`
- API path: `/finance/api/`
- Compose project: `spent-analyzer`
- Services: `spent-postgres`, `spent-api`, `spent-web`
- Shared proxy network: `homelab_proxy`
- Data volume: `spent-analyzer_postgres_data`

The alerting system remains the priority workload. Production compose does not publish Spent Analyzer ports to the host; nginx reaches the app through Docker's `homelab_proxy` network.

## HTTPS And Local Auth

Spent Analyzer uses app-scoped local username/password authentication. The homelab nginx proxy should serve all apps over HTTPS using a local CA certificate.

Recommended local certificate model:

1. Create a private local CA on the Mini PC.
2. Use that CA to sign a server certificate for `homelab.local`, `homelab`, and `192.168.1.71`.
3. Mount the server certificate into nginx.
4. Install the local CA certificate on trusted laptops/phones so browsers trust `https://homelab.local`.

Create the local CA and server certificate on the Mini PC:

```bash
cd ~/repos/alerting-system
mkdir -p nginx/certs
chmod 700 nginx/certs

openssl genrsa -out nginx/certs/homelab-local-ca.key 4096
openssl req -x509 -new -nodes \
  -key nginx/certs/homelab-local-ca.key \
  -sha256 -days 3650 \
  -out nginx/certs/homelab-local-ca.crt \
  -subj "/CN=Homelab Local CA"

openssl genrsa -out nginx/certs/homelab.local.key 2048
openssl req -new \
  -key nginx/certs/homelab.local.key \
  -out nginx/certs/homelab.local.csr \
  -subj "/CN=homelab.local"

cat > nginx/certs/homelab.local.ext <<'EOF'
subjectAltName=DNS:homelab.local,DNS:homelab,IP:192.168.1.71
extendedKeyUsage=serverAuth
EOF

openssl x509 -req \
  -in nginx/certs/homelab.local.csr \
  -CA nginx/certs/homelab-local-ca.crt \
  -CAkey nginx/certs/homelab-local-ca.key \
  -CAcreateserial \
  -out nginx/certs/homelab.local.crt \
  -days 825 -sha256 \
  -extfile nginx/certs/homelab.local.ext

chmod 600 nginx/certs/*.key
```

Install the CA certificate, not the server key, on client devices:

- Windows: import `nginx/certs/homelab-local-ca.crt` into `Trusted Root Certification Authorities`.
- macOS: import into Keychain Access > System, then set trust to Always Trust.
- iOS: install the profile, then enable full trust in certificate trust settings.
- Android: install as a user CA certificate; Chrome should trust it for user-installed roots on normal browser traffic.

After creating the certs, deploy/recreate the alerting proxy:

```bash
cd ~/repos/alerting-system
bash scripts/ubuntu/deploy-alerting.sh
```

Verify:

```bash
curl -kI https://homelab.local/
curl -kI https://homelab.local/admin/
curl -kI https://homelab.local/frigate/
curl -kI https://homelab.local/finance/
docker logs homelab_proxy --tail 100
```

Use `-k` only for command-line smoke tests before the CA is installed on the client. Browsers should show a trusted lock after installing the CA.

## Deployment

Create `.env` on the Mini PC from `.env.example` and set production values:

```env
SPENT_POSTGRES_DB=spent_analyzer
SPENT_POSTGRES_USER=spent
SPENT_POSTGRES_PASSWORD=replace-with-strong-password
SPENT_CORS_ORIGINS=["https://homelab.local"]
SPENT_PUBLIC_BASE_URL=https://homelab.local/finance
SPENT_PUBLIC_API_BASE_URL=https://homelab.local/finance/api
SPENT_LOCAL_USERS=[{"username":"mauro","email":"mauro@example.test","display_name":"Mauro","password_hash":"pbkdf2_sha256$260000$..."}]
SPENT_SESSION_SECRET=replace-with-long-random-secret
SPENT_SESSION_COOKIE_PATH=/finance
SPENT_SESSION_COOKIE_SECURE=true
SPENT_SESSION_COOKIE_SAMESITE=lax
SPENT_FX_AUTO_UPDATE_ENABLED=true
```

Deploy:

```bash
cd ~/repos/spent-analyzer
bash scripts/ubuntu/deploy-spent-analyzer.sh
```

The deploy script validates compose config, prints resource information, creates `homelab_proxy` if missing, builds containers, and smoke-tests API health.

## Local Docker End-To-End Check

The local Docker compose stack mirrors the production subpath and local-auth flow without requiring local TLS:

```bash
docker compose up -d --build
```

Open:

```text
http://localhost:8080/finance/
```

Default local credentials:

```text
usuario: mauro
contrasena: local-password-123
```

Useful smoke checks:

```bash
curl http://localhost:8080/finance/api/health
curl -i -X POST http://localhost:8080/finance/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"mauro","password":"local-password-123"}'
```

## NGINX Proxy Changes

The current nginx config lives in the `alerting-system` project. Add these routes to `nginx/conf.d/default.conf`:

```nginx
server {
    listen 80;
    server_name _;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name _;
    resolver 127.0.0.11 valid=30s ipv6=off;
    client_max_body_size 25m;

    ssl_certificate /etc/nginx/certs/homelab.local.crt;
    ssl_certificate_key /etc/nginx/certs/homelab.local.key;
    ssl_protocols TLSv1.2 TLSv1.3;

location = /finance {
    return 302 /finance/;
}

location /finance/api/ {
    set $finance_api_upstream spent-api:8000;
    rewrite ^/finance/api/(.*)$ /$1 break;
    proxy_pass http://$finance_api_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
}

location /finance/ {
    set $finance_web_upstream spent-web:80;
    rewrite ^/finance/(.*)$ /$1 break;
    proxy_pass http://$finance_web_upstream;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
}
```

Also add a homepage card pointing to `/finance/`, expose `443:443`, and mount `nginx/certs` into the proxy container as `/etc/nginx/certs:ro`.

Longer term, move `compose/proxy.compose.yml`, `nginx/conf.d`, `nginx/html`, and certificate automation into a standalone `homelab-platform` repo. That should happen when TLS/cert renewal becomes shared infrastructure.

## Database Backup And Restore

Create a local backup from a running compose DB:

```bash
bash scripts/backup-current-db.sh
```

For production compose, use:

```bash
SPENT_COMPOSE_FILE=docker-compose.prod.yml SPENT_DB_SERVICE=spent-postgres bash scripts/backup-current-db.sh
```

Restore on the Mini PC:

```bash
CONFIRM_RESTORE=1 SPENT_USER_EMAIL_MAPPINGS="mauro@example.test=mauro@example.test" \
  bash scripts/ubuntu/restore-spent-db.sh backups/spent_analyzer_YYYYMMDDTHHMMSSZ.dump
```

For local auth, keep the configured local user email equal to the existing restored user email when possible. If the configured email changes later, use `SPENT_USER_EMAIL_MAPPINGS=old@example.test=new@example.test` during restore.

## Resource And Storage Sizing

Current observed local size:

- Database: about 10 MB.
- Expenses: 257 rows from `2025-12-31` through `2026-07-02`.
- Import lines: 390 rows.
- Local runtime baseline: Postgres about 37 MiB, API about 81 MiB, web about 18 MiB.

Production allocation:

- Postgres memory limit: 512 MB.
- API memory limit: 512 MB.
- Web memory limit: 128 MB.
- Postgres volume target: at least 2 GB.
- Host free-space target: keep 5-10 GB free for dumps, future data, Docker images, and operational margin.

The three-year relational dataset should stay well below 250 MB unless receipt image storage is added later. Uploaded statement and ticket files are currently processed through temporary files, not retained as large binary DB payloads.

## Production Readiness Checklist

- `SPENT_ENVIRONMENT=production`.
- `SPENT_TEST_AUTH_ENABLED=false`.
- Strong `SPENT_SESSION_SECRET`.
- `SPENT_LOCAL_USERS` contains only approved local accounts and PBKDF2 password hashes.
- Local CA certificate is installed on trusted client devices.
- nginx certificate files exist before starting `homelab_proxy`.
- `.env` stays uncommitted.
- `docker-compose.prod.yml` validates on the Mini PC.
- Alerting nginx routes `/finance/` and `/finance/api/`.
- Backup dump restored and MAURO local auth email matches the restored MAURO user row.
- `docker stats` confirms alerting containers remain healthy after deploy.
Generate a local password hash before filling `SPENT_LOCAL_USERS`:

```bash
python3 scripts/hash-local-password.py
```
