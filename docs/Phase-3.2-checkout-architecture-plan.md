# Phase 3.2+ Architecture Plan — Checkout, Maintenance, Supply & Payroll

**Status:** Final Plan (Pre-Build)
**Date:** March 29, 2026
**Depends on:** Workflows 1, 1A, 2, 3, 3B, Cancellation Handler (all completed)

---

## Design Principles

1. **One form, one moment** — The cleaner fills out everything at checkout: confirmation, GPS, maintenance issues, supply usage. No separate forms, no context-switching.
2. **Two-workflow pattern** — Mirrors clock-in: an ingestion workflow normalizes raw data, a validation workflow processes it. Proven pattern, consistent system.
3. **Sheets remain source of truth** — Calendar, email, forms are interfaces. All status lives in Google Sheets.
4. **Payroll is isolated** — Separate workflow, only reads COMPLETED jobs. Never coupled to checkout logic.

---

## Part 1 — Workflow 2 Update (Clock-Out Link Delivery)

### What Changes

Workflow 2 currently generates a clock-in link (pre-filled Google Form URL) and embeds it in the assignment email and calendar events. It will now also generate a **clock-out link** pointing to the new Checkout Form.

### Clock-Out Link Format

Pre-filled Google Form URL with:

- `bookingUid` (from CleaningJobs)
- `cleanerId` (assigned cleaner)
- `propertyName` (display only — looked up from Properties tab)

### Where It Goes

- **Assignment email** — Both links included. Clock-in link labeled clearly as "Step 1: Clock In on Arrival." Clock-out link labeled "Step 2: Clock Out When Finished."
- **Calendar event description** — Both links appended.
- **CleaningJobs sheet** — New column `clockOutLink` stored alongside `clockInLink`.

### Why Send Both Upfront

- Eliminates the need for a second email workflow after clock-in approval.
- Cleaner has everything in one place from the start.
- Reduces system complexity (no trigger chain: clock-in approved → generate link → send email).

---

## Part 2 — Checkout Google Form (Single Form)

### Pre-filled Fields (cleaner does not type these)

| Field | Source |
|-------|--------|
| `bookingUid` | From CleaningJobs |
| `cleanerId` | Assigned cleaner |
| `propertyName` | Display context only |

### Cleaner-Filled Fields

| Field | Required | Notes |
|-------|----------|-------|
| Confirm Checkout | Yes | Must be "Yes" to proceed |
| Capture Location (GPS) | Yes | Google Maps link or coordinates |

### Maintenance Section (conditional — only if issues exist)

| Field | Required | Notes |
|-------|----------|-------|
| Issue Reported? | Yes | Yes/No gate — if "No", skip below |
| Issue Type | If issue = Yes | Dropdown: Plumbing, Electrical, Appliance, Structural, Other |
| Description | If issue = Yes | Free text |
| Photo Upload | If issue = Yes | Image attachment |
| Priority | If issue = Yes | Low / Medium / High / Urgent |

### Supply Section (always filled)

| Field | Required | Notes |
|-------|----------|-------|
| Supplies Used | Yes | Multi-select or checklist of items |
| Quantity per Item | Yes | Number field per selected item |
| Low Stock Alert | No | Checkbox: "Any item running low?" |

**Why supply is always required:** Every cleaning uses supplies. Making it mandatory ensures inventory tracking stays accurate. If nothing was used (unlikely), cleaner selects "None."

---

## Part 3 — New Sheet Tabs

| Tab | Purpose |
|-----|---------|
| **RawCheckoutResponses** | Google Form response dump (trigger source for ingestion workflow) |
| **CheckoutSubmissions** | Normalized submissions with `processingStatus` (mirrors `ClockInSubmissions`) |
| **MaintenanceTickets** | Issues reported by cleaners, linked by `bookingUid` |
| **SupplyUsageLog** | Per-checkout item usage records, linked by `bookingUid` |
| **SupplyInventory** | Master inventory tracker — current quantity per item, alert threshold |

### CheckoutSubmissions Columns

- `bookingUid`
- `cleanerIdFromForm`
- `gpsLat`
- `gpsLng`
- `submissionTimestamp`
- `processingStatus` (PENDING → APPROVED / REJECTED)
- `resultMessage`
- `processedAt`

