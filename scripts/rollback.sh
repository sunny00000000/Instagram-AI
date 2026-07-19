#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/opt/cryptopulse}"
PROJECT_SUBDIR="${PROJECT_SUBDIR:-cryptopulse_ai}"
TARGET_COMMIT="${1:-}"
if [[ -z "${TARGET_COMMIT}" ]]; then
  echo "Usage: bash scripts/rollback.sh <known-good-git-commit>"
  exit 1
fi

if [[ -f "${REPO_DIR}/${PROJECT_SUBDIR}/docker-compose.yml" ]]; then
  APP_DIR="${APP_DIR:-${REPO_DIR}/${PROJECT_SUBDIR}}"
else
  APP_DIR="${APP_DIR:-${REPO_DIR}}"
fi

git -C "${REPO_DIR}" fetch --all --tags
git -C "${REPO_DIR}" checkout --detach "${TARGET_COMMIT}"
cd "${APP_DIR}"
docker compose build
docker compose up -d --remove-orphans
sleep 8
docker compose exec -T app curl --fail http://127.0.0.1:8080/health
