#!/usr/bin/env bash
set -euo pipefail

if [ "${CONFIRM_RESTORE:-}" != "1" ]; then
  echo "This will replace the production Spent Analyzer database." >&2
  echo "Run with CONFIRM_RESTORE=1 after verifying the dump path." >&2
  exit 1
fi

if [ $# -ne 1 ]; then
  echo "Usage: CONFIRM_RESTORE=1 $0 /path/to/spent_analyzer.dump" >&2
  exit 1
fi

dump_path="$1"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"
env_file="${SPENT_ENV_FILE:-.env}"
compose_project="${SPENT_COMPOSE_PROJECT:-spent-analyzer}"
compose_file="${SPENT_COMPOSE_FILE:-docker-compose.prod.yml}"
db_service="${SPENT_DB_SERVICE:-spent-postgres}"
db_name="${SPENT_POSTGRES_DB:-spent_analyzer}"
db_user="${SPENT_POSTGRES_USER:-spent}"

cd "$repo_root"

if [ ! -f "$dump_path" ]; then
  echo "Dump not found: $dump_path" >&2
  exit 1
fi

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $repo_root/$env_file" >&2
  exit 1
fi

echo "Stopping app containers before restore..."
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" stop spent-api spent-web || true

echo "Restoring $dump_path into $db_name..."
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" exec -T "$db_service" \
  pg_restore -U "$db_user" -d "$db_name" --clean --if-exists --no-owner < "$dump_path"

if [ -n "${SPENT_USER_EMAIL_MAPPINGS:-}" ]; then
  echo "Applying SPENT_USER_EMAIL_MAPPINGS..."
  IFS=',' read -ra mappings <<< "$SPENT_USER_EMAIL_MAPPINGS"
  for mapping in "${mappings[@]}"; do
    old_email="${mapping%%=*}"
    new_email="${mapping#*=}"
    if [ -z "$old_email" ] || [ -z "$new_email" ] || [ "$old_email" = "$new_email" ]; then
      echo "Skipping invalid mapping: $mapping" >&2
      continue
    fi
    docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" exec -T "$db_service" \
      psql -U "$db_user" -d "$db_name" \
      -v ON_ERROR_STOP=1 \
      -v old_email="$old_email" \
      -v new_email="$new_email" <<'SQL'
UPDATE users
SET email = :'new_email'
WHERE email = :'old_email'
  AND google_sub IS NULL;
SQL
  done
fi

echo "Starting app containers..."
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" up -d spent-api spent-web
docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file" ps

echo "Restore complete."
