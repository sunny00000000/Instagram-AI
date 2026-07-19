# Testing Strategy

## Test layers

- Unit: scoring, signing, rendering, QC, cleanup
- Integration: complete mock market-to-dry-publish pipeline
- Container: image build and health command
- External sandbox: Gemini and Meta test-account canaries
- Production canary: one manual run before six-hour automation

## Commands

```bash
python -m pip install -e '.[dev]'
ruff check src tests
pytest -q
coverage run -m pytest
coverage report -m
docker build -t cryptopulse-ai:test .
docker run --rm --env-file .env cryptopulse-ai:test cryptopulse doctor
```

External live APIs are intentionally not called by the automated test suite because tests must be deterministic and must never publish content.
