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

> **First time setup check**: If n8n API key is not in `.env`, remind the human to go to  
> n8n → Settings → API → Enable & copy key → paste into `.env` as `N8N_API_KEY=xxxx`

---

## Folder Structure

```
project-root/
├── CLAUDE.md              ← you are here
├── .env                   ← N8N_API_KEY lives here (never commit this)
├── .gitignore             ← must include .env
├── workflows/
│   ├── active/            ← production-ready workflows
│   └── drafts/            ← work in progress
├── tests/
│   └── payloads/          ← sample JSON payloads for webhook testing
└── docs/
    └── credentials.md     ← credential names used in n8n (no secrets, just names)
```

---

## Core Commands You Must Know

### Load API key from .env
```bash
export $(cat .env | xargs)
```

### List all workflows
```bash
curl -s http://localhost:5678/api/v1/workflows \
  -H "X-N8N-API-KEY: $N8N_API_KEY" | jq '.data[] | {id, name, active}'
```

### Get a specific workflow (to inspect current state)
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
7. CHECK execution result → look for status: "success" or "error"
8. IF error → read error message → fix JSON → go back to step 5
9. REPORT to human: what changed, what the test result was, any warnings
```

**Never tell the human "it should work" without actually running step 6-7.**

---

## Credential Names (reference these in workflow JSON, never the actual secrets)

These credentials are already configured in n8n. Use these exact names in workflow nodes:

| Service | Credential Name in n8n |
|---------|------------------------|
| Gmail | `Gmail account` |
| Google Sheets | `Google Sheets account` |
| Google Calendar | `Google Calendar account` |
| Google Forms | `Google Forms account` |
| HTTP Basic/API calls | `HTTP Header Auth` |

> If you create a node that needs a credential not listed here, flag it to the human.  
> They will set it up in n8n UI and give you the credential name to add here.

---

## Workflow JSON Rules

- Always include `"name"`, `"nodes"`, `"connections"`, `"settings"` keys at root level
- Node IDs must be unique UUIDs — generate new ones, never copy-paste
- Keep `"active": false` for all drafts until human approves
- For Google services: use `"authentication": "oAuth2"` in node parameters
- For webhook triggers: document the webhook URL in a Sticky Note node at the top
- Always add a Sticky Note node explaining what the workflow does (node type: `n8n-nodes-base.stickyNote`)

---

## Testing Rules

1. **Always test before declaring done**
2. For Gmail/Sheets/Calendar: run with `"mode": "manual"` first — check the execution log
3. For webhook workflows: use a sample payload from `tests/payloads/`
4. If a test touches real Gmail/Sheets: warn the human first and use test data
5. After a successful test: move workflow JSON from `drafts/` to `active/`

---

## What You Cannot Do (tell the human instead)

- Set up OAuth credentials in n8n (they must do this in the browser)
- Access n8n if it's not running — remind them to run `npm start`
- Fix bugs caused by missing credentials — ask for the credential name
- Deploy to production without human approval

---

## Error Patterns & Fixes

| Error | Likely Cause | Fix |
|-------|-------------|-----|
| `401 Unauthorized` | Wrong/missing API key | Check `.env`, reload with `export $(cat .env \| xargs)` |
| `404 Not Found` | Wrong workflow ID | Run list command to get correct ID |
| `Credential not found` | Credential name mismatch | Check `docs/credentials.md` for exact name |
| `node X failed` | Logic error in that node | Get full execution details, read the node error |
| `n8n connection refused` | n8n not running | Ask human to run `npm start` |

---

## Git Workflow

This folder has its own independent git repo. Initialize it once:

```bash
git init
git add CLAUDE.md .gitignore docs/ workflows/
git commit -m "init: n8n workspace"
```

After every successful workflow change:
```bash
git add workflows/
git commit -m "workflow: short description of what changed"
```

Never commit:
- `.env`
- Any file with actual API keys or OAuth tokens
- `workflows/drafts/` unless human approves

---

## Human's Role (Architect)

The human will:
- Tell you what the workflow should accomplish
- Approve workflows before activation
- Set up credentials in n8n UI when needed
- Tell you the test scenario and expected output

You will handle everything else.