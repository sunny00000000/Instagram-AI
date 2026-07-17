#!/usr/bin/env bash
set -Eeuo pipefail

APP_DIR="${APP_DIR:-/opt/cryptopulse}"
TARGET_COMMIT="${1:-}"
if [[ -z "${TARGET_COMMIT}" ]]; then
  echo "Usage: bash scripts/rollback.sh <known-good-git-commit>"
  exit 1
fi
cd "${APP_DIR}"
git fetch --all --tags
git checkout --detach "${TARGET_COMMIT}"
docker compose build
docker compose up -d --remove-orphans
sleep 8
docker compose exec -T app curl --fail http://127.0.0.1:8080/health
