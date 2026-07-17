#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/cryptopulse}"
BACKUP_DIR="${BACKUP_DIR:-${APP_DIR}/backups}"
mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
cd "${APP_DIR}"
docker compose exec -T app sh -c 'test -f /app/data/cryptopulse.db && cat /app/data/cryptopulse.db' > "${BACKUP_DIR}/cryptopulse-${STAMP}.db"
find "${BACKUP_DIR}" -type f -name 'cryptopulse-*.db' -mtime +14 -delete
