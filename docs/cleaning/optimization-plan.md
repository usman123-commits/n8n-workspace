# Cleaning Operations — Staged Optimization Plan

**Goal:** Cut Google Sheets execution count dramatically by replacing scheduled-poll architecture with webhook-driven architecture, now that n8n is on cloud and reachable from the public internet.

**Primary metric:** scheduled executions per day.
**Secondary:** fewer nodes per run, less sheet I/O, less debugging surface.

---

## Current State (baseline)

| Workflow | Trigger | Frequency | Exec/day |
|----------|---------|-----------|----------|
| WF 1 — Hostfully Sync | Schedule | every 1 min | 1,440 |
| WF 2 — Cleaner Assignment | Schedule | every 1 min | 1,440 |
| WF 3W — ClockIn Webhook | Webhook | on submit | ~5 |
| WF 3B — ClockIn Validation | Schedule | every 1 min | 1,440 |
| WF 4W — Checkout Webhook | Webhook | on submit | ~5 |
| WF 4B — Checkout Validation | Schedule | every 1 min | 1,440 |
| WF 5 — Payroll | Schedule | daily 02:00 | 1 |
| WF 2B — Job Response | Webhook | on click | ~10 |
| WF 2C — Offer Timeout | Schedule | ? | ~100 |
| WF 1A — Extended Checkout | Webhook | on-demand | ~1 |
| cancellationHandler | Webhook | on-demand | ~1 |

**Scheduled executions/day: ~5,861**
The vast majority fire with nothing to do — they poll sheets to discover work that could have been pushed to them.

---

## Target State

| Workflow | Trigger | Frequency | Exec/day |
|----------|---------|-----------|----------|
| WF 1 — Hostfully Ingest | Webhook (Hostfully) | per event | ~30 |
| WF 2 — Cleaner Assignment | Schedule (kept, owns race-lock) | every 1 min | 1,440 |
| WF 3W — ClockIn + Validate (merged) | Webhook | on submit | ~5 |
| WF 4W — Checkout + Validate (merged) | Webhook | on submit | ~5 |
| WF 5 — Payroll | Schedule | daily 02:00 | 1 |
| WF 2B — Job Response | Webhook | on click | ~10 |
| WF 2C — Offer Timeout | Wait node inside WF 2 | n/a | 0 |
| WF 1A — Extended Checkout | Webhook (from WF 1) | on-demand | ~1 |
| cancellationHandler | Webhook (from WF 1) | on-demand | ~1 |

**Scheduled executions/day: ~1,441** (Workflow 2 only)

**Saving: ~4,420 scheduled executions/day (~75%).**

WF 2's 1-minute schedule is preserved because its `processingFlag` row-level lock owns race-condition prevention and Phase 2 sequential offer logic — this is intentional and not a quota leak, it's the coordinator.

---

## Phase 0 — Discovery & Cleanup (no risk, no workflow changes)

Do these first. They clean the workspace so later phases are unambiguous.

### Tasks

1. **Archive outdated workflows**
   - `Workflow 3 – Form Responses 1 to ClockInSubmissions` (ID `ieebrbqVyvQwb0ig`) — replaced by 3W, already inactive
   - `Workflow 4 – Checkout Ingestion` (ID `VTlIwLr3cK896sLO`, Google Sheets Trigger version) — replaced by 4W, already inactive
   - Action: export their JSON to `workflows/archived/cleaning/` and delete from n8n UI.

2. **Update `CLAUDE.md` workflow table**
   - Mark 2B (`IZIywHWhoK32cp7Z`) and 2C (`DQbsPmZGHAI4JVDl`) as live.
   - Record webhook URLs for 1A, cancellationHandler, 2B, 3W, 4W in the table so they are one grep away.
   - Remove the two archived rows (3 and 4).

3. **Add Workflow 2 dual-trigger TODO** — see "Deferred Items" section below; doc location specified there.

4. **Fix outstanding bugs from earlier sessions** (independent of optimization)
   - Re-create the two rules in WF 2B's Switch node via n8n UI so `combinator`, `options.version:2`, and `id` fields are generated correctly.
   - Correct CleaningJobs row 55: `scheduledCleaningTimeUTC` should be `2026-09-06T15:00:00.000Z` (currently `2026-10-11T15:00:00.000Z`).

**Risk:** none.
**Rollout:** one commit.

---

## Phase 1 — Merge Ingestion + Validation Webhooks

**This is the biggest quota win.** Kills 2,880 scheduled executions/day by removing WF 3B and WF 4B.