### MaintenanceTickets Columns

- `ticketId` (auto-generated)
- `bookingUid`
- `propertyUid` (looked up from CleaningJobs)
- `cleanerId`
- `issueType`
- `description`
- `photoUrl`
- `priority`
- `status` (OPEN → assigned to maintenance workflow later)
- `reportedAt`

### SupplyUsageLog Columns

- `bookingUid`
- `cleanerId`
- `propertyUid`
- `itemName`
- `quantityUsed`
- `loggedAt`

### SupplyInventory Columns

- `itemName`
- `currentQuantity`
- `alertThreshold`
- `lastUpdatedAt`

---

## Part 4 — Checkout Ingestion Workflow (Workflow 4)

**Mirrors:** Workflow 3 (Form Responses → ClockInSubmissions)
**Trigger:** Google Sheets Trigger — new row in `RawCheckoutResponses`

### What It Does

1. **Triggers on new form response** in `RawCheckoutResponses`.
2. **Processes one at a time** (Split In Batches, batch size 1).
3. **Validates required fields** — `bookingUid`, `cleanerId`, `Confirm Checkout = Yes`, GPS present.
4. **Normalizes GPS** — Same logic as Workflow 3: resolves shortened Google Maps links, parses full URLs, extracts lat/lng.
5. **Duplicate protection** — Checks `CheckoutSubmissions` for existing APPROVED row for this `bookingUid`. If found, skips insert.
6. **Inserts into CheckoutSubmissions** — Normalized row with `processingStatus = PENDING`.
7. **If maintenance fields are populated** — Inserts a row into `MaintenanceTickets` with `status = OPEN`.
8. **If maintenance fields are empty** — Skips maintenance insert entirely.
9. **Always processes supply fields** — For each supply item reported, inserts a row into `SupplyUsageLog`.

**Important:** Maintenance and supply data are written during ingestion (not validation). These are factual reports from the cleaner — they don't depend on whether the checkout is approved or rejected. Even a rejected checkout (GPS fail) should still capture that the cleaner reported a broken pipe.

---

## Part 5 — Checkout Validation Workflow (Workflow 4B)

**Mirrors:** Workflow 3B (ClockIn Validation Processor)
**Trigger:** Schedule (every 1 minute)

### What It Does

1. **Polls CheckoutSubmissions** — Reads all rows, filters to `processingStatus = PENDING`.
2. **Looks up CleaningJobs** — Gets the job row by `bookingUid`.
3. **Validation checks (all must pass):**

| Check | Rule | Fail Result |
|-------|------|-------------|
| Cleaner match | `cleanerIdFromForm` must equal `cleanerId` in CleaningJobs | REJECTED: "Cleaner not assigned to this booking" |
| Clock-in exists | CleaningJobs `status` must be `IN_PROGRESS` (clock-in was approved) | REJECTED: "No approved clock-in found" |
| GPS radius | Distance ≤ 100m from property coordinates (Haversine, same as clock-in) | REJECTED: "Outside property radius ([X]m away)" |
| Minimum duration | `submissionTimestamp - clockInTimeUTC` ≥ 30 minutes | REJECTED: "Checkout too soon ([X] min after clock-in)" |
| Maximum duration | `submissionTimestamp - clockInTimeUTC` ≤ 6 hours | REJECTED: "Checkout too late ([X] hrs after clock-in)" |

### Why 30 min / 6 hours (not 1 hr / 4 hrs)

- **30 min minimum:** Small studios or quick turnover units can legitimately take 30–45 minutes. A 1-hour minimum would reject valid work. 30 minutes catches accidental or fraudulent submissions.
- **6 hour maximum:** Some properties are large, some have deep-clean situations, some cleaners handle restocking. 4 hours is too tight. 6 hours catches forgotten clock-outs while allowing real variance. Beyond 6 hours is almost certainly an error.

### On Approval

