# Workflow 2 — PHASE 2: Cleaner Assignment + Calendar Dispatch

**n8n ID:** `AU1w579al67hGom7`
**Phase:** 2 (Cleaner Assignment)
**Trigger:** Schedule (every few minutes)

---

## Purpose

Picks up PENDING cleaning jobs created by Workflow 1 and assigns a cleaner, creates calendar events, sends the assignment email, and generates the clock-in link. This is the bridge between "booking received" and "cleaner knows about the job".

---

## What It Does

1. **Loads Reference Data** — Reads Properties, CleanersProfile, and all CleaningJobs tabs upfront. These are used throughout the workflow for lookups.

2. **Finds Unassigned Jobs** — Reads CleaningJobs, filters to only rows where `status=PENDING`, `cleanerId` is empty, no `calendarEventId`, and no `processingFlag` (row-level lock).

3. **Locks Each Job** — Sets a `processingFlag` on the CleaningJobs row before processing. This prevents a second run from picking up the same job.

4. **Enriches with Reservation Data** — Looks up the Reservations tab by `bookingUid` to get property name, address, and guest info for the email/calendar.

5. **Assigns Cleaner** — Two paths:
   - **Fixed assignment:** If the Properties row has a non-empty `fixedCleanerId`, that cleaner is assigned directly. `_isFixedAssignment = true`. Assignment count is NOT incremented.
   - **Round-robin:** If no fixed cleaner, picks from available cleaners by lowest `assignmentCount` in CleanersProfile (tiebreak: alphabetical `cleanerId`). Checks the selected cleaner has no ASSIGNED job with an overlapping `scheduledCleaningTimeUTC` window. **Fixed cleaners are excluded from this pool** — any cleaner who appears as a `fixedCleanerId` on any property is never eligible for round-robin assignment on other properties.

6. **Handles Unavailability** — If no cleaner is available (`_noCleanerAvailable = true`):
   - Sets `status = NEEDS_MANUAL_ASSIGNMENT` on the CleaningJobs row
   - Clears `processingFlag`
   - Sends an admin alert email to the admin with property name, bookingUid, and scheduled time (data pulled directly from Assign Cleaner node output)

7. **Generates Clock-In and Clock-Out Links** — Builds two React app URLs with `bookingId` and `cleanerId` as query parameters:
   - **Clock-In Link** — `https://n8n-forms.vercel.app/clockin?bookingId=...&cleanerId=...` — cleaner submits on arrival (handled by Workflow 3W)
   - **Clock-Out Link** — `https://n8n-forms.vercel.app/checkout?bookingId=...&cleanerId=...` — cleaner submits when finished (handled by Workflow 4W)

8. **Updates Job Record** — Writes `cleanerId`, `assignedAt`, `clockInLink`, and `clockOutLink` to CleaningJobs.

9. **Increments Assignment Count** — Adds 1 to the cleaner's `assignmentCount` in CleanersProfile. Fixed assignments skip incrementing. If `_needsReset = true` (current date past `assignmentCountResetDateUTC`), count resets to 0 and a new reset date (first of next month UTC) is written.

10. **Creates Calendar Events** — Creates two Google Calendar events (start = scheduledCleaningTimeUTC, end = start + 3 hours):
    - Admin calendar (master view of all cleanings)
    - Cleaner-specific calendar (shared as view-only to the cleaner)
    - Event description includes both clock-in and clock-out links (labeled Step 1 / Step 2)
    - Skips if `calendarEventId` already exists (no duplicates)

11. **Stores Calendar Event IDs** — Writes `calendarEventId` and `adminCalendarEventId` back to CleaningJobs for future updates/cancellations.

12. **Sends Assignment Email** — Gmail to the cleaner with: property name, address, date, time, guest count, booking reference, calendar link, clock-in link (Step 1), and clock-out link (Step 2).

13. **Finalizes** — Sets `status=ASSIGNED`, clears the `processingFlag` lock, and updates Reservations `cleaningStatus=ASSIGNED`.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| Properties | Read (`fixedCleanerId` for fixed assignment, property name, address) |
| CleanersProfile | Read (`cleanerId`, email, calendarId, assignmentCount) + Update (assignmentCount, assignmentCountResetDateUTC) |
| CleaningJobs | Read (all rows for availability) + Update (assignment, calendar IDs, status) |
| Reservations | Read (guest info) + Update (cleaningStatus) |

---

## External Services

- Google Calendar (create events on admin + cleaner calendars)
- Gmail (send assignment email to cleaner, admin alert if no cleaner available)

---

## Key Design Decisions

- **Row-level locking** via `processingFlag` prevents race conditions between schedule runs
- **Fixed vs round-robin** — Properties sheet controls assignment mode per property via `fixedCleanerId`; if empty, round-robin by `assignmentCount` kicks in
- **CleanersProfile uses `cleanerId`** — all lookups and sheet matching use `cleanerId`, not `fixedCleanerId`
- **Restore node after sheet update** — a `Restore Job Data After Count Update` Code node re-attaches full job data after the Google Sheets update node (which only returns the columns it wrote)
- **Admin alert uses node reference** — `Send Admin Alert` references `$('Assign Cleaner').item.json` directly so `propertyName`, `bookingUid`, and `scheduledCleaningTimeUTC` are always populated correctly
- **Calendar is view-only** — cleaners cannot edit events; all changes go through workflows
- **Both links sent upfront** — clock-in (Step 1) and clock-out (Step 2) links are delivered together in the assignment email and calendar event. Cleaner has everything from day one, no second email needed after clock-in
- **`clockOutLink` stored in CleaningJobs** — `clockOutLink` column (AA) added alongside `clockInLink` (AB) for Workflow 4B to reference
- **Fixed cleaners excluded from round-robin** — the Assign Cleaner node builds a set of all `fixedCleanerId` values across all Properties rows and removes them from the round-robin pool. This prevents a cleaner fixed to property A from being assigned to property B via round-robin.

---

## Tested Scenarios

| Test | Expected | Result |
|------|----------|--------|
| Normal assignment (cleaner available) | Cleaner assigned, calendar events created, Gmail sent, sheets updated | ✅ Pass |
| Fixed property assignment (`fixedCleanerId` set) | Fixed cleaner assigned, `_isFixedAssignment=true`, count not incremented | ✅ Pass |
| No cleaner available (all busy) | `_noCleanerAvailable=true`, status=NEEDS_MANUAL_ASSIGNMENT, admin alert sent with correct property name | ✅ Pass |
| Clock-out link in email + calendar | Email contains both Step 1 (clock-in) and Step 2 (clock-out) links. Calendar description contains both. CleaningJobs row has `clockOutLink` populated | ⏳ Needs retest |
| Fixed cleaner not spilling into other properties | Cleaner fixed to Eagle's Nest should NOT be assigned to 120 Opry House via round-robin | ✅ Pass (exec #3755) |
| Fixed cleaner assigned to their own property | Eagle's Nest job → Nouman assigned, `_isFixedAssignment=True` | ✅ Pass (exec #3756) |
