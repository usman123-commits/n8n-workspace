"""
Patch Workflow 2 at the raw text level to avoid json surrogate issues.
Changes:
  1. Assign Cleaner: add declinedBy filtering to the availableCleaners check
  2. Connections: reroute Cleaner Available? false -> Is Fixed Assignment?
  3. Add 4 new nodes: Is Fixed Assignment?, Generate Offer Links, Send Offer Email, Update Job Offered
  4. Add 4 new connections for the offer chain
"""
import json, re

with open('workflows/active/cleaning/workflow-2-cleaner-assignment.json', encoding='utf-8') as f:
    content = f.read()

# ── 1. Patch Assign Cleaner jsCode (raw JSON-encoded string replacement) ───
OLD = (
    "  // Available cleaners = non-busy AND not fixed to another property\\n"
    "  const availableCleaners = cleaners.filter(r => {\\n"
    "    const cId = get(r, 'cleanerId');\\n"
    "    return cId && !busyCleanerIds.has(cId) && !allFixedCleanerIds.has(cId);\\n"
    "  });"
)
NEW = (
    "  // Get declined cleaners for this specific job\\n"
    "  const declinedByStr = (item.declinedBy || '').toString().trim();\\n"
    "  const declinedByIds = declinedByStr\\n"
    "    ? declinedByStr.split(',').map(s => s.trim()).filter(Boolean)\\n"
    "    : [];\\n\\n"
    "  // Available cleaners = non-busy AND not fixed AND not declined this job\\n"
    "  const availableCleaners = cleaners.filter(r => {\\n"
    "    const cId = get(r, 'cleanerId');\\n"
    "    return cId && !busyCleanerIds.has(cId)\\n"
    "      && !allFixedCleanerIds.has(cId)\\n"
    "      && !declinedByIds.includes(cId);\\n"
    "  });"
)
if OLD not in content:
    print("ERROR: OLD filter text not found — check string")
    exit(1)
content = content.replace(OLD, NEW, 1)
print("OK: Assign Cleaner patched (declinedBy filtering added)")

# ── 2. Reroute connection: Cleaner Available? false -> Is Fixed Assignment? ─
OLD_CONN = '"Cleaner Available?": {\n            "main": [\n                [\n                    {\n                        "node": "Mark Needs Manual Assignment",\n                        "type": "main",\n                        "index": 0\n                    }\n                ],\n                [\n                    {\n                        "node": "Increment Assignment Count",\n                        "type": "main",\n                        "index": 0\n                    }\n                ]\n            ]\n        }'
NEW_CONN = '"Cleaner Available?": {\n            "main": [\n                [\n                    {\n                        "node": "Mark Needs Manual Assignment",\n                        "type": "main",\n                        "index": 0\n                    }\n                ],\n                [\n                    {\n                        "node": "Is Fixed Assignment?",\n                        "type": "main",\n                        "index": 0\n                    }\n                ]\n            ]\n        }'
if OLD_CONN not in content:
    print("ERROR: Cleaner Available? connection block not found — check string")
    exit(1)
content = content.replace(OLD_CONN, NEW_CONN, 1)
print("OK: Cleaner Available? connection rerouted")

