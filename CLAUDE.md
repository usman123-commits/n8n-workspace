# CLAUDE.md — n8n Workflow Automation Workspace

You are the **engineering partner** for this n8n automation workspace.
The human acts as **architect** — they define what workflows should do.
You handle: writing workflow JSON, pushing to n8n, running tests, reading results, fixing bugs, and iterating.

**This workspace contains multiple projects.** Each project has its own subdirectory under `workflows/` and `docs/`.
When working on a project, read its project-specific docs for full context.

---

## Your Environment

| Item | Value |
|------|-------|
| n8n URL | `http://localhost:5678` |
| n8n started via | `npm start` in cmd terminal |
| API base | `http://localhost:5678/api/v1` |
| API key | Stored in `.env` as `N8N_API_KEY` (never hardcode it) |
| Workflows folder | `./workflows/` (all JSONs live here) |
| This folder | Standalone `n8n-workspace/` — separate from any other git repo |
| JSON tool | `jq` is NOT installed — always use `python3` for JSON parsing (see commands below) |

> **This is a dedicated workspace folder.** It is NOT inside any other project.  
> Open only this folder in Claude Code — not a parent folder.

> **First time setup check**: If n8n API key is not in `.env`, remind the human to:  
> n8n → Settings → API → Enable & copy key → paste into `.env` as `N8N_API_KEY=xxxx`

---

## Folder Structure

```
n8n-workspace/
├── CLAUDE.md                  ← you are here (shared rules + project index)
├── .mcp.json                  ← MCP server config (never commit)
├── .env                       ← N8N_API_KEY (never commit)
├── .gitignore
├── gcp-oauth.keys.json        ← Google Cloud OAuth credentials (never commit)
├── workflows/
│   ├── active/
│   │   ├── cleaning/          ← cleaning operations workflows
│   │   └── cold-email/        ← cold email workflows
│   └── drafts/
│       ├── cleaning/
│       └── cold-email/
├── tests/
│   └── payloads/
│       ├── cleaning/
│       └── cold-email/
└── docs/
    ├── cleaning/              ← cleaning project docs & plans
    └── cold-email/            ← cold email project docs & plans
```

---

## ⚠️ Critical: jq is NOT installed — Use python3 Instead

Every curl command that would use `jq` must use `python3` instead.
Never write `| jq` — it will fail every time.

```bash
# List workflows (no jq)
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -c "import json,sys; [print(x['id'], x['name']) for x in json.load(sys.stdin)['data']]"

# Get execution status (no jq)
curl -s "http://localhost:5678/api/v1/executions?workflowId=WORKFLOW_ID&limit=5" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -c "import json,sys; [print(x['id'], x['status'], x['startedAt']) for x in json.load(sys.stdin)['data']]"

# Pretty print any response (no jq)
curl -s http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -m json.tool
```

---

## ⚠️ Critical: /run Endpoint Does NOT Work

`POST /api/v1/workflows/ID/run` returns "method not allowed" on this setup.
**Never try to use it.** It will always fail.

### How to actually test workflows:

**Option A — Webhook-triggered workflows:**
```bash
# Trigger via the webhook URL directly
curl -X POST "http://localhost:5678/webhook/YOUR-WEBHOOK-PATH" \
  -H "Content-Type: application/json" \
  -d @tests/payloads/test-payload.json
```

**Option B — Scheduled / manual workflows:**
- Activate the workflow via API (see below)
- Tell the human: "Please click Test Workflow in n8n UI"
- Then immediately watch the execution log via API

**Option C — Check last execution after manual trigger:**
```bash
curl -s "http://localhost:5678/api/v1/executions?workflowId=WORKFLOW_ID&limit=1" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -m json.tool
```

> When you cannot trigger a workflow directly, tell the human exactly what to click in n8n UI,
> then immediately read the execution result yourself and report back.

---

## Core n8n Commands (all using python3, no jq)

