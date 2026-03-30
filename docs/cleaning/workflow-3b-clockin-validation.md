# Workflow 3B — ClockIn Validation Processor

**n8n ID:** `B7duBLBoOCdLpztS`
**Phase:** 3.1 (Clock-In Validation)
**Trigger:** Schedule (every 1 minute)

---

## Purpose

Validates pending clock-in submissions by checking cleaner assignment and GPS proximity, then updates CleaningJobs status accordingly.

---

## What It Does

1. **Polls ClockInSubmissions** — Reads all rows from the `ClockInSubmissions` tab every minute.

2. **Filters to PENDING** — Only processes rows where `processingStatus = "PENDING"`.

3. **Looks Up Cleaning Job** — For each pending submission, reads the corresponding `CleaningJobs` row by `bookingUid`.

4. **Merges Submission and Job** — Combines the submission data with the CleaningJobs data for validation.

5. **Validates Cleaner Assignment** — Compares `cleanerIdFromForm` (from the submission) with `cleanerId` (from CleaningJobs). If they don't match, the submission is **REJECTED** with message "Cleaner not assigned to this booking".

6. **Gets Property Coordinates** — Looks up `latitude` and `longitude` from the **Properties** tab by `propertyUid`.

7. **Calculates Distance** — Uses the Haversine formula to compute the distance in meters between the cleaner's GPS coordinates and the property coordinates.

8. **Radius Check** — If distance ≤ 100 meters:
   - **APPROVED**: Updates `ClockInSubmissions` with `processingStatus = "APPROVED"`, `resultMessage = "Clock-in successful"`, `processedAt`.
   - Updates `CleaningJobs`: `status = "IN_PROGRESS"`, `clockInTimeUTC`, `gpsClockInLat`, `gpsClockInLng`, `gpsStatus = "INSIDE_RADIUS"`.

9. **Outside Radius** — If distance > 100 meters:
   - **REJECTED**: Updates `ClockInSubmissions` with `processingStatus = "REJECTED"`, `resultMessage` containing the distance, `processedAt`.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| ClockInSubmissions | Read + Update |
| CleaningJobs | Read + Update (on approval) |
| Properties | Read (for GPS coordinates) |

---

## Validation Rules

| Check | Pass Condition | Fail Result |
|-------|---------------|-------------|
| Cleaner Assignment | `cleanerIdFromForm` matches `cleanerId` in CleaningJobs | REJECTED |
| GPS Radius | Distance ≤ 100 meters from property | REJECTED |
