# Workflow 4W — Checkout Ingestion (Webhook)

**n8n ID:** `ptUTUMasJXbVzm2Q`
**Phase:** 3.2 (Checkout Ingestion)
**Trigger:** Webhook `POST /webhook/checkout`
**Replaces:** Workflow 4 (Google Sheets Trigger version — now inactive)

---

## Purpose

Receives checkout submissions from the React checkout page, normalizes and validates the data, writes a PENDING row into `CheckoutSubmissions`, and in parallel dispatches maintenance tickets and supply usage records if reported.

---

## What It Does

1. **Receives POST** — React page sends JSON to `/webhook/checkout`. n8n nests the body under `$json.body` — the Normalize node unwraps this.

2. **Normalizes Fields** — Accepts both React camelCase (`bookingId`, `cleanerId`, `confirmCheckout`, `captureLocation`, `submittedAt`, `issueReported`, `issueType`, `issueDescription`, `photoUrls`, `issuePriority`, `supplies`) and legacy Google Forms column names. Detects whether the GPS location is a short link (`maps.app.goo.gl` / `goo.gl/maps`). Parses supply usage: if `supplies` is a React object (`{ "Trash Bags": 2 }`), iterates entries; otherwise reads individual form columns (e.g., `Trash Bags — Qty Used`).

3. **Resolves Short Links** — If the location is a short link, makes an HTTP GET to follow the redirect and extract lat/lng from the response body.

4. **Parses & Validates** — If the location is a full URL or raw `lat,lng`, parses coordinates directly. Validates:
   - `Booking ID` present
   - `Cleaner ID` present
   - `Confirm Checkout = "yes"`
   - GPS coordinates parseable

5. **Error Path** — If validation fails, sends a simplified error email to the cleaner (via Gemini LLM to humanize the message) and responds with `400 { status: "error", message: "..." }`. Gemini failures fall through gracefully (`onError: continueRegularOutput`). Fan-out: `Extract Simplified Error` connects to both `Send Error Email` and `Respond Error` in parallel so the webhook response is not blocked by Gmail.

6. **Duplicate Check** — Looks up `CheckoutSubmissions` for the same `bookingUid` with `processingStatus = APPROVED`. If found, responds `200 { status: "skipped" }` without inserting.

7. **Inserts Row** — Appends to `CheckoutSubmissions`: `bookingUid`, `cleanerIdFromForm`, `gpsLat`, `gpsLng`, `submissionTimestamp`, `processingStatus = "PENDING"`, `resultMessage = ""`, `processedAt = ""`.

8. **Fan-out After Insert** — Three branches run in parallel after the row is inserted:
   - **Respond Success** — immediately returns `200 { status: "success", bookingUid: "..." }`
   - **Maintenance branch** — if `issueReported` is truthy, appends a row to `MaintenanceTickets` with `bookingUid`, `issueType`, `description`, `photoUrl`, `priority`, `status = "OPEN"`, `createdAt`
   - **Supply branch** — `Parse Supply Items` emits one item per supply used (or `[]` if none); `Append Supply Usage` then appends each row to `SupplyUsageLog` with `bookingUid`, `itemName`, `quantityUsed`, `submittedAt` (skips entirely when array is empty)

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
| CheckoutSubmissions | Read (duplicate check) + Append |
| MaintenanceTickets | Append (if issue reported) |
| SupplyUsageLog | Append (one row per supply item used) |

---

## Key Design Decisions

- **No raw sheet append** — submissions are not logged before validation. Row only lands in `CheckoutSubmissions` after passing all checks.
- **`alwaysOutputData: true`** on the Lookup node — ensures flow continues when no APPROVED row exists (the normal case).
- **Fan-out on error** — `Extract Simplified Error` connects to both `Send Error Email` and `Respond Error` in parallel, so the webhook response is not blocked by Gmail.
- **Fan-out after insert** — `Insert into CheckoutSubmissions` fans out to three nodes: Respond Success, Is Maintenance?, and Parse Supply Items. All three fire simultaneously; the webhook response is not blocked by the background branches.
- **Parse Supply Items returns `[]` when empty** — the Append Supply Usage node receives no items and skips gracefully; no error occurs when no supplies are reported.
- **Supplies accept both React object and form columns** — `item.supplies` as a key-value object (React) or individual `ItemName — Qty Used` columns (Google Forms) both produce the same normalized array.
- **Downstream:** Workflow 4B polls `CheckoutSubmissions` for PENDING rows and validates them, updating `CleaningJobs.status = COMPLETED`.
