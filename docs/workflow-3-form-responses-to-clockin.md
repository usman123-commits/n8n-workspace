# Workflow 3 — Form Responses 1 to ClockInSubmissions

**n8n ID:** `ieebrbqVyvQwb0ig`
**Phase:** 3.1 (Clock-In Ingestion)
**Trigger:** Google Sheets Trigger (new row added to `Raw Form Responses` tab)

---

## Purpose

Ingests raw clock-in form submissions from Google Forms, normalizes the GPS data, and writes structured rows into the `ClockInSubmissions` tab for validation by Workflow 3B.

---

## What It Does

1. **Triggers on New Form Response** — Google Sheets Trigger fires when a new row appears in the `Raw Form Responses` tab (linked to the Google Form that cleaners submit on arrival).

2. **Processes One at a Time** — Uses Split In Batches (batch size 1) to handle each submission sequentially.

3. **Normalizes and Checks Location** — Extracts the `Capture Location` field and determines if it's a shortened Google Maps link (`maps.app.goo.gl` / `goo.gl/maps`) or a full URL/coordinates.

4. **Resolves Short Links** — If the location is a short link, makes an HTTP GET request to follow redirects and extracts lat/lng coordinates from the resolved response body.

5. **Parses Full URLs** — If the location is a full Google Maps URL, raw `lat,lng`, or DMS coordinates, parses them directly using regex.

6. **Validates Required Fields** — Checks that `Booking ID`, `Cleaner ID`, and `Confirm Arrival = "Yes"` are present. Throws an error if arrival is not confirmed or location is missing.

7. **Duplicate Protection** — Looks up existing rows in `ClockInSubmissions` for the same `bookingUid`. If any row already has `processingStatus = APPROVED`, skips the insert (prevents double clock-ins for the same booking).

8. **Inserts Structured Row** — Appends a normalized row to `ClockInSubmissions` with fields: `bookingUid`, `cleanerIdFromForm`, `gpsLat`, `gpsLng`, `submissionTimestamp`, `processingStatus = "PENDING"`, `resultMessage = ""`, `processedAt = ""`.

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| Raw Form Responses | Read (trigger) |
| ClockInSubmissions | Read (duplicate check) + Append |

---

## Downstream Workflows

- **Workflow 3B** picks up PENDING rows in ClockInSubmissions and validates them
