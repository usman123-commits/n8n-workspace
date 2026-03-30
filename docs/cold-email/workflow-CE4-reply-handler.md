# CE-4: Reply Handler and Categorization

**Trigger:** Schedule — every 30 minutes (Gmail poll)
**Purpose:** Categorize every reply and route the right info to you immediately

---

## Flow

```
Every 30 min: poll outreach inbox
    |
    v
For each new email:
    |
    v
Match sender against Google Sheet leads
    |
    ├── Not a lead → Ignore
    │
    └── Lead found → Get full context (sequence stage, ICP score, pain signal)
                      |
                      v
                 Claude Categorization (claude-haiku-4-5)
                      |
          ┌───────────┼───────────┬──────────────┬────────────────┐
          v           v           v              v                v
     INTERESTED   SOFT INT    NOT NOW      UNSUBSCRIBE          OOO
          |           |           |              |                |
          v           v           v              v                v
     Telegram:    Telegram:   Update sheet:  Add to            Extract
     full reply   context +   status =       Suppression       return date
     + suggested  schedule    CLOSED         List.             Reschedule
     response     5-day                      Silent.           Email 2 to
     + Send/Edit  follow-up                  No notification   return + 2 days
     buttons      reminder                                     |
                                                               v
                                                          Notify only if
                                                          return > 3 weeks
```

---

## Reply Categories

| Category | Claude Detection | Action | Notification |
|----------|-----------------|--------|--------------|
| Interested | Wants to learn more, book a call | Stop sequence, suggest response | Telegram: full reply + suggested response + Send/Edit buttons |
| Soft Interested | Positive but not ready ("sounds interesting but...") | Stop sequence, schedule follow-up | Telegram: context + 5-day reminder in sheet |
| Not Now | Timing/budget objection | Close sequence | Update sheet only |
| Unsubscribe | "Remove me", "stop emailing" | Suppress permanently | Silent — no notification |
| Out of Office | Auto-reply with return date | Pause sequence, reschedule | Telegram only if return > 3 weeks |

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | Schedule Trigger | Cron | Every 30 min |
| 2 | Gmail Read | Gmail | Fetch new emails from outreach inbox |
| 3 | Read Leads Sheet | Google Sheets | Get all leads for matching |
| 4 | Match Sender | Code | Check if sender email exists in leads data |
| 5 | Get Lead Context | Code | Pull sequence stage, ICP score, pain signal |
| 6 | Claude Categorize | HTTP Request (Claude API) | claude-haiku-4-5. Input: reply text + lead context |
| 7 | Category Router | Switch | Route by category field |
| 8 | Handle Interested | Google Sheets + Telegram | Update sheet + send notification with suggested response |
| 9 | Handle Soft Interested | Google Sheets + Telegram | Update sheet + schedule follow-up reminder |
| 10 | Handle Not Now | Google Sheets | Update status = CLOSED |
| 11 | Handle Unsubscribe | Google Sheets | Add to Suppression List tab |
| 12 | Handle OOO | Code + Google Sheets | Extract return date, reschedule follow-up |
| 13 | OOO Long Absence Alert | IF + Telegram | Notify only if return > 3 weeks |

---

## Claude Categorization Prompt

Input:
- Reply text (full email body)
- Lead context: name, business, sequence stage, ICP score, pain signal

Output JSON:
```json
{
  "category": "interested|soft_interested|not_now|unsubscribe|ooo",
  "confidence": 0.95,
  "returnDate": "2026-04-15",  // only for OOO
  "suggestedResponse": "..."   // only for interested/soft_interested
}
```

Why Claude over keyword matching: "We had a system built last year but it stopped working" is
INTERESTED (proven budget + need). Keyword matching would miss this entirely.

---

## Key Decisions

- **30-min poll (not real-time):** Gmail push notifications require Pub/Sub setup. Polling is simpler and 30 min is fast enough for cold email replies
- **claude-haiku-4-5 for categorization:** Fast, cheap. Categorization is simpler than email generation
- **Silent unsubscribe handling:** No notification clutter for leads that opt out
- **OOO smart rescheduling:** Email 2 rescheduled to return date + 2 days (gives them time to catch up)
- **Suggested response for Interested:** Claude drafts a reply using the prospect's own language. You can send with one tap or edit

---

## Cross-Workflow Dependencies

- **CE-3 ↔ CE-4:** Both detect and record replies. CE-3 checks before sending. CE-4 categorizes and notifies.
  - **Resolution:** CE-4 is authoritative for categorization. CE-3 only checks if ANY reply exists (simple boolean). CE-4 handles the detailed routing.
- **CE-4 → CE-3:** Suppression List (written by CE-4) is read by CE-3 before every send
- **CE-4 → Sheet:** OOO rescheduling modifies the lead's next send date, which CE-3 reads
