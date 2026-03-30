# Workflow 1 — Hostfully to Operto Reservation Cleaning Sync

**n8n ID:** `JKS8Imjt5Nvp1ReG`
**Phase:** 1 (Booking Ingestion)
**Trigger:** Schedule (polls Hostfully API periodically)

---

## Purpose

This is the primary ingestion workflow. It polls the Hostfully API for new confirmed bookings across all tracked properties and writes structured records into Google Sheets. It is the entry point for the entire cleaning operations pipeline.

---

## What It Does

1. **Polls Hostfully API** — Fetches reservations from the Hostfully platform for each tracked property UID using HTTP Request nodes with the Hostfully API key.

2. **Filters New Bookings** — Compares each reservation's `createdUtcDateTime` against the last stored timestamp to identify only new bookings (`type === "BOOKING"`, `status === "BOOKED"`).

3. **Creates Reservation Record** — Appends a row to the **Reservations** tab in Google Sheets with fields: `bookingUid`, `propertyUid`, `checkIn`, `checkOut`, `guestName`, `adultCount`, `source`, `createdUtc`, `cleaningStatus = "PENDING"`.

4. **Derives Cleaning Job** — Immediately creates a corresponding row in the **CleaningJobs** tab with: `bookingUid`, `propertyUid`, `cleaningDate`, `cleaningTime`, `checkoutTimeUTC`, `scheduledCleaningTimeUTC`, `durationHours = 3`, `status = "PENDING"`, and empty fields for `cleanerId`, `assignedAt`, `calendarEventId`, `clockInTimeUTC`.

5. **Extended Checkout Detection** — After new bookings are processed, a separate branch identifies potential extended checkouts. A booking is a candidate if it was **created before** the stored timestamp (already in the sheet) but **updated after** it (recently changed in Hostfully). The candidate list is then cross-checked against the Reservations sheet:
   - The sheet's stored `checkOut` is compared to Hostfully's new checkout (both converted to UTC)
   - Only bookings where the **new checkout is strictly later** than the stored one are treated as genuine extensions
   - False positives (bookings updated for other reasons — guest info, notes, etc.) are filtered out here
   - Confirmed extensions trigger **Workflow 1A (Extended Checkout Handler)** via webhook

   **Field values passed downstream:**
   - `newCleaningDate` and `newCleaningTime` are derived from `checkOutLocalDateTime` (local time) — not from the UTC ISO string — so they are consistent with how original cleaning jobs are created
   - `newCheckoutTimeUTC` and `newScheduledCleaningTimeUTC` are the UTC ISO equivalents, derived from `checkOutZonedDateTime`

6. **Updates Stored Timestamp** — After processing, saves the latest `createdUtcDateTime` so the next poll only picks up newer bookings.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| Reservations | Append (new booking) |
| CleaningJobs | Append (new cleaning job) |

---

## Downstream Workflows

- **Workflow 2 (Phase 2)** picks up PENDING cleaning jobs and assigns cleaners
- **Workflow 1A (Extended Checkout Handler)** is called when checkout times change
