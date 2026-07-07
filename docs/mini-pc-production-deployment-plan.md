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

## HTTPS And Google OAuth

Google OAuth is implemented inside Spent Analyzer only. It is not proxy-wide auth for `/admin/`, `/frigate/`, or `/portainer/`.

Preferred no-cost HTTPS path:

1. Use a real domain you own, such as `homelab.example.com`.
2. Create a private LAN DNS record pointing that name to the Mini PC IP, currently `192.168.1.71`.
3. Issue a free Let's Encrypt certificate using DNS-01 validation. DNS-01 proves domain control with a TXT record and does not require exposing the Mini PC to the internet.
4. Configure Google OAuth redirect URI exactly as:

```text
https://homelab.example.com/finance/api/auth/google/callback
```

5. Mount the certificate and key into the homelab nginx proxy and add a `443` listener.

Alternatives:

- HTTP-01 with Let's Encrypt is simpler but requires public port `80` to reach the Mini PC.
- Caddy local CA or `mkcert` can produce trusted local certificates on devices where the local CA is installed, but this is awkward for phones and not the recommended Google OAuth route.
- A Tailscale `.ts.net` HTTPS hostname may be viable if Tailscale becomes the accepted access layer.

References:

- Google OAuth redirect rules: `https://developers.google.com/identity/protocols/oauth2/web-server`
- Let's Encrypt challenges: `https://letsencrypt.org/docs/challenge-types/`
- Let's Encrypt FAQ: `https://letsencrypt.org/docs/faq/`
- Caddy local HTTPS: `https://caddyserver.com/docs/automatic-https`
- mkcert: `https://github.com/FiloSottile/mkcert`

## Deployment

Create `.env` on the Mini PC from `.env.example` and set production values:

```env
SPENT_POSTGRES_DB=spent_analyzer
SPENT_POSTGRES_USER=spent
SPENT_POSTGRES_PASSWORD=replace-with-strong-password
SPENT_CORS_ORIGINS=["https://homelab.example.com"]
SPENT_PUBLIC_BASE_URL=https://homelab.example.com/finance
SPENT_PUBLIC_API_BASE_URL=https://homelab.example.com/finance/api
SPENT_GOOGLE_CLIENT_ID=your-google-client-id
SPENT_GOOGLE_CLIENT_SECRET=your-google-client-secret
SPENT_ALLOWED_GOOGLE_EMAILS=["your-google-account@gmail.com"]
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

## NGINX Proxy Changes

The current nginx config lives in the `alerting-system` project. Add these routes to `nginx/conf.d/default.conf`:

```nginx
client_max_body_size 25m;

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
```

Also add a homepage card pointing to `/finance/`.

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
CONFIRM_RESTORE=1 SPENT_USER_EMAIL_MAPPINGS="mauro@example.test=your-google-account@gmail.com" \
  bash scripts/ubuntu/restore-spent-db.sh backups/spent_analyzer_YYYYMMDDTHHMMSSZ.dump
```

The email mapping preserves the existing MAURO user row, memberships, expenses, imports, and audit ownership while changing the login email to the Google account.

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
- Google OAuth client configured with the exact HTTPS callback URL.
- `SPENT_ALLOWED_GOOGLE_EMAILS` includes only approved accounts.
- `.env` stays uncommitted.
- `docker-compose.prod.yml` validates on the Mini PC.
- Alerting nginx routes `/finance/` and `/finance/api/`.
- Backup dump restored and MAURO email mapping applied before first Google login.
- `docker stats` confirms alerting containers remain healthy after deploy.
