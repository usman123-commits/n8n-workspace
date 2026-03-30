# Workflow 1A — Extended Checkout Handler

**n8n ID:** `NZNbIHz9Qutwj1fa`
**Phase:** 1 (Booking Ingestion — sub-workflow)
**Trigger:** Webhook (`POST /webhook/extended-checkout-handler`)

---

## Purpose

Handles cases where a guest's checkout time changes after the initial booking was already ingested. Called by Workflow 1 when it detects a checkout time mismatch for an existing reservation.

---

## What It Does

1. **Receives Webhook Payload** — Accepts a POST with: `bookingUid`, `propertyUid`, `cleanerId`, `oldCheckout`, `newCheckout`, `newCheckoutTimeUTC`, `newScheduledCleaningTimeUTC`, `newCleaningDate`, `newCleaningTime`.

2. **Looks Up Cleaning Job** — Finds the existing CleaningJobs row by `bookingUid`.

3. **Routes by Job Status** — Uses a Switch node to handle differently based on current job status:
   - **PENDING** — Updates the CleaningJobs row with new checkout/cleaning times. Updates the Reservations row with the new checkout. Logs to ExtendedCheckouts tab.
   - **ASSIGNED** — Same updates as PENDING, plus reschedules both the admin and cleaner calendar events to reflect the new time window, and sends the cleaner a notification email about the schedule change.

4. **Updates CleaningJobs** — Writes new values for `checkoutTimeUTC`, `scheduledCleaningTimeUTC`, `cleaningDate`, `cleaningTime`.

5. **Updates Reservations** — Writes the new `checkOut` datetime.

6. **Reschedules Calendar Events** (ASSIGNED only) — Updates both admin calendar and cleaner-specific calendar events with new start/end times.

7. **Notifies Cleaner** (ASSIGNED only) — Sends a Gmail notification to the assigned cleaner with the updated schedule details.

8. **Logs to ExtendedCheckouts** — Appends a record to the ExtendedCheckouts tab with old/new times, status at time of change, and whether the cleaner was notified.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| CleaningJobs | Read + Update |
| Reservations | Update |
| ExtendedCheckouts | Append |
| CleanersProfile | Read (for cleaner email lookup) |
| Properties | Read (for property name) |

---

## External Services

- Google Calendar (update events when status is ASSIGNED)
- Gmail (notify cleaner when status is ASSIGNED)
