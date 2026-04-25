import json, copy

with open('workflows/drafts/whatsapp/whatsapp-claude-workflow.json') as f:
    wf = json.load(f)

nodes = wf['nodes']
connections = wf['connections']

def find(name):
    for n in nodes:
        if n['name'] == name: return n
    return None

# CHANGE 1 — Update IF Filter
filt = find('Filter Messages')
filt['parameters']['conditions']['conditions'] = [
    {"id": "c1", "leftValue": "={{ $json.body.message }}", "rightValue": "",
     "operator": {"type": "string", "operation": "notEmpty"}},
    {"id": "c2", "leftValue": "={{ $json.body.from }}", "rightValue": "status",
     "operator": {"type": "string", "operation": "notContains"}},
    {"id": "c3",
     "leftValue": "={{ $json.body.isGroup === false || $json.body.groupJid === $env.GROUP_JID }}",
     "rightValue": "true",
     "operator": {"type": "string", "operation": "equals"}}
]
filt['parameters']['conditions']['combinator'] = 'and'
print('Change 1 done')

# CHANGE 2 — Update Prepare Variables
pv = find('Prepare Variables')
pv['parameters']['assignments']['assignments'] = [
    {"id": "v1",  "name": "contact_jid",      "value": "={{ $json.body.from }}",                                           "type": "string"},
    {"id": "v2",  "name": "contact_name",     "value": "={{ $json.body.fromName || '' }}",                                 "type": "string"},
    {"id": "v3",  "name": "incoming_message", "value": "={{ $json.body.message }}",                                        "type": "string"},
    {"id": "v4",  "name": "timestamp",        "value": "={{ $json.body.timestamp || new Date().toISOString() }}",          "type": "string"},
    {"id": "v5",  "name": "sheet_date",       "value": "={{ new Date().toISOString().slice(0,10) }}",                      "type": "string"},
    {"id": "v6",  "name": "phone_number",     "value": "={{ $json.body.from.replace(/@.*$/, '') }}",                       "type": "string"},
    {"id": "v7",  "name": "is_group",         "value": "={{ $json.body.isGroup }}",                                        "type": "boolean"},
    {"id": "v8",  "name": "group_jid",        "value": "={{ $json.body.groupJid || '' }}",                                 "type": "string"},
    {"id": "v9",  "name": "participant",      "value": "={{ $json.body.participant || '' }}",                              "type": "string"},
    {"id": "v10", "name": "memory_key",       "value": "={{ $json.body.isGroup ? $json.body.groupJid : $json.body.from }}", "type": "string"},
    {"id": "v11", "name": "reply_to",         "value": "={{ $json.body.isGroup ? $json.body.groupJid : $json.body.from }}", "type": "string"},
]
print('Change 2 done')

# CHANGE 3 — Update Fetch Message History filter
fmh = find('Fetch Message History')
fmh['parameters']['filtersUI']['values'][0]['lookupColumn'] = 'memory_key'
fmh['parameters']['filtersUI']['values'][0]['lookupValue']  = "={{ $('Prepare Variables').item.json.memory_key }}"
print('Change 3 done')

# CHANGE 4 — Add Switch node
switch_node = {
    "parameters": {
        "mode": "rules",
        "rules": {
            "values": [
                {
                    "conditions": {
                        "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                        "conditions": [{"id": "s1", "leftValue": "={{ $json.is_group }}", "rightValue": "false",
                                        "operator": {"type": "string", "operation": "equals"}}],
                        "combinator": "and"
                    },
                    "outputKey": "Private"
                },
                {
                    "conditions": {
                        "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
                        "conditions": [{"id": "s2", "leftValue": "={{ $json.is_group }}", "rightValue": "true",
                                        "operator": {"type": "string", "operation": "equals"}}],
                        "combinator": "and"
                    },
                    "outputKey": "Group"
                }
            ]
        },
        "options": {}
    },
    "id": "switch-001", "name": "Route by Type",
    "type": "n8n-nodes-base.switch", "typeVersion": 3,
    "position": [880, 304]
}
nodes.append(switch_node)
print('Change 4 done')

# CHANGE 5 — Group Trigger Check
gtc = {
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose"},
            "conditions": [
                {"id": "g1", "leftValue": "={{ $json.incoming_message }}",             "rightValue": "?",   "operator": {"type": "string", "operation": "contains"}},
                {"id": "g2", "leftValue": "={{ $json.incoming_message.toLowerCase() }}","rightValue": "bot", "operator": {"type": "string", "operation": "contains"}},
                {"id": "g3", "leftValue": "={{ $json.incoming_message }}",             "rightValue": "@",   "operator": {"type": "string", "operation": "contains"}}
            ],
            "combinator": "or"
        },
        "options": {}
    },
    "id": "gtc-001", "name": "Group Trigger Check",
    "type": "n8n-nodes-base.if", "typeVersion": 2,
    "position": [1100, 560]
}
nodes.append(gtc)
print('Change 5 done')

