# Troubleshooting

## `Insufficient eligible assets`

- Add a CoinGecko Demo key.
- Check provider rate limits and logs.
- Reduce market-cap/volume thresholds only after assessing manipulation risk.

## Gemini 429 or 503

```dotenv
LLM_MAX_CONCURRENCY=1
LLM_BATCH_SIZE=10
```

Restart and retry later. The provider uses exponential backoff but free-tier quotas still apply.

## Caddy certificate failure

- Confirm ports 80 and 443 are open in both OCI and UFW.
- Confirm `PUBLIC_HOST` resolves to the OCI public IP.
- Do not include `https://` in `PUBLIC_HOST`.
- Include `https://` in `PUBLIC_BASE_URL`.

## Meta cannot fetch media

- Open the exact signed media URL from a different internet connection.
- Check URL expiry.
- Confirm Caddy HTTPS is trusted.
- Confirm generated files still exist.
- Increase `MEDIA_URL_TTL_SECONDS` and `MEDIA_DELETE_GRACE_HOURS`.

## Reel missing

```bash
which ffmpeg
docker compose exec app ffmpeg -version
```

The system skips Reels if FFmpeg is unavailable but still creates carousel and Story assets.

## OCI instance is reclaimed or stopped

Always Free idle-instance reclamation and regional capacity policies can change. Keep database backups and Git as the source of truth for code. Recreate the VM, restore `.env` securely, restore the database, and run the deployment script.
