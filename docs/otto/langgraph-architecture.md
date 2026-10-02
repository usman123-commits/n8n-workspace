# OTTO Agent -- LangGraph Architecture (v1 draft)

Replaces the single n8n AI Agent (11k-char prompt + tools) with a LangGraph.js graph.
Code owns facts and state; the LLM only understands messages and phrases replies.

Decisions (2026-10-02): JavaScript, LangGraph.js, OpenRouter, hosted on Vercel, graph writes to MongoDB, n8n stays as the WhatsApp/voice/notification layer.

---

## 1. Core principles

1. **The LLM never produces facts.** Items, prices, totals, order status and order IDs come from MongoDB via code. The LLM may only rephrase facts it is handed. (This is the fix for execution 5715, where the agent invented four karahis.)
2. **Numbered replies are resolved in code.** When the bot shows a numbered list, the options are saved in state. A reply of "9" is mapped to option 9 by code; no LLM involved.
3. **Conversation state lives in the graph**, checkpointed per phone. The pending-confirmation and pending-cancellation flows become `stage` values, not separate collections and classifier calls.
4. **At most 2 LLM calls per message**: `understand` (always) and `compose` (most turns). Everything else is plain code.
5. **Small prompts**: each LLM node gets a short, single-purpose prompt plus structured input.

---

## 2. System overview

```
WhatsApp
   |
Baileys bridge (PC, :3000)
   |  POST /webhook/otto-baileys
n8n (PC)
   - allowlist check
   - voice note -> Whisper -> text
   - POST https://<agent>/api/chat   { phone, jid, profileName, text, messageId, timestamp }
   |                                  header: x-agent-secret
   v
OTTO Agent (Vercel Function, Node, LangGraph.js)
   - runs graph, reads/writes MongoDB, calls OpenRouter
   - returns { reply, events[] }
   |
n8n
   - send reply via Baileys
   - for each event: notify owner (order_placed, handoff_created)
   - Rider Pickup Notification workflow stays as is (schedule, reads orders)
```

What moves out of n8n: Bot Config read, handoff check, pending checks, both classifier chains, AI Agent, tool sub-workflows, Process Reply, Log Conversation, Append Order, Log Handoff, Track/Update Spend.

What stays in n8n: webhook, allowlist, Whisper, send, owner notifications, rider pickup schedule.

### API contract

Request `POST /api/chat`
```json
{ "phone": "221466012467213", "jid": "221466012467213@lid", "profileName": "Usman",
  "text": "9", "messageId": "<baileys msg id>", "timestamp": "2026-10-02T15:07:47Z" }
```

Response `200`
```json
{ "reply": "string or null (null = stay silent, e.g. active handoff)",
  "events": [
    { "type": "order_placed", "orderId": "OTTO-...", "items": [...], "total": 1200, "address": "..." },
    { "type": "handoff_created", "reason": "..." }
  ] }
```

`messageId` is used for idempotency: if the same id arrives twice (Baileys/n8n retry), the stored reply is returned and nothing is written twice.

---

## 3. Graph state

```js
// src/state.js
const OttoState = Annotation.Root({
  // identity (per request)
  phone, jid, profileName, messageId,

  // turn input/output (reset every request)
  userText,          // raw text from n8n
  selection,         // resolved option from lastShownList, or null
  understanding,     // structured output of `understand`
  facts,             // structured data the action node produced for `compose`
  reply,             // final text
  events,            // [] of side effects for n8n

  // persistent (checkpointed per phone)
  messages,          // last N turns {role, text} -- trimmed to MAX_CONTEXT
  cart,              // [{ itemId, name, qty, price }]
  address,           // string | null
  stage,             // see below
  pending,           // { kind, payload, createdAt } | null  -- expires after 30 min
  lastShownList,     // { kind: 'categories'|'items'|'options', options: [{ id, label }] } | null
});
```

### Stages

| stage | meaning | replaces |
|-------|---------|----------|
| `idle` | nothing in progress | -- |
| `building_cart` | customer is adding items | -- |
| `awaiting_address` | cart ok, need address | -- |
| `awaiting_order_confirm` | summary shown, waiting for yes/no | -- |
| `awaiting_duplicate_confirm` | duplicate check flagged, waiting for confirm/cancel/modify | `pendingConfirmations` |
| `awaiting_cancel_confirm` | latest order is `preparing`, asked "cancel/modify or keep?" | `pendingCancellations` |

`pending.createdAt` older than 30 minutes -> `loadContext` resets stage to `idle` (same rule as today).

Checkpointer: `MongoDBSaver` from `@langchain/langgraph-checkpoint-mongodb`, `thread_id = phone`, same database (collections `checkpoints`, `checkpoint_writes`).

---

## 4. Graph

