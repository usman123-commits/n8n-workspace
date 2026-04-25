# Cold Email — Google Sheets Schema

**Spreadsheet:** Cold Email Outreach — Zelvop
**Spreadsheet ID:** `1XZFkpgFbidxelGcZZ6_C3YjwktAJOqFbZ9h-AlndcXU`
**Same rules as cleaning project:** Always use `mode: "id"` for documentId and sheetName

---

## Sheet Tab IDs

| Tab Name | Sheet ID (gid) | Purpose |
|----------|----------------|---------|
| `Raw Leads` | `0` | New leads for scoring |
| `Approved Leads` | `1866609254` | Scored >= 7, ready for email |
| `Review Queue` | `989136210` | Scored < 7, manual review |

---

## Tab: Raw Leads

Where you add new leads during research. CE-1 processes these.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| Row ID | Text | Manual | Unique ID (e.g. ROW-001) |
| Business Name | Text | Manual | Business name |
| Owner First Name | Text | Manual | Owner / decision maker first name |
| Owner Last Name | Text | Manual | Owner / decision maker last name |
| City | Text | Manual | City / metro area |
| Business Phone | Text | Manual | Phone number |
| Website URL | Text | Manual | Business website |
| Google Maps URL | Text | Manual | Google Maps listing link |
| Yelp URL | Text | Manual | Yelp listing (optional) |
| Source | Text | Manual | Where lead came from (e.g. Google Maps) |
| Date Added | Date | Manual | Date lead was added |
| Research Notes | Text | Manual | Email source, ICP flags, notes |
| ICP Score | Number | CE-1 | 1-10 from Claude. Empty = not yet scored |

> **CE-1 filter logic:** only processes rows where `ICP Score` is empty AND `Google Maps URL` is not empty.

---

## Tab: Approved Leads

Leads scored >= 7, ready for email generation and sequence.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| businessName | Text | CE-1 | Copied from Raw Leads |
| contactName | Text | CE-1 | Owner first name |
| contactEmail | Text | CE-1 | Email for outreach |
| city | Text | CE-1 | City |
| icpScore | Number | CE-1 | Score (>= 7) |
| painSignal | Text | CE-1 | Detected pain |
| emailAngle | Text | CE-1 | Suggested angle |
| email1Subject | Text | CE-2 | Generated subject line |
| email1Body | Text | CE-2 | Generated email body |
| email1Approved | Boolean | CE-2 | Approved via Telegram |
| email2Body | Text | TBD | Follow-up email 2 content |
| email3Body | Text | TBD | Follow-up email 3 content |
| email4Body | Text | TBD | Follow-up email 4 content |
| currentStep | Number | CE-3 | Which email was last sent (1-4) |
| lastSendDate | DateTime | CE-3 | When last email was sent |
| nextSendDate | DateTime | CE-3 | When next email is due |
| status | Text | CE-3/4 | READY / IN_SEQUENCE / REPLIED / CLOSED / UNSUBSCRIBED |
| repliedAt | DateTime | CE-3/4 | When reply was received |
| replyCategory | Text | CE-4 | interested / soft_interested / not_now / unsubscribe / ooo |
| followUpDate | DateTime | CE-4 | For soft interested / OOO rescheduling |
| approvedAt | DateTime | CE-2 | When email was approved |

---

## Tab: Review Queue

Leads scored < 7, awaiting manual review.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| businessName | Text | CE-1 | Business name |
| contactName | Text | CE-1 | Owner first name |
| contactEmail | Text | CE-1 | Email |
| city | Text | CE-1 | City |
| icpScore | Number | CE-1 | Score (< 7) |
| icpReason | Text | CE-1 | Why scored low |
| painSignal | Text | CE-1 | Any pain detected |
| decision | Text | Manual | APPROVE / DISCARD |
| decisionNotes | Text | Manual | Why you overrode |

---

## Tab: Suppression List

Emails that must never be contacted again.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| email | Text | CE-4 | Suppressed email address |
| reason | Text | CE-4 | unsubscribe / bounce / manual |
| suppressedAt | DateTime | CE-4 | When added |
| leadName | Text | CE-4 | Original lead name (for reference) |

---

## Tab: Campaign Log

Every email sent, for reporting and audit.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| contactEmail | Text | CE-3 | Recipient |
| businessName | Text | CE-3 | Business |
| emailStep | Number | CE-3 | 1, 2, 3, or 4 |
| subject | Text | CE-3 | Subject line used |
| sentAt | DateTime | CE-3 | Send timestamp |
| sentFrom | Text | CE-3 | Sending inbox |

---

## Tab: Email Templates

Reference templates for Claude's email generation prompt.

| Column | Type | Source | Description |
|--------|------|--------|-------------|
| templateName | Text | Manual | e.g., "Template A - Pain Point" |
| subject | Text | Manual | Example subject line |
| body | Text | Manual | Full email text |
| notes | Text | Manual | When to use this style |

---

## Cross-Tab Dependencies

```
Raw Leads ──[CE-1]──> Approved Leads (score >= 7)  +  ICP Score written back
                  └──> Review Queue (score < 7)     +  ICP Score written back

Approved Leads ──[CE-2]──> email1Subject, email1Body filled
               ──[CE-3]──> status, currentStep, lastSendDate updated
               ──[CE-4]──> replyCategory, repliedAt updated

Suppression List <──[CE-4]── unsubscribe replies added
                 ──[CE-3]──> checked before every send

Campaign Log <──[CE-3]── every send recorded
             ──[CE-5]──> read for weekly metrics
```
