# Workflow 2B -- Job Response Handler

**n8n ID:** `IZIywHWhoK32cp7Z`
**Phase:** 2 (Cleaner Assignment -- Accept/Decline)
**Trigger:** Webhook GET `/webhook/job-response`

---

## Purpose

Handles a cleaner's response (accept or decline) to a job offer sent by Workflow 2. When a cleaner clicks Accept or Decline in their offer email, this webhook processes the response, updates all systems, and returns a confirmation page.

---

## Prerequisites

This workflow requires three new columns in the **CleaningJobs** sheet (gid `2047086003`):

| Column | Purpose |
|--------|---------|
| `offeredTo` | cleanerId of the cleaner currently being offered the job |
| `offeredAt` | ISO timestamp of when the offer was sent (for timeout logic) |
| `declinedBy` | Comma-separated list of cleanerIds who declined this job |

These columns are written by Workflow 2 (when making an offer) and read/cleared by this workflow.

---

## Webhook URL

```
GET http://localhost:5678/webhook/job-response?bookingUid=XXX&cleanerId=YYY&response=accept
GET http://localhost:5678/webhook/job-response?bookingUid=XXX&cleanerId=YYY&response=decline
```

**Query parameters:**

| Param | Required | Values |
|-------|----------|--------|
| `bookingUid` | Yes | The booking's unique ID |
| `cleanerId` | Yes | The cleaner's ID (must match `offeredTo` on the job) |
| `response` | Yes | `accept` or `decline` |

---

## What It Does

### 1. Validate Request
- Extracts query parameters from the webhook URL
- Reads the CleaningJobs row by `bookingUid`
- Validates:
  - All 3 params present
  - Job exists and has `status=OFFERED`
  - `offeredTo` matches the `cleanerId` in the request
  - If already ASSIGNED: returns "already accepted" error page
  - If status is anything else: returns "no longer available" error page

### 2. Route via Switch
Routes to one of three paths based on validation result:
- **Accept** -- full assignment flow
- **Decline** -- reset to PENDING for next offer
- **Error** -- returns error HTML page

---

### Accept Path (15 nodes)

