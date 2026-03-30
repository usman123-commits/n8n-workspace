# Cold Email — Tools and Credentials

---

## External Services Required

### 1. Claude API (Anthropic)
- **Used by:** CE-1 (scoring), CE-2 (email generation), CE-4 (reply categorization)
- **Models:**
  - `claude-haiku-4-5` — ICP scoring + reply categorization (fast, ~$0.001/call)
  - `claude-sonnet-4-6` — Email generation (better writing, ~$0.01/call)
- **n8n node:** HTTP Request to `https://api.anthropic.com/v1/messages`
- **Auth:** API key in header `x-api-key`
- **Estimated cost:** $5-15/month at 20 emails/day

### 2. Apify
- **Used by:** CE-1 (Google Maps scraping)
- **Actor:** Google Maps Scraper
- **Returns:** Business category, review count, rating, review texts, website URL, phone
- **n8n node:** HTTP Request to Apify API
- **Auth:** Apify API token
- **Cost:** $5/month starter (500 scrapes/month)

### 3. Jina.ai Reader
- **Used by:** CE-1 (website content extraction)
- **Endpoint:** `https://r.jina.ai/{url}`
- **Returns:** Clean rendered text of JS-heavy sites (Wix, Squarespace)
- **n8n node:** HTTP Request
- **Auth:** Free tier (no auth needed for basic usage)
- **Cost:** Free at current volume

### 4. Telegram Bot
- **Used by:** CE-2 (approval), CE-4 (reply notifications), CE-5 (weekly report)
- **Setup:** Create bot via @BotFather on Telegram
- **n8n node:** Telegram node (send) + Telegram Trigger node (receive button callbacks)
- **Auth:** Bot token from BotFather
- **Cost:** Free

### 5. Gmail / SMTP
- **Used by:** CE-3 (sending), CE-4 (inbox polling)
- **Account:** outreach@zelvophq.com
- **n8n node:** Gmail node (for reading) + SMTP node or Gmail node (for sending)
- **Auth:** OAuth2 or App Password
- **Cost:** Free (Gmail) or ~$1/mo (Hostinger)

### 6. Gmail Postmaster Tools
- **Used by:** Manual weekly check (not automated)
- **URL:** https://postmaster.google.com
- **Purpose:** Domain spam rate, IP reputation, domain reputation
- **Cost:** Free

---

## n8n Credential Setup Required

| Credential | Type | Service | Workflows |
|------------|------|---------|-----------|
| Google Sheets account | OAuth2 | Google Sheets | CE-1, CE-2, CE-3, CE-4, CE-5 |
| Gmail account | OAuth2 | Gmail | CE-3, CE-4 |
| Claude API | HTTP Header Auth | Anthropic API | CE-1, CE-2, CE-4 |
| Apify API | HTTP Header Auth | Apify | CE-1 |
| Telegram Bot | Telegram API | Telegram | CE-2, CE-4, CE-5 |

> Google Sheets and Gmail credentials already exist from the cleaning project.
> New credentials needed: Claude API, Apify API, Telegram Bot.

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