### Rationale

3W/3B and 4W/4B are a webhook→submission-row→poll→validate→result-row→poll pattern. The poll step was required when n8n was local because external services couldn't reach it. On cloud, the webhook can just do the whole thing synchronously in one execution.

`ClockInSubmissions` and `CheckoutSubmissions` stay as **audit logs** — they still get PENDING rows written, but a single merged workflow also does the validation and status update in the same run. A human sees the same audit trail; the machine does fewer round-trips.

### Workflow 3W merged shape (before → after)

**Before (3W + 3B, two workflows):**
```
Webhook → Normalize → Validate → Lookup dup → Insert PENDING → Respond 200
                                                 ↓
                                        (poll every 1 min)
                                                 ↓
 Schedule → Read all ClockInSubmissions → Filter PENDING → Lookup CleaningJob
         → Merge → Validate cleaner match → Read property GPS
         → Haversine → Update submission → Update CleaningJobs
```
3B fires 1,440x/day regardless of volume.

**After (single merged WF 3W):**
```
Webhook → Normalize → Validate fields → Respond 200 (fan-out)
                                         ↓ (in parallel, does not block response)
                              Lookup dup (by bookingUid, APPROVED)
                                         ↓ continues if no dup
                              Insert PENDING row (audit log)
                                         ↓
                              Lookup CleaningJob by bookingUid
                                         ↓
                              Validate cleanerIdFromForm == cleanerId
                                         ↓
                              Lookup Properties GPS by propertyUid
                                         ↓
                              Haversine distance check
                                ├─ ≤100m → Update submission APPROVED
                                │          + Update CleaningJobs IN_PROGRESS
                                └─ >100m → Update submission REJECTED
                                           (CleaningJobs unchanged)
```

### Workflow 4W merged shape

Same pattern as 3W. Checkout has three fan-out branches after insert (Respond Success, Maintenance, Supply) — those stay. The 4B polling behavior becomes a synchronous section after the insert.

**Critical:** the Respond Success node still fan-outs early so the cleaner's page doesn't wait for GPS validation or sheet writes.

### Sheet operations per merged workflow

| Workflow | Sheet ops before | Sheet ops after | Saving |
|----------|------------------|------------------|--------|
| ClockIn path | 5 reads + 3 writes across 2 workflows | 4 reads + 3 writes in 1 workflow | 1 read, same writes |
| Checkout path | 5 reads + 5 writes across 2 workflows | 4 reads + 5 writes in 1 workflow | 1 read, same writes |

Quota win comes from **removing 2,880 scheduled executions** that each read the full Submissions tab, not from per-run savings.

### Test plan (Phase 1)

- [ ] Happy path clock-in (inside radius) → CleaningJobs.status=IN_PROGRESS, ClockInSubmissions row APPROVED, submission webhook responded 200 in <2s
- [ ] Clock-in outside radius → submission REJECTED, CleaningJobs unchanged
- [ ] Clock-in with wrong cleaner → REJECTED with "Cleaner not assigned"
- [ ] Duplicate clock-in (already APPROVED) → 200 `skipped`
- [ ] Happy path checkout with supplies + maintenance → all three branches fire
- [ ] Checkout with validation error → 400, error email sent, no row in CheckoutSubmissions
- [ ] Measure: response latency should be ≤2s p95 (same as before, since validation now runs *after* Respond Success)

### Risk & rollback

**Risk:** low. The merged workflow is a superset of the existing 3W's logic plus 3B's logic inlined. Worst case, one synchronous step fails and submission sits in PENDING — same terminal state as today if 3B fails.

**Rollback:** keep 3B and 4B in n8n but deactivate. If merged WF has a bug, reactivate 3B/4B and the backlog gets picked up within 1 minute.

**Delete 3B and 4B** only after 1 week of clean runs on merged workflows.

---

## Phase 2 — Hostfully Webhook Migration

Replaces WF 1's 1-minute poll with event-driven ingestion. Saves 1,440 scheduled executions/day.

### What Hostfully gives us

Hostfully's Webhook API (v3) allows registering callbacks for these events:

| Event | When it fires | Our routing |
|-------|---------------|-------------|
| `NEW_BOOKING` | New confirmed booking created | → create Reservations + CleaningJobs rows |
| `BOOKING_UPDATED` | Existing booking changed (checkout extended, cancelled, guest info edited, notes, etc.) | → router: is `status=CANCELLED`? → cancellationHandler. Is `checkOut` later than stored? → 1A. Else → ignore. |