# ── 3. Add 4 new nodes before the closing ] of the nodes array ─────────────
new_nodes_json = json.dumps([
    {
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
                "conditions": [
                    {
                        "id": "is-fixed",
                        "leftValue": "={{ $json._isFixedAssignment }}",
                        "rightValue": True,
                        "operator": {"type": "boolean", "operation": "equals"}
                    }
                ],
                "combinator": "and"
            },
            "options": {}
        },
        "id": "wf2mod01-aaaa-4bbb-cccc-dd0000000001",
        "name": "Is Fixed Assignment?",
        "type": "n8n-nodes-base.if",
        "typeVersion": 2,
        "position": [-5024, -432],
        "notes": "TRUE = fixed cleaner (auto-assign, existing flow). FALSE = round-robin (send offer email)."
    },
    {
        "parameters": {
            "jsCode": (
                "const WEBHOOK_BASE = 'http://localhost:5678/webhook/job-response';\n"
                "const job = $input.first().json;\n"
                "const bookingUid = job.bookingUid || '';\n"
                "const cleanerId  = job.cleanerId  || '';\n"
                "const qs = '?bookingUid=' + encodeURIComponent(bookingUid)\n"
                "         + '&cleanerId='  + encodeURIComponent(cleanerId);\n"
                "const acceptLink  = WEBHOOK_BASE + qs + '&response=accept';\n"
                "const declineLink = WEBHOOK_BASE + qs + '&response=decline';\n"
                "const startTime = (job.scheduledCleaningTimeUTC || '').trim();\n"
                "let dateStr = 'TBD', timeStr = 'TBD';\n"
                "if (startTime) {\n"
                "  const d = new Date(startTime);\n"
                "  if (!isNaN(d.getTime())) {\n"
                "    dateStr = d.toISOString().slice(0, 10);\n"
                "    timeStr = d.toISOString().slice(11, 16) + ' UTC';\n"
                "  }\n"
                "}\n"
                "return [{ json: {\n"
                "  ...job,\n"
                "  acceptLink,\n"
                "  declineLink,\n"
                "  offerDateStr: dateStr,\n"
                "  offerTimeStr: timeStr,\n"
                "  offeredAt: new Date().toISOString()\n"
                "} }];"
            )
        },
        "id": "wf2mod02-aaaa-4bbb-cccc-dd0000000002",
        "name": "Generate Offer Links",
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [-4800, -624],
        "notes": "Builds Accept/Decline webhook URLs and formats date/time for the offer email."
    },
    {
        "parameters": {
            "sendTo":    "={{ $json.cleanerEmail }}",
            "subject":   "=New Cleaning Job Available - {{ $json.propertyName || $json.propertyUid }}",
            "emailType": "text",
            "message": (
                "=Hi {{ $json.cleanerName || 'there' }},\n\n"
                "A new cleaning job is available and we would like to offer it to you.\n\n"
                "Property: {{ $json.propertyName || $json.propertyUid }}\n"
                "Date:     {{ $json.offerDateStr }}\n"
                "Time:     {{ $json.offerTimeStr }}\n\n"
                "Please respond within 1 hour.\n\n"
                "ACCEPT JOB:\n{{ $json.acceptLink }}\n\n"
                "DECLINE:\n{{ $json.declineLink }}\n\n"
                "If you do not respond within 1 hour, the job will be offered to another cleaner."
            ),
            "options": {}
        },
        "id": "wf2mod03-aaaa-4bbb-cccc-dd0000000003",
        "name": "Send Offer Email",
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": [-4576, -624],
        "webhookId": "c4d5e6f7-a8b9-4c0d-1e2f-a3b4c5d6e7f8",
        "credentials": {
            "gmailOAuth2": {"id": "6sr232YN6z3c4tiW", "name": "Gmail account"}
        },
        "notes": "Sends the offer with Accept/Decline links. Cleaner has 1 hour to respond."
    },
    {
        "parameters": {
            "operation": "update",
            "documentId": {"__rl": True, "value": "1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw", "mode": "id"},
            "sheetName":  {"__rl": True, "value": "2047086003", "mode": "id"},
            "columns": {
                "mappingMode": "defineBelow",
                "value": {
                    "bookingUid":      "={{ $json.bookingUid }}",
                    "status":          "OFFERED",
                    "cleanerId":       "={{ $json.cleanerId }}",
                    "assignedCleaner": "={{ $json.cleanerName }}",
                    "assignedAt":      "={{ $json.offeredAt }}",
                    "offeredTo":       "={{ $json.cleanerId }}",
                    "offeredAt":       "={{ $json.offeredAt }}",
                    "processingFlag":  " "
                },
                "matchingColumns": ["bookingUid"],
                "schema": [
                    {"id": "bookingUid",      "displayName": "bookingUid",      "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "status",          "displayName": "status",          "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "cleanerId",       "displayName": "cleanerId",       "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "assignedCleaner", "displayName": "assignedCleaner", "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "assignedAt",      "displayName": "assignedAt",      "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "offeredTo",       "displayName": "offeredTo",       "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "offeredAt",       "displayName": "offeredAt",       "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True},
                    {"id": "processingFlag",  "displayName": "processingFlag",  "type": "string", "required": False, "defaultMatch": False, "display": True, "canBeUsedToMatch": True}
                ],
                "attemptToConvertTypes": False,
                "convertFieldsToString": False
            },
            "options": {}
        },
        "id": "wf2mod04-aaaa-4bbb-cccc-dd0000000004",
        "name": "Update Job Offered",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.4,
        "position": [-4352, -624],
        "credentials": {
            "googleSheetsOAuth2Api": {"id": "q52dbWoN6OaKRDZO", "name": "Google Sheets account"}
        },
        "notes": "Sets status=OFFERED, records offeredTo and offeredAt. Clears processingFlag."
    }
], indent=4, ensure_ascii=True)

