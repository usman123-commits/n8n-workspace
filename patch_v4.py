import json, sys

with open('workflows/drafts/cold-email/CE1-lead-qualification.json', 'rb') as f:
    wf = json.loads(f.read().decode('utf-8', errors='replace'))

nodes = wf['nodes']
connections = wf['connections']

# ── 1. Change Wait for Scraper from 90s → 30s (polling interval) ─────────────
for n in nodes:
    if n['name'] == 'Wait for Scraper':
        n['parameters']['amount'] = 30
        sys.stderr.write('Updated: Wait for Scraper → 30s\n')

# ── 2. Fix Apify Get Results URL (body.data, not data) ────────────────────────
for n in nodes:
    if n['name'] == 'Apify Get Results':
        n['parameters']['url'] = (
            "={{ 'https://api.apify.com/v2/datasets/' "
            "+ $('Apify Start Scraper').item.json.body.data.defaultDatasetId "
            "+ '/items' }}"
        )
        sys.stderr.write('Updated: Apify Get Results URL\n')

# ── 3. Add "Check Apify Status" HTTP GET node ─────────────────────────────────
check_status_node = {
    "parameters": {
        "url": "={{ 'https://api.apify.com/v2/acts/nwua9Gu5YrADL7ZDj/runs/' + $('Apify Start Scraper').item.json.body.data.id }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "options": {
            "response": {
                "response": {
                    "fullResponse": True,
                    "responseFormat": "json"
                }
            }
        }
    },
    "id": "a1b2c3d4-ce01-4aaa-bbbb-poll000000001",
    "name": "Check Apify Status",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4,
    "position": [600, 64],
    "credentials": {
        "httpHeaderAuth": {
            "id": "JFJHpRwTtiSH45ng",
            "name": "Apify API"
        }
    }
}

# ── 4. Add "Is Run Done?" IF node ─────────────────────────────────────────────
is_done_node = {
    "parameters": {
        "conditions": {
            "options": {
                "caseSensitive": True,
                "leftValue": "",
                "typeValidation": "strict"
            },
            "conditions": [
                {
                    "id": "condition-run-done",
                    "leftValue": "={{ $json.body.data.status }}",
                    "rightValue": "SUCCEEDED",
                    "operator": {
                        "type": "string",
                        "operation": "equals"
                    }
                }
            ],
            "combinator": "and"
        },
        "options": {}
    },
    "id": "a1b2c3d4-ce01-4aaa-bbbb-poll000000002",
    "name": "Is Run Done?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": [720, 64]
}

nodes.append(check_status_node)
nodes.append(is_done_node)
sys.stderr.write('Added: Check Apify Status, Is Run Done?\n')

# ── 5. Update connections ─────────────────────────────────────────────────────
# Old: Wait for Scraper → Apify Get Results
# New: Wait for Scraper → Check Apify Status → Is Run Done?
#        TRUE  → Apify Get Results
#        FALSE → Wait for Scraper  (loop)

connections['Wait for Scraper'] = {
    "main": [[{"node": "Check Apify Status", "type": "main", "index": 0}]]
}

connections['Check Apify Status'] = {
    "main": [[{"node": "Is Run Done?", "type": "main", "index": 0}]]
}

connections['Is Run Done?'] = {
    "main": [
        # TRUE (output 0) → Apify Get Results
        [{"node": "Apify Get Results", "type": "main", "index": 0}],
        # FALSE (output 1) → Wait for Scraper (loop back)
        [{"node": "Wait for Scraper", "type": "main", "index": 0}]
    ]
}

sys.stderr.write('Updated: connections (polling loop wired)\n')

# ── Build safe PUT payload ────────────────────────────────────────────────────
safe = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {
        k: v for k, v in wf.get("settings", {}).items()
        if k not in ["availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"]
    }
}

sys.stdout.buffer.write(json.dumps(safe, ensure_ascii=True).encode('ascii'))
