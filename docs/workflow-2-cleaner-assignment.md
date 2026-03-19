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

5. **Assigns Cleaner** — Matches `propertyUid` to `fixedCleanerId` from the Properties tab. Checks the cleaner isn't already booked for an overlapping time window using all CleaningJobs data.

6. **Handles Unavailability** — If no cleaner is available:
   - Sets `processingFlag = "NEEDS_MANUAL"` on the job
   - Sends an admin alert email

7. **Generates Clock-In Link** — Builds a pre-filled Google Form URL with `bookingUid` and `cleanerId` embedded. This is what the cleaner clicks on arrival (Phase 3).

8. **Updates Job Record** — Writes `cleanerId`, `assignedAt`, and `clockInLink` to CleaningJobs.

9. **Increments Assignment Count** — Adds 1 to the cleaner's `assignmentCount` in CleanersProfile for workload tracking.

10. **Creates Calendar Events** — Creates two Google Calendar events (start = scheduledCleaningTimeUTC, end = start + 3 hours):
    - Admin calendar (master view of all cleanings)
    - Cleaner-specific calendar (shared as view-only to the cleaner)
    - Event description includes the clock-in link
    - Skips if `calendarEventId` already exists (no duplicates)

11. **Stores Calendar Event IDs** — Writes `calendarEventId` and `adminCalendarEventId` back to CleaningJobs for future updates/cancellations.

12. **Sends Assignment Email** — Gmail to the cleaner with: property name, address, date, time, guest count, booking reference, calendar link, and clock-in link.

13. **Finalizes** — Sets `status=ASSIGNED`, clears the `processingFlag` lock, and updates Reservations `cleaningStatus=ASSIGNED`.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| Properties | Read (fixedCleanerId, property name, address) |
| CleanersProfile | Read (email, calendarId, assignmentCount) + Update (assignmentCount) |
| CleaningJobs | Read (all rows for availability) + Update (assignment, calendar IDs, status) |
| Reservations | Read (guest info) + Update (cleaningStatus) |

---

## External Services

- Google Calendar (create events on admin + cleaner calendars)
- Gmail (send assignment email to cleaner, admin alert if no cleaner available)

---

## Key Design Decisions

- **Row-level locking** via `processingFlag` prevents race conditions between schedule runs
- **fixedCleanerId** (not round-robin) — each property has a dedicated cleaner
- **Calendar is view-only** — cleaners cannot edit events; all changes go through workflows
- **Clock-in link in email + calendar** — two channels to reach the cleaner