### Load API key from .env
```bash
export $(grep -v '^#' .env | xargs)
```

### List all workflows
```bash
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -c "import json,sys; [print(x['id'], '|', x['name'], '| active:', x['active']) for x in json.load(sys.stdin)['data']]"
```

### Get a specific workflow (full JSON)
```bash
curl -s http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | python3 -m json.tool
```

### Push (update) a workflow from local JSON
```bash
curl -X PUT http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/active/your-workflow.json
```

### Create a brand new workflow
```bash
curl -X POST http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @workflows/drafts/new-workflow.json
```

### Activate a workflow
```bash
curl -X PATCH http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": true}'
```

### Deactivate a workflow
```bash
curl -X PATCH http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"active": false}'
```

### Get last 5 executions + status
```bash
curl -s "http://localhost:5678/api/v1/executions?workflowId=WORKFLOW_ID&limit=5" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | \
  python3 -c "import json,sys; [print(x['id'], x['status'], x['startedAt']) for x in json.load(sys.stdin)['data']]"
```

### Get full execution details (errors live here)
```bash
curl -s http://localhost:5678/api/v1/executions/EXECUTION_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | python3 -m json.tool
```

---

## Standard Work Loop (follow this every time)

```
1. READ the task from the human (what should this workflow do?)
2. CHECK if workflow already exists → list workflows
3. GET current JSON if updating → save to workflows/ folder
4. EDIT the JSON (make your changes)
5. PUSH to n8n via PUT/POST
6. TRIGGER the test (webhook curl OR ask human to click Test in n8n UI)
7. READ the execution result via API immediately after
8. IF error → read error message → fix JSON → back to step 5
9. VERIFY in Google Workspace via MCP tools (see section below)
10. REPORT to human: what changed, test result, workspace verification
```

**Never tell the human "it should work" without completing steps 6–9.**
**Never try POST /run — it does not work on this setup.**

---

## Projects Index

| Project | Folder | Status | Docs |
|---------|--------|--------|------|
| **Cleaning Operations** | `cleaning/` | Active (7 workflows) | `docs/cleaning/` |
| **Cold Email** | `cold-email/` | New | `docs/cold-email/` |
| **Messaging Sync (GHL ↔ Hostfully)** | `messaging-sync/` | Spec — awaiting provisioning from David | `docs/messaging-sync/` |

---

# PROJECT 1: CLEANING OPERATIONS

## Workflows & Their IDs

| ID | Workflow Name | Trigger | Status |
|----|--------------|---------|--------|
| `AU1w579al67hGom7` | PHASE 2 – Cleaner Assignment + Calendar Dispatch | Schedule (every 1 min) | Active |
| `IZIywHWhoK32cp7Z` | Workflow 2B – Job Response Handler | Webhook POST `/webhook/job-response` | Live |
| `DQbsPmZGHAI4JVDl` | Workflow 2C – Offer Timeout Checker | Schedule | Live |
| `EbYPXFGOuXeDH5Cw` | Workflow 3W – Clock-In Ingestion + Validation (Merged) | Webhook POST `/webhook/clockin` | **Active (Phase 1 merged)** |
| `ptUTUMasJXbVzm2Q` | Workflow 4W – Checkout Ingestion (Webhook) | Webhook POST `/webhook/checkout` | Active |
| `um2uq299261x1xyV` | Workflow 4B – Checkout Validation Processor | Schedule (every 1 min) | Active (Phase 1 target: merge into 4W) |
| `7X0QKeFueWTdz0GW` | Workflow 5 – Payroll Processing | Schedule (daily 02:00 UTC) | Active |
| `BQ6uHsWxBcegrfrv` | cancellationHandler | Webhook POST `/webhook/cancellation-handler` | Active |
| `NZNbIHz9Qutwj1fa` | Extended Checkout Handler | Webhook POST `/webhook/extended-checkout-handler` | Active |
| `DnVBNO7uxLSrXNYe` | Workflow 1 — Hostfully Booking Ingest (Webhook) | Webhook POST `/webhook/hostfully-booking-event` | **Active — production (Phase 2 live)** |

