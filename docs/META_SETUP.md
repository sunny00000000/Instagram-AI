# Meta Setup

## Account requirements

Use an eligible Instagram professional account connected to a Facebook Page. Create a Meta app and request the permissions required by the current Instagram/Facebook content-publishing APIs.

## Configuration

```dotenv
DRY_RUN=true
META_GRAPH_VERSION=v25.0
META_ACCESS_TOKEN=...
INSTAGRAM_USER_ID=...
FACEBOOK_PAGE_ID=...
PUBLIC_HOST=your-domain.example
PUBLIC_BASE_URL=https://your-domain.example
MEDIA_SIGNING_SECRET=...
```

## Validation sequence

1. Keep `DRY_RUN=true`.
2. Confirm Caddy obtains a trusted HTTPS certificate.
3. Confirm a signed generated media URL is reachable from a network outside OCI.
4. Confirm token permissions and IDs with Meta API tools.
5. Use a test account or controlled Page for the first live run.
6. Set `DRY_RUN=false`.
7. Run `cryptopulse run-once` manually.
8. Confirm every returned Meta post ID and inspect all published content.
9. Monitor logs for delayed container-processing errors.

## Why media is not deleted instantly

Meta creates asynchronous media containers and may fetch the source after the initial API call. The application waits for container completion and uses a default 24-hour cleanup grace to avoid broken publication. Reduce the grace only after observing your account’s reliable processing behavior.
