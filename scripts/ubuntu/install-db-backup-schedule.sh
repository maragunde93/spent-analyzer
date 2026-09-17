#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "$script_dir/../.." && pwd)"

unit_name="spent-analyzer-db-backup"
run_user="${SPENT_BACKUP_RUN_USER:-${SUDO_USER:-$(id -un)}}"
run_group="$(id -gn "$run_user")"
compose_project="${SPENT_COMPOSE_PROJECT:-spent-analyzer}"
compose_file="${SPENT_COMPOSE_FILE:-docker-compose.prod.yml}"
env_file="${SPENT_ENV_FILE:-$repo_root/.env}"
db_service="${SPENT_DB_SERVICE:-spent-postgres}"
db_name="${SPENT_POSTGRES_DB:-spent_analyzer}"
db_user="${SPENT_POSTGRES_USER:-spent}"
backup_dir="${SPENT_BACKUP_DIR:-$repo_root/backups}"
daily_keep="${SPENT_BACKUP_DAILY_KEEP:-7}"
weekly_keep="${SPENT_BACKUP_WEEKLY_KEEP:-10}"
monthly_keep="${SPENT_BACKUP_MONTHLY_KEEP:-12}"
on_calendar="${SPENT_BACKUP_ON_CALENDAR:-*-*-* 03:15:00}"

if [ "$(id -u)" -eq 0 ]; then
  admin=()
else
  command -v sudo >/dev/null 2>&1 || {
    echo "sudo is required to install the systemd units." >&2
    exit 1
  }
  admin=(sudo)
fi

command -v systemctl >/dev/null 2>&1 || {
  echo "systemd is required on this host." >&2
  exit 1
}

command -v docker >/dev/null 2>&1 || {
  echo "Docker is required on this host." >&2
  exit 1
}

if [ ! -f "$repo_root/scripts/backup-rotated-db.sh" ]; then
  echo "Backup script not found under $repo_root/scripts." >&2
  exit 1
fi

if [ ! -f "$env_file" ]; then
  echo "Environment file not found: $env_file" >&2
  exit 1
fi

# Keeping generated unit values free of whitespace makes systemd parsing
# predictable and avoids silently targeting a different path.
for value in "$repo_root" "$env_file" "$backup_dir" "$compose_project" "$compose_file" "$db_service" "$db_name" "$db_user"; do
  if [[ "$value" =~ [[:space:]] ]]; then
    echo "Paths and service settings cannot contain whitespace: $value" >&2
    exit 2
  fi
done

for retention in "$daily_keep" "$weekly_keep" "$monthly_keep"; do
  if ! [[ "$retention" =~ ^[1-9][0-9]*$ ]]; then
    echo "Backup retention values must be positive integers: $retention" >&2
    exit 2
  fi
done

if [[ "$on_calendar" == *$'\n'* ]] || [[ "$on_calendar" == *$'\r'* ]]; then
  echo "SPENT_BACKUP_ON_CALENDAR cannot contain newlines." >&2
  exit 2
fi

if ! id "$run_user" >/dev/null 2>&1; then
  echo "Backup user does not exist: $run_user" >&2
  exit 1
fi

if [ "$(id -un)" = "$run_user" ]; then
  docker_check=(docker info)
elif [ "$(id -u)" -eq 0 ] && command -v runuser >/dev/null 2>&1; then
  docker_check=(runuser -u "$run_user" -- docker info)
else
  docker_check=(sudo -u "$run_user" docker info)
fi

if ! "${docker_check[@]}" >/dev/null 2>&1; then
  echo "User '$run_user' cannot access Docker." >&2
  echo "Add it to the docker group, re-login, and run this installer again." >&2
  exit 1
fi

service_tmp="$(mktemp)"
timer_tmp="$(mktemp)"
cleanup() {
  rm -f -- "$service_tmp" "$timer_tmp"
}
trap cleanup EXIT

cat > "$service_tmp" <<EOF
[Unit]
Description=Spent Analyzer PostgreSQL rotating backup
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
User=$run_user
Group=$run_group
WorkingDirectory=$repo_root
Environment=SPENT_COMPOSE_PROJECT=$compose_project
Environment=SPENT_COMPOSE_FILE=$compose_file
Environment=SPENT_ENV_FILE=$env_file
Environment=SPENT_DB_SERVICE=$db_service
Environment=SPENT_POSTGRES_DB=$db_name
Environment=SPENT_POSTGRES_USER=$db_user
Environment=SPENT_BACKUP_DIR=$backup_dir
Environment=SPENT_BACKUP_DAILY_KEEP=$daily_keep
Environment=SPENT_BACKUP_WEEKLY_KEEP=$weekly_keep
Environment=SPENT_BACKUP_MONTHLY_KEEP=$monthly_keep
ExecStart=/usr/bin/env bash $repo_root/scripts/backup-rotated-db.sh
UMask=0077
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF

cat > "$timer_tmp" <<EOF
[Unit]
Description=Schedule Spent Analyzer PostgreSQL backups

[Timer]
OnCalendar=$on_calendar
Persistent=true
RandomizedDelaySec=5m
AccuracySec=1m
Unit=$unit_name.service

[Install]
WantedBy=timers.target
EOF

echo "Installing systemd service and timer..."
"${admin[@]}" install -m 0644 "$service_tmp" "/etc/systemd/system/$unit_name.service"
"${admin[@]}" install -m 0644 "$timer_tmp" "/etc/systemd/system/$unit_name.timer"
"${admin[@]}" systemctl daemon-reload

echo "Running an immediate backup to verify the configuration..."
"${admin[@]}" systemctl start "$unit_name.service"

echo "Enabling the persistent backup timer..."
"${admin[@]}" systemctl enable --now "$unit_name.timer"

echo
"${admin[@]}" systemctl --no-pager status "$unit_name.timer"
echo
"${admin[@]}" systemctl --no-pager list-timers "$unit_name.timer"
echo
echo "Backup scheduling is installed. Missed runs execute after the Mini PC starts again."
echo "Logs: journalctl -u $unit_name.service"
