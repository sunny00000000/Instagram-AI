#!/usr/bin/env bash
set -Eeuo pipefail
python - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
