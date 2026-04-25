# Clock-In Response Contract — Workflow 3W

**Workflow:** `EbYPXFGOuXeDH5Cw` — Workflow 3W – Clock-In Ingestion + Validation (Merged)  
**Endpoint:** `POST /webhook/clockin`  
**Response mode:** `responseNode` — the webhook holds the connection open until a Respond node fires.

---

## Request Payload (from React app)

```json
{
  "bookingId":       "eb68f11d-c077-409b-a3c2-ba96d3bf8af2",
  "cleanerId":       "iwshwh3eeeesij28e892js21j2",
  "confirmArrival":  "yes",
  "captureLocation": "36.1643154,-86.828049",
  "submittedAt":     "2026-04-25T16:30:00.000Z"
}
```

---

## Response Contract

Every response — including 4xx and 5xx — returns a JSON body. Never rely solely on HTTP status code; always parse the body.

### ✅ 200 — Approved

```json
{
  "status":     "approved",
  "message":    "Clock-in confirmed. You are within the allowed radius. Proceed with cleaning.",
  "bookingUid": "eb68f11d-c077-409b-a3c2-ba96d3bf8af2"
}
```

**When:** Cleaner is assigned to the booking AND is within 100m of the property.  
**Workflow path:** Insert → Lookup → Get Booking → Validate Assignment ✓ → Get Coords → Distance ≤ 100m → Update APPROVED → Update CleaningJobs → Update Reservations → Send Email → **Respond Approved**  
**Sheet writes:**
- `ClockInSubmissions`: new row written, then updated to `APPROVED`
- `CleaningJobs`: `status = IN_PROGRESS`, `clockInTimeUTC`, `gpsClockInLat/Lng`, `gpsStatus = INSIDE_RADIUS`
- `Reservations`: `cleaningStatus = IN_PROGRESS`

---

### 200 — Duplicate

```json
{
  "status":     "duplicate",
  "message":    "Clock-in already recorded for this booking.",
  "bookingUid": "eb68f11d-c077-409b-a3c2-ba96d3bf8af2"
}
```

**When:** There is already an `APPROVED` row in `ClockInSubmissions` for this `bookingUid`.  
**Workflow path:** Lookup Existing ClockIn → Reject If Already Approved → Should Insert? ✗ → **Respond Duplicate**  
**Sheet writes:** None — short-circuits before insert.  
**What to do:** Nothing. The cleaner is already clocked in. This is not an error.

---

### 400 — Validation Error

```json
{
  "status":  "error",
  "message": "Arrival not confirmed"
}
```

Possible messages from `ParseAndValidate`:
| `message` | Cause |
|-----------|-------|
| `Arrival not confirmed` | `confirmArrival` field is missing or not `"yes"` |
| `Location link missing` | `captureLocation` field is empty |
| `Invalid Google Maps link format: could not find coordinates.` | GPS string is not parseable |

**When:** Field validation fails before any sheet write.  
**Workflow path:** Normalize → ParseAndValidate ✗ → Has Error? [error] → **Respond Error**  
**Sheet writes:** None — fails before insert.  
**What to do:** Check the payload. The React app should never send a malformed request; if you see this in production, check the form submission code.

---

### 403 — Cleaner Not Assigned

```json
{
  "status":     "rejected",
  "reason":     "cleaner_mismatch",
  "message":    "You are not assigned to this booking. Please contact admin.",
  "bookingUid": "eb68f11d-c077-409b-a3c2-ba96d3bf8af2"
}
```

**When:** The `cleanerId` in the payload does not match the `cleanerId` on the `CleaningJobs` row for that booking.  
**Workflow path:** … → Validate Cleaner Assignment ✗ → Reject Cleaner Not Assigned (sheet update) → **Respond Cleaner Not Assigned**  
**Sheet writes:**
- `ClockInSubmissions`: row written then updated to `REJECTED`, resultMessage = "Cleaner not assigned to this booking"
**What to do:** Check `CleaningJobs` to confirm which `cleanerId` is assigned. The URL link sent to the cleaner in the assignment email should have the correct `cleanerId` pre-filled.

---

### 403 — Outside Radius

```json
{
  "status":     "rejected",
  "reason":     "outside_radius",
  "message":    "Your location is outside the allowed 100m radius. Please move closer to the property and try again.",
  "bookingUid": "eb68f11d-c077-409b-a3c2-ba96d3bf8af2"
}
```