```
START
  -> loadContext ----(active handoff)----------------------------> END (reply = null)
  -> resolveSelection
  -> understand (LLM)
  -> route ---------------------------------------------------------+
       | greeting / smalltalk / off_topic  -> smallTalk             |
       | browse_menu                       -> showCategories        |
       | pick_category                     -> showItems             |
       | add_items / remove_items          -> updateCart            |
       | give_address                      -> setAddress            |
       | confirm/decline (stage-dependent) -> resolvePending        |
       | place_order                       -> reviewOrder           |
       | order_status                      -> orderStatus           |
       | cancel_order                      -> cancelRequest         |
       | complaint / wants_human           -> createHandoff         |
       +------------------------------------------------------------+
  -> compose (LLM, skipped when the action node produced a final template reply)
  -> persist
  -> END
```

### Node responsibilities

| Node | Type | Does |
|------|------|------|
| `loadContext` | code | Reads latest `handoffs` doc for phone (status `active` -> stop). Expires stale `pending`. Loads menu from cache (module-level, 5 min TTL, from `menuitems` where `available: true`). Idempotency check on `messageId`. |
| `resolveSelection` | code | If `userText` is a bare number (or "2 aur 5") and `lastShownList` exists -> map to options. Also maps "1/2/3" to confirm/cancel/modify when stage is awaiting_*. |
| `understand` | LLM | Structured output (zod): `intent`, `items: [{ text, qty, size? }]`, `category`, `address`, `confirmation: confirm|decline|modify|null`. Input: short prompt + stage + last 6 messages + labels of `lastShownList`. Never sees prices. |
| `route` | code | Conditional edge. Stage wins over intent when the customer is answering a pending question. |
| `showCategories` | code | Distinct categories from menu -> numbered list -> `lastShownList`. |
| `showItems` | code | Items of chosen category with prices -> numbered list -> `lastShownList`. |
| `updateCart` | code | Fuzzy-match item text to menu (Fuse.js). One match -> add. Several (sizes/variants) -> show options list. None -> "not on menu" + closest suggestions. |
| `setAddress` | code | Store address; if cart non-empty -> `reviewOrder`. |
| `reviewOrder` | code | Missing address -> ask. Else build summary with totals (computed in code) -> stage `awaiting_order_confirm`. |
| `resolvePending` | code | `awaiting_order_confirm` + confirm -> `duplicateCheck`. `awaiting_duplicate_confirm` + confirm -> `placeOrder`; decline/modify -> clear. `awaiting_cancel_confirm` + confirm -> `createHandoff`; decline -> keep order. Unclear -> re-ask with the same options. |
| `duplicateCheck` | code | Today's rules unchanged: latest order for phone, within 30 min and/or same items -> stage `awaiting_duplicate_confirm` with reason. Else -> `placeOrder`. |
| `placeOrder` | code | Insert into `orders` (`status: 'preparing'`, `jid`, real numbers/arrays). Clear cart. Emit `order_placed`. |
| `orderStatus` | code | Latest order for phone -> facts. |
| `cancelRequest` | code | Latest order. `preparing` -> stage `awaiting_cancel_confirm`. Otherwise explain it can no longer be changed. |
| `createHandoff` | code | Insert into `handoffs` (`status: 'active'`). Emit `handoff_created`. |
| `smallTalk` | code | Greeting / off-topic facts (one-line scope message). |
| `compose` | LLM | Turns `facts` into a short Roman Urdu reply. Numbered lists are rendered by code and inserted verbatim via a `{{LIST}}` placeholder -- the LLM cannot change items or prices. |
| `persist` | code | Insert user + assistant docs into `conversations` (`role`, `sessionId`). Record token usage/cost from OpenRouter into `botconfigs` (`LLM_SPENT`). Store reply under `messageId` for idempotency. |

---

## 5. LLM layer

- Client: `ChatOpenAI` from `@langchain/openai` with `configuration.baseURL = "https://openrouter.ai/api/v1"` and the OpenRouter key.
- Model ids are config, not code: `UNDERSTAND_MODEL`, `COMPOSE_MODEL` in env (overridable from `botconfigs`).
- `understand` uses `withStructuredOutput(zodSchema)`; on parse failure -> intent `unclear` (re-ask), never guess.
- Model choice is decided by the eval set (section 8), not upfront. Start with a cheap fast model for `understand`, and test whether `compose` can use the same one.
- Prompts live in `src/prompts/*.js`, each short and single-purpose (target < 1.5k chars).

---

## 6. MongoDB

| Collection | Used by | Change vs today |
|------------|---------|-----------------|
| `menuitems` | loadContext (cached) | read only |
| `orders` | duplicateCheck, placeOrder, orderStatus, cancelRequest | same shape |
| `handoffs` | loadContext, createHandoff | same shape |
| `conversations` | persist | same shape (history for humans/analytics; the graph uses checkpoint state) |
| `botconfigs` | config + spend | add `LLM_SPENT`, model ids |
| `checkpoints`, `checkpoint_writes` | LangGraph checkpointer | new |
| `processedMessages` | idempotency (`_id = messageId`, TTL 7 days) | new |
| `pendingConfirmations`, `pendingCancellations` | -- | replaced by graph state (keep for history, stop writing) |

