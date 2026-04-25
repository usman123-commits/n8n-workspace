# CE-1: Lead Qualification Engine

**Workflow ID:** `4TaA4kHwa5r1GULP`
**Trigger:** Google Sheets — row added in "Raw Leads" tab
**Status:** Built & tested ✅
**Purpose:** Automatically score every new lead against ICP criteria

---

## Flow

```
Row added to Raw Leads
    |
    v
Filter Already Scored
    → skips rows where ICP Score is already filled
    |
    v
Apify Google Maps Scraper (Actor: nwua9Gu5YrADL7ZDj)
    → POST /v2/acts/{actorId}/runs  — starts the scrape
    → Wait 90 seconds
    → GET /v2/datasets/{defaultDatasetId}/items  — fetches results
    → returns: category, review count, rating, last 20 reviews,
               website URL, phone, booking link detected
    |
    v
Jina.ai Website Fetch
    → GET https://r.jina.ai/{websiteURL}
    → returns clean rendered text (handles Wix, Squarespace)
    |
    v
Combine Data (Code node)
    → merges Apify + Jina into single item
    → truncates website text to 4000 chars for Claude context
    |
    v
Claude ICP Scoring (claude-haiku-4-5-20251001)
    → POST https://api.anthropic.com/v1/messages
    → Input: reviews + website text + business metadata
    → Output: { score: 1-10, reason, painSignal, emailAngle }
    → Note: Claude wraps response in ```json fences — stripped before parsing
    |
    v
Score Router (IF node)
    |
    ├── Score >= 7 → Append to "Approved Leads" tab
    │                + Update ICP Score in Raw Leads
    │
    └── Score < 7  → Append to "Review Queue" tab
                     + Update ICP Score in Raw Leads
```

---

## ICP Scoring Criteria (embedded in Claude prompt)

| Signal | What to Look For | Weight |
|--------|-----------------|--------|
| Team size | Reviews mentioning "the team", "crew", multiple cleaners | High |
| Booking method | WhatsApp/phone = good (manual pain). Online system = less need | High |
| Review count | 40-80 is sweet spot (established but not enterprise) | Medium |
| Airbnb/vacation rental | Mentioned in reviews or website | High (proven use case) |
| Franchise tags | Chain brand detected | Auto-disqualify (score 1) |
| Owner responds to reviews | Personal engagement = decision maker accessible | Medium |

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | New Lead Trigger | Google Sheets Trigger | `rowAdded` event on Raw Leads tab |
| 2 | Filter Already Scored | Filter | Passes only rows where `ICP Score` is empty AND `Google Maps URL` is not empty |
| 3 | Apify Start Scraper | HTTP Request | POST to Apify actor `nwua9Gu5YrADL7ZDj`. Body: `{ startUrls, maxReviews: 20 }` |
| 4 | Wait for Scraper | Wait | 90 seconds — Apify needs time to complete the scrape |
| 5 | Apify Get Results | HTTP Request | GET `https://api.apify.com/v2/datasets/{defaultDatasetId}/items` |
| 6 | Extract Apify Data | Code | Pulls category, reviews, rating, phone, booking link from Apify output |
| 7 | Jina Website Fetch | HTTP Request | GET `https://r.jina.ai/{websiteURL}` — no auth needed |
| 8 | Combine Data | Code | Merges Apify + Jina, truncates website text to 4000 chars |
| 9 | Claude ICP Scoring | HTTP Request | POST to Claude API. Headers: `x-api-key`, `anthropic-version: 2023-06-01` |
| 10 | Parse Claude Score | Code | Strips markdown fences, parses JSON, extracts score/reason/painSignal/emailAngle |
| 11 | Score Router | IF | `icpScore >= 7` → true branch (Approved), else false branch (Review Queue) |
| 12 | Write Approved Leads | Google Sheets | Append to Approved Leads tab (gid: 1866609254) |
| 13 | Write Review Queue | Google Sheets | Append to Review Queue tab (gid: 989136210) |
| 14 | Update Raw Lead Score | Google Sheets | Update `ICP Score` column in Raw Leads, matched by `Business Name` |

---

## Google Sheet — Raw Leads Tab Columns

| Column | Source | Description |
|--------|--------|-------------|
| Row ID | Manual | Unique identifier (e.g. ROW-001) |
| Business Name | Manual | Name of the cleaning business |
| Owner First Name | Manual | Owner / decision maker first name |
| Owner Last Name | Manual | Owner / decision maker last name |
| City | Manual | City / metro area |
| Business Phone | Manual | Phone number |
| Website URL | Manual | Business website |
| Google Maps URL | Manual | Google Maps listing link |
| Yelp URL | Manual | Yelp listing (optional) |
| Source | Manual | Where lead was found (e.g. Google Maps) |
| Date Added | Manual | Date lead was added |
| Research Notes | Manual | Your notes (email source, flags, etc.) |
| ICP Score | CE-1 | 1-10 from Claude. Empty = not yet scored |

---

## Key Decisions

- **Apify over direct scraping:** Google Maps blocks direct scraping. Apify actors handle anti-bot measures
- **`defaultDatasetId` for results:** Apify run response includes `defaultDatasetId` — more reliable than constructing URL from run ID
- **90s wait:** Apify scraping takes 45-90 seconds. 30s was too short and caused 404s on dataset fetch
- **Jina.ai over direct fetch:** Cleaning business sites are JS-rendered (Wix/Squarespace). Raw HTTP GET returns empty page
- **claude-haiku-4-5-20251001 for scoring:** Fast and cheap (~$0.001/call). Scoring doesn't need sonnet-level writing quality
- **Strip markdown fences:** Claude wraps JSON output in ` ```json ``` ` blocks. Parse node strips these before `JSON.parse()`
- **Review Queue instead of auto-discard:** Claude occasionally underscores good leads. Manual override preserves them
- **Filter by empty ICP Score:** Prevents re-scoring leads that the trigger picks up again on subsequent polls
