# Workflow 2C -- Offer Timeout Checker

**n8n ID:** `DQbsPmZGHAI4JVDl`
**Phase:** 2 (Cleaner Assignment -- Timeout handling)
**Trigger:** Schedule (every 10 minutes)

---

## Purpose

Monitors OFFERED cleaning jobs and detects when a cleaner has not responded within the timeout window (1 hour). Treats a timeout the same as a decline: adds the cleaner to `declinedBy` and resets the job to PENDING so Workflow 2 can offer it to the next available cleaner.

This is the safety net that prevents jobs from being stuck in OFFERED status forever.

---

## What It Does

1. **Read Offered Jobs** -- Reads CleaningJobs filtered to `status=OFFERED`
2. **Filter Expired** -- Keeps only jobs where `offeredAt` is more than 60 minutes ago
3. **Split In Batches** -- Processes one expired offer at a time
4. **Build Timeout Data** -- Adds the timed-out cleaner (`offeredTo`) to `declinedBy` list
5. **Reset Job to PENDING** -- Updates CleaningJobs:
   - `status` = PENDING
   - Clears `cleanerId`, `assignedCleaner`, `assignedAt`, `offeredTo`, `offeredAt`, `processingFlag`
   - Writes updated `declinedBy`
6. **Loop** -- Returns to Split In Batches for the next expired offer

---

## Configuration

The timeout duration is set in the **Filter Expired** Code node:

```js
const TIMEOUT_MINUTES = 60; // 1 hour
```

To change the timeout, edit this value. The schedule interval (10 minutes) can be adjusted in the Schedule Trigger node.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| CleaningJobs | Read (filter status=OFFERED) + Update (reset to PENDING) |

---

## External Services

None. This workflow only reads and writes to Google Sheets.

---

## Key Design Decisions

- **No admin alert here** -- When all cleaners have been exhausted (all in `declinedBy`), this workflow does NOT send the admin alert. Instead, it resets to PENDING and lets Workflow 2 handle it. Workflow 2's existing logic will find no available cleaners and trigger `NEEDS_MANUAL_ASSIGNMENT` + admin alert email. This avoids duplicating alert logic.

- **Timeout = decline** -- A non-response is treated identically to an explicit decline. The cleaner is added to `declinedBy` so they won't be offered the same job again.

- **10-minute scan interval** -- Checks every 10 minutes. A job offered at :00 with a 60-minute timeout will be detected as expired somewhere between :60 and :70 (worst case 10 minutes late). This is acceptable for jobs scheduled hours or days ahead.

- **Batch processing** -- Uses Split In Batches to handle multiple expired offers one at a time, avoiding write conflicts on the same sheet.

---

## Interaction with Other Workflows

| Workflow | Relationship |
|----------|-------------|
| **Workflow 2** | Sets `status=OFFERED`, `offeredTo`, `offeredAt` when making an offer. After 2C resets to PENDING, Workflow 2 picks the job up again and offers to the next available cleaner (skipping those in `declinedBy`). If no cleaners remain, Workflow 2 sets NEEDS_MANUAL_ASSIGNMENT + admin alert. |
| **Workflow 2B** | If the cleaner responds (accept/decline) before the timeout, 2B processes it and 2C never sees the job (status is no longer OFFERED). |

---

## Worst-Case Timeline (all 3 cleaners unresponsive)

With 3 cleaners, 1-hour timeout, and 10-minute scan interval:

| Time | Event |
|------|-------|
| T+0 min | Workflow 2 offers to Cleaner A (status=OFFERED) |
| T+60-70 min | 2C detects timeout, resets to PENDING |
| T+71 min | Workflow 2 offers to Cleaner B |
| T+131-141 min | 2C detects timeout, resets to PENDING |
| T+142 min | Workflow 2 offers to Cleaner C |
| T+202-212 min | 2C detects timeout, resets to PENDING |
| T+213 min | Workflow 2 finds all in declinedBy, sets NEEDS_MANUAL_ASSIGNMENT, sends admin alert |

**Total worst case: ~3.5 hours** before admin is alerted. This is fine for jobs scheduled days ahead. For same-day jobs, a shorter timeout could be configured.

---

## Tested Scenarios

| Test | Expected | Result |
|------|----------|--------|
| One OFFERED job past 1 hour | Reset to PENDING, offeredTo added to declinedBy | Pending |
| Multiple OFFERED jobs past 1 hour | Each processed individually via batch loop | Pending |
| OFFERED job under 1 hour | Skipped (not expired yet) | Pending |
| No OFFERED jobs | Workflow runs and exits cleanly (no items to process) | Pending |
| offeredAt is empty or invalid | Skipped by Filter Expired (treated as not expired) | Pending |
