#!/usr/bin/env bash
set -Eeuo pipefail

REPOSITORY_URL="${1:-}"
BRANCH="${2:-main}"
APP_DIR="${APP_DIR:-/opt/cryptopulse}"

if [[ -z "${REPOSITORY_URL}" ]]; then
  echo "Usage: bash scripts/deploy_oci.sh <git-repository-url> [branch]"
  exit 1
fi

if [[ ! -d "${APP_DIR}/.git" ]]; then
  git clone --branch "${BRANCH}" "${REPOSITORY_URL}" "${APP_DIR}"
else
  git -C "${APP_DIR}" fetch --prune origin
  git -C "${APP_DIR}" checkout "${BRANCH}"
  git -C "${APP_DIR}" pull --ff-only origin "${BRANCH}"
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

echo "Deployment complete. Check: docker compose logs -f app"
