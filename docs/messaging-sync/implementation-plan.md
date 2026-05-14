# Messaging Sync — n8n Implementation Plan

**Replaces:** HostBuddy
**Connects:** Hostfully Inbox ↔ GoHighLevel Conversations
**Source spec:** [spec.md](spec.md)

---

## How this plan differs from the spec

The original spec assumes a custom-built middleware service (Cloudflare Workers, Lambda, etc.). We already have **n8n on cloud** (`https://n8n.srv1566844.hstgr.cloud`) which is functionally equivalent — it has public HTTPS webhook endpoints, persistent execution, scheduled triggers, native HTTP request nodes, and credential storage.

**Decisions made for the n8n implementation:**

| Spec requirement | n8n approach |
|------------------|--------------|
| HTTPS endpoints `/hostfully/webhook` & `/ghl/outbound` | Two n8n Webhook nodes (one per workflow) |
| KV store for dedupe + thread→contact cache | Google Sheets — new tabs `MessageDedup` and `ThreadContactMap` (TTL via daily cleanup workflow) |
| Dead-letter queue | n8n's built-in execution log + a `MessagingErrors` sheet tab |
| Signature verification | Code node verifying `X-GHL-Signature` (Ed25519) |
| Secrets management | n8n Credentials store |

**Why not a separate service:** we'd duplicate existing infra. n8n on cloud handles the volume easily. If volume grows past ~100 msg/min we'd revisit.

---

## Workflows to build

| ID | Name | Trigger | Purpose |
|----|------|---------|---------|
| WF-MS-1 | Hostfully → GHL Inbound | Webhook `/webhook/hostfully-inbox-message` | Guest message lands in GHL Conversations |
| WF-MS-2 | GHL → Hostfully Outbound | Webhook `/webhook/ghl-outbound-message` | Reply from GHL goes back to guest via Hostfully |
| WF-MS-3 | Contact Upsert (sub-workflow) | Internal call from WF-MS-1 and existing WF1 | Create/update GHL contact with reservation context |
| WF-MS-4 | Dedup Cache Cleanup | Schedule (daily 03:00) | Drop dedup keys older than 7 days |

WF-MS-3 also gets called from the existing **Workflow 1 — Hostfully Booking Ingest** on `NEW_BOOKING` so contacts are pre-created with reservation context before any message arrives.

---

## Phase plan

### Phase A — Provisioning (human tasks, blocks all coding)

These cannot be automated and must complete first:

1. **Confirm Hostfully API version is v3.2** — needed for thread-per-reservation messaging. Check by calling `GET /api/v3.2/threads/<any-thread-uid>`. If it 404s we're on v3.0/v3.1 and the spec needs revisiting.
2. **GHL credentials choice — PIT or Marketplace app**
   - Recommended for v1: **PIT** (Private Integration Token) on the location. Faster, no marketplace approval. Single sub-account is fine.
   - Save as n8n credential `GHL API` (HTTP Header Auth, header `Authorization: Bearer <token>`).
3. **~~Create GHL Custom Conversation Provider~~** -- DROPPED
   - PIT tokens cannot create Custom Conversation Providers (requires OAuth marketplace app).
   - **Alternative:** Register a standard GHL webhook in GHL UI (Settings -> Integrations -> Webhooks).
   - Event: `OutboundMessage`, URL: `https://n8n.srv1566844.hstgr.cloud/webhook/ghl-outbound-message`.
   - Inbound messages are posted as `type: "Email"` (no conversationProviderId needed).
4. **Create GHL custom fields** (Settings → Custom Fields → Contacts)
   - `hostfully_lead_uid` (Text)
   - `hostfully_thread_uid` (Text)
   - `hostfully_property_uid` (Text)
   - `reservation_check_in` (Date)
   - `reservation_check_out` (Date)
   - `booking_channel` (Single-line text or Dropdown: Airbnb / Vrbo / Booking.com / Direct)
   - Note the field IDs returned — we need them in the upsert payload.
5. **Register Hostfully webhook for `NEW_INBOX_MESSAGE`**
   - `POST https://api.hostfully.com/api/v3/webhooks` — same way we did for `NEW_BOOKING` already.
   - `callbackUrl: https://n8n.srv1566844.hstgr.cloud/webhook/hostfully-inbox-message`

### Phase B — Sheets infrastructure

Add 3 new tabs to the V2 spreadsheet `1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw`:

**Tab `MessageDedup`** — idempotency keys
| Column | Type | Notes |
|--------|------|-------|
| `messageKey` | string | Format: `hf:<message_uid>` or `ghl:<messageId>` |
| `direction` | string | `inbound` or `outbound` |
| `createdAt` | ISO UTC | For TTL cleanup |

**Tab `ThreadContactMap`** — thread_uid → GHL contactId cache
| Column | Type | Notes |
|--------|------|-------|
| `threadUid` | string | Hostfully v3.2 thread UID |
| `ghlContactId` | string | GHL contact ID |
| `leadUid` | string | Hostfully lead UID (for traceability) |
| `lastSeenAt` | ISO UTC | Updated on each message; helps debug stale mappings |

**Tab `MessagingErrors`** — dead-letter for failed sync attempts
| Column | Type | Notes |
|--------|------|-------|
| `direction` | string | `inbound` or `outbound` |
| `errorMessage` | string | Captured from failed node |
| `payload` | string | JSON payload that failed |
| `createdAt` | ISO UTC | When the failure happened |

