#!/usr/bin/env bash
set -Eeuo pipefail

REPO_DIR="${REPO_DIR:-/opt/cryptopulse}"
PROJECT_SUBDIR="${PROJECT_SUBDIR:-cryptopulse_ai}"
BRANCH="${1:-main}"

if [[ -f "${REPO_DIR}/${PROJECT_SUBDIR}/docker-compose.yml" ]]; then
  APP_DIR="${APP_DIR:-${REPO_DIR}/${PROJECT_SUBDIR}}"
else
  APP_DIR="${APP_DIR:-${REPO_DIR}}"
fi

git -C "${REPO_DIR}" fetch --prune origin
git -C "${REPO_DIR}" checkout "${BRANCH}"
git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"

cd "${APP_DIR}"
docker compose config >/dev/null
docker compose build --pull
docker compose up -d --remove-orphans
sleep 8
curl --fail --silent "https://${PUBLIC_HOST:-localhost}/health" \
  || docker compose exec -T app curl --fail http://127.0.0.1:8080/health
