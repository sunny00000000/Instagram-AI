#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/opt/cryptopulse}"
PROJECT_SUBDIR="${PROJECT_SUBDIR:-cryptopulse_ai}"
if [[ -f "${REPO_DIR}/${PROJECT_SUBDIR}/docker-compose.yml" ]]; then
  APP_DIR="${APP_DIR:-${REPO_DIR}/${PROJECT_SUBDIR}}"
else
  APP_DIR="${APP_DIR:-${REPO_DIR}}"
fi
BACKUP_DIR="${BACKUP_DIR:-${REPO_DIR}/backups}"
mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
cd "${APP_DIR}"
docker compose exec -T app sh -c 'test -f /app/data/cryptopulse.db && cat /app/data/cryptopulse.db' \
  > "${BACKUP_DIR}/cryptopulse-${STAMP}.db"
find "${BACKUP_DIR}" -type f -name 'cryptopulse-*.db' -mtime +14 -delete
