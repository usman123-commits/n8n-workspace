# Accept/Decline Feature — Minimal Test Plan

**Workflows under test:** Workflow 2 (modified), Workflow 2B, Workflow 2C
**Pre-conditions:**
- CleaningJobs sheet has columns: `offeredTo`, `offeredAt`, `declinedBy`
- At least one PENDING cleaning job exists with no cleaner assigned
- At least 2 cleaners in CleanersProfile (for decline → next cleaner flow)
- n8n running, all 3 workflows active (or triggered manually)

---

## Test 1 — Happy Path: Round-Robin Offer → Accept

**What it tests:** Workflow 2 sends offer email, cleaner accepts, job becomes ASSIGNED.

### Steps
1. Ensure a PENDING job exists in CleaningJobs (empty cleanerId, empty offeredTo)
2. Trigger Workflow 2 (click Test in n8n UI or wait for schedule)
3. Check CleaningJobs row → should be `status=OFFERED`, `offeredTo=<cleanerId>`, `offeredAt=<timestamp>`
4. Check cleaner's email → offer email received with Accept/Decline links
5. Click the **Accept** link in the email
6. Browser shows green "Job Accepted!" page

### Expected sheet state after accept
```
status         = ASSIGNED
offeredTo      = (empty)
offeredAt      = (empty)
cleanerId      = <cleanerId>
calendarEventId = <event ID>
clockInLink    = <URL>
checkoutLink   = <URL>
processingFlag = (empty)
```
### Expected emails
- Cleaner: confirmation email with property, date, time, clock-in/out links

### Expected calendar
- Admin calendar: new event for the cleaning time
- Cleaner calendar: new event with clock-in/out links in description

---

## Test 2 — Round-Robin Offer → Decline → Next Cleaner

**What it tests:** Decline resets to PENDING, Workflow 2 picks up and offers to next cleaner.

### Steps
1. Same setup as Test 1
2. After offer email arrives, click **Decline**
3. Browser shows yellow "Job Declined" page
4. Check CleaningJobs → `status=PENDING`, `declinedBy=<cleanerId1>`, `cleanerId=(empty)`
5. Wait for Workflow 2 to run again (or trigger manually)
6. Check CleaningJobs → `status=OFFERED`, `offeredTo=<cleanerId2>` (different cleaner)
7. Check second cleaner's email → offer email received
8. Click Accept → job becomes ASSIGNED

### Key check
- `declinedBy` must contain the first cleaner's ID after decline
- Second offer must NOT go to the same cleaner (they're in `declinedBy`)

---

## Test 3 — Offer Timeout (Workflow 2C)

**What it tests:** No response for 1 hour → treated as decline → next cleaner offered.

### Steps
1. Manually set a job row in CleaningJobs:
   - `status = OFFERED`
   - `offeredTo = <cleanerId>`
   - `offeredAt = <timestamp 2 hours ago>` (e.g., `2026-04-15T08:00:00.000Z`)
   - `declinedBy = (empty)`
2. Trigger Workflow 2C (click Test in n8n UI)
3. Check CleaningJobs → `status=PENDING`, `declinedBy=<cleanerId>`, `offeredTo=(empty)`
4. Trigger Workflow 2 → should offer to next available cleaner

---

## Test 4 — All Cleaners Decline → Admin Alert

**What it tests:** When all round-robin cleaners are in `declinedBy`, job gets NEEDS_MANUAL_ASSIGNMENT.

### Steps
1. Set a job in CleaningJobs:
   - `status = PENDING`
   - `declinedBy = <all cleaner IDs comma-separated>` (e.g., `CLN001,CLN002,CLN003`)
   - `cleanerId = (empty)`
2. Trigger Workflow 2
3. Assign Cleaner node finds 0 available cleaners (all in declinedBy)
4. Check CleaningJobs → `status=NEEDS_MANUAL_ASSIGNMENT`
5. Check admin email → alert email received

---

## Test 5 — Fixed Property: Auto-Assign (No Offer)

**What it tests:** Fixed-property jobs skip the offer flow entirely.

### Steps
1. Ensure the PENDING job's `propertyUid` is a property with `fixedCleanerId` set in the Properties sheet
2. Trigger Workflow 2
3. Job should go directly from PENDING → ASSIGNED (no OFFERED state, no offer email)
4. Check email → full assignment email (not an offer), with clock-in/out links

### Key check
- No offer email sent
- `offeredTo` and `offeredAt` remain empty
- Job never touches `status=OFFERED`

---

## Test 6 — Edge Cases for Workflow 2B

### 6a — Click Accept link twice
1. Accept a job (Test 1)
2. Click the same Accept link again
3. Browser should show red "Error: This job has already been accepted."
4. Verify no duplicate calendar events created

### 6b — Click with wrong cleanerId
```
GET /webhook/job-response?bookingUid=XXX&cleanerId=WRONG&response=accept
```
Browser should show red "Error: This offer was not sent to you."

### 6c — Missing query params
```
GET /webhook/job-response?bookingUid=XXX
```
Browser should show red "Error: Missing required parameters."

---

## Curl Commands for Tests 3 / 6b / 6c

```bash
# Test 6b: wrong cleanerId
curl -s "http://localhost:5678/webhook-test/job-response?bookingUid=TEST&cleanerId=WRONG&response=accept"

# Test 6c: missing params
curl -s "http://localhost:5678/webhook-test/job-response?bookingUid=TEST"

# Trigger 2C manually (use Test Workflow in n8n UI — no webhook)
```

---

## Pass Criteria Summary

| Test | Pass When |
|------|-----------|
| 1 — Accept | Job = ASSIGNED, calendar created, confirmation email received |
| 2 — Decline → next | declinedBy updated, second offer goes to different cleaner |
| 3 — Timeout | 2C resets expired offer to PENDING, declinedBy updated |
| 4 — All decline | NEEDS_MANUAL_ASSIGNMENT, admin alert email sent |
| 5 — Fixed assign | No OFFERED state, direct ASSIGNED, no offer email |
| 6a — Double accept | Second click returns "already accepted" error page |
| 6b — Wrong cleaner | Returns "not sent to you" error page |
| 6c — Missing params | Returns "missing parameters" error page |
