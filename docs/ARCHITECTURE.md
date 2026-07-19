# Architecture

## System objective

Execute a complete market-intelligence-to-social-publication cycle every six hours without creating one operating-system process or container per cryptocurrency.

## Logical agent hierarchy

```text
CEO Orchestrator
├── Market Manager
│   ├── paginated market workers
│   └── preliminary scoring workers
├── News Manager
│   ├── RSS workers
│   └── GDELT global-news worker
├── Research Manager
│   ├── history workers
│   ├── project-profile workers
│   └── Gemini/OpenAI analysis batches
├── Decision Board
│   ├── technical confirmation
│   ├── news/fundamental score
│   └── contradiction/risk adjustment
├── Content Studio
│   ├── caption/hashtag worker
│   ├── carousel renderer
│   ├── Story renderer
│   └── Reel builder
├── Quality Gate
│   ├── deterministic checks
│   └── independent AI review
├── Publishing Manager
│   ├── Instagram publisher
│   └── Facebook publisher
├── Learning Agent
│   └── six-hour result evaluator
└── Cleanup Agent
    └── media retention enforcement
```

## Execution guarantees

- Single-run file lock prevents overlapping cycles.
- Scheduler `max_instances=1` provides a second overlap control.
- External calls use bounded concurrency and retries.
- QC has a maximum of two generation attempts.
- Failed QC prevents publishing.
- Failed publication marks the run failed and retains media for diagnosis/retry.
- Prediction records are only persisted after all configured publishing succeeds.
- Public media URLs are HMAC-signed and expire.

## Data flow

```text
CoinGecko all eligible assets ─┐
                              ├─> Preliminary score ─> 15 bullish / 15 bearish
RSS + GDELT news ─────────────┘                                │
                                                              v
                                         history + project profile + matched news
                                                              │
                                                              v
                                             LLM/heuristic structured analysis
                                                              │
                                                              v
                                          deterministic final decision board
                                                              │
                                             5 bullish + 5 bearish
                                                              │
                                   render → QC → publish → evaluate → cleanup
```

## Storage

SQLite is used for the zero-budget single-node deployment. The schema is designed around small retained records:

- `runs`
- `predictions`
- `publishes`
- `project_profiles`

Move to PostgreSQL when using multiple application replicas or higher write concurrency.

## Security boundaries

- API secrets exist only in `.env` on OCI.
- Database and media volumes are not exposed directly.
- Caddy terminates HTTPS.
- Media access requires a valid signed path and expiry.
- The FastAPI documentation endpoint is disabled in production.
- OCI firewall and security lists expose only SSH/HTTP/HTTPS.
