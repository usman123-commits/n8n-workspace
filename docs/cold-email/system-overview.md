# Cold Email System — Overview

**Status:** Pre-Build
**Date:** March 30, 2026
**Project:** Zelvop — Field Operations Systems

---

## What This System Does

Automated cold email outreach for Zelvop's cleaning business automation service.
Replaces Instantly.ai at current scale (20 emails/day, 1 inbox, 150 leads).

The system handles: lead qualification, personalized email generation, human approval,
sequence sending, reply handling, and weekly reporting.

---

## The 5 Workflows

| # | Workflow | Trigger | Purpose |
|---|---------|---------|---------|
| CE-1 | Lead Qualification Engine | Google Sheets (new row) | Score leads against ICP using Apify + Claude |
| CE-2 | Email Generation + Approval | Schedule (8am daily) | AI-generate personalized emails, approve via Telegram |
| CE-3 | Sequence Execution Engine | Schedule (10am + 2pm daily) | Send emails on schedule with reply detection |
| CE-4 | Reply Handler | Gmail poll (every 30 min) | Categorize replies, notify via Telegram |
| CE-5 | Weekly Report | Schedule (Sunday 7pm) | Performance summary to Telegram |

---

## Data Flow

```
You add lead to Google Sheet
        |
        v
[CE-1] Score & qualify lead (Apify + Claude)
        |
    Score >= 7? ──No──> Review Queue (manual override)
        |
       Yes
        |
        v
[CE-2] Generate Email 1 (Claude) → Telegram approval
        |
    Approved? ──No──> Regenerate with feedback (up to 3x)
        |
       Yes
        |
        v
[CE-3] Send Email 1 → wait 3 days → Email 2 → wait 3 days → Email 3 → wait 7 days → Email 4
        |
    Reply detected? ──Yes──> Stop sequence
        |                         |
        v                         v
   Continue sequence      [CE-4] Categorize reply → Telegram notification
                                  |
                          ┌───────┼───────┬──────────┬────────────┐
                          v       v       v          v            v
                     Interested  Soft   Not Now  Unsubscribe    OOO
                     (notify +  (notify (close)  (suppress)  (reschedule)
                      suggest    + 5-day
                      response)  reminder)

[CE-5] Every Sunday: aggregate all metrics → Telegram report
```

---

## Google Sheet Structure

**Spreadsheet:** To be created

| Tab | Purpose |
|-----|---------|
| Raw Leads | New leads you add during research |
| Approved Leads | Scored >= 7, ready for email generation |
| Review Queue | Scored < 7, manual review needed |
| Suppression List | Unsubscribed emails — never contact again |
| Email Templates | Template references for Claude prompt |
| Campaign Log | Every email sent (for reporting) |

---

## Tool Stack

| Tool | Role | Cost |
|------|------|------|
| n8n (self-hosted) | All workflow automation | $0 (localhost) |
| Google Sheets | Lead database + tracking | $0 |
| Gmail / Hostinger SMTP | Email sending (outreach@zelvophq.com) | $0-$1/mo |
| Claude API | ICP scoring + email generation + reply categorization | ~$5-15/mo |
| Apify | Google Maps scraping | $5/mo starter |
| Jina.ai | Website content extraction | Free tier |
| Telegram Bot | Approval workflow + notifications + reports | $0 |
| Gmail Postmaster Tools | Deliverability monitoring | $0 |

**Total:** ~$10-30/month

---

## Design Principles

1. **You only make judgment calls** — every repetitive task is automated
2. **Human-in-the-loop for quality** — every Email 1 gets your Telegram approval before sending
3. **Google Sheets is source of truth** — all state lives in the sheet
4. **Plain text emails** — Email 1 and 2 are plain text (better deliverability)
5. **Natural send patterns** — 10 emails at 10am, 10 at 2pm, random delays between each
6. **Reply-first** — always check for replies before sending follow-ups

---

## Build Order

| Week | Build | Why This Order |
|------|-------|----------------|
| 1 | CE-3 (Sending) + CE-1 (Scoring) | Sending gives immediate value; scoring removes manual work |
| 2 | CE-2 (Generation) + CE-4 (Reply Handler) | Quality layer + reply management |
| 3 | CE-5 (Reporting) + prompt refinement | Reporting + optimize based on first 2 weeks |

---

## Scale Triggers (When to Add Instantly.ai)

Add Instantly.ai when ALL of these are true:
- Running 3+ outreach inboxes simultaneously
- Sending 100+ emails/day total
- Booked at least 3 clients from this system
- Lead list exceeds 500

Until then, n8n is the better choice.

---

## Open Questions (Must Resolve Before Building)

1. **Follow-up emails (2, 3, 4):** AI-generated per lead or static templates?
2. **Email sending account:** Gmail free vs Google Workspace vs Hostinger SMTP?
3. **Volume balancing:** 25 Email 1s/day generated vs 20 total sends/day — queue overflow?
4. **Telegram approval architecture:** Needs webhook trigger for button callbacks
5. **Suppression list check:** CE-3 must check suppression list before every send
