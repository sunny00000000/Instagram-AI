# Security Policy

- Never commit `.env`, API keys, access tokens, private keys, or database files.
- Use a private Git repository for production credentials and deployment automation.
- Rotate Meta and AI provider tokens immediately if they are exposed.
- Keep `DRY_RUN=true` until the complete smoke test passes.
- Restrict OCI security-list ingress to TCP 22, 80, and 443; do not expose the database.
- Use a long random `MEDIA_SIGNING_SECRET` and HTTPS for public media URLs.
- Generated media URLs are signed and time-limited. Raw market/news payloads are not published.
- The system uses only public or authorized data sources. It must not ingest confidential, hacked, or non-public information.
