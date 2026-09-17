#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: backup-rotated-db.sh [--safety]

Without arguments, creates/updates daily, weekly, and monthly PostgreSQL dumps.
With --safety, creates a unique pre-destructive-operation dump instead.
EOF
}

mode="rotated"
case "${1:-}" in
  "") ;;
  --safety) mode="safety" ;;
  -h|--help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/.." && pwd)"

compose_project="${SPENT_COMPOSE_PROJECT:-spent-analyzer}"
compose_file="${SPENT_COMPOSE_FILE:-docker-compose.yml}"
env_file="${SPENT_ENV_FILE:-.env}"
db_service="${SPENT_DB_SERVICE:-postgres}"
db_name="${SPENT_POSTGRES_DB:-spent_analyzer}"
db_user="${SPENT_POSTGRES_USER:-spent}"
backup_root="${SPENT_BACKUP_DIR:-$repo_root/backups}"
daily_keep="${SPENT_BACKUP_DAILY_KEEP:-7}"
weekly_keep="${SPENT_BACKUP_WEEKLY_KEEP:-10}"
monthly_keep="${SPENT_BACKUP_MONTHLY_KEEP:-12}"
safety_keep="${SPENT_BACKUP_SAFETY_KEEP:-20}"

for retention in "$daily_keep" "$weekly_keep" "$monthly_keep" "$safety_keep"; do
  if ! [[ "$retention" =~ ^[1-9][0-9]*$ ]]; then
    echo "Backup retention values must be positive integers: $retention" >&2
    exit 2
  fi
done

cd "$repo_root"

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
command -v flock >/dev/null 2>&1 || { echo "flock is required" >&2; exit 1; }

mkdir -p "$backup_root"
chmod 700 "$backup_root"

exec 9>"$backup_root/.backup.lock"
if ! flock -n 9; then
  echo "Another database backup is already running." >&2
  exit 1
fi

tmp_dump="$(mktemp "$backup_root/.spent_analyzer.XXXXXX.dump")"
cleanup() {
  rm -f -- "$tmp_dump"
}
trap cleanup EXIT

compose=(docker compose -p "$compose_project" -f "$compose_file" --env-file "$env_file")

echo "Creating a PostgreSQL dump..."
"${compose[@]}" exec -T "$db_service" \
  pg_dump -U "$db_user" -d "$db_name" --format=custom --no-owner --no-acl > "$tmp_dump"

if [ ! -s "$tmp_dump" ]; then
  echo "Backup failed: pg_dump produced an empty file." >&2
  exit 1
fi

# A custom-format dump should be readable by the matching PostgreSQL image.
"${compose[@]}" exec -T "$db_service" pg_restore --list < "$tmp_dump" >/dev/null

install_dump() {
  local destination="$1"
  local pending="${destination}.tmp"
  install -m 600 "$tmp_dump" "$pending"
  mv -f -- "$pending" "$destination"
}

prune_directory() {
  local directory="$1"
  local keep="$2"
  local files=()
  local index

  mapfile -t files < <(find "$directory" -maxdepth 1 -type f -name 'spent_analyzer_*.dump' -printf '%f\n' | sort -r)
  for ((index=keep; index<${#files[@]}; index++)); do
    rm -f -- "$directory/${files[$index]}"
  done
}

timestamp="$(date -u +%Y%m%dT%H%M%SZ)"

if [ "$mode" = "safety" ]; then
  safety_dir="$backup_root/safety"
  mkdir -p "$safety_dir"
  chmod 700 "$safety_dir"
  safety_path="$safety_dir/spent_analyzer_${timestamp}_$$.dump"
  install_dump "$safety_path"
  prune_directory "$safety_dir" "$safety_keep"
  echo "Safety backup complete: $safety_path"
  exit 0
fi

daily_dir="$backup_root/daily"
weekly_dir="$backup_root/weekly"
monthly_dir="$backup_root/monthly"
mkdir -p "$daily_dir" "$weekly_dir" "$monthly_dir"
chmod 700 "$daily_dir" "$weekly_dir" "$monthly_dir"

daily_path="$daily_dir/spent_analyzer_$(date -u +%F).dump"
weekly_path="$weekly_dir/spent_analyzer_$(date -u +%G-W%V).dump"
monthly_path="$monthly_dir/spent_analyzer_$(date -u +%Y-%m).dump"

# Re-running in the same period atomically refreshes that period's restore point.
install_dump "$daily_path"
install_dump "$weekly_path"
install_dump "$monthly_path"

prune_directory "$daily_dir" "$daily_keep"
prune_directory "$weekly_dir" "$weekly_keep"
prune_directory "$monthly_dir" "$monthly_keep"

echo "Rotated backup complete:"
echo "  daily:  $daily_path"
echo "  weekly: $weekly_path"
echo "  monthly: $monthly_path"
