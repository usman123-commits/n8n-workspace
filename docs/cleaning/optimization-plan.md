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
  "callbackUrl": "https://<your-n8n-cloud-host>/webhook/hostfully-booking-event"
}
```

**Second call, same shape, change eventType:**
```json
{
  "agencyUid": "<your agency UID>",
  "eventType": "BOOKING_UPDATED",
  "webHookType": "POST_JSON",
  "callbackUrl": "https://<your-n8n-cloud-host>/webhook/hostfully-booking-event"
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

### New Workflow 1 shape (webhook-driven)

```
Webhook POST /webhook/hostfully-booking-event
   ↓
Respond 200 immediately (Hostfully retries on non-2xx)
   ↓
Switch on $json.body.eventType
   ├─ NEW_BOOKING → Fetch lead by leadUid (Hostfully API)
   │               → Normalize fields
   │               → Lookup Reservations (dup check by bookingUid)
   │               → if new: append Reservations + CleaningJobs (status PENDING)
   │
   ├─ BOOKING_UPDATED → Fetch lead by leadUid
   │                  → Switch on status:
   │                     ├─ CANCELLED → POST to /webhook/cancellation-handler
   │                     ├─ BOOKED + checkOut changed later → POST to /webhook/extended-checkout-handler
   │                     └─ else → ignore (no-op)
   │
   └─ other → log + ignore
```

### Why keep cancellationHandler and 1A separate

Initially I considered merging both into the new WF 1. Rejected because:
- cancellationHandler has 20 nodes (calendar delete, cleaner email, 2-path switch)
- 1A has 17 nodes (calendar reschedule, cleaner email, 2-path switch)
- Merging yields a 60+ node workflow that would be painful to debug
- Keeping them separate means the webhook-router WF 1 stays ~15 nodes and each handler owns one concern
- No performance cost: internal n8n-to-n8n webhook call is a few ms

Both stay as today; WF 1 just becomes the dispatcher rather than the poller.

### Auth on the inbound webhook

Hostfully signs webhook calls (per their docs, you'll want to verify signature header). At minimum, add an n8n webhook node-level authentication:
- n8n webhook node → Authentication: "Header Auth" → require a shared secret header (e.g., `X-Webhook-Secret: <random>`) that you also configure in Hostfully's webhook settings if they support custom headers; or
- Accept all and verify Hostfully's signature in a first Code node.

You're going to research the auth side yourself — the research question is: **does Hostfully v3 webhooks send a signature header (HMAC of body)?** If yes, verify it. If no, fall back to keeping the n8n webhook URL secret and restrict on source IP if possible.

### Migration cutover

1. Build new WF 1 in drafts, inactive.
2. Register Hostfully webhooks pointing to it.
3. Turn on new WF 1.
4. Leave old polling WF 1 running in parallel for 24 hours — dup check prevents double-insert.
5. Confirm new WF 1 caught at least one NEW_BOOKING and one BOOKING_UPDATED in production.
6. Deactivate old polling WF 1.
7. After 1 week clean: delete old polling WF 1.

### Test plan (Phase 2)

- [ ] Register webhooks, verify GET returns both
- [ ] Book a test reservation in Hostfully → NEW_BOOKING webhook fires → WF 1 creates rows
- [ ] Extend checkout on existing booking → BOOKING_UPDATED fires → 1A handler called → cleaner rescheduled
- [ ] Cancel a booking → BOOKING_UPDATED with status=CANCELLED → cancellationHandler called
- [ ] Edit guest note only → BOOKING_UPDATED fires, routing ignores (no-op) — critical to verify, false positives cause duplicate work
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

## Phase 5 — Sheet Column Cleanup

Audit every tab for columns no workflow reads. Candidates likely include:
- Legacy Google Forms columns on Submissions tabs (`Confirm Arrival`, `Capture Location` string form) — now superseded by normalized columns
- Any V1 residue

Do this **last**, after migration is stable. Column removal is the operation most likely to silently break a workflow.

**Approach:** for each tab, `grep` all workflow JSON for column letter and header string; anything with zero hits is a candidate. Remove in a single PR per tab.

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
