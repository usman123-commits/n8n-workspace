# CE-2: Email Generation + Telegram Approval

**Trigger:** Schedule — 8am daily
**Purpose:** Generate personalized Email 1 for approved leads, get human approval via Telegram

---

## Flow

```
8am daily trigger
    |
    v
Read Approved Leads (where "Email 1 Generated" is empty)
    |
    v
Limit to 25 leads per batch
    |
    v
Claude Email Generation (claude-sonnet-4-6)
    → Input: lead data + scoring notes + email angle + 4 template references
    → Output JSON: { subject, body }
    |
    v
Send to Telegram with Approve / Reject buttons
    |
    ├── [Approve] → Write subject + body to sheet → Mark "Ready to Send"
    │
    └── [Reject] → Prompt for feedback → Claude regenerates → Re-send for approval
                    (up to 3 iterations, then flag for manual review)
```

---

## Nodes

| # | Node | Type | Details |
|---|------|------|---------|
| 1 | Schedule Trigger | Cron | 8am daily |
| 2 | Read Approved Leads | Google Sheets | Filter: Email 1 Generated = empty |
| 3 | Limit | Limit | Cap at 25 per batch |
| 4 | Claude Email Generation | HTTP Request (Claude API) | claude-sonnet-4-6. Template-guided |
| 5 | Telegram Send Preview | Telegram | Message with subject, body, Approve/Reject buttons |
| 6 | Telegram Webhook | Telegram Trigger | Receives button callback (separate trigger or sub-workflow) |
| 7 | IF Approved | IF | Route based on button pressed |
| 8 | Write to Sheet (Approved) | Google Sheets | Update Email 1 Subject, Email 1 Body, Ready to Send |
| 9 | Request Feedback | Telegram | Ask user for rejection reason |
| 10 | Claude Regenerate | HTTP Request (Claude API) | Original + feedback → new version |
| 11 | Retry Counter | IF | iteration < 3 → loop back to Telegram preview |
| 12 | Flag Manual Review | Google Sheets | Mark lead for manual handling |

---

## Claude Email Generation Prompt Guidelines

- Receives: lead name, business name, city, review snippets, website content, ICP score, pain signal, email angle
- Receives: 4 email templates as style references
- Must match template tone: short paragraphs, conversational, one-sentence CTA
- Must never mention Pakistan or sender's location
- Must write in clean American English
- Must end with soft CTA (20-minute call)
- Output: JSON with separate `subject` and `body` fields

---

## Telegram Approval Message Format

```
--- New Email for Review ---

Lead: Sarah Johnson — Sparkle Clean Co (Austin, TX)
ICP Score: 8/10
Pain Signal: Reviews mention team coordination issues

Subject: {{ subject }}

{{ body }}

[Approve] [Reject]
```

---

## Architecture Note: Telegram Buttons

The Approve/Reject inline buttons require a **Telegram Trigger node** (webhook)
to receive the callback. This means either:

**Option A:** Split into 2 workflows
- CE-2a: Schedule → Generate → Send Telegram preview
- CE-2b: Telegram Trigger → Handle approval/rejection → Update sheet

**Option B:** Use n8n's Wait node
- Single workflow with Wait node that pauses until Telegram webhook fires

Option A is simpler and more reliable for n8n.

---

## Key Decisions

- **claude-sonnet-4-6 for generation** (not haiku): Email writing quality matters. Sonnet produces better personalization
- **25 per batch cap:** You review each email. 25 takes ~15-20 min. More than that = rubber-stamping
- **3 rejection iterations max:** Prevents infinite loops. After 3 rejects, manual review
- **Templates as style references:** Constrains Claude to your validated tone, not its default formal style

---

## Open Question

**Follow-up emails (2, 3, 4):** This workflow only generates Email 1.
Where do follow-up email bodies come from? Options:
1. Static templates per sequence position (simpler, less personalized)
2. AI-generated at the same time as Email 1 (more complex, better quality)
3. AI-generated on-demand by CE-3 when due (most flexible, adds latency)
