# Replacing HostBuddy with GHL Conversations + Hostfully

**Owner:** David / Day Drinking Properties
**Audience:** Engineering
**Status:** Spec — ready to scope and build
**Source:** Provided by David, 2026-05-02

---

## 1. Scope

Replace HostBuddy (current AI guest-messaging layer) with GoHighLevel's native **Conversations** module, fed by Hostfully's messaging webhooks and API. Hostfully stays the PMS of record and continues to talk to the OTAs (Airbnb, Vrbo, Booking.com); GHL becomes the single place where humans (and GHL's AI Employee / workflows) read and respond to guests.

In scope:
- Two-way message sync between Hostfully Inbox ↔ GHL Conversations
- Contact upsert in GHL on every new Hostfully lead/booking, with reservation context attached as custom fields
- Outbound messages from GHL routed back through Hostfully so they land on the correct OTA channel (Airbnb API, Vrbo API, Booking, email, SMS, WhatsApp — Hostfully handles the channel)
- Loop prevention so messages don't bounce between systems
- A clean cutover plan to retire HostBuddy

Out of scope (for v1):
- Migrating historical message threads from HostBuddy
- Replacing HostBuddy's AI replies with GHL AI Employee / workflows — that's phase 2, after the pipes work
- Any change to how OTAs connect to Hostfully

---

## 2. End goal

A guest sends a message on Airbnb. Within seconds, that message appears as an inbound message on the correct contact in GHL Conversations, with reservation metadata visible. A team member (or a GHL workflow / AI Employee) replies inside GHL. That reply is delivered back to the guest on Airbnb via Hostfully — no HostBuddy in the path.

End state when working:
- HostBuddy can be turned off with no loss of guest messaging functionality
- All guest comms live in GHL alongside everything else (CRM, marketing, pipelines)
- Reservation context (property, dates, channel, lead UID) is on every contact, available for personalization in GHL automations

---

## 3. Architecture

```
  ┌─────────────┐    ┌────────────┐    ┌──────────────┐    ┌────────────┐
  │ Guest (OTA) │ ⇄  │  Hostfully │ ⇄  │  Middleware  │ ⇄  │    GHL     │
  │  Airbnb /   │    │  (PMS +    │    │  (this is    │    │ Conversa-  │
  │  Vrbo / BDC │    │   inbox)   │    │   what we    │    │   tions    │
  └─────────────┘    └────────────┘    │   build)     │    └────────────┘
                                       └──────────────┘
```

**Two flows:**
- **Inbound (guest → GHL):** Hostfully webhook → middleware fetches thread → middleware upserts GHL contact → middleware posts inbound message to GHL via Conversations API.
- **Outbound (GHL → guest):** GHL OutboundMessage webhook -> middleware looks up the Hostfully thread UID stored on the contact -> middleware posts message to Hostfully thread -> Hostfully delivers it on the right channel.

**Implementation note (2026-05):** Originally designed around GHL's Custom Conversation Provider, but PIT tokens cannot create providers (requires OAuth marketplace app). Replaced with standard GHL webhook (OutboundMessage event) + inbound messages posted as type Email. Functionally equivalent, simpler setup.

---

## 4. Prerequisites / Provisioning

Before any code:

1. **Hostfully**
   - API key (Hostfully PMP → Settings → API). Needs access to v3.2 endpoints (thread-per-reservation model).
   - Confirm we're on API v3.2 — earlier versions used thread-per-guest, which complicates reservation context.
   - Reference: https://dev.hostfully.com/v3.0/reference/v32-messaging-update

2. **GHL** (Location ID: `RSZ3HWAGH7WnU52Zs6aW`)
   - **Using:** Private Integration Token (PIT) for the location.
   - Required scopes: `conversations.write`, `conversations/message.write`, `conversations/message.readonly`, `contacts.write`, `contacts.readonly`, `conversations.readonly`.
   - ~~Custom Conversation Provider~~ -- DROPPED (PIT tokens cannot create providers; requires OAuth marketplace app).
   - **Instead:** Register a standard GHL webhook for `OutboundMessage` event pointing to `https://n8n.srv1566844.hstgr.cloud/webhook/ghl-outbound-message`. Inbound messages posted as type `Email`.

3. **Hosting for middleware**
   - Stateless HTTP service, public HTTPS endpoint, low-latency. Cloudflare Workers, AWS Lambda + API Gateway, or a small Node/Python service on Fly.io / Render — engineer's choice.
   - Needs a small DB or KV store for: idempotency keys, message-ID dedupe, thread-UID ↔ contact-ID mapping cache.

4. **Secrets management** for: `HOSTFULLY_API_KEY`, GHL OAuth creds or PIT, webhook signing secrets.

---

## 5. Step-by-step build plan

### Step 1 — Stand up the middleware skeleton
Two HTTPS endpoints:
- `POST /hostfully/webhook` — receives Hostfully events
- `POST /ghl/outbound` — receives GHL outbound provider webhook

Add:
- Signature verification on the GHL endpoint (GHL sends `X-GHL-Signature`, Ed25519 — verify against GHL's public key. Legacy `X-WH-Signature` is being deprecated July 2026, so go straight to Ed25519.)
- Optional shared-secret header on the Hostfully endpoint (Hostfully doesn't sign by default).
- A request log + dead-letter queue.

### Step 2 — Register GHL Outbound Webhook
~~Custom Conversation Provider~~ -- DROPPED (PIT limitation).
Instead, register a standard GHL webhook: GHL -> Settings -> Integrations -> Webhooks -> OutboundMessage event -> URL: `https://<our-middleware>/ghl/outbound`. This fires whenever any GHL user or workflow sends a message on any contact. WF-MS-2 filters to only route messages for contacts with a Hostfully thread UID.

### Step 3 — Register Hostfully webhooks
Register at least these event types pointing at `https://<our-middleware>/hostfully/webhook`:
- `NEW_INBOX_MESSAGE` — inbound guest message (payload now includes `message_uid`, `lead_uid`, `thread_uid`, `created`, `property_uid`, `type`, `status`)
- `NEW_BOOKING` — to upsert/update the GHL contact with reservation details
- `BOOKING_UPDATED` — to keep custom fields fresh (date changes, cancellations)

Use `webHookType: POST_JSON` and the `/api/v3/webhooks` endpoint.

### Step 4 — Build the contact upsert
On `NEW_BOOKING` (and on `NEW_INBOX_MESSAGE` if the contact doesn't exist yet):
1. Fetch the lead from Hostfully: `GET /api/v3/leads/{leadUid}` → pull guest name, email, phone, channel, check-in / check-out, property.
2. Search GHL for an existing contact by email and/or phone (`GET /contacts/search`).
3. Upsert via `POST /contacts/upsert` with custom fields:
   - `hostfully_lead_uid`
   - `hostfully_thread_uid`
   - `hostfully_property_uid`
   - `reservation_check_in`, `reservation_check_out`
   - `booking_channel` (Airbnb / Vrbo / Booking.com / Direct)
4. Cache `thread_uid → contactId` in our KV so the inbound flow doesn't have to refetch every time.

> Custom fields need to be pre-created in GHL (Settings → Custom Fields) before the upsert runs.

### Step 5 — Wire inbound (Hostfully → GHL)
Handler for `POST /hostfully/webhook` when `event_type == NEW_INBOX_MESSAGE`:
1. Read `thread_uid`, `message_uid`, `lead_uid`, `message_content`, `type` from payload.
2. Dedupe: if we've seen `message_uid` already, return 200 and stop.
3. Fetch the thread for full context if needed: `GET /api/v3.2/threads/{threadUid}`. Confirm `type == GUEST_TO_HOST` (skip host-originated messages — those came from us via step 6).
4. Resolve the GHL contact ID from the cache, or upsert via Step 4 if missing.
5. Post into GHL Conversations:
   ```
   POST https://services.leadconnectorhq.com/conversations/messages/inbound
   Authorization: Bearer <token>
   {
     "type": "Email",
     "contactId": "<ghl_contact_id>",
     "message": "<message_content>",
     "direction": "inbound",
     "altId": "<message_uid>"   // for idempotency
   }
   ```
6. Return 200 to Hostfully promptly. Do the GHL post async if we need to keep the webhook ack fast.

### Step 6 — Wire outbound (GHL → Hostfully)
Handler for `POST /ghl/outbound`:
1. Verify `X-GHL-Signature`. Reject on failure.
2. Pull `contactId`, `messageId`, `body`, `type` from payload.
3. Look up the contact's `hostfully_thread_uid` custom field (cache or `GET /contacts/{id}`).
4. Send to Hostfully:
   ```
   POST https://api.hostfully.com/api/v3.2/threads/{threadUid}/messages
   X-HOSTFULLY-APIKEY: <key>
   {
     "content": "<body>",
     "sendVia": "AUTO"   // let Hostfully pick the right channel (Airbnb API, Vrbo API, etc.)
   }
   ```
5. **Stamp the message** so the inbound webhook can recognize it as our own echo and skip it (e.g., prepend a zero-width marker, or store the outbound `messageId` and check Hostfully's `NEW_INBOX_MESSAGE` payload for `type == HOST_TO_GUEST` and skip those entirely — simpler).
6. Acknowledge GHL with 200 + status update so the message shows "delivered" in the GHL UI.

### Step 7 — Loop prevention
Two guards (use both):
- **Type filter:** in the inbound handler, only forward `type == GUEST_TO_HOST` (or whatever the v3.2 enum value is — confirm in payload). Drop everything else.
- **Idempotency keys:** dedupe on Hostfully `message_uid` going into GHL, and on GHL `messageId` going into Hostfully. Store both in the KV with a 7-day TTL.

### Step 8 — Test in shadow mode (1–2 weeks)
- Run middleware live but **leave HostBuddy on** as the primary responder.
- For each new guest message, verify it appears in GHL within 30 seconds with the right contact + custom fields.
- Manually reply from GHL on a few test reservations, confirm it lands on Airbnb/Vrbo correctly.
- Watch for: duplicate messages, missing contacts, wrong channel routing, signature failures.

### Step 9 — Cutover
1. Disable HostBuddy's auto-reply rules (start with one property, then all).
2. Enable GHL workflows / AI Employee on the Hostfully-sourced contacts to handle the auto-reply tier HostBuddy was doing.
3. Monitor response times and guest satisfaction for 1–2 weeks.
4. Cancel HostBuddy.

### Step 10 — Phase 2 (after pipes are stable)
- Build GHL AI Employee prompt + knowledge base to match (or beat) what HostBuddy was doing.
- Add tags / pipelines for guest lifecycle (pre-arrival, in-stay, post-checkout).
- Hook in SMS/voice from GHL for guests who opt in.
- Add reporting dashboards in GHL pulling on the Hostfully custom fields.

---

## 6. Known gotchas

- **Hostfully thread-per-reservation / multi-booking conflict:** v3.2 creates a new thread per reservation, not per guest. A repeat guest will have multiple threads over time. GHL collapses all bookings into one Contact Profile (matched by email/phone), so `hostfully_thread_uid` on the contact is a single field -- a new booking via WF-MS-3 overwrites the old thread UID.
  - **Impact on inbound (WF-MS-1):** No problem -- thread UID comes directly from the Hostfully webhook payload, so inbound routing is always correct.
  - **Impact on outbound (WF-MS-2):** Real risk -- if a guest has two overlapping active bookings (e.g. VRBO booking #1 still active, Airbnb booking #2 just created), WF-MS-2 reads the custom field and routes replies to the most recent thread, potentially to the wrong reservation.
  - **v1 decision:** Store the most recent active thread UID on the contact. Acceptable for the common case (one active booking per guest at a time). The `ThreadContactMap` sheet retains history of all thread-to-contact mappings.
  - **v2 fix (Phase 2):** Move per-booking fields (`hostfully_thread_uid`, check-in/out, channel) onto GHL Opportunity Cards instead of the Contact. One Opportunity per booking. WF-MS-2 looks up the active Opportunity for the contact to find the correct thread UID. This fully solves the multi-booking conflict.
  - **Flag to David:** If a repeat guest has two simultaneous active reservations, outbound replies in GHL will route to the most recent booking's thread. Rare edge case for v1 but worth communicating.
- **Vrbo messaging API delay:** Vrbo can take a few minutes after a new booking before the message thread is available. If we try to send outbound before that, it'll fail. Handle: retry with backoff if Hostfully returns "thread not ready."
- **Airbnb content rules:** Airbnb strips URLs and contact info from messages on inquiries (pre-confirmation). GHL workflows generating links need to know this. Add a check: if `booking_channel == Airbnb` and `status != CONFIRMED`, sanitize URLs out of outbound messages.
- **GHL contact dedupe:** if a guest books twice with slightly different email casing or phone formatting, we'll create duplicates. Normalize email (lowercase) and phone (E.164) before searching.
- **Webhook ordering:** Hostfully (and others) don't guarantee ordering. The `NEW_INBOX_MESSAGE` webhook can arrive before `NEW_BOOKING`. The inbound handler must be able to upsert a contact from the message alone if the booking webhook hasn't landed yet.
- **Rate limits:** GHL V2 APIs are rate-limited per OAuth token. Batch / queue if we ever do bulk backfills.

---

## 7. What we need from David to start

- Sign-off on Marketplace app vs. PIT (recommend Marketplace app)
- Hostfully API key (or confirmation of who has it)
- Decision on hosting platform for middleware
- List of properties to start shadow mode on (recommend 1–2 first)
- Confirmation of which custom fields already exist in GHL vs. need to be created

---

## 8. Reference docs

- Hostfully Messaging API v3.2: https://dev.hostfully.com/v3.0/reference/v32-messaging-update
- Hostfully webhooks: https://dev.hostfully.com/reference/webhooks-1
- ~~GHL Custom Conversation Providers~~ (DROPPED -- PIT limitation): https://marketplace.gohighlevel.com/docs/marketplace-modules/ConversationProviders/
- GHL Add Inbound Message: https://marketplace.gohighlevel.com/docs/ghl/conversations/add-an-inbound-message
- GHL Outbound Message webhook: https://marketplace.gohighlevel.com/docs/webhook/OutboundMessage
- GHL webhook signature verification: https://marketplace.gohighlevel.com/docs/webhook/WebhookIntegrationGuide
