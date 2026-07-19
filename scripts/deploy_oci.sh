#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY_URL="${1:-}"
BRANCH="${2:-main}"
REPO_DIR="${REPO_DIR:-/opt/cryptopulse}"
PROJECT_SUBDIR="${PROJECT_SUBDIR:-cryptopulse_ai}"

if [[ -z "${REPOSITORY_URL}" ]]; then
  echo "Usage: bash scripts/deploy_oci.sh <git-repository-url> [branch]"
  exit 1
fi

if [[ ! -d "${REPO_DIR}/.git" ]]; then
  git clone --branch "${BRANCH}" "${REPOSITORY_URL}" "${REPO_DIR}"
else
  git -C "${REPO_DIR}" fetch --prune origin
  git -C "${REPO_DIR}" checkout "${BRANCH}"
  git -C "${REPO_DIR}" pull --ff-only origin "${BRANCH}"
fi

if [[ -f "${REPO_DIR}/${PROJECT_SUBDIR}/docker-compose.yml" ]]; then
  APP_DIR="${APP_DIR:-${REPO_DIR}/${PROJECT_SUBDIR}}"
else
  APP_DIR="${APP_DIR:-${REPO_DIR}}"
fi

cd "${APP_DIR}"
if [[ ! -f .env ]]; then
  cp .env.example .env
  chmod 600 .env
  echo "Created ${APP_DIR}/.env. Edit it before enabling live publishing."
fi

docker compose config >/dev/null
docker compose build --pull
docker compose up -d --remove-orphans
docker compose ps

echo "Deployment complete. Project directory: ${APP_DIR}"
echo "Check logs: cd ${APP_DIR} && docker compose logs -f app"
