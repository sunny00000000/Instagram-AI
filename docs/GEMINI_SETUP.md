# Gemini Setup

1. Create a Gemini API key in Google AI Studio.
2. Add it only to the server `.env`.
3. Use the official `google-genai` package.
4. Start with dry-run mode and low concurrency.

```dotenv
DRY_RUN=true
LLM_PROVIDER=gemini
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-3.5-flash
LLM_BATCH_SIZE=10
LLM_MAX_CONCURRENCY=2
```

Validate:

```bash
docker compose up -d --force-recreate app
docker compose exec app cryptopulse doctor
docker compose exec app cryptopulse run-once
docker compose logs --since=30m app
```

If the API returns rate-limit errors, reduce `LLM_MAX_CONCURRENCY`, increase batch size carefully, or switch temporarily to `LLM_PROVIDER=heuristic`.