Note: Hostfully calls these **leads** internally in payloads, not "bookings" — payloads reference `leadUid`, not `bookingUid`. Our code should map.

### Registration — how to set it up

**Hostfully API endpoint:**
```
POST https://api.hostfully.com/api/v3/webhooks
Headers:
  X-HOSTFULLY-APIKEY: <your API key>
  Content-Type: application/json
```

**Request body (register NEW_BOOKING):**
```json
{
  "agencyUid": "<your agency UID>",
  "eventType": "NEW_BOOKING",
  "webHookType": "POST_JSON",
  "callbackUrl": "https://n8n.srv1566844.hstgr.cloud/webhook/hostfully-booking-event"
}
```

**Second call, same shape, change eventType:**
```json
{
  "agencyUid": "<your agency UID>",
  "eventType": "BOOKING_UPDATED",
  "webHookType": "POST_JSON",
  "callbackUrl": "https://n8n.srv1566844.hstgr.cloud/webhook/hostfully-booking-event"
}
```

Both events can point to the **same n8n webhook URL** — the workflow routes internally on `eventType`.

**Verify registration:**
```
GET https://api.hostfully.com/api/v3/webhooks
Headers: X-HOSTFULLY-APIKEY: <key>
```
Should list both.

**Delete if needed:**
```
DELETE https://api.hostfully.com/api/v3/webhooks/<webhookUid>
```

### Hostfully webhook payload (thin — always fetch full lead)

```json
{
  "agency_uid":  "1293fab6-71ba-4317-a3c0-be3365180c7b",
  "event_type":  "BOOKING_UPDATED",
  "lead_uid":    "ce0668b5-7abd-4928-8dba-113d687dac58",
  "property_uid":"906738ca-aacb-4e86-be5f-9e7616507c12"
}
```

Hostfully sends only these 4 fields. Full booking data must be fetched separately:
`GET https://platform.hostfully.com/api/v3/leads/{lead_uid}?agencyUid={agencyUid}`

Processing order:
1. Verify `agency_uid` matches our agency — drop events from other agencies
2. Route on `event_type`
3. Fetch full lead from Hostfully API using `lead_uid`

### New Workflow 1 shape (webhook-driven, implemented)

**n8n workflow ID:** `DnVBNO7uxLSrXNYe` (inactive draft — activate after testing)

```
Webhook POST /webhook/hostfully-booking-event
   ↓
Respond 200 immediately (Hostfully retries on non-2xx)
   ↓
Agency Check (drop if agency_uid doesn't match)
   ↓
Fetch Lead by UID → GET /api/v3/leads/{lead_uid}
   ↓
Route on Event Type (Switch)
   ├─ NEW_BOOKING:
   │   Lookup Reservation (dup check by uid)
   │   → Reservation Exists? (IF)
   │      → NO: Create Reservation Record
   │             → Prepare Cleaning Job Data
   │             → Create Cleaning Job Record
   │             → Update Reservation with Cleaning Job ID
   │      → YES: no-op (already in sheet)
   │
   └─ BOOKING_UPDATED:
       Is Cancelled? (IF lead.status === 'CANCELLED')
         → YES: Lookup Reservation for Cancellation
                → Cancellation Idempotency Guard
                → POST /webhook/cancellation-handler
         → NO (BOOKED): Prepare Extended Checkout Candidate
                         → Lookup Reservation for Candidate
                         → Reservation Exists Guard (newCheckOut > stored?)
                         → POST /webhook/extended-checkout-handler
```

**What was removed vs old polling WF:** Schedule trigger, Read Last Timestamp, Initialize Cursor,
two paginated Fetch Leads HTTP nodes, Has More Pages loop, Accumulate Leads, Split In Batches,
Output Leads Individually, Compute Max After Loop, Update Stored Timestamp, Filter New Bookings,
Detect Extended Checkouts, Detect Cancellations, Split Extended Candidates,
Merge Lead and Lookup, Ensure One Item — **17 nodes eliminated**.

**What changed in kept nodes:**
- All three Lookup Reservation nodes: `mode:"name"` → `mode:"id"` with numeric gid `569949670`
- `Prepare Cleaning Job Data`: reads from `Fetch Lead by UID` (removed `Merge Lead and Lookup` ref)
- `Reservation Exists Guard`: simplified from batch-loop to single-event comparison
- `Cancellation Idempotency Guard`: simplified from batch-loop to single-event check
- Trigger URLs: `localhost:5678` → `https://n8n.srv1566844.hstgr.cloud`