- **CheckoutSubmissions:** `processingStatus = APPROVED`, `resultMessage = "Checkout successful"`, `processedAt`.
- **CleaningJobs:** `status = COMPLETED`, `clockOutTimeUTC`, `gpsClockOutLat`, `gpsClockOutLng`, `gpsClockOutStatus = INSIDE_RADIUS`.
- **Reservations:** `cleaningStatus = COMPLETED`.
- **SupplyInventory:** For each item in `SupplyUsageLog` for this `bookingUid`, decrease `currentQuantity`. If `currentQuantity` drops below `alertThreshold`, send admin alert email with item name, current quantity, and property.

**Why supply inventory updates happen on approval (not ingestion):** If a checkout is rejected, the cleaner may resubmit. Deducting on ingestion would double-count. Deducting on approval ensures each approved checkout triggers exactly one inventory update.

### On Rejection

- **CheckoutSubmissions:** `processingStatus = REJECTED`, `resultMessage` with reason, `processedAt`.
- **No other sheets updated.**
- **Cleaner can retry** by submitting the form again (same as clock-in rejection flow).

### Admin Alerts

- **Supply shortage:** Email to admin when any item drops below threshold.
- **Repeated rejections:** (Future consideration) If the same `bookingUid` has 3+ rejected checkout attempts, alert admin for manual intervention.

---

## Part 6 — Payroll Workflow (Workflow 5) — Separate

**Trigger:** Schedule (daily or weekly, depending on payroll cycle)

### What It Does

1. **Reads CleaningJobs** — Filters to `status = COMPLETED` AND `payrollStatus` is empty or `NOT_STARTED`.
2. **Calculates worked hours:** `clockOutTimeUTC - clockInTimeUTC`.
3. **Writes to CleaningJobs:** `workedHours`, `payrollStatus = READY`.
4. **Exports payroll data** — either to a dedicated PayrollRecords tab or directly to external payroll system.

### Why Separate

- Payroll has a different trigger cadence (daily/weekly, not per-event).
- Payroll logic should never be coupled to checkout validation — if checkout validation has a bug, it shouldn't corrupt payroll.
- Payroll may need manual review gates that don't belong in a real-time flow.

---

## Part 7 — Known Issue: Job Overlap Risk

### The Problem

Workflow 2 schedules jobs assuming fixed 3-hour durations. If Cleaner A has Job 1 at 11:00 (window 11:00–14:00) and Job 2 at 14:00, but Job 1 actually takes 4 hours, Job 2 starts late.

### Why Round-Robin Doesn't Fully Protect You

Round-robin distributes jobs across cleaners, but the same cleaner can still get back-to-back jobs at the same property or nearby properties. The overlap check in Workflow 2 only looks at `scheduledCleaningTimeUTC` windows, not actual duration.

### Recommended Fix (Future — Workflow 2 Enhancement)

Add a **60-minute buffer** between assignments for the same cleaner. When checking availability in the round-robin step, treat the time window as `scheduledCleaningTimeUTC` to `scheduledCleaningTimeUTC + durationHours + 1 hour` instead of just `+ durationHours`.

### Why Not Now

This is a Workflow 2 change, not a checkout concern. It doesn't block Phase 3.2 development. Flag it, build checkout first, then improve scheduling.

---

## Build Order

| Step | What | Depends On |
|------|------|------------|
| 1 | Create Checkout Google Form | Nothing |
| 2 | Add sheet tabs (RawCheckoutResponses, CheckoutSubmissions, MaintenanceTickets, SupplyUsageLog, SupplyInventory) | Nothing |
| 3 | Update Workflow 2 (generate + embed clock-out link) | Step 1 |
| 4 | Build Workflow 4 (checkout ingestion) | Steps 1, 2 |
| 5 | Build Workflow 4B (checkout validation) | Steps 2, 4 |
| 6 | Build Workflow 5 (payroll) | Step 5 |
| 7 | (Future) Update Workflow 2 scheduling buffer | Independent |

---

## Summary of New Columns on Existing Sheets

### CleaningJobs (new columns)

- `clockOutLink`
- `clockOutTimeUTC`
- `gpsClockOutLat`
- `gpsClockOutLng`
- `gpsClockOutStatus`
- `workedHours`
- `payrollStatus`

### Reservations (no new columns)

- `cleaningStatus` already exists — will receive value `COMPLETED`