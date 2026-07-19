# Instagram-AI Real User Test Report

**Repository:** `sunny00000000/Instagram-AI`  
**Audited branch:** `main`  
**Audited commit:** `15ae8de44c69141c58aa9ae99914d6bd0f3a5b94`  
**Test date:** 2026-07-19  
**Corrected build:** `v0.1.1-testfix`

## Executive result

The application core is functional and passed linting, type checking, compilation, unit tests, mock integration tests, API lifecycle checks, media generation, and user-configuration scenarios. The current GitHub repository, however, was uploaded inside an extra `cryptopulse_ai/` directory. That layout breaks the documented root-level installation commands, Oracle deployment scripts, and GitHub Actions discovery.

The corrected build in this package is flattened so `Dockerfile`, `docker-compose.yml`, `pyproject.toml`, `scripts/`, `src/`, and `.github/workflows/` are at the repository root.

## Exact-source verification

Because the test runtime could not resolve GitHub's public clone hostname, the repository source was tested from the previously generated release mirror. The following Git blob hashes were compared against GitHub and matched:

| File | GitHub/current blob SHA | Result |
|---|---|---|
| `README.md` | `e09a1faf78f8eacf06a123127e9f7e6f6b6c4288` | Matched |
| `cryptopulse_ai/pyproject.toml` | `6f0bc9ba0b6a3690963b2290bf5ee3cdf9cb7cc1` | Matched |
| `cryptopulse_ai/Dockerfile` | `6bb265d404362964783c671133fa99f84aa99bd6` | Matched |
| `cryptopulse_ai/src/cryptopulse/config.py` | `ce24bdea94bb10ac4f733f7a93585b9bbfb9ad09` | Matched |

## Tests on current `main` code

| Test | Result |
|---|---|
| Editable Python installation | Passed when executed inside `cryptopulse_ai/` |
| Hashed production dependency installation | Passed |
| Ruff lint | Passed |
| Mypy strict checks | Passed: 28 source files |
| Python bytecode compilation | Passed |
| Pytest | Passed: 7/7 |
| Overall test coverage | 76% |
| Sample image generation | Passed: 26 PNG files |
| FastAPI `/health` | HTTP 200 |
| FastAPI `/ready` in safe dry-run | HTTP 200 |
| Prometheus `/metrics` | HTTP 200 |
| API documentation endpoint | HTTP 200 in test environment |
| Secret-pattern scan | No real API keys/private keys found |
| Bandit security scan | No high-severity findings; two medium and four low review items |
| Dependency vulnerability audit | Not completed because the runtime could not reach PyPI |
| Docker image execution | Not completed because no Docker daemon was available in the test runtime |
| Live Gemini/CoinGecko/Meta calls | Not executed without user credentials |

### Coverage areas needing live integration validation

- CoinGecko provider: approximately 38%
- Gemini/OpenAI provider: approximately 45%
- Meta publisher: approximately 32%
- News provider: approximately 30%
- Reel/video generation service: approximately 26%

These modules rely heavily on external services and require staged canary testing with real credentials.

## Real user scenarios reproduced

### 1. Beginner follows README from repository root — failed on current GitHub layout

The root contains `README.md`, but `pyproject.toml`, `Dockerfile`, `docker-compose.yml`, `scripts/`, and source code are inside `cryptopulse_ai/`.

Observed failure:

```text
ERROR: file:///.../Instagram-AI does not appear to be a Python project:
neither setup.py nor pyproject.toml found.
```

### 2. Oracle beginner follows documented deployment — failed on current GitHub layout

The documentation expects:

```text
/tmp/cryptopulse-source/scripts/bootstrap_oci.sh
/opt/cryptopulse/docker-compose.yml
```

The current repository actually places those files below `cryptopulse_ai/`, so the paths do not exist where the scripts expect them.

### 3. GitHub Actions user — failed on current GitHub layout

The workflows were uploaded under:

```text
cryptopulse_ai/.github/workflow/ci.yml
cryptopulse_ai/.github/workflow/deploy-oci.yml
```

GitHub only discovers workflow files under root `.github/workflows/`. No workflow run was attached to the audited latest commit.

### 4. Native Python user outside Docker — failed on current defaults