### Why keep cancellationHandler and 1A separate

Both stay as today — WF 1 just becomes the dispatcher rather than the poller.
- cancellationHandler: calendar delete, cleaner email, 2-path switch
- 1A: calendar reschedule, cleaner email, 2-path switch
- Merging would yield 60+ node workflow; internal webhook call costs only a few ms

### Auth on the inbound webhook

Hostfully signs webhook calls (per their docs, you'll want to verify signature header). At minimum, add an n8n webhook node-level authentication:
- n8n webhook node → Authentication: "Header Auth" → require a shared secret header (e.g., `X-Webhook-Secret: <random>`) that you also configure in Hostfully's webhook settings if they support custom headers; or
- Accept all and verify Hostfully's signature in a first Code node.

You're going to research the auth side yourself — the research question is: **does Hostfully v3 webhooks send a signature header (HMAC of body)?** If yes, verify it. If no, fall back to keeping the n8n webhook URL secret and restrict on source IP if possible.

### Migration cutover

~~1. Build new WF 1 in drafts, inactive.~~ ✅ Done — ID `DnVBNO7uxLSrXNYe`
~~2. Register Hostfully webhooks pointing to it.~~ ✅ Done — `NEW_BOOKING` + `BOOKING_UPDATED` registered
~~3. Activate new WF 1 (`DnVBNO7uxLSrXNYe`) in n8n.~~ ✅ Done — active as of 2026-05-01
4. **Confirm new WF 1 caught at least one NEW_BOOKING and one BOOKING_UPDATED in production.**
~~5. Old polling WF 1 (`JKS8Imjt5Nvp1ReG`) deactivated.~~ ✅ Done — deactivated 2026-05-01 (skipped parallel window — dup guard prevents double-insert if reactivated)
6. After 1 week clean (by 2026-05-08): delete old polling WF 1 (`JKS8Imjt5Nvp1ReG`).

### Test plan (Phase 2)

- [x] Register webhooks — `NEW_BOOKING` + `BOOKING_UPDATED` registered pointing to `/webhook/hostfully-booking-event`
- [x] Activate new WF 1 and verify webhook path is live — active as of 2026-05-01
- [x] Book a test reservation in Hostfully → NEW_BOOKING fires → Reservations + CleaningJobs rows created (verified execution 4318, lead `c17f1069`)
- [ ] Extend checkout on existing booking → BOOKING_UPDATED fires → 1A handler triggered → cleaner rescheduled
- [ ] Cancel a booking → BOOKING_UPDATED with status=CANCELLED → cancellationHandler triggered
- [ ] Edit guest note only → BOOKING_UPDATED fires, routing ignores (no-op) — critical: false positives cause duplicate work
- [ ] Measure: NEW_BOOKING → Reservations row in <5s

### Risk & rollback

**Risk:** medium. Webhook delivery can miss. Mitigation: leave old polling WF 1 deactivated but ready. If webhooks miss >0.1% of events, reactivate it.

**Deferred safety net:** see Deferred Items below — eventually add a 1×/hour safety-net poll that reconciles missed webhooks.

---

## Phase 3 — WF 2C Offer Timeout via Wait Node

Replace the standalone WF 2C schedule-poll workflow with a `Wait` node inside WF 2's offer path.

### Today

WF 2 sends an offer → writes `offerSentAt` → ends.
WF 2C polls every N minutes: finds offers older than X minutes with no response → advances to next cleaner.

### After

WF 2 sends an offer → Wait node (duration = offer window, e.g., 15 min) → check CleaningJobs row for response:
- if `offerStatus=ACCEPTED` → no-op (WF 2B already handled)
- if `offerStatus=DECLINED` → skip (WF 2B already re-entered WF 2)
- if still `OFFERED` → advance to next cleaner (or NEEDS_MANUAL_ASSIGNMENT)

### Why

- Removes WF 2C entirely (one fewer workflow to maintain).
- Removes its schedule executions.
- Offer-timeout logic lives next to offer-send logic — easier to reason about.

### Risk

- n8n Wait nodes persist state on the server; a restart could drop them. On cloud n8n this is generally safe, but verify by killing and restarting a queued wait.
- Long waits (hours) are fine; minutes-scale is bulletproof.

### Defer until Phase 1 and 2 are stable.

---

## Phase 4 — Sub-Workflow Extraction (quality of life)

Once Phase 1 and 2 land, extract reusable pieces into sub-workflows:

| Sub-workflow | Used by | Purpose |
|--------------|---------|---------|
| `sw-normalize-webhook-body` | 3W, 4W, 1 | Unwrap `$json.body`, coerce types |
| `sw-haversine-gps-check` | 3W merged, 4W merged | Radius check against Properties |
| `sw-send-cleaner-email` | 2, 1A, cancellationHandler | Gmail with consistent template |

Not urgent. Ship if node counts per workflow exceed ~40.

---

## Phase 5 — Sheet Cleanup (Tabs + Columns)

### Tab Deletions

Audited all 17 tabs on 2026-05-01. Five tabs are dead — no active workflow reads or writes them.

| Tab | gid | Rows | Why dead | Status |
|-----|-----|------|----------|--------|
| `Form Responses 1` | `1983546329` | 104 | Old Google Forms checkout responses. Only read by retired WF4 (`VTlIwLr3cK896sLO`). | **TODO: delete** |
| `Raw Form Responses` | `0` | 1013 | Old Google Forms clock-in responses. Only read by retired WF3 (`ieebrbqVyvQwb0ig`). | **TODO: delete** |
| `temp` | `1516062411` | ~10 | No header row, no workflow references it. | **TODO: delete** |
| `timeStamps` | `1265548981` | 1 | Hostfully poller cursor. Old poller deactivated 2026-05-01. | **TODO: delete** |
| `SupplyInventory` | `2127266498` | 0 data | Headers: `itemName, currentQuantity, alertThreshold, lastUpdatedAt`. **Keep — will be used in supply inventory tracking logic.** | ✅ Keep |

**TODO:** Delete these 4 tabs from the V2 spreadsheet (architect to action in Google Sheets UI):
- `Form Responses 1` (gid `1983546329`)
- `Raw Form Responses` (gid `0`)
- `temp` (gid `1516062411`)
- `timeStamps` (gid `1265548981`)

### Column Audit (active tabs)

Audited on 2026-05-01. Submissions tabs are already clean — no legacy Google Forms column names remain.

| Tab | Status | Notes |
|-----|--------|-------|
| `ClockInSubmissions` | ✅ Clean | 8 normalized columns: `bookingUid, cleanerIdFromForm, gpsLat, gpsLng, submissionTimestamp, processingStatus, resultMessage, processedAt` |
| `CheckoutSubmissions` | ✅ Clean | Same 8 columns as ClockInSubmissions |
| `Reservations` | ⚠️ Review | 35 columns — likely has legacy columns from old poller. Audit after WF1 cutover. |
| `CleaningJobs` | ⚠️ Review | 35 columns — audit after WF1 cutover confirms all needed columns. |
| All others | Not yet audited | Do after migrations are stable |

Do column removal **last**, after all workflow migrations are confirmed stable. Column removal is the operation most likely to silently break a workflow.

**Approach:** for each tab, grep all workflow JSON for the column header string; anything with zero hits is a candidate. Remove in a single commit per tab.

---

## Deferred Items (intentional, not forgotten)

These are not being done now but are captured so they don't get lost.

### 1. WF 2 dual-trigger (webhook + schedule safety-net)

**What:** make WF 2 also webhook-triggerable (by WF 1 after new booking insert) so assignment can start within seconds instead of up-to-1-minute.

**Why deferred:** WF 2's 1-minute poll is already acceptable latency, and the schedule is the source of the `processingFlag` race-condition lock. Adding a second trigger without rethinking the lock could cause double-assignment. Do it once we've observed real-world latency complaints.

**Doc location (tracked TODO):**
- `docs/cleaning/workflow-2-cleaner-assignment.md` → section **"Deferred: Dual-Trigger Webhook Entry"** at the bottom of the file.

### 2. Hostfully safety-net poll

**What:** once WF 1 is webhook-driven, add a small schedule (1×/hour) that queries Hostfully for any bookings created/updated in the last 2 hours and reconciles against Reservations. Catches any missed webhook deliveries.

**Why deferred:** need real-world webhook miss-rate data first. If Hostfully's delivery SLA is good enough, this is overkill.

### 3. Retire WF 3B and WF 4B entirely

**What:** delete from n8n after 1 week of clean runs on merged 3W/4W.

**Why deferred:** keep as deactivated rollback for at least 7 days.

### 4. Fix time storage in Reservations tab (WF 1 — Create Reservation Record node)

**What:** three fields in `Create Reservation Record` are not clean UTC:

| Column | Current (buggy) | Should be |
|--------|-----------------|-----------|
| `checkIn` | `checkInLocalDateTime` — local time, no tz info (e.g., `2026-06-13T16:00:00`) | `new Date(checkInZonedDateTime).toISOString()` → `2026-06-13T21:00:00.000Z` |
| `checkOut` | `checkOutLocalDateTime` — local time, no tz info (e.g., `2026-06-17T10:00:00`) | `new Date(checkOutZonedDateTime).toISOString()` → `2026-06-17T15:00:00.000Z` |
| `createdUtc` | `metadata.createdUtcDateTime` stored raw — Hostfully names it UTC but sends no `Z` (e.g., `2026-03-05T00:27:45`), parsers treat it as local | append `Z` if missing: `(val.endsWith('Z') ? val : val + 'Z')` |
| `createdAtSystem` | `$now.toISO()` — n8n server local offset (e.g., `-05:00`), not `Z` | `$now.toUTC().toISO()` |

Note: CleaningJobs tab is already correct — `checkoutTimeUTC` and `scheduledCleaningTimeUTC` are derived from `checkOutZonedDateTime` via `new Date(zoned).toISOString()` which correctly produces UTC with `Z`.

**Why deferred:** the old polling WF 1 stored the same local times (same Hostfully source), so existing rows already have this format. Fixing it mid-table creates inconsistency unless all existing rows are backfilled at the same time. Wait until the old poller is retired and all rows are from the new webhook workflow, then fix and backfill in one operation.

**Workflow file:** `workflows/drafts/cleaning/workflow-1-hostfully-webhook.json`
**Node to change:** `Create Reservation Record` (columns `checkIn`, `checkOut`, `createdUtc`, `createdAtSystem`)

### 5. Handle OFFERED job status in cancellationHandler and Extended Checkout Handler

**What:** Neither the `cancellationHandler` workflow nor the `Extended Checkout Handler` currently checks whether the CleaningJob is already in `OFFERED` status (WF2 has already sent an offer to a cleaner) before proceeding.

**Current risk:**
- **Cancellation path:** If a booking is cancelled while a cleaner offer is outstanding, `cancellationHandler` fires (marks job CANCELLED, sends cancellation email to cleaner) but the cleaner still holds an active `acceptLink` / `declineLink`. If they click Accept after cancellation, WF2B will process the response against a CANCELLED job.
- **Extended checkout path:** If checkout is extended while an offer is outstanding, the extended checkout handler reschedules the calendar event and updates the sheet, but the cleaner's offer links still point to the old time. The cleaner may accept based on the old schedule.

**Fix needed (both handlers):**
1. After looking up the Reservation/CleaningJob row, check `status`
2. If `status = OFFERED`: send a retraction message to the cleaner (or at minimum log it) before proceeding with cancellation/rescheduling
3. Optionally: flip `status` to a transitional state (`CANCELLING`, `RESCHEDULING`) during processing to prevent WF2B from acting on a stale accept/decline

**Why deferred:** requires changes to both `cancellationHandler` and `Extended Checkout Handler` workflows plus possibly `WF2B`. Scope is larger than WF1 alone. Defer until WF1 is stable in production for at least one week.

**Workflows affected:** `cancellationHandler` (`BQ6uHsWxBcegrfrv`), `Extended Checkout Handler` (`NZNbIHz9Qutwj1fa`), potentially `WF2B – Job Response Handler` (`IZIywHWhoK32cp7Z`)

---

## Rollout Order (recommended)

| Week | Phase | Effort |
|------|-------|--------|
| 1 | Phase 0 (cleanup, bug fixes) | half a day |
| 2 | Phase 1 (merge 3W+3B, then 4W+4B) | 1 day each, ship one at a time |
| 3 | (observation week — leave 3B/4B deactivated) | — |
| 4 | Phase 2 (Hostfully webhooks) | 1–2 days incl. auth research |
| 5 | (observation week) | — |
| 6 | Phase 3 (2C → Wait node) | half a day |
| Later | Phase 4, Phase 5 | as needed |

Ship one phase, observe for a week, ship the next. Never ship two phases in the same week.

---

## Success Metrics

After Phase 1 + 2:
- [ ] Scheduled executions/day drops from ~5,861 to ~1,441
- [ ] Sheet read API calls drop proportionally (measure via n8n execution log)
- [ ] Webhook p95 latency for clock-in and checkout stays ≤2s
- [ ] No cancellations or extended checkouts missed (spot check weekly against Hostfully admin UI)
- [ ] New bookings appear in Reservations within 5s of Hostfully event (was: up to 60s)
