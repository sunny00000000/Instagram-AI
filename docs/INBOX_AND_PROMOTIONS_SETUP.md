# Inbox and Promotions Setup

## Safety order
1. Keep `DRY_RUN=true`.
2. Keep `AUTO_REPLY_ENABLED=false`.
3. Create a Meta app and add Instagram/Messenger products as applicable.
4. Set the callback URL to `https://YOUR_HOST/webhooks/meta`.
5. Set the same random value in Meta and `META_WEBHOOK_VERIFY_TOKEN`.
6. Put the Meta App Secret in `META_APP_SECRET` on Oracle only.
7. Subscribe to supported message events for the professional account/Page.
8. Send messages from a Meta test user and inspect logs/database.
9. Enable `AUTO_REPLY_ENABLED=true` only after valid-signature, duplicate-event and dry-run checks pass.

## Required Oracle `.env` values
```dotenv
ENABLE_INSTAGRAM_MESSAGES=true
ENABLE_FACEBOOK_MESSAGES=false
AUTO_REPLY_ENABLED=false
META_APP_ID=YOUR_APP_ID
META_APP_SECRET=YOUR_APP_SECRET
META_WEBHOOK_VERIFY_TOKEN=YOUR_RANDOM_VERIFY_TOKEN
META_ACCESS_TOKEN=YOUR_LONG_LIVED_TOKEN
PROMOTION_FINAL_ACCEPTANCE_REQUIRES_OWNER=true
```

## Test commands
```bash
cd /opt/cryptopulse
docker compose up -d --build
docker compose exec app cryptopulse doctor
curl "https://YOUR_HOST/webhooks/meta?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=12345"
docker compose logs -f app
```

Never upload `.env`, tokens, app secrets, SSH keys, or webhook secrets to GitHub.
