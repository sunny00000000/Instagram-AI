#!/usr/bin/env bash
set -Eeuo pipefail

if command -v docker >/dev/null 2>&1 && docker compose ps --status running app >/dev/null 2>&1; then
  docker compose exec -T app cryptopulse doctor
  docker compose exec -T app curl --fail http://127.0.0.1:8080/health
  if grep -Eq '^DRY_RUN=true' .env; then
    docker compose exec -T app cryptopulse run-once
  else
    echo "Live mode detected; skipping destructive publishing smoke run."
  fi
else
  python -m cryptopulse.cli doctor
  pytest -q
fi