The existing `.env.example` used `/app/data/...` paths intended for the container. A normal non-root local user received a permission error while trying to create `/app`.

### 5. Instagram-only and Facebook-only dry-run users — misleading output

The old dry-run publisher reported Instagram and Facebook records without respecting the per-platform flags. It also did not accurately model Story and Reel records.

### 6. Custom configuration user — partially ignored

Several content/QC strings were fixed to “Top 5” and “6 hours” even when `TOP_FINAL_PER_SIDE` or `PREDICTION_HORIZON_HOURS` changed.

## Corrections included in `v0.1.1-testfix`

- Flattened repository structure suitable for GitHub, Docker, CI, and OCI.
- Root `.github/workflows/ci.yml` and `.github/workflows/deploy-oci.yml`.
- Safe beginner defaults:
  - `DRY_RUN=true`
  - `LLM_PROVIDER=heuristic`
  - all publishing switches disabled
  - generated media retained for review
- Cross-platform relative development paths (`./data/...`).
- Docker Compose still overrides storage with `/app/data/...` inside the container.
- Dry-run publication records now respect Instagram-only, Facebook-only, Story, and Reel switches.
- Content, QC, covers, score labels, and filenames respect configured pick count and prediction horizon.
- OCI deploy/update/rollback/backup scripts detect both flattened and legacy nested layouts.
- Added realistic user-scenario tests.

## Validation of corrected build

| Test | Result |
|---|---|
| Ruff lint | Passed |
| Mypy | Passed: 28 source files |
| Compilation | Passed |
| Pytest | Passed: 11/11 |
| Shell syntax | Passed |
| Docker Compose YAML parse | Passed |
| OCI cloud-init YAML parse | Passed |
| GitHub CI YAML parse | Passed |
| GitHub deploy YAML parse | Passed |
| Beginner safe-default scenario | Passed |
| Instagram-only scenario | Passed |
| Facebook-only scenario | Passed |
| Custom 3-pick/12-hour scenario | Passed |
| Mock all-format E2E | Passed: carousels, Stories, and two Reels |
| Nested-layout OCI deployment simulation | Passed |

The all-format mock run completed with 18 publication records, 26 PNG files, two MP4 files, and successful QC for both bullish and bearish packages.

## Credentials required for staged live testing

Never commit or send any secret value in chat.

### Required for AI analysis

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=<store only in Oracle .env>
GEMINI_MODEL=gemini-3.5-flash
```

### Strongly recommended for market scanning

```dotenv
COINGECKO_API_KEY=<store only in Oracle .env>
```

### Required for Instagram/Facebook publishing

```dotenv
META_ACCESS_TOKEN=<long-lived token; secret>
INSTAGRAM_USER_ID=<non-secret account ID>
FACEBOOK_PAGE_ID=<non-secret Page ID>
PUBLIC_HOST=<public hostname>
PUBLIC_BASE_URL=https://<public hostname>
MEDIA_SIGNING_SECRET=<random secret>
```

### Required for GitHub-to-Oracle automatic deployment

Store these under GitHub repository/environment secrets:

```text
OCI_HOST
OCI_USER
OCI_SSH_PRIVATE_KEY
```

Do not upload the Oracle private key as a repository file.

## Staged live test gate

1. Deploy fixed code with `DRY_RUN=true` and all publishing disabled.
2. Validate health, readiness, database, renderer, and scheduler.
3. Add CoinGecko key and run one market/news scan.
4. Add Gemini key, retain `DRY_RUN=true`, and review AI output.
5. Configure HTTPS and verify signed media URLs from an external network.
6. Add Meta credentials and enable only Instagram carousel publishing.
7. Publish one controlled canary carousel and verify the returned post ID.
8. Enable Facebook album publishing and test once.
9. Enable Stories only after the account is confirmed eligible.
10. Enable Reels and verify MP4 upload/processing.
11. Keep the scheduler disabled until all canaries pass.
12. Enable the six-hour schedule and monitor the first 24 hours.

## Remaining boundary

A clean mock test suite cannot prove that external credentials, account permissions, provider quotas, Meta review status, DNS, TLS, and Oracle networking are correct. Those items require the staged live tests above.
