# WhatsApp AI Auto-Reply — Setup

## n8n Workflow ID
`dj7Drw7mdoJfk7B4`

## Files (all removable)
- `workflows/drafts/whatsapp/` — workflow JSON
- `docs/whatsapp/` — this file
- `C:\folderF\whatsapp-ai-bridge\` — Baileys Node.js bridge (separate folder)

## To Remove Everything
```bash
rm -rf workflows/drafts/whatsapp/
rm -rf docs/whatsapp/
# Delete workflow in n8n UI or via API:
# curl -X DELETE http://localhost:5678/api/v1/workflows/dj7Drw7mdoJfk7B4 -H "X-N8N-API-KEY: $N8N_API_KEY"
# Then delete C:\folderF\whatsapp-ai-bridge\ manually
```

## n8n Environment Variables to Add
Go to n8n → Settings → Environment Variables:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | Your Claude API key |
| `GOOGLE_SHEET_ID` | Your conversations sheet ID |
| `BAILEYS_BRIDGE_URL` | `http://localhost:3000` (or server IP) |

## Google Sheet Setup
1. Create a new Google Sheet
2. Name the first tab: `conversations`
3. Add headers in row 1:
   - A: `timestamp`
   - B: `contact_jid`
   - C: `contact_name`
   - D: `direction`
   - E: `message_text`
   - F: `session_date`
4. Share the sheet with your Google Service Account email (Editor)
5. Copy the Sheet ID from the URL and set as `GOOGLE_SHEET_ID`

## Flow
```
Baileys (WhatsApp) → POST /webhook/whatsapp-incoming (n8n)
  → Filter (block groups/status)
  → Prepare Variables
  → Google Sheets: Fetch last 10 messages
  → Code: Format history for Claude
  → Claude Haiku API
  → Delay 3–7s (typing simulation)
  → POST http://localhost:3000/send (Baileys sends reply)
  → Google Sheets: Log incoming + outgoing
```

## Baileys Bridge Config
Update `index.js` in `whatsapp-ai-bridge/` to POST to:
`http://localhost:5678/webhook/whatsapp-incoming`

Or set the n8n webhook URL in Baileys index.js POST /incoming handler.
