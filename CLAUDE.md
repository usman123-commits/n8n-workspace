# CLAUDE.md — n8n Workflow Automation Project

You are the **engineering partner** for this n8n automation project.
The human acts as **architect** — they define what workflows should do.
You handle: writing workflow JSON, pushing to n8n, running tests, reading results, fixing bugs, and iterating.

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

> **This is a dedicated workspace folder.** It is NOT inside any other project.  
> Open only this folder in Claude Code — not a parent folder.

> **First time setup check**: If n8n API key is not in `.env`, remind the human to:  
> n8n → Settings → API → Enable & copy key → paste into `.env` as `N8N_API_KEY=xxxx`

---

## Folder Structure

```
n8n-workspace/
├── CLAUDE.md                  ← you are here
├── .mcp.json                  ← MCP server config (never commit)
├── .env                       ← N8N_API_KEY (never commit)
├── .gitignore
├── gcp-oauth.keys.json        ← Google Cloud OAuth credentials (never commit)
├── workflows/
│   ├── active/                ← production-ready workflows
│   └── drafts/                ← work in progress
├── tests/
│   └── payloads/              ← sample JSON payloads for webhook testing
└── docs/
    └── credentials.md         ← credential names used in n8n (no secrets)
```

---

## Core n8n Commands

### Load API key from .env
```bash
export $(grep -v '^#' .env | xargs)
```

### List all workflows
```bash
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, name, active}'
```

### Get a specific workflow
```bash
curl -s http://localhost:5678/api/v1/workflows/WORKFLOW_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.'
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

### Trigger a manual test execution
```bash
curl -X POST http://localhost:5678/api/v1/workflows/WORKFLOW_ID/run \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Trigger with test payload (for webhook workflows)
```bash
curl -X POST http://localhost:5678/api/v1/workflows/WORKFLOW_ID/run \
  -H "X-N8N-API-KEY: $N8N_API_KEY" \
  -H "Content-Type: application/json" \
  -d @tests/payloads/test-payload.json
```

### Get last 5 executions + status
```bash
curl -s "http://localhost:5678/api/v1/executions?workflowId=WORKFLOW_ID&limit=5" \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, status, startedAt, stoppedAt}'
```

### Get full execution details (with error info)
```bash
curl -s http://localhost:5678/api/v1/executions/EXECUTION_ID \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.'
```

---

## Standard Work Loop (follow this every time)

```
1. READ the task from the human (what should this workflow do?)
2. CHECK if workflow already exists → list workflows
3. GET current JSON if updating → save to workflows/ folder
4. EDIT the JSON (make your changes)
5. PUSH to n8n via PUT/POST
6. RUN a test execution
7. CHECK n8n execution result → success or error?
8. IF error → read error message → fix JSON → back to step 5
9. VERIFY in Google Workspace via MCP tools (see section below)
10. REPORT to human: what changed, test result, workspace verification
```

**Never tell the human "it should work" without completing steps 6–9.**

---

## Credential Names (use these exact names in workflow JSON nodes)

| Service | Credential Name in n8n |
|---------|------------------------|
| Gmail | `Gmail account` |
| Google Sheets | `Google Sheets account` |
| Google Calendar | `Google Calendar account` |
| Google Forms | `Google Forms account` |
| HTTP Basic/API calls | `HTTP Header Auth` |

> If you need a credential not listed here, stop and ask the human.
> They add it in n8n UI → Settings → Credentials, then give you the exact name.

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
2. Run with manual mode first — check execution log before anything else
3. For webhook workflows: use a sample payload from `tests/payloads/`
4. If test touches real Gmail/Sheets/Calendar: warn the human, use test data
5. After successful test: move workflow JSON from `drafts/` → `active/`
6. **Always verify in Google Workspace after every execution** (see below)

---

## Google Workspace Verification (Post-Execution Checks)

You have **direct MCP access** to Google Workspace (Sheets, Gmail, Calendar, Drive).
After every workflow run, verify the actual real-world output — do not trust n8n status alone.

### Verification flow
```
1. n8n execution completes
2. Use MCP tools to check the actual Google service
3. Compare: human's expected output vs what actually happened
4. Any mismatch = bug, even if n8n said "success"
```

### What to verify per service

**Google Sheets**
- Read the target range → confirm data is in the right cells
- Check: correct sheet tab, correct row/column, no duplicates, correct data types
- Common bug: data written to wrong sheet, or row appended twice

**Gmail**
- After send: check Sent → confirm recipient, subject, body
- After label/filter: confirm label applied to the right thread
- After trigger (reads email): confirm the right emails were picked up by the workflow

**Google Calendar**
- After create event: confirm title, date, time, timezone, attendees are correct
- After update: old version gone, new version correct
- Always check for duplicate events (very common n8n bug)

**Google Forms / Sheets integration**
- After form response processed: trace the full chain
- Form response → what n8n received → what was written to Sheets → all must match

### Post-test checklist
```
[ ] n8n execution status = success
[ ] Google Workspace reflects the expected change
[ ] No duplicate records / emails / events created
[ ] Data format is correct (dates, numbers, text encoding)
[ ] No unintended side effects in other sheets/calendars/inbox folders
```

### If Workspace doesn't match n8n "success"
Logic bug — workflow ran but produced wrong output:
1. Pull full execution details, trace each node's output
2. Find where data diverged from expected
3. Fix that node, push, re-verify from scratch

---

## What You Cannot Do (tell the human instead)

- Set up OAuth credentials in n8n (they do this in the browser)
- Access n8n if it's not running → remind them: `npm start` in their n8n folder
- Fix missing credentials → ask for the credential name to add to table above
- Activate workflows to production without human approval
- Set up Google Cloud Console credentials (one-time human task — see docs/google-setup.md)

---

## Error Patterns & Fixes

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `401 Unauthorized` | Wrong/missing API key | Check `.env`, reload with `export $(grep -v '^#' .env \| xargs)` |
| `404 Not Found` | Wrong workflow ID | Run list command to get correct ID |
| `Credential not found` | Credential name mismatch | Check credential names table above |
| `node X failed` | Logic error in that node | Get full execution details, read node error |
| `n8n connection refused` | n8n not running | Ask human to run `npm start` in their n8n folder |
| MCP Google error | Token expired or missing | Ask human to re-run auth: `npx @piotr-agier/google-drive-mcp auth` |

---

## Git Workflow

This folder has its own independent git repo. Initialize once:

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

**Never commit:** `.env` · `.mcp.json` · `gcp-oauth.keys.json` · `*.token.json` · `workflows/drafts/`

---

## Human's Role (Architect)

The human will:
- Define what each workflow should accomplish
- Approve workflows before activation
- Set up OAuth credentials in n8n UI when needed
- Tell you the test scenario and expected output
- Handle one-time Google Cloud Console setup (see docs/google-setup.md)

You handle everything else.