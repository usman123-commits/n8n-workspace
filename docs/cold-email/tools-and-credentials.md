# Cold Email — Tools and Credentials

---

## n8n Credentials (configured & ready)

| Credential Name | n8n ID | Type | Header | Used By |
|----------------|--------|------|--------|---------|
| `Google Sheets account` | `q52dbWoN6OaKRDZO` | OAuth2 | — | CE-1, CE-2, CE-3, CE-4, CE-5 |
| `Google Sheets Trigger account` | `E2pL4RCwwnxZSv1L` | OAuth2 | — | CE-1 trigger |
| `Claude API` | `zlY2A0vDJbGDd7Ey` | HTTP Header Auth | `x-api-key` | CE-1, CE-2, CE-4 |
| `Apify API` | `JFJHpRwTtiSH45ng` | HTTP Header Auth | `Authorization: Bearer` | CE-1 |
| `Gmail account` | `6sr232YN6z3c4tiW` | OAuth2 | — | CE-3, CE-4 |

**Still needed (not yet created):**
| Credential | Type | Used By |
|------------|------|---------|
| `Telegram Bot` | Telegram API | CE-2, CE-4, CE-5 |

---

## External Services

### 1. Claude API (Anthropic)
- **Used by:** CE-1 (scoring), CE-2 (email generation), CE-4 (reply categorization)
- **Models:**
  - `claude-haiku-4-5-20251001` — ICP scoring + reply categorization (fast, ~$0.001/call)
  - `claude-sonnet-4-6` — Email generation (better writing, ~$0.01/call)
- **Endpoint:** `POST https://api.anthropic.com/v1/messages`
- **Required headers:** `x-api-key`, `anthropic-version: 2023-06-01`, `content-type: application/json`
- **Note:** Claude sometimes wraps JSON output in markdown fences — always strip before parsing

### 2. Apify
- **Used by:** CE-1 (Google Maps scraping)
- **Actor ID:** `nwua9Gu5YrADL7ZDj` (Google Maps Scraper)
- **Flow:** POST to start run → wait 90s → GET dataset items via `defaultDatasetId`
- **Results endpoint:** `GET https://api.apify.com/v2/datasets/{defaultDatasetId}/items`
- **Auth:** `Authorization: Bearer {token}` header
- **Cost:** $5/month starter (500 scrapes/month)

### 3. Jina.ai Reader
- **Used by:** CE-1 (website content extraction)
- **Endpoint:** `GET https://r.jina.ai/{url}`
- **Returns:** Clean rendered text of JS-heavy sites (Wix, Squarespace)
- **Auth:** None required for free tier
- **Cost:** Free at current volume

### 4. Telegram Bot
- **Used by:** CE-2 (approval), CE-4 (reply notifications), CE-5 (weekly report)
- **Setup:** Create bot via @BotFather on Telegram
- **n8n node:** Telegram node (send) + Telegram Trigger node (receive button callbacks)
- **Status:** Not yet set up

### 5. Gmail / SMTP
- **Used by:** CE-3 (sending), CE-4 (inbox polling)
- **Account:** outreach@zelvophq.com
- **n8n node:** Gmail node (reading) + Gmail/SMTP node (sending)
- **Auth:** OAuth2 (credential already exists: `Gmail account`)

---

## Monthly Cost Summary

| Service | Cost | Notes |
|---------|------|-------|
| n8n | $0 | Self-hosted (localhost) |
| Google Sheets | $0 | Free |
| Gmail / Hostinger SMTP | $0-1 | Free Gmail or Rs. 99/mo Hostinger |
| Claude API | $5-15 | ~$0.001/scoring call + ~$0.01/generation call |
| Apify | $5 | Starter plan, 500 scrapes/month |
| Jina.ai | $0 | Free tier |
| Telegram | $0 | Free |
| Gmail Postmaster | $0 | Free |
| **Total** | **$10-21** | At 20 emails/day, 150 leads |

---

## Domain Setup Checklist

Before sending cold emails, verify:

- [ ] SPF record set for zelvophq.com
- [ ] DKIM signing enabled
- [ ] DMARC policy published
- [ ] Domain warmed for 3-4 weeks (manual warmup with trusted contacts)
- [ ] Gmail Postmaster Tools verified for zelvophq.com
- [ ] outreach@zelvophq.com inbox created and accessible