Connection: one `MongoClient` cached on `globalThis` so warm function invocations reuse it.

New indexes:
```js
db.processedMessages.createIndex({ createdAt: 1 }, { expireAfterSeconds: 604800 })
db.locks.createIndex({ expiresAt: 1 }, { expireAfterSeconds: 0 })
```

---

## 7. Hosting on Vercel -- constraints and answers

| Concern | Answer |
|---------|--------|
| MongoDB reachability | Vercel must reach the DB over the internet. If MongoDB is on the PC, move to MongoDB Atlas (free M0) or expose it securely. **Blocker until confirmed.** |
| Hobby plan is non-commercial | OK for build/test. OTTO is a business -> production needs Pro or another host. Code stays portable (plain Node handler) so it can also run on the PC next to n8n. |
| Function duration | Target < 10 s per message (2 LLM calls). Set `maxDuration` in `vercel.json`; n8n HTTP timeout slightly above it. |
| Cold starts | Keep dependencies small; cache Mongo client + menu at module level. |
| Two messages from same phone at once | Per-phone lock: `locks` doc `{ _id: phone, expiresAt }` via `findOneAndUpdate`; second request waits briefly then runs on the updated state. |
| Auth | `x-agent-secret` header checked against env `AGENT_SECRET`; n8n stores it in an HTTP Header Auth credential. |
| Secrets | `MONGODB_URI`, `OPENROUTER_API_KEY`, `AGENT_SECRET` in Vercel env vars, never in code. |

---

## 8. Project layout

```
otto-agent/
  api/
    chat.js              # Vercel handler: auth, lock, invoke graph, return {reply, events}
  src/
    graph.js             # StateGraph wiring + conditional edges
    state.js             # Annotation (section 3)
    llm.js               # OpenRouter client factory
    db.js                # cached MongoClient + collection helpers
    menu.js              # menu cache, category list, fuzzy matching (Fuse.js)
    lock.js              # per-phone lock
    nodes/
      loadContext.js  resolveSelection.js  understand.js  route.js
      showCategories.js  showItems.js  updateCart.js  setAddress.js
      reviewOrder.js  resolvePending.js  duplicateCheck.js  placeOrder.js
      orderStatus.js  cancelRequest.js  createHandoff.js  smallTalk.js
      compose.js  persist.js
    prompts/
      understand.js  compose.js
  eval/
    cases.jsonl          # real messages + expected intent/items/stage
    run.js               # replays cases, scores understand + end-to-end
  scripts/
    chat-cli.js          # local REPL against the graph (no WhatsApp needed)
  vercel.json
  package.json
  .env.example
```

Dependencies: `@langchain/langgraph`, `@langchain/langgraph-checkpoint-mongodb`, `@langchain/openai`, `@langchain/core`, `mongodb`, `zod`, `fuse.js`.

---

## 9. Build plan

| Phase | Deliverable | Done when |
|-------|-------------|-----------|
| 0 | Confirm MongoDB host (Atlas or reachable), create Vercel project, env vars | `/api/health` on Vercel reads `botconfigs` |
| 1 | Scaffold + state + checkpointer + `loadContext`, `resolveSelection`, `understand`, `showCategories`, `showItems`, add-by-number, `persist` | CLI: "menu" -> categories, "9" -> correct karahi list from DB |
| 2 | `updateCart` (by name), `setAddress`, `reviewOrder`, `compose` | Full order conversation in CLI, totals computed in code |
| 3 | `duplicateCheck`, `resolvePending`, `placeOrder`, `orderStatus`, `cancelRequest`, `createHandoff` | All flows the n8n bot handles today pass in CLI |
| 4 | Eval set (50+ real messages from `conversations`), pick models | Intent accuracy and item-match accuracy at agreed thresholds |
| 5 | n8n "OTTO Agent Bridge" workflow (webhook -> Whisper -> HTTP agent -> send -> notify) in shadow mode | Agent replies logged next to live replies for a day, reviewed |
| 6 | Switch traffic, deactivate old AI Agent path | Old workflow kept inactive for rollback |

---

## 10. Decisions log

| # | Question | Answer (2026-10-02) |
|---|----------|---------------------|
| 1 | Where is MongoDB hosted? | MongoDB Atlas -- reachable from Vercel, no blocker |
| 2 | Explicit "confirm" before placing an order? | Yes -- `awaiting_order_confirm` stays mandatory before the duplicate check |
| 3 | Reply language | Always Roman Urdu |
| 4 | Variants/sizes grouping | Open -- each size is its own `menuitems` document today; revisit in phase 2 |

Code lives in its own repo: `C:\folderF\otto-agent` (README there).
