# Items Needed from David Before We Can Build

These are the human-only tasks. Code can't proceed without them.

---

## 1. Confirm Hostfully API version

**Question:** Are you on Hostfully API v3.2 (thread-per-reservation messaging model)?

**How to confirm:** From the Hostfully PMP dashboard → Settings → API → check the version listed. Or share the API key with us and we'll test it in 30 seconds.

**Why it matters:** v3.2 changed messaging from thread-per-guest to thread-per-reservation. The whole spec assumes v3.2. If you're on an older version, the data model is different and the timeline shifts.

---

## 2. Hostfully API key

We already have one configured for the cleaning workflows (credential `Hostfully API` in n8n, ID `9KxNwfaP8qRHdRPm`). **Confirm:** does that same key have access to v3.2 messaging endpoints? If yes, no action needed.

If a different key is required, send us the new one — we'll add it as a separate credential.

---

## 3. GHL credentials — pick one path

**Option A — Private Integration Token (PIT)** ⭐ recommended for v1
- Faster to set up (5 minutes)
- Single sub-account
- You generate it in: GHL → Settings → Private Integrations → Create
- Required scopes: `conversations.write`, `conversations/message.write`, `conversations/message.readonly`, `contacts.write`, `contacts.readonly`
- Send us the token + your Location ID (`RSZ3HWAGH7WnU52Zs6aW`)

**Option B — Marketplace App**
- Slower (requires marketplace approval)
- Scales across multiple sub-accounts
- Choose this only if you plan to add more brands/locations later

**Tell us:** A or B?

---

## 4. Create GHL Custom Conversation Provider

⚠️ **Nothing works without this.** This is what lets GHL send outbound replies back through us.

**You do this once we have the API token from #3.** We can do it via API (give us the green light and we'll fire the call) or you can do it in the GHL UI if available for your plan.

We need to capture the resulting `conversationProviderId` and store it in `.env`.

---

## 5. Create GHL Custom Fields

In **GHL → Settings → Custom Fields → Contacts**, create these (or confirm they already exist — if so, send us the field IDs):

| Field name | Type | Notes |
|------------|------|-------|
| `hostfully_lead_uid` | Text | Hostfully lead UID |
| `hostfully_thread_uid` | Text | Active messaging thread UID |
| `hostfully_property_uid` | Text | Property UID |
| `reservation_check_in` | Date | Check-in date |
| `reservation_check_out` | Date | Check-out date |
| `booking_channel` | Single-line text | Airbnb / Vrbo / Booking.com / Direct |

Once created, send us the field IDs (visible in the URL when you edit a field, or via the GHL custom fields API).

---

## 6. Pick first test properties

For shadow-mode testing (Phase G of the implementation plan), we need 1–2 low-volume properties to test against without disrupting your main operation. Which would you like to start with?

---

## 7. Conversation Provider name

What should the channel show as in the GHL UI? Suggestions:
- `Hostfully`
- `PMS Messaging`
- `Guest Messaging`

Your preference?

---

## Once we have answers to 1–7

We'll:
1. Configure n8n credentials (add `GHL API` credential)
2. Run the GHL provider creation API call → save the conversation provider ID
3. Register the Hostfully `NEW_INBOX_MESSAGE` webhook
4. Add the 3 new sheet tabs (MessageDedup, ThreadContactMap, MessagingErrors)
5. Build and test workflows WF-MS-3, WF-MS-1, WF-MS-2 in that order
6. Hand back to you to start shadow-mode testing