# Remove outer [] and indent each line by 8 spaces, prefix with comma
inner = new_nodes_json.strip()[1:-1].strip()  # remove [ and ]
indented = '\n'.join('        ' + line for line in inner.split('\n'))

# Insert before the closing ],\n    "connections" line
NODES_CLOSE = '    ],\n    "connections"'
if NODES_CLOSE not in content:
    print("ERROR: nodes array closing marker not found")
    exit(1)
content = content.replace(NODES_CLOSE, ',\n' + indented + '\n    ],\n    "connections"', 1)
print("OK: 4 new nodes injected")

# ── 4. Add new connections before the closing } of connections object ───────
new_connections = json.dumps({
    "Is Fixed Assignment?": {
        "main": [
            [{"node": "Increment Assignment Count", "type": "main", "index": 0}],
            [{"node": "Generate Offer Links",        "type": "main", "index": 0}]
        ]
    },
    "Generate Offer Links": {"main": [[{"node": "Send Offer Email",   "type": "main", "index": 0}]]},
    "Send Offer Email":      {"main": [[{"node": "Update Job Offered", "type": "main", "index": 0}]]},
    "Update Job Offered":    {"main": [[{"node": "Split In Batches",   "type": "main", "index": 0}]]}
}, indent=4, ensure_ascii=True)

# Extract inner content (without outer {})
conn_inner = new_connections.strip()[1:-1].strip()
indented_conn = '\n'.join('        ' + line for line in conn_inner.split('\n'))

# Insert before the closing } of the connections block
CONN_CLOSE = '    },\n    "settings"'
if CONN_CLOSE not in content:
    print("ERROR: connections closing marker not found")
    exit(1)
content = content.replace(CONN_CLOSE, ',\n' + indented_conn + '\n    },\n    "settings"', 1)
print("OK: 4 new connections injected")

# ── 5. Write back ─────────────────────────────────────────────────────────
with open('workflows/active/cleaning/workflow-2-cleaner-assignment.json', 'w', encoding='utf-8') as f:
    f.write(content)
print("OK: file saved")

# ── 6. Verify it's still valid JSON ──────────────────────────────────────
with open('workflows/active/cleaning/workflow-2-cleaner-assignment.json', encoding='utf-8') as f:
    try:
        data = json.load(f)
        node_names = [n['name'] for n in data['nodes']]
        print(f"OK: valid JSON, {len(data['nodes'])} nodes")
        for name in ['Is Fixed Assignment?', 'Generate Offer Links', 'Send Offer Email', 'Update Job Offered']:
            print(f"  {'FOUND' if name in node_names else 'MISSING'}: {name}")
    except Exception as e:
        print("ERROR: JSON parse failed:", e)
