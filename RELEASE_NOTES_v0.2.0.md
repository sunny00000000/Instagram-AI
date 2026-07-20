# CryptoPulse AI v0.2.0

## Added
- Signed Meta webhook verification and ingestion
- Instagram/Facebook message event parser
- Echo-event filtering and message-ID deduplication
- Human-readable AI-assisted greeting disclosure
- Crypto-question safety replies
- Complaint escalation
- Promotion extraction, scoring and red-flag detection
- Automatic high-risk scam rejection
- Mandatory owner approval for final advertising acceptance
- Minimal conversation audit table
- Safe disabled-by-default environment configuration

## Validation
- Ruff passed
- Mypy passed for 32 source files
- Python compilation passed
- Pytest passed: 19/19
- HMAC signature valid/invalid scenarios passed
- Normal follower, crypto question, complaint, incomplete promotion, complete promotion and scam scenarios passed

## Live boundary
Live Meta delivery was not executed because no Meta App Secret, access token, professional account or test user credentials were supplied. Keep `AUTO_REPLY_ENABLED=false` until Meta test-account validation succeeds.