### Deactivated / Rollback Only (do not reactivate)

| ID | Workflow Name | Replaced By |
|----|--------------|-------------|
| `JKS8Imjt5Nvp1ReG` | Hostfully to Operto Reservation Cleaning Sync (OLD poller) | `DnVBNO7uxLSrXNYe` — delete after 7-day observation (deactivated 2026-05-01) |
| `qIV56v4P8klISyR2` | Workflow 3W – Clock-In Ingestion (old) | `EbYPXFGOuXeDH5Cw` — delete after 7-day observation |
| `B7duBLBoOCdLpztS` | Workflow 3B – ClockIn Validation Processor | `EbYPXFGOuXeDH5Cw` — delete after 7-day observation |
| `ieebrbqVyvQwb0ig` | Workflow 3 – Form Responses 1 to ClockInSubmissions | Fully retired — safe to delete |
| `VTlIwLr3cK896sLO` | Workflow 4 – Checkout Ingestion (Google Sheets trigger) | Fully retired — safe to delete |

---

## Google Sheets — Main Data Source

**Spreadsheet ID (V2):** `1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw`

### ⚠️ Critical: Always Use Sheet IDs, Never Sheet Names

When configuring Google Sheets nodes in n8n, **always use the numeric sheet ID** (gid),
never the tab name string. Using names causes failures when n8n can't resolve them.

This applies to **both** the `documentId` (spreadsheet) and `sheetName` (tab) fields.

For `documentId`, use `"mode": "id"` with the spreadsheet ID:
```json
"documentId": {
  "__rl": true,
  "value": "1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw",
  "mode": "id"
}
```

For `sheetName`, use `"mode": "id"` with the numeric gid:
```json
"sheetName": {
  "__rl": true,
  "value": "2047086003",
  "mode": "id"
}
```
**Never use `"mode": "name"` or `"mode": "list"`** — they are unreliable and will break.

### ⚠️ Critical: Google Sheets Append Nodes Require a `schema` Field

When writing a Google Sheets append node with `"mappingMode": "defineBelow"`, you **must** include a `schema` array alongside the `value` map. Without it, n8n throws `"Could not get parameter: columns.schema"` at runtime even if all expressions are correct.

```json
"columns": {
  "mappingMode": "defineBelow",
  "value": {
    "columnA": "={{ $json.fieldA }}",
    "columnB": "LITERAL"
  },
  "schema": [
    {"id": "columnA", "displayName": "columnA", "type": "string", "required": false, "defaultMatch": false, "display": true, "canBeUsedToMatch": true},
    {"id": "columnB", "displayName": "columnB", "type": "string", "required": false, "defaultMatch": false, "display": true, "canBeUsedToMatch": true}
  ]
}
```

Every column in `value` must have a matching entry in `schema`. Use `"type": "string"` for all columns.

### ⚠️ Critical: Always Use `$json` from the Directly Connected Node

In n8n, `$json` refers to the output of the **immediately preceding connected node**. When a node in the middle of a chain (e.g. an IF or Sheets lookup) strips or replaces the data, downstream nodes using `$json` will get the wrong data.

**Rule:** Before writing any expression in a node, trace what `$json` actually contains at that point. Ask: "What node feeds this one, and what does it output?"

Common trap — Google Sheets lookup followed by a write node:
```
Lookup Reservation (returns {}) → Reservation Exists? → Create Reservation Record
                                                          ↑
                                          $json here = {} from the lookup, NOT the lead data
```

**`$('NodeName').first().json.*` works fine inside Google Sheets column expressions.** Use it whenever `$json` at that point contains the wrong data (e.g. an empty lookup result). No Code node needed — reference the correct upstream node directly.

### ⚠️ Critical: Never Assume a Node's Output Fields — Verify First

