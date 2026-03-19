# Cancellation Handler

**n8n ID:** `BQ6uHsWxBcegrfrv`
**Phase:** Cross-cutting (handles cancellations at any stage)
**Trigger:** Webhook (`POST /webhook/cancellation-handler`)

---

## Purpose

Processes booking cancellations triggered by Workflow 1 when Hostfully reports a cancelled reservation. Handles cleanup of CleaningJobs, Reservations, calendar events, and cleaner notifications based on the job's current status.

---

## What It Does

1. **Receives Cancellation Payload** — Accepts a POST webhook with `bookingUid` and `propertyUid`.

2. **Looks Up Cleaning Job** — Finds the CleaningJobs row by `bookingUid`.

3. **Checks if Job Exists** — If no matching job is found, the workflow stops (NoOp).

4. **Routes by Job Status** — Uses a Switch node to handle differently:

### PENDING Path (no cleaner assigned yet)
5. **Updates CleaningJobs** — Sets `status = "CANCELLED"`.
6. **Updates Reservations** — Sets `cleaningStatus = "CANCELLED"`.
7. **Logs to CancelledBookings** — Appends a record with `cleanerNotified = "false"`.

### ASSIGNED Path (cleaner was already assigned)
5. **Updates CleaningJobs** — Sets `status = "CANCELLED"`, `calendarStatus = "CANCELLED"`, clears `calendarEventId` and `adminCalendarEventId`.
6. **Updates Reservations** — Sets `cleaningStatus = "CANCELLED"`.
7. **Updates Admin Calendar Event** — Renames event to "CANCELLED – [propertyUid]".
8. **Updates Cleaner Calendar Event** — Renames event to "CANCELLED – [propertyUid]".
9. **Looks Up Cleaner Email** — Reads CleanersProfile by `cleanerId` to get email.
10. **Looks Up Property Name** — Reads Properties by `propertyUid` for the email subject.
11. **Sends Cancellation Email** — Notifies the cleaner via Gmail that the booking has been cancelled and no action is required.
12. **Logs to CancelledBookings** — Appends a record with `cleanerNotified = "true"`.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| CleaningJobs | Read + Update |
| Reservations | Update |
| CancelledBookings | Append |
| CleanersProfile | Read (ASSIGNED path only) |
| Properties | Read (ASSIGNED path only) |

---

## External Services

- Google Calendar (update events — ASSIGNED path only)
- Gmail (send cancellation notification — ASSIGNED path only)
