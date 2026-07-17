#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/cryptopulse}"
BRANCH="${1:-main}"
cd "${APP_DIR}"

git fetch --prune origin
git checkout "${BRANCH}"
git pull --ff-only origin "${BRANCH}"
docker compose config >/dev/null
docker compose build --pull
docker compose up -d --remove-orphans
sleep 8
curl --fail --silent https://"${PUBLIC_HOST:-localhost}"/health || docker compose exec -T app curl --fail http://127.0.0.1:8080/health
