# Real User Test Report — v0.2.0

## Result
The application passed all automated and simulated real-user scenarios available without external credentials.

| Persona/scenario | Expected behavior | Result |
|---|---|---|
| New follower says hello | Transparent, natural greeting | PASS |
| Follower asks whether Bitcoin will rise | No guarantee; asks for coin/post detail | PASS |
| User reports misleading content | Acknowledge, collect evidence, owner escalation | PASS |
| Advertiser sends incomplete offer | Request website, domain email, budget, contract, rights and dates | PASS |
| Advertiser sends complete credible offer | Initial verification only; mandatory owner review | PASS |
| Scammer requests seed phrase/fee | Automatic rejection; no secrets disclosed | PASS |
| Meta sends echo event | Ignored | PASS |
| Meta retries same message ID | Deduplicated by database unique key and lookup | PASS |
| Invalid webhook HMAC | HTTP 403 | PASS |
| Valid verification challenge | Returns exact challenge | PASS |
| Auto reply disabled | Event may be classified/stored without sending | PASS by design |
| Dry-run reply enabled | Simulated message ID returned | PASS |

## Remaining live tests
- Meta developer webhook subscription
- Instagram professional test-account message delivery
- Facebook Page Messenger delivery
- 24-hour messaging-window behavior
- Production token expiry/renewal
- Real sender-language response quality with Gemini

These require the owner's Meta credentials and cannot be truthfully certified offline.