# CHANGE 6 — Fetch Group History
fgh = copy.deepcopy(fmh)
fgh['id']   = 'gs-004'
fgh['name'] = 'Fetch Group History'
fgh['position'] = [1320, 560]
fgh['alwaysOutputData'] = True
fgh['parameters']['filtersUI']['values'][0]['lookupColumn'] = 'contact_jid'
fgh['parameters']['filtersUI']['values'][0]['lookupValue']  = "={{ $('Prepare Variables').item.json.group_jid }}"
fgh['parameters']['options'] = {"returnAllMatches": True}
nodes.append(fgh)
print('Change 6 done')

# CHANGE 7 — Format Group History code node
group_history_code = (
    "// Format group history for Claude with sender names\n"
    "const allItems = $input.all();\n"
    "const vars = $('Prepare Variables').item.json;\n\n"
    "let contents = [];\n\n"
    "for (const item of allItems) {\n"
    "  const row = item.json;\n"
    "  if (!row.message_text || !row.direction) continue;\n"
    "  const senderLabel = row.direction === 'outgoing' ? 'Zara' : (row.contact_name || 'User');\n"
    "  contents.push({\n"
    "    role: row.direction === 'outgoing' ? 'assistant' : 'user',\n"
    "    content: row.direction === 'outgoing' ? row.message_text : '[' + senderLabel + ']: ' + row.message_text\n"
    "  });\n"
    "}\n\n"
    "contents = contents.slice(-15);\n\n"
    "contents.push({\n"
    "  role: 'user',\n"
    "  content: '[' + vars.contact_name + ']: ' + vars.incoming_message\n"
    "});\n\n"
    "return [{ json: { contents } }];"
)
fhg_code = {
    "parameters": {"jsCode": group_history_code},
    "id": "code-003", "name": "Format Group History for Claude",
    "type": "n8n-nodes-base.code", "typeVersion": 2,
    "position": [1540, 560],
    "alwaysOutputData": True
}
nodes.append(fhg_code)
print('Change 7 done')

# CHANGE 8 — Call Claude Haiku (Group)
claude_orig = find('Call Claude Haiku')
claude_group = copy.deepcopy(claude_orig)
claude_group['id']   = 'http-003'
claude_group['name'] = 'Call Claude Haiku (Group)'
claude_group['position'] = [1760, 560]
group_system = (
    "You are participating in a WhatsApp group chat. Multiple people talk here. "
    "Messages include sender names in format [Name]: message. "
    "Keep replies short and casual. Address the sender by name when relevant. "
    "Only reply when something is clearly directed at you or is a question. "
    "Use light humor when appropriate. Never use bullet points or formal formatting. "
    "Never reveal you are an AI. Match the language being used in the group. "
    "If someone writes in Urdu reply in Urdu, if English then English."
)
claude_group['parameters']['body'] = (
    "={{ JSON.stringify({ "
    "model: 'claude-haiku-4-5-20251001', "
    "max_tokens: 150, "
    "system: '" + group_system + "', "
    "messages: $json.contents.map(m => ({ role: m.role === 'model' ? 'assistant' : m.role, content: m.content || (m.parts && m.parts[0].text) || '' })) "
    "}) }}"
)
nodes.append(claude_group)
print('Change 8 done')

# CHANGE 9 — Group Typing Delay + Prepare Group Reply + Send Group Reply
delay_orig = find('Human Typing Delay')
group_delay = copy.deepcopy(delay_orig)
group_delay['id']       = 'code-004'
group_delay['name']     = 'Group Typing Delay'
group_delay['position'] = [1980, 560]
nodes.append(group_delay)

nodes.append({
    "parameters": {
        "assignments": {"assignments": [
            {"id": "gr1", "name": "ai_reply", "value": "={{ $json.ai_reply }}", "type": "string"}
        ]},
        "options": {}
    },
    "id": "set-003", "name": "Prepare Group Reply",
    "type": "n8n-nodes-base.set", "typeVersion": 3,
    "position": [2200, 560]
})

nodes.append({
    "parameters": {
        "method": "POST",
        "url": "={{ $env.BAILEYS_BRIDGE_URL || 'http://localhost:3000' }}/send",
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "content-type", "value": "application/json"}]},
        "sendBody": True,
        "specifyBody": "string",
        "body": "={{ JSON.stringify({ to: $('Prepare Variables').item.json.group_jid, message: $('Group Typing Delay').item.json.ai_reply }) }}",
        "options": {}
    },
    "id": "http-004", "name": "Send Group Reply via Baileys",
    "type": "n8n-nodes-base.httpRequest", "typeVersion": 4,
    "position": [2420, 560],
    "onError": "continueRegularOutput"
})
print('Change 9 done')

