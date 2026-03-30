# CE-1: Lead Qualification Engine

**Trigger:** Google Sheets — new row in "Raw Leads" tab
**Purpose:** Automatically score every new lead against ICP criteria

---

## Flow

```
New row in Raw Leads
    |
    v
Apify Google Maps Scraper
    → business category, review count, rating,
      last 20 review texts, website URL, phone,
      booking functionality detected
    |
    v
Jina.ai Website Fetch
    → clean text of homepage + contact/booking pages
    → handles JS-rendered sites (Wix, Squarespace)
    |
    v
Claude ICP Scoring (claude-haiku-4-5)
    → Input: reviews + website text + business metadata
    → Output JSON: { score: 1-10, reason, painSignal, emailAngle }
    |
    v
Score Router (IF node)
    |
    ├── Score >= 7 → Write to "Approved Leads" tab
    │                 (score, reason, angle, timestamp)
    │
    └── Score < 7  → Write to "Review Queue" tab
                      (you can manually override)
```

---

## ICP Scoring Criteria (embedded in Claude prompt)

| Signal | What to Look For | Weight |
|--------|-----------------|--------|
| Team size | Reviews mentioning "the team", "crew", multiple cleaners | High |
| Booking method | WhatsApp/phone = good (manual pain). Online system = less need | High |
| Review count | 40-80 is sweet spot (established but not enterprise) | Medium |
| Airbnb/vacation rental | Mentioned in reviews or website | High (proven use case) |
| Franchise tags | Chain brand detected | Auto-disqualify |
| Owner responds to reviews | Personal engagement = decision maker accessible | Medium |

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | Google Sheets Trigger | Trigger | Fires on new row in Raw Leads |
| 2 | Apify Google Maps Scraper | HTTP Request | Actor: Google Maps Scraper. Input: Google Maps URL from row |
| 3 | Jina.ai Website Fetch | HTTP Request | `https://r.jina.ai/{websiteURL}`. Returns rendered text |
| 4 | Claude ICP Scoring | HTTP Request (Claude API) | claude-haiku-4-5. Prompt includes ICP criteria. Returns JSON |
| 5 | Score Router | IF | `score >= 7` → approved branch, else → review branch |
| 6 | Update Approved Leads | Google Sheets | Append to Approved Leads tab |
| 7 | Update Review Queue | Google Sheets | Append to Review Queue tab |

---

## Google Sheet Columns — Raw Leads Tab

| Column | Source | Description |
|--------|--------|-------------|
| businessName | Manual | Name of the cleaning business |
| city | Manual | City / metro area |
| websiteURL | Manual | Business website |
| googleMapsURL | Manual | Google Maps listing link |
| notes | Manual | Your research notes |
| status | Workflow | PENDING → SCORED |
| icpScore | Workflow | 1-10 from Claude |
| icpReason | Workflow | One-sentence explanation |
| painSignal | Workflow | Specific pain detected |
| emailAngle | Workflow | Suggested approach for Email 1 |
| scoredAt | Workflow | Timestamp |

---

## Key Decisions

- **Apify over direct scraping:** Google Maps blocks direct scraping. Apify actors handle anti-bot measures
- **Jina.ai over direct fetch:** Cleaning business sites are JS-rendered (Wix/Squarespace). Raw HTTP GET returns empty page
- **claude-haiku-4-5 for scoring:** Fast and cheap (~$0.001/call). Scoring doesn't need sonnet-level writing quality
- **Review Queue instead of auto-discard:** Claude occasionally underscores good leads. Manual override preserves them
- **JSON output from Claude:** Downstream nodes route on score field directly. No parsing needed
