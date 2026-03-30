# CE-3: Sequence Execution Engine

**Trigger:** Schedule — 10am and 2pm daily
**Purpose:** Send the right email to the right person at the right time

---

## Flow

```
10am / 2pm trigger
    |
    v
Read all leads where:
    - Email body exists (approved)
    - Last send >= N days ago (3 for E2/E3, 7 for E4)
    - Replied column is empty
    - Sequence not closed
    - NOT in Suppression List
    |
    v
Limit to 10 per run (20/day total)
    |
    v
For each lead:
    |
    v
Reply Detection Check (Gmail search for sender)
    |
    ├── Reply found → Stop sequence → Update sheet → Telegram notification
    │
    └── No reply → Continue
                    |
                    v
              Random delay (5-20 min)
                    |
                    v
              Send email via Gmail SMTP
              (plain text for E1/E2, signature for E3/E4)
                    |
                    v
              Update sheet: lastSendDate, emailStep, status = "In Sequence"
```

---

## Sequence Timing

| Email | Days After Previous | Format | Tracking Pixel |
|-------|-------------------|--------|----------------|
| Email 1 | Immediate (after approval) | Plain text | No |
| Email 2 | +3 days | Plain text | No |
| Email 3 | +3 days | Plain text + signature | Optional |
| Email 4 | +7 days | Plain text + signature | Optional |

Total sequence duration: ~13 days per lead

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | Schedule Trigger | Cron | 10am and 2pm |
| 2 | Read Due Leads | Google Sheets | Filter by timing + status logic |
| 3 | Check Suppression List | Google Sheets | Cross-reference against suppressed emails |
| 4 | Limit | Limit | Cap at 10 per run |
| 5 | Gmail Reply Check | Gmail | Search inbox for sender's email address |
| 6 | IF Reply Found | IF | Route: reply found vs no reply |
| 7 | Stop Sequence | Google Sheets | Update: Replied = date, status = REPLIED |
| 8 | Reply Telegram Alert | Telegram | Notify with reply content + context |
| 9 | Wait (Random Delay) | Wait | 5-20 min random delay between sends |
| 10 | Send Email | Gmail (SMTP) | Send from outreach@zelvophq.com |
| 11 | Update Sheet | Google Sheets | lastSendDate, emailStep, status |

---

## Send Safety Rules

- **Max 10 emails per run** (20/day across 2 runs)
- **Max 30-50 per inbox per day** (Gmail safe threshold)
- **Random 5-20 min delay** between each send (avoids bot-like burst)
- **Two daily windows** (10am + 2pm) mimics human email behavior
- **Reply check before every send** — prevents sending follow-up to someone who already replied
- **Suppression list check** — never email someone who unsubscribed
- **Plain text for E1/E2** — bypasses many spam filters, looks like a real person typed it
- **No tracking pixels in E1/E2** — tracking pixels are a spam signal

---

## Key Decisions

- **10am + 2pm split:** Looks like human checking email twice a day. A single 20-email burst at 10am looks automated
- **Reply check per-lead, per-send:** Timing matters. Reply on Day 3, follow-up on Day 4 = you look like a bot
- **Plain text first:** HTML/images/tracking pixels = marketing email to spam filters. Plain text = normal person

---

## Cross-Workflow Dependencies

- **CE-2 → CE-3:** Email 1 body and subject must exist in sheet (written by CE-2 after approval)
- **CE-4 → CE-3:** Suppression list (populated by CE-4) must be checked before every send
- **CE-3 → CE-4:** Both update the sheet's Replied column — CE-3 stops sequence, CE-4 categorizes

---

## Open Questions

1. **Follow-up email content:** Where do Email 2, 3, 4 bodies come from?
2. **Inbox rotation:** Current plan is 1 inbox. When scaling to 2-4, CE-3 needs rotation logic
3. **Race condition with CE-4:** Both workflows update reply status. Which is authoritative?