1. **Read Cleaner Row** -- CleanersProfile filtered by cleanerId (email, calendarId, name)
2. **Read Property Row** -- Properties filtered by propertyUid (address, propertyName)
3. **Lookup Reservation** -- Reservations filtered by bookingUid (guest info)
4. **Build Accept Data** -- Merges job + cleaner + property + reservation into one item
5. **Generate Links** -- Creates clock-in and checkout URLs (same logic as Workflow 2)
6. **Calculate Time** -- Computes startTime/endTime from `scheduledCleaningTimeUTC` + 3 hours
7. **Create Admin Calendar Event** -- On admin calendar (usman2acountf@gmail.com)
8. **Create Cleaner Calendar Event** -- On cleaner's calendar with clock-in/out links in description
9. **Prepare Event IDs** -- Extracts calendar event IDs from create responses
10. **Update Job Accepted** -- Sets CleaningJobs: `status=ASSIGNED`, calendar IDs, links, clears `offeredTo`/`offeredAt`
11. **Respond Accepted** -- Returns HTML confirmation page to cleaner's browser (green "Job Accepted!")
12. **Send Confirmation Email** -- Full assignment email to cleaner (same content as Workflow 2's email)
13. **Compute Count** -- Calculates new assignmentCount (skips increment for fixed assignments)
14. **Update Count** -- Writes new count to CleanersProfile
15. **Update Reservation Status** -- Sets `cleaningStatus=ASSIGNED` on Reservations tab

> The webhook responds (step 11) **before** sending email and updating counts, so the cleaner gets instant feedback.

---

### Decline Path (3 nodes)

1. **Build Decline Data** -- Appends cleanerId to existing `declinedBy` comma-separated list
2. **Update Job Declined** -- Sets CleaningJobs: `status=PENDING`, clears `cleanerId`/`assignedCleaner`/`assignedAt`/`offeredTo`/`offeredAt`, writes updated `declinedBy`
3. **Respond Declined** -- Returns HTML page (yellow "Job Declined -- will be offered to another cleaner")

> After decline, status returns to PENDING so Workflow 2 picks it up again on next schedule run. Workflow 2's assignment logic must skip cleaners listed in `declinedBy`.

---

### Error Path (1 node)

1. **Respond Error** -- Returns HTML page (red "Error" with specific message)

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| CleaningJobs | Read (filter by bookingUid) + Update (assignment or decline) |
| CleanersProfile | Read (filter by cleanerId) + Update (assignmentCount) |
| Properties | Read (filter by propertyUid) |
| Reservations | Read (filter by bookingUid) + Update (cleaningStatus) |

---

## External Services

- Google Calendar (create admin + cleaner events) -- Accept path only
- Gmail (send confirmation email) -- Accept path only

---

## Key Design Decisions

- **GET webhook** -- Cleaner clicks a link in email, which is a browser GET request. No forms, no logins.
- **Respond before email** -- The Respond to Webhook node fires before email/count/reservation updates. Cleaner sees confirmation instantly; background tasks complete after.
- **Filtered sheet reads** -- Instead of reading all rows and filtering in Code (like Workflow 2), this workflow uses Google Sheets `filtersUI` to read only the exact row needed. More efficient for a single-job handler.
- **Idempotent validation** -- Clicking the accept link twice returns "already accepted" error page instead of creating duplicate events.
- **Decline resets to PENDING** -- The declined job goes back to PENDING status with the declining cleaner added to `declinedBy`. Workflow 2's scheduler picks it up and offers to the next available cleaner (skipping those in `declinedBy`).
- **Space clears** -- Uses `" "` (single space) to clear fields like `offeredTo`, matching the existing pattern in Workflow 2 for `processingFlag`.

---

## HTML Response Pages

| Response | Background Color | Title |
|----------|-----------------|-------|
| Accepted | Green (#f0fdf4) | "Job Accepted!" |
| Declined | Yellow (#fefce8) | "Job Declined" |
| Error | Red (#fef2f2) | "Error" + specific message |

All pages are mobile-friendly (viewport meta tag) and tell the cleaner to close the page.

---

## Interaction with Other Workflows

| Workflow | Relationship |
|----------|-------------|
| **Workflow 2** | Sends the offer email with Accept/Decline links pointing to this webhook. Sets `status=OFFERED`, `offeredTo`, `offeredAt`. |
| **Workflow 2C** | Timeout checker. If 1 hour passes with no response, treats as decline and resets to PENDING. |
| **Workflow 3/3W** | Clock-in ingestion. Only works after job is ASSIGNED (which this workflow sets on accept). |
| **Cancellation Handler** | If a booking is cancelled while OFFERED, cancellation handler should clear the offer and notify the cleaner. |

---

## Testing

### Test Accept
```bash
curl -s "http://localhost:5678/webhook-test/job-response?bookingUid=TEST123&cleanerId=CLN001&response=accept"
```

### Test Decline
```bash
curl -s "http://localhost:5678/webhook-test/job-response?bookingUid=TEST123&cleanerId=CLN001&response=decline"
```

### Test Error (missing params)
```bash
curl -s "http://localhost:5678/webhook-test/job-response?bookingUid=TEST123"
```

> Note: Use `webhook-test` path during development (n8n test mode). Production uses `webhook`.

---

## Tested Scenarios

| Test | Expected | Result |
|------|----------|--------|
| Accept with valid OFFERED job | ASSIGNED, calendar created, email sent, links generated | Pending |
| Decline with valid OFFERED job | PENDING, cleanerId cleared, declinedBy updated | Pending |
| Click accept link twice | Second click returns "already accepted" error page | Pending |
| Wrong cleanerId for this offer | Returns "offer was not sent to you" error page | Pending |
| Job already cancelled | Returns "no longer available" error page | Pending |
| Missing query parameters | Returns "missing parameters" error page | Pending |
