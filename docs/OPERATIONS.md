# Operations Runbook

## Daily checks

```bash
cd /opt/cryptopulse
docker compose ps
docker compose logs --since=24h app | tail -n 300
curl https://PUBLIC_HOST/health
```

Verify four completed runs per UTC day and investigate failed runs.

## Manual run

```bash
docker compose exec app cryptopulse run-once
```

## Safe configuration rollout

```bash
cp .env .env.backup.$(date -u +%Y%m%dT%H%M%SZ)
nano .env
docker compose config
docker compose up -d --force-recreate app
docker compose exec app cryptopulse doctor
```

## Incident response

1. Set `DRY_RUN=true`.
2. Recreate the app container.
3. Preserve logs and database backup.
4. Identify the failing provider or stage.
5. Add a regression test.
6. Deploy the fix in dry-run mode.
7. Execute a manual canary.
8. Re-enable live publishing.

Commands:

```bash
sed -i 's/^DRY_RUN=false/DRY_RUN=true/' .env
docker compose up -d --force-recreate app
bash scripts/backup_db.sh
docker compose logs --since=2h app > incident.log
```

## Key rotation

After changing a secret:

```bash
nano .env
docker compose up -d --force-recreate app
docker compose exec app cryptopulse doctor
```