# CHANGE 10 — Group logging
gs_orig = find('Log Incoming Message')
log_gin = copy.deepcopy(gs_orig)
log_gin['id']   = 'gs-005'
log_gin['name'] = 'Log Group Incoming'
log_gin['position'] = [2640, 560]
log_gin['parameters']['columns']['value'] = {
    "timestamp":    "={{ $('Prepare Variables').item.json.timestamp }}",
    "contact_jid":  "={{ $('Prepare Variables').item.json.group_jid }}",
    "contact_name": "={{ $('Prepare Variables').item.json.contact_name }}",
    "direction":    "incoming",
    "message_text": "={{ $('Prepare Variables').item.json.incoming_message }}",
    "session_date": "={{ $('Prepare Variables').item.json.sheet_date }}"
}
nodes.append(log_gin)

log_gout = copy.deepcopy(find('Log Outgoing Message'))
log_gout['id']   = 'gs-006'
log_gout['name'] = 'Log Group Outgoing'
log_gout['position'] = [2860, 560]
log_gout['parameters']['columns']['value'] = {
    "timestamp":    "={{ new Date().toISOString() }}",
    "contact_jid":  "={{ $('Prepare Variables').item.json.group_jid }}",
    "contact_name": "BOT",
    "direction":    "outgoing",
    "message_text": "={{ $('Group Typing Delay').item.json.ai_reply }}",
    "session_date": "={{ $('Prepare Variables').item.json.sheet_date }}"
}
nodes.append(log_gout)
print('Change 10 done')

# CHANGE 11 — Update Send Reply via Baileys (private) to use reply_to
send_priv = find('Send Reply via Baileys')
send_priv['parameters']['body'] = "={{ JSON.stringify({ to: $('Prepare Variables').item.json.reply_to, message: $('Human Typing Delay').item.json.ai_reply }) }}"
print('Change 11 done')

# CHANGE 12 — New sticky note
nodes.append({
    "parameters": {
        "content": "## New Env Variable Needed\n`GROUP_JID` = paste your group JID here\n(e.g. `120363xxxxxx@g.us`)\n\nFind it: set `DEBUG_JIDS=true` in Baileys `.env`,\nsend a message in the group, copy JID from terminal.",
        "height": 160, "width": 340, "color": 6
    },
    "id": "sticky-005", "name": "Group JID Note",
    "type": "n8n-nodes-base.stickyNote", "typeVersion": 1,
    "position": [1100, 160]
})
print('Change 12 done')

# CHANGE 13 — Update setup sticky
setup = find('Setup Instructions')
setup['parameters']['content'] += (
    "\n\n**4.** Set `GROUP_JID` in n8n environment variables\n"
    "**5.** Group replies only trigger when message contains `?`, `bot`, or `@`"
)
print('Change 13 done')

# Shift private-branch nodes right to make room for Switch node at x=880
shift_nodes = [
    'Fetch Message History', 'Format History for Gemini', 'Call Claude Haiku',
    'Human Typing Delay', 'Prepare Reply', 'Send Reply via Baileys',
    'Log Incoming Message', 'Log Outgoing Message'
]
for n in nodes:
    if n['name'] in shift_nodes:
        n['position'][0] += 220

# Update connections
connections['Prepare Variables'] = {
    "main": [[{"node": "Route by Type", "type": "main", "index": 0}]]
}
connections['Route by Type'] = {
    "main": [
        [{"node": "Fetch Message History", "type": "main", "index": 0}],
        [{"node": "Group Trigger Check",   "type": "main", "index": 0}]
    ]
}
connections['Group Trigger Check'] = {
    "main": [
        [{"node": "Fetch Group History", "type": "main", "index": 0}],
        []
    ]
}
connections['Fetch Group History'] = {
    "main": [[{"node": "Format Group History for Claude", "type": "main", "index": 0}]]
}
connections['Format Group History for Claude'] = {
    "main": [[{"node": "Call Claude Haiku (Group)", "type": "main", "index": 0}]]
}
connections['Call Claude Haiku (Group)'] = {
    "main": [[{"node": "Group Typing Delay", "type": "main", "index": 0}]]
}
connections['Group Typing Delay'] = {
    "main": [[{"node": "Prepare Group Reply", "type": "main", "index": 0}]]
}
connections['Prepare Group Reply'] = {
    "main": [[{"node": "Send Group Reply via Baileys", "type": "main", "index": 0}]]
}
connections['Send Group Reply via Baileys'] = {
    "main": [[{"node": "Log Group Incoming", "type": "main", "index": 0}]]
}
connections['Log Group Incoming'] = {
    "main": [[{"node": "Log Group Outgoing", "type": "main", "index": 0}]]
}

with open('workflows/drafts/whatsapp/whatsapp-claude-workflow.json', 'w') as f:
    json.dump(wf, f, indent=2)

print('\nAll 13 changes applied and saved.')
