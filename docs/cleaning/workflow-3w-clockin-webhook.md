# Workflow 3W — Clock-In Ingestion (Webhook)

**n8n ID:** `qIV56v4P8klISyR2`
**Phase:** 3.1 (Clock-In Ingestion)
**Trigger:** Webhook `POST /webhook/clockin`
**Replaces:** Workflow 3 (Google Sheets Trigger version — now inactive)

---

## Purpose

Receives clock-in submissions from the React clock-in page, normalizes and validates the data, and writes a structured PENDING row into `ClockInSubmissions` for Workflow 3B to validate.

---

## What It Does

1. **Receives POST** — React page sends JSON to `/webhook/clockin`. n8n nests the body under `$json.body` — the Normalize node unwraps this.

2. **Normalizes Fields** — Accepts both React camelCase (`bookingId`, `cleanerId`, `confirmArrival`, `captureLocation`, `submittedAt`) and legacy Google Sheets column names. Detects whether the GPS location is a short link (`maps.app.goo.gl` / `goo.gl/maps`).

3. **Resolves Short Links** — If the location is a short link, makes an HTTP GET to follow the redirect and extract lat/lng from the response body.

4. **Parses & Validates** — If the location is a full URL or raw `lat,lng`, parses coordinates directly. Validates:
   - `Booking ID` present
   - `Cleaner ID` present
   - `Confirm Arrival = "yes"`
   - GPS coordinates parseable

5. **Error Path** — If validation fails, sends a simplified error email to the cleaner (via Gemini LLM to humanize the message) and responds with `400 { status: "error", message: "..." }`. Gemini failures fall through gracefully (`onError: continueRegularOutput`).

6. **Duplicate Check** — Looks up `ClockInSubmissions` for the same `bookingUid` with `processingStatus = APPROVED`. If found, responds `200 { status: "skipped" }` without inserting.

7. **Inserts Row** — Appends to `ClockInSubmissions`: `bookingUid`, `cleanerIdFromForm`, `gpsLat`, `gpsLng`, `submissionTimestamp`, `processingStatus = "PENDING"`, `resultMessage = ""`, `processedAt = ""`.

8. **Responds** — `200 { status: "success", bookingUid: "..." }`

---

## Response Codes

| Code | Body | When |
|------|------|------|
| 200 | `{ status: "success" }` | Row inserted successfully |
| 200 | `{ status: "skipped" }` | Already approved for this booking |
| 400 | `{ status: "error", message: "..." }` | Validation failed |

---

## Sheets Touched

| Tab | Operation |
|-----|-----------|
| ClockInSubmissions | Read (duplicate check) + Append |

---

## Key Design Decisions

- **No raw sheet append** — raw submissions are not logged before validation. Row only lands in `ClockInSubmissions` after passing all checks.
- **`alwaysOutputData: true`** on the Lookup node — ensures flow continues when no APPROVED row exists (the normal case).
- **Fan-out on error** — `Extract Simplified Error` connects to both `Send Error Email` and `Respond Error` in parallel, so the webhook response is not blocked by Gmail.
- **Downstream:** Workflow 3B polls `ClockInSubmissions` for PENDING rows and validates them.
