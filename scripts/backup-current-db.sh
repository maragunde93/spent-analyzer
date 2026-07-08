#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

compose_project="${SPENT_COMPOSE_PROJECT:-spent-analyzer}"
compose_file="${SPENT_COMPOSE_FILE:-docker-compose.yml}"
env_file="${SPENT_ENV_FILE:-.env}"
db_service="${SPENT_DB_SERVICE:-postgres}"
db_name="${SPENT_POSTGRES_DB:-spent_analyzer}"
db_user="${SPENT_POSTGRES_USER:-spent}"
backup_dir="${SPENT_BACKUP_DIR:-$repo_root/backups}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup_path="$backup_dir/spent_analyzer_${timestamp}.dump"

cd "$repo_root"

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $repo_root/$env_file" >&2
  exit 1
fi

mkdir -p "$backup_dir"

echo "Creating backup: $backup_path"
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" exec -T "$db_service" \
  pg_dump -U "$db_user" -d "$db_name" --format=custom > "$backup_path"

echo "Backup complete."