### Phase C — Build WF-MS-3 (Contact Upsert sub-workflow)

The reusable contact-creation/update logic. Inputs: lead JSON. Outputs: `ghlContactId`.

Flow:
```
Input (lead JSON)
  ↓
Normalize (lowercase email, E.164 phone)
  ↓
GHL Search Contact by email
  ↓
Found? → Update with custom fields (PUT /contacts/{id})
   ↓ NO
GHL Search Contact by phone
  ↓
Found? → Update with custom fields
   ↓ NO
Create new contact (POST /contacts/)
  ↓
Return { ghlContactId, threadUid, leadUid }
```

Used by:
- WF-MS-1 (when message arrives for an unknown contact)
- Existing WF1 — add a new step at the end of NEW_BOOKING path

### Phase D — Build WF-MS-1 (Hostfully → GHL Inbound)

Trigger: `POST /webhook/hostfully-inbox-message`

```
Webhook → Respond 200 (immediate ACK so Hostfully doesn't retry)
        → Agency Check (drop other-agency events)
        → Type Filter: only continue if event_type == NEW_INBOX_MESSAGE
        → Lookup MessageDedup by hf:<message_uid>
            → exists? STOP (idempotent)
        → Fetch full message: GET /api/v3.2/messages/<message_uid>
        → Direction Filter: only continue if type == GUEST_TO_HOST
        → Lookup ThreadContactMap by thread_uid
            → found? use cached ghlContactId
            → not found? Fetch lead → call WF-MS-3 → cache result
        → POST to GHL: /conversations/messages/inbound
            { type: "Email", contactId, message, direction: "inbound", altId: <message_uid> }
        → Append MessageDedup row
        → Append ThreadContactMap row (or update lastSeenAt)
```

### Phase E — Build WF-MS-2 (GHL → Hostfully Outbound)

Trigger: `POST /webhook/ghl-outbound-message`

```
Webhook → Verify X-GHL-Signature (Ed25519 against GHL public key)
        → reject 401 on failure
        → Respond 200 (immediate ACK)
        → Lookup MessageDedup by ghl:<messageId>
            → exists? STOP
        → GET GHL contact /contacts/{contactId}
            → extract custom field hostfully_thread_uid
        → POST to Hostfully: /api/v3.2/threads/{threadUid}/messages
            { content: <body>, sendVia: "AUTO" }
        → On success: PUT GHL message status = delivered
        → On failure (e.g., thread not ready): PUT status = failed, append MessagingErrors row, retry with backoff (Phase E.1)
        → Append MessageDedup row
```

### Phase F — Wire WF1 to call WF-MS-3 on NEW_BOOKING

Add one step to existing `Workflow 1 — Hostfully Booking Ingest` in the NEW_BOOKING branch, after `Update Reservation with Cleaning Job ID`:
```
Update Reservation with Cleaning Job ID
  ↓
Call WF-MS-3 (Contact Upsert) with the lead data
  ↓
(end)
```

This guarantees a GHL contact exists for every Hostfully booking before any message arrives, even if `NEW_INBOX_MESSAGE` fires first (the inbound workflow handles that race anyway via WF-MS-3).

### Phase G — Shadow mode test (1–2 weeks)

- Activate WF-MS-1 and WF-MS-2 in production
- Leave HostBuddy ON as primary responder
- On test property, manually reply from GHL on a real guest thread → verify it lands on Airbnb
- Verify no duplicates, no loops, no missing contacts
- Watch `MessagingErrors` tab daily

### Phase H — Cutover

1. Disable HostBuddy auto-replies on one property
2. Enable GHL workflow / AI Employee on Hostfully-sourced contacts
3. Monitor 48h
4. Roll to remaining properties one at a time
5. Cancel HostBuddy after 1 week of clean operation

### Phase I — Phase 2 (out of scope for v1, captured for later)

- GHL AI Employee prompt + KB parity with HostBuddy
- Lifecycle tags (pre-arrival, in-stay, post-checkout) — drives different GHL workflow branches
- SMS/voice from GHL for opt-in guests
- Reporting dashboards

---

## Open questions for David (before Phase A)

1. **Hostfully API version** — are we on v3.2? (5-second test we can run once we have the API key)
2. **GHL credentials path** — PIT for v1, or build the Marketplace app from day one?
3. **Custom field IDs** — do any of the proposed custom fields already exist in GHL? If so, give us the existing IDs to reuse.
4. **First test property** — which 1-2 properties to start shadow mode on?
5. **Conversation Provider name** — what should the channel be called in GHL UI? Suggested: "Hostfully" or "PMS Messaging."

---

## Risk register

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Message loop (host reply echoes back as inbound) | Medium | High | Two guards: type filter + dedup keys (Phase 7 of spec) |
| GHL Conversation Provider not set as default channel → outbound webhooks never fire | Medium | High | Verified during Phase A provisioning; manual test before going live |
| Vrbo "thread not ready" on outbound right after new booking | High | Medium | Retry with exponential backoff in WF-MS-2; log to `MessagingErrors` if still failing after 5 min |
| Webhook ordering — message arrives before booking | Low | Low | WF-MS-1 calls WF-MS-3 if contact missing; works either order |
| Sheets-as-KV gets slow at scale | Low (current volume) | Medium | Monitor row count on MessageDedup; if >50k revisit with Redis/DB |
| GHL rate limits | Low | Medium | Use altId for idempotent inbound posts; backoff on 429 |
