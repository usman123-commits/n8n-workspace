# CE-5: Weekly Performance Report

**Trigger:** Schedule — Sunday 7pm
**Purpose:** Automated weekly summary to Telegram so you start Monday with full context

---

## Flow

```
Sunday 7pm trigger
    |
    v
Read all sheet tabs (Approved Leads, Campaign Log, Suppression List)
    |
    v
Code node: aggregate metrics for the past 7 days
    |
    v
Code node: detect anomalies
    |
    v
Format report message
    |
    v
Send to Telegram
```

---

## Metrics Calculated

### Volume
- Total Email 1s sent this week (new outreach)
- Total follow-ups sent (Email 2, 3, 4 combined)
- Total emails sent (all types)

### Replies
- Total replies received
- Breakdown: Interested / Soft Interested / Not Now / Unsubscribe / OOO
- Reply rate percentage (replies / emails sent)

### Pipeline
- Total leads by stage (Raw / Approved / In Sequence / Replied / Closed)
- Leads added this week
- Leads scored and qualified this week
- Leads rejected by ICP scoring

### Quality
- Approval rate (approved / total generated in CE-2)
- Average ICP score of approved leads

---

## Anomaly Flags

| Condition | Flag |
|-----------|------|
| Reply rate drops below 1.5% week-over-week | Deliverability or copy concern |
| ICP approval rate drops below 50% | Lead research criteria may need tightening |
| Unsubscribe rate > 5% of replies | Email content may be too aggressive |
| Zero replies for 7+ consecutive days | Check Gmail Postmaster Tools immediately |

---

## Telegram Report Format

```
--- Weekly Report (Mar 24 - Mar 30) ---

SENDS
  Email 1s: 18
  Follow-ups: 42
  Total: 60

REPLIES (5 total — 8.3% rate)
  Interested: 2
  Soft Interested: 1
  Not Now: 1
  Unsubscribe: 1
  OOO: 0

PIPELINE
  Raw Leads: 23
  Approved: 15
  In Sequence: 48
  Replied: 12
  Closed: 8

QUALITY
  Approval rate: 88% (22/25)
  Avg ICP score: 7.8

FLAGS
  None this week.
```

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | Schedule Trigger | Cron | Sunday 7pm |
| 2 | Read All Tabs | Google Sheets (multiple) | Approved Leads, Campaign Log, Suppression List |
| 3 | Aggregate Metrics | Code | Calculate all metrics for past 7 days |
| 4 | Detect Anomalies | Code | Compare to previous week, check thresholds |
| 5 | Format Report | Code | Build Telegram message string |
| 6 | Send Report | Telegram | Send to your chat |

---

## Key Decisions

- **Sunday 7pm:** Monday morning is planning time. Report arrives the night before
- **Telegram, not email:** Consistent with all other notifications. One channel for everything
- **Anomaly flags:** The most valuable part. Raw numbers without context don't drive action
