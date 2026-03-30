# Cold Email Automation — Architecture Plan

**Status:** Planning
**Date:** March 30, 2026

---

## Overview

Automated cold email outreach system. Handles the full pipeline:
lead collection, email verification, campaign sending, reply tracking, and follow-ups.

---

## Planned Workflows

| # | Workflow | Purpose |
|---|---------|---------|
| CE-1 | Lead Ingestion | Import leads from Google Sheets / CSV / manual entry |
| CE-2 | Email Verification | Verify email addresses before sending (reduce bounces) |
| CE-3 | Campaign Sender | Send initial cold emails on schedule (with rate limiting) |
| CE-4 | Reply Tracker | Monitor inbox for replies, categorize (interested / not interested / bounce) |
| CE-5 | Follow-Up Sender | Send follow-up emails to non-responders on schedule |
| CE-6 | Analytics | Track open rates, reply rates, bounce rates in Google Sheets |

---

## Planned Google Sheets Tabs

| Tab | Purpose |
|-----|---------|
| Leads | All leads with contact info, company, status |
| Campaigns | Campaign definitions (subject, body template, schedule) |
| EmailLog | Every email sent (timestamp, lead, campaign, status) |
| Replies | Tracked replies with categorization |
| Bounces | Failed deliveries |
| Analytics | Aggregated metrics |

---

## Design Principles

1. **Rate limiting** — Never exceed Gmail sending limits (500/day for regular, 2000/day for Workspace)
2. **Personalization** — Templates with merge fields (name, company, role)
3. **Bounce protection** — Verify emails before sending to protect sender reputation
4. **Opt-out handling** — Track unsubscribe requests, never email twice
5. **Follow-up cadence** — Configurable delays between follow-ups (e.g., 3 days, 7 days, 14 days)
6. **Sheets as source of truth** — All state lives in Google Sheets

---

## Status

- [ ] Define lead source and format
- [ ] Create Google Sheet with tabs
- [ ] Build CE-1: Lead Ingestion
- [ ] Build CE-2: Email Verification
- [ ] Build CE-3: Campaign Sender
- [ ] Build CE-4: Reply Tracker
- [ ] Build CE-5: Follow-Up Sender
- [ ] Build CE-6: Analytics

> This plan will be refined once the human defines the specific requirements.
