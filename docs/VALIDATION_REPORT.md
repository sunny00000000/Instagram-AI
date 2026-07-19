# Release validation report

Release baseline: `0.1.0`  
Validation date: 2026-07-16 UTC

## Completed automated checks

- `ruff check src tests`: passed
- `mypy src/cryptopulse`: passed with no issues in 28 source files
- `pytest -q`: 7 tests passed
- `python -m compileall -q src tests`: passed
- Bash syntax validation for every `scripts/*.sh`: passed
- YAML parsing for Docker Compose, OCI cloud-init, and GitHub Actions: passed
- Complete mock pipeline: passed from market scan through media, QC, dry publishing, persistence, and cleanup controls
- Generated carousel and Story sample images inspected
- Credential-marker scan: no embedded API-key patterns found
- Dependency resolution: `uv.lock` and hashed `requirements.lock` generated successfully

## Environment-dependent acceptance checks

The artifact build environment did not provide a Docker daemon. Therefore the Docker image and live Compose stack must be built by CI or on the OCI host before promotion. The included GitHub CI workflow performs `docker build`, and `scripts/smoke_test.sh` performs the OCI runtime smoke test.

Live Gemini, CoinGecko, Instagram, and Facebook publication cannot be end-to-end validated without the owner's credentials, eligible Meta assets, provider quota, and a public HTTPS hostname. Keep `DRY_RUN=true` until the provider-specific checks in `README.md`, `docs/GEMINI_SETUP.md`, and `docs/META_SETUP.md` pass.

## OCI release gate

Run these commands on the Oracle instance:

```bash
cd /opt/cryptopulse
docker compose config
docker compose build --pull
docker compose up -d
docker compose ps
bash scripts/smoke_test.sh
docker compose logs --since=30m app
```

Do not change `DRY_RUN=false` unless `/ready` is healthy, a Gemini-enabled dry run succeeds, the signed media URLs are publicly reachable over HTTPS, and Meta returns valid publication IDs in a controlled test.