**When:** Haversine distance between the cleaner's GPS and the property coordinates exceeds 100 metres.  
**Workflow path:** … → DistanceCalculation → Radius Check ✗ → Update REJECTED (radius) → Getting Cleaners Profile → Checking If Cleaner Exists → Send Rejected Email → **Respond Outside Radius**  
**Sheet writes:**
- `ClockInSubmissions`: row updated to `REJECTED`, resultMessage = "Cleaner outside allowed 100m radius"
**What to do:** Cleaner needs to physically move to the property entrance and retry. The React app shows a "Try Again" button that re-captures GPS. Property coordinates are in the `Properties` sheet — verify they are accurate if this fires unexpectedly.

**Radius threshold:** 100 metres. Defined in the `Radius Check` IF node (`distance <= 100`). To change, update that node in n8n.

---

### 404 — Booking Not Found

```json
{
  "status":  "error",
  "message": "Booking not found in system. Please verify the booking ID or contact admin."
}
```

**When:** The `bookingId` from the payload does not match any row in `CleaningJobs`.  
**Workflow path:** … → Insert → Lookup Inserted Row → Get Booking (0 rows) → Booking Found? ✗ → **Respond Booking Not Found**  
**Sheet writes:**
- `ClockInSubmissions`: row inserted with status `PENDING` (never updated — stays PENDING as an orphan record)
**What to do:** Verify the `bookingId` in the clock-in URL matches the `bookingUid` column in `CleaningJobs`. This can happen if the URL was hand-edited or if Workflow 2 failed to create the CleaningJobs row.

---

### 500 — Insert Failed

```json
{
  "status":  "error",
  "message": "Clock-in could not be saved. Please try again. If this keeps happening, contact admin."
}
```

**When:** `Insert Structured Row` succeeded but `Lookup Inserted Row` returned 0 results — the row could not be found immediately after insert (rare race condition or Sheets API lag).  
**Workflow path:** Insert → Lookup Inserted Row (0 rows) → Inserted Row Found? ✗ → **Respond Insert Failed**  
**What to do:** Cleaner can retry. If it keeps happening, check Google Sheets API quota and credentials.

---

### 500 — Property Not Configured

```json
{
  "status":  "error",
  "message": "Property coordinates not configured. Please contact admin."
}
```

**When:** `Get Property Coordinates` returns 0 rows — the property's `propertyUid` from `CleaningJobs` has no matching row in the `Properties` sheet, or `latitude`/`longitude` are empty.  
**Workflow path:** … → Get Property Coordinates (0 rows) → Property Found? ✗ → **Respond Property Missing**  
**What to do:** Open the `Properties` tab in the spreadsheet and confirm the row exists with valid `latitude` and `longitude` values.

---

## All Workflow Paths (summary)

```
Webhook
 └─ Normalize → ParseAndValidate
      ├─ [error]  → Respond Error (400)
      └─ [ok]     → Lookup Existing ClockIn → Reject If Already Approved
                         ├─ [duplicate]  → Respond Duplicate (200)
                         └─ [new]        → Insert Row → Lookup Inserted Row
                                               ├─ [not found]  → Respond Insert Failed (500)
                                               └─ [found]      → Get Booking
                                                     ├─ [not found]  → Respond Booking Not Found (404)
                                                     └─ [found]      → Edit Fields → Merge → Validate Assignment
                                                           ├─ [mismatch]  → Reject (sheet) → Respond Cleaner Not Assigned (403)
                                                           └─ [match]     → Get Property Coords
                                                                 ├─ [not found]  → Respond Property Missing (500)
                                                                 └─ [found]      → Haversine Distance
                                                                       ├─ [> 100m]  → Update REJECTED → Email → Respond Outside Radius (403)
                                                                       └─ [≤ 100m]  → Update APPROVED → CleaningJobs → Reservations → Email → Respond Approved (200)
```

---

## Timing

The happy path (approved) takes **~18–22 seconds** because it makes 7+ Google Sheets API calls and sends an email before responding. This is expected. The React app uses a 35-second timeout to accommodate this.

Fast paths (validation error, duplicate) respond in **< 2 seconds** because they short-circuit before any Sheets writes.

---

## Debugging Checklist

| Symptom | Check |
|---------|-------|
| Getting 403 `cleaner_mismatch` for the right cleaner | Confirm `cleanerId` in URL matches `CleaningJobs.cleanerId` (not `assignedCleaner` name) |
| Getting 403 `outside_radius` at the right location | Verify `Properties` lat/lng are correct for that property |
| Getting 404 for a real booking | Check `CleaningJobs` has a row with that `bookingUid`; check Workflow 2 ran |
| ClockInSubmissions row stays PENDING | Booking not found path or insert failed path — no update node ran |
| Happy path response took > 35s and timed out on the app | Google Sheets/Gmail API unusually slow; check API quota |
| n8n shows success but app shows timeout | Workflow took > 35s; check execution timing in n8n execution log |
