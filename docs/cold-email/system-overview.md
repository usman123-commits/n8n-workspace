# Cold Email System — Overview

**Status:** CE-1 built & tested ✅ | CE-2 through CE-5 not yet built
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

| # | Workflow ID | Workflow | Trigger | Status |
|---|------------|---------|---------|--------|
| CE-1 | `4TaA4kHwa5r1GULP` | Lead Qualification Engine | Google Sheets (row added) | Built & tested ✅ |
| CE-2 | — | Email Generation + Approval | Schedule (8am daily) | Not built |
| CE-3 | — | Sequence Execution Engine | Schedule (10am + 2pm daily) | Not built |
| CE-4 | — | Reply Handler | Gmail poll (every 30 min) | Not built |
| CE-5 | — | Weekly Report | Schedule (Sunday 7pm) | Not built |

---

## Google Sheet

**Spreadsheet:** Cold Email Outreach — Zelvop
**ID:** `1XZFkpgFbidxelGcZZ6_C3YjwktAJOqFbZ9h-AlndcXU`

| Tab | Sheet ID (gid) | Purpose |
|-----|----------------|---------|
| Raw Leads | `0` | New leads you add during research |
| Approved Leads | `1866609254` | Scored >= 7, ready for email generation |
| Review Queue | `989136210` | Scored < 7, manual review needed |
| Suppression List | — (not yet created) | Unsubscribed emails — never contact again |
| Email Templates | — (not yet created) | Template references for Claude prompt |
| Campaign Log | — (not yet created) | Every email sent (for reporting) |

---

## Data Flow

```
You add lead to Raw Leads tab
        |
        v
[CE-1] Filter (skip if ICP Score already filled)
        |
        v
[CE-1] Apify scrapes Google Maps → Jina fetches website → Claude scores lead
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

## Tool Stack

| Tool | Role | Cost |
|------|------|------|
| n8n (self-hosted) | All workflow automation | $0 (localhost) |
| Google Sheets | Lead database + tracking | $0 |
| Gmail / Hostinger SMTP | Email sending (outreach@zelvophq.com) | $0-$1/mo |
| Claude API (haiku-4-5) | ICP scoring + reply categorization | ~$0.001/call |
| Claude API (sonnet-4-6) | Email generation | ~$0.01/call |
| Apify | Google Maps scraping (actor: nwua9Gu5YrADL7ZDj) | $5/mo starter |
| Jina.ai | Website content extraction | Free tier |
| Telegram Bot | Approval workflow + notifications + reports | $0 |
| Gmail Postmaster Tools | Deliverability monitoring | $0 |

**Total:** ~$10-21/month at 20 emails/day, 150 leads

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
| 1 | CE-1 (Scoring) ✅ | Removes manual qualification work immediately |
| 2 | CE-2 (Generation) + CE-3 (Sending) | Core outreach loop |
| 3 | CE-4 (Reply Handler) + CE-5 (Reporting) | Close the loop on replies and metrics |

---

## Scale Triggers (When to Add Instantly.ai)

Add Instantly.ai when ALL of these are true:
- Running 3+ outreach inboxes simultaneously
- Sending 100+ emails/day total
- Booked at least 3 clients from this system
- Lead list exceeds 500

Until then, n8n is the better choice.
