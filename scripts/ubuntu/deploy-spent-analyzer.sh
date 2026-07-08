#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
env_file="${SPENT_ENV_FILE:-.env}"
compose_project="${SPENT_COMPOSE_PROJECT:-spent-analyzer}"
compose_file="${SPENT_COMPOSE_FILE:-docker-compose.prod.yml}"

cd "$repo_root"

if [[ "$env_file" = /* ]]; then
  env_path="$env_file"
else
  env_path="$repo_root/$env_file"
fi

if [ ! -f "$env_path" ]; then
  echo "Environment file not found: $env_path" >&2
  echo "Copy .env.example to .env, fill production values, then deploy again." >&2
  exit 1
fi

echo "Using environment file: $env_path"
echo
echo "Host memory:"
free -h || true
echo
echo "Host disk:"
df -h / "$repo_root" || true
echo
echo "Current Docker usage:"
docker stats --no-stream || true

docker network inspect homelab_proxy >/dev/null 2>&1 || docker network create homelab_proxy

docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_path" config >/dev/null
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_path" pull
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_path" up -d --build --force-recreate
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_path" ps

echo
echo "Smoke-testing API health inside the Compose project..."
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_path" exec -T spent-api \
  python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=5).read().decode())"

echo
echo "Deployment complete. NGINX should route the app at /finance/ after the alerting-system proxy config is updated."