Do not assume what fields a node outputs based on intuition or prior experience with other tools.
**Wrong fields in expressions cause silent undefined bugs that only appear at runtime.**

**Rule:** Before using any field from a node's output in a downstream expression, confirm that field actually exists in the output. Two ways to verify:

1. **Run the workflow once and read the execution log** — the n8n UI shows the exact JSON each node outputs. This is always authoritative.
2. **Check the official n8n docs for that node type** — [docs.n8n.io](https://docs.n8n.io) lists the exact output schema for every built-in node.

**Known output schemas (confirmed from execution logs):**

| Node | Operation | What it outputs |
|------|-----------|-----------------|
| Google Sheets | Lookup row | The matched row's column values as `{ columnName: value, ... }`. **No `row_number`, no metadata.** When not found + `alwaysOutputData: true` → `{}` |
| Google Sheets | Append row | The appended row's data |
| HTTP Request | Any | The raw response body parsed as JSON (or text) |
| Webhook | Trigger | `{ headers: {}, body: {}, ... }` — body fields NOT at top level until unwrapped |
| Code | Any | Whatever you explicitly `return` — nothing else |

**Reliable existence check after Google Sheets Lookup:**
```json
{
  "leftValue": "={{ String($json.someRequiredColumn || '') }}",
  "rightValue": "",
  "operator": { "type": "string", "operation": "notEquals" }
}
```
Use a column that is **always populated** in that sheet (e.g. `bookingUid`, `cleaningJobId`).
Never use `$json.row_number` — it is not in the Google Sheets node output.

### Sheet Tab IDs (V2 Spreadsheet)

| Tab Name | Sheet ID (gid) | Purpose |
|----------|----------------|---------|
| `Raw Form Responses` | `0` | Incoming form data |
| `timeStamps` | `1265548981` | Clock-in/out records |
| `Reservations` | `569949670` | Booking data |
| `CleaningJobs` | `2047086003` | Cleaning assignments |
| `ClockInSubmissions` | `1402437116` | Validated clock-in records |
| `ExtendedCheckouts` | `1082018038` | Extended checkout records |
| `CleanersProfile` | `1920390373` | Cleaner info |
| `CancelledBookings` | `1881509778` | Cancellation records |
| `Properties` | `766791868` | Property data |
| `RawCheckoutResponses` | `1680465218` | Raw checkout form responses |
| `CheckoutSubmissions` | `1292187736` | Validated checkout submissions |
| `MaintenanceTickets` | `569911294` | Maintenance issue reports |
| `SupplyUsageLog` | `469288724` | Supply usage per booking |
| `PayrollRecords` | `166953005` | Payroll records (one per completed job) |
| `PayrollErrors` | `1485642013` | Payroll calculation errors for admin review |

When verifying workflow output, always read the relevant tab directly using MCP tools.
Use the Spreadsheet ID above — do not ask the human for it.

---

## Credential Names (use exact names in workflow JSON nodes)

| Service | Credential Name in n8n | Credential ID |
|---------|------------------------|---------------|
| Gmail | `Gmail account` | — |
| Google Sheets | `Google Sheets account` | `q52dbWoN6OaKRDZO` |
| Google Calendar | `Google Calendar account` | — |
| Google Forms | `Google Forms account` | — |
| HTTP Basic/API calls | `HTTP Header Auth` | — |

> When writing workflow node JSON, use BOTH the name AND the ID for Google Sheets.
> Example node credential field:
> ```json
> "credentials": {
>   "googleSheetsOAuth2Api": {
>     "id": "q52dbWoN6OaKRDZO",
>     "name": "Google Sheets account"
>   }
> }
> ```
> For other services, fill in the ID column as you discover them.

---

## Workflow JSON Rules

- Always include `"name"`, `"nodes"`, `"connections"`, `"settings"` at root level
- Node IDs must be unique UUIDs — generate new ones, never copy-paste
- Keep `"active": false` for all drafts until human approves
- For Google services: use `"authentication": "oAuth2"` in node parameters
- For webhook triggers: document the webhook URL in a Sticky Note node
- Always add a Sticky Note node explaining what the workflow does (`n8n-nodes-base.stickyNote`)

---

## Testing Rules

1. **Always test before declaring done**
2. Never use `/run` endpoint — it does not work (see critical section above)
3. For webhook workflows: trigger via `curl` to the webhook URL
4. For other workflows: ask human to click Test in n8n UI, then read the execution log
5. If test touches real Gmail/Sheets/Calendar: warn the human first, use test data
6. After successful test: move workflow JSON from `drafts/` → `active/`
7. **Always verify in Google Workspace after every execution** (see below)

---

## Google Workspace Verification (Post-Execution Checks)

You have direct MCP access to Google Workspace. After every workflow run,
verify the actual real-world output — do not trust n8n status alone.

### Verification flow
```
1. Workflow executes (via webhook curl or human clicks Test)
2. Read n8n execution log via API
3. Use MCP to check the actual Google service
4. Compare: expected output vs what actually happened
5. Any mismatch = bug, even if n8n said "success"
```

### What to verify per service

**Google Sheets** (use Spreadsheet ID above — no need to ask human)
- Read the target tab → confirm data landed in the right cells
- Check: correct tab, correct row/column, no duplicates, correct data types
- Common bug: data written to wrong tab, or row appended twice

**Gmail**
- After send: check Sent → confirm recipient, subject, body correct
- After label/filter: confirm label applied to the right thread
- After trigger (reads email): confirm the right emails were picked up

**Google Calendar**
- After create event: confirm title, date, time, timezone, attendees
- After update: old version gone, new version correct
- Always check for duplicate events (very common n8n bug)

### Post-test checklist
```
[ ] n8n execution status = success
[ ] Execution log shows correct data flowing through nodes
[ ] Google Workspace reflects the expected change
[ ] No duplicate records / emails / events
[ ] Data format correct (dates, numbers, text encoding)
[ ] No side effects in unrelated tabs/calendars/inbox folders
```

---

## What You Cannot Do (tell the human instead)

- Use `/run` to trigger workflows — it doesn't work, use webhook or ask human
- Set up OAuth credentials in n8n (human does this in browser)
- Access n8n if it's not running → remind them: run `npm start` in n8n folder
- Activate workflows to production without human approval

---

## Error Patterns & Fixes

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `401 Unauthorized` | Wrong/missing API key | Reload: `export $(grep -v '^#' .env \| xargs)` |
| `404 Not Found` | Wrong workflow ID | Use workflow IDs table above |
| `405 Method Not Allowed` | Used `/run` endpoint | Never use `/run` — use webhook or manual trigger |
| `Credential not found` | Name or ID mismatch | Check credential table above |
| `node X failed` | Logic error in that node | Get full execution details, read node error |
| `n8n connection refused` | n8n not running | Ask human to run `npm start` |
| `python3 not found` | python3 path issue | Try `python` instead of `python3` |
| MCP Google error | Token expired | Re-run: `npx @piotr-agier/google-drive-mcp auth` |

---

## Git Workflow

Initialize once:
```bash
git init
git add CLAUDE.md .gitignore docs/ workflows/
git commit -m "init: n8n workspace"
```

After every successful workflow change:
```bash
git add workflows/
git commit -m "workflow: describe what changed"
```

**Never commit:** `.env` · `.mcp.json` · `gcp-oauth.keys.json` · `*.token.json`

---

## Human's Role (Architect)

The human will:
- Define what each workflow should accomplish
- Click "Test Workflow" in n8n UI when asked (since /run doesn't work)
- Approve workflows before activation
- Set up new OAuth credentials in n8n UI when needed

You handle everything else.

---

## Spreadsheet Migration History

| Version | Spreadsheet ID | Status |
|---------|---------------|--------|
| V1 (Original) | `12q_ZZJEkE6xQGJH0XxwCFlt821lpEBgCjLkfm0GmX-g` | RETIRED |
| V2 (Current) | `1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw` | ACTIVE |

**Always use V2 ID.** Never reference V1 in any workflow or verification.

---

## ⚠️ Critical: n8n PUT API — Strip These Fields

When updating a workflow via `PUT /api/v1/workflows/ID`, only send these 4 fields:
- `name`
- `nodes`
- `connections`
- `settings`

**Strip everything else before sending** or you get:
`"request/body must NOT have additional properties"`

Fields to strip from root: `id`, `active`, `shared`, `staticData`, `meta`, `pinData`

Fields to strip from `settings`: `availableInMCP`, `timeSavedMode`, `callerPolicy`, `binaryMode`

### Safe PUT template (use this every time):
```python
import json, sys

with open(sys.argv[1]) as f:
    wf = json.load(f)

safe = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {
        k: v for k, v in wf.get("settings", {}).items()
        if k not in ["availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"]
    }
}

print(json.dumps(safe))
```

Usage:
```bash
python3 strip_workflow.py workflows/active/my-workflow.json | \
  curl -X PUT http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
    -H "X-N8N-API-KEY: $N8N_API_KEY" \
    -H "Content-Type: application/json" \
    -d @-
```

---

## Schema Reference (V2 Sheet)

### Properties Tab
- `fixedCleanerId` — the permanently assigned cleaner for this property
- ~~`cleanerId`~~ — REMOVED, replaced by `fixedCleanerId`

### CleanersProfile Tab
- `assignmentCount` — number of jobs assigned this period
- `assignmentCountResetDate` — date when assignmentCount was last reset

> Any workflow node or expression referencing `cleanerId` is a bug — change to `fixedCleanerId`.

---

# PROJECT 2: COLD EMAIL AUTOMATION

## Overview

Automated cold email outreach system built with n8n workflows.
Full docs: `docs/cold-email/`

## Workflows & Their IDs

| ID | Workflow Name | Trigger Type |
|----|--------------|--------------|
| `4TaA4kHwa5r1GULP` | CE-1 Lead Qualification Engine | Google Sheets Trigger (new row in Raw Leads) |

## Google Sheets — Cold Email Data

**Spreadsheet ID:** `1gF7uU_3KsWy5XGm16Rf1mNuDVy-tsTreEMDx0wGt244`
**Sheet Name:** Zelvop Outreach System — 2026

| Tab Name | Sheet ID (gid) | Purpose |
|----------|----------------|---------|
| `Raw Leads` | `0` | New leads for scoring |
| `NoWeb` | `1213372079` | Leads without websites |
| `Approved Leads` | `161711194` | Scored >= 7, ready for email |
| `Review Queue` | `987679073` | Scored < 7, manual review |
| `Outreach Log` | `796443488` | Email send log |
| `Reply Tracker` | `1582781887` | Reply tracking |
| `Weekly Report` | `1740217095` | Weekly metrics |

> Same rules apply: always use `mode: "id"` for both documentId and sheetName.

## Forms

| Form | Form ID | Purpose |
|------|---------|---------|
| — | — | — |

## Credential Names

Uses the same n8n credentials as Cleaning Operations (Gmail, Google Sheets, etc.).

| Service | Credential Name in n8n | Credential ID | Type |
|---------|------------------------|---------------|------|
| Google Sheets | `Google Sheets account` | `q52dbWoN6OaKRDZO` | OAuth2 |
| Google Sheets Trigger | `Google Sheets Trigger account` | `E2pL4RCwwnxZSv1L` | OAuth2 |
| Claude API | `Claude API` | `zlY2A0vDJbGDd7Ey` | HTTP Header Auth (`x-api-key`) |
| Apify API | `Apify API` | `JFJHpRwTtiSH45ng` | HTTP Header Auth (`Authorization: Bearer`) |