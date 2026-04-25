import json, sys

with open('workflows/drafts/cold-email/CE1-lead-qualification.json', 'rb') as f:
    wf = json.loads(f.read().decode('utf-8', errors='replace'))

nodes = wf['nodes']
connections = wf['connections']

# ── 1. Fix Claude Email Writing prompt ───────────────────────────────────────
email_prompt = (
    "You write cold outreach emails for Zelvop — scheduling and dispatch software for cleaning businesses.\\n\\n"
    "STRICT RULES:\\n"
    "- Body is MAX 80 words. Cut anything that is not essential.\\n"
    "- Informal tone. Write like a real person, not a marketer.\\n"
    "- Line 1: use their first name + one specific observation (their rating, review count, or a detail from the pain signal).\\n"
    "- Line 2: one sentence naming their specific problem.\\n"
    "- Line 3: one sentence on what Zelvop solves for them — no feature lists, no buzzwords.\\n"
    "- Last line: a soft question they can answer in one sentence (opens conversation, no pressure).\\n"
    "- BANNED phrases: 'I hope this finds you well', 'quick call', 'hop on a demo', 'revolutionize', 'game-changer', 'at Zelvop we believe'\\n\\n"
    "SUBJECT LINE:\\n"
    "- Under 8 words\\n"
    "- Specific to them (use their name, review count, or pain)\\n"
    "- Curiosity or direct pain — not generic\\n\\n"
    "<lead>\\n"
    "  <name>\" + $json.ownerFirstName + \"</name>\\n"
    "  <business>\" + $json.businessName + \", \" + $json.city + \"</business>\\n"
    "  <rating>\" + $json.totalScore + \" stars, \" + $json.reviewsCount + \" reviews</rating>\\n"
    "  <pain_signal>\" + $json.painSignal + \"</pain_signal>\\n"
    "  <email_angle>\" + $json.emailAngle + \"</email_angle>\\n"
    "  <research_notes>\" + $json.researchNotes + \"</research_notes>\\n"
    "</lead>\\n\\n"
    "Return ONLY valid JSON, no markdown fences:\\n"
    "{\\n"
    "  \\\"emailSubject\\\": \\\"<subject line — specific, under 8 words>\\\",\\n"
    "  \\\"emailBody\\\": \\\"<the full email, max 80 words>\\\"\\n"
    "}"
)

new_email_json_body = (
    '={{ JSON.stringify({\n'
    '  "model": "claude-haiku-4-5-20251001",\n'
    '  "max_tokens": 600,\n'
    '  "messages": [\n'
    '    {\n'
    '      "role": "user",\n'
    '      "content": "' + email_prompt + '"\n'
    '    }\n'
    '  ]\n'
    '}) }}'
)

for n in nodes:
    if n['name'] == 'Claude Email Writing':
        n['parameters']['jsonBody'] = new_email_json_body
        # Use Claude API credential (same as ICP scoring node)
        n['credentials'] = {
            "httpHeaderAuth": {
                "id": "zlY2A0vDJbGDd7Ey",
                "name": "Claude API"
            }
        }
        sys.stderr.write('Updated: Claude Email Writing\n')

# ── 2. Add "Parse Email Response" Code node ───────────────────────────────────
parse_email_node = {
    "parameters": {
        "jsCode": """// Parse Claude email response and merge with lead data
const claudeResp = $input.item.json;
const lead = $('Parse Claude Score').item.json;

// Extract text from Claude response
let text = '';
if (claudeResp.content && claudeResp.content[0]) {
  text = claudeResp.content[0].text || '';
}

// Strip markdown fences
text = text.replace(/^```(?:json)?\\s*/i, '').replace(/\\s*```\\s*$/i, '').trim();

let emailSubject = '';
let emailBody = '';

try {
  const parsed = JSON.parse(text);
  emailSubject = parsed.emailSubject || '';
  emailBody = parsed.emailBody || '';
} catch(e) {
  emailBody = text;
}

return [{ json: {
  ...lead,
  emailSubject,
  emailBody
} }];"""
    },
    "id": "a1b2c3d4-ce01-4aaa-bbbb-email00000001",
    "name": "Parse Email Response",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": [3408, -240]
}

nodes.append(parse_email_node)
sys.stderr.write('Added: Parse Email Response\n')

# ── 3. Update Write Approved Leads — add email columns ───────────────────────
for n in nodes:
    if n['name'] == 'Write Approved Leads':
        cols = n['parameters']['columns']
        # Add new column mappings
        cols['value']['Email 1 Subject'] = '={{ $json.emailSubject }}'
        cols['value']['Email 1 Body'] = '={{ $json.emailBody }}'
        # Add to schema
        cols['schema'].append({
            "id": "Email 1 Subject",
            "displayName": "Email 1 Subject",
            "required": False,
            "defaultMatch": False,
            "display": True,
            "type": "string",
            "canBeUsedToMatch": True
        })
        cols['schema'].append({
            "id": "Email 1 Body",
            "displayName": "Email 1 Body",
            "required": False,
            "defaultMatch": False,
            "display": True,
            "type": "string",
            "canBeUsedToMatch": True
        })
        sys.stderr.write('Updated: Write Approved Leads columns\n')

# ── 4. Rewire connections ─────────────────────────────────────────────────────
# Old: Score Router TRUE → Claude Email Writing → Write Approved Leads
# New: Score Router TRUE → Claude Email Writing → Parse Email Response → Write Approved Leads

connections['Claude Email Writing'] = {
    "main": [[{"node": "Parse Email Response", "type": "main", "index": 0}]]
}
connections['Parse Email Response'] = {
    "main": [[{"node": "Write Approved Leads", "type": "main", "index": 0}]]
}
sys.stderr.write('Updated: connections (Parse Email Response wired)\n')

# ── Build safe PUT payload ─────────────────────────────────────────────────────
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
