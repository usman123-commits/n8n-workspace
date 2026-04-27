"""
Add email nodes to merged 4W workflow (same pattern as 3W):
  - Happy path:  Get Cleaner Profile → Send Cleaner Checkout Email → Send Admin Checkout Email → Respond Approved (→ maintenance/supply in background)
  - Pre-GPS reject: Get Cleaner Profile (Rejected) → Send Cleaner Pre-GPS Reject Email → Respond Pre-GPS Reject
  - Outside radius: Get Cleaner Profile (Outside) → Send Cleaner Outside Radius Email → Respond Outside Radius
"""
import json, uuid

ROOT  = 'C:/folderF/n8n-workspace'
PATH  = f'{ROOT}/workflows/active/cleaning/workflow-4w-merged-checkout.json'
SS_ID = '1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw'
SHEETS_CRED = {"id": "q52dbWoN6OaKRDZO", "name": "Google Sheets account"}
GMAIL_CRED  = {"name": "Gmail account"}
ADMIN_EMAIL = "usman2acountf@gmail.com"
GID_CLEANERS = "1920390373"

def newid():
    return str(uuid.uuid4())

def doc_id_ref(v):
    return {"__rl": True, "value": v, "mode": "id"}

def gmail_node(name, send_to, subject, message, position):
    return {
        "id": newid(),
        "name": name,
        "type": "n8n-nodes-base.gmail",
        "typeVersion": 2.1,
        "position": position,
        "onError": "continueRegularOutput",
        "parameters": {
            "sendTo": send_to,
            "subject": subject,
            "emailType": "text",
            "message": message,
            "options": {}
        },
        "credentials": {"gmailOAuth2": GMAIL_CRED}
    }

def gs_lookup(name, filter_col, filter_val, position):
    return {
        "id": newid(),
        "name": name,
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": position,
        "onError": "continueRegularOutput",
        "parameters": {
            "operation": "read",
            "documentId": doc_id_ref(SS_ID),
            "sheetName": doc_id_ref(GID_CLEANERS),
            "filtersUI": {
                "values": [{"lookupColumn": filter_col, "lookupValue": filter_val}]
            },
            "options": {}
        },
        "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED}
    }

with open(PATH, encoding='utf-8') as f:
    wf = json.load(f)

C = wf['connections']

# ─────────────────────────────────────────────────────────────
# 1. HAPPY PATH: rewire Update Reservations COMPLETED chain
#    Current: Update Reservations COMPLETED → Respond Approved + Is Maintenance? + Parse Supply Items
#    New:     Update Reservations COMPLETED → Get Cleaner Profile
#                                              → Send Cleaner Checkout Email (onError: continue)
#                                              → Send Admin Checkout Email   (onError: continue)
#                                              → Respond Approved
#                                              → Is Maintenance?  (background)
#                                              → Parse Supply Items (background)
# ─────────────────────────────────────────────────────────────

n_get_profile_approved = gs_lookup(
    "Get Cleaner Profile",
    "cleanerId",
    "={{ $('Radius Check').item.json.cleanerId }}",
    [3600, -300]
)

n_send_cleaner_approved = gmail_node(
    "Send Cleaner Checkout Email",
    send_to  = "={{ $json.cleanerEmail }}",
    subject  = "=Checkout Confirmed — {{ $('Radius Check').item.json.propertyName }}",
    message  = (
        "=Hi {{ $json.cleanerName || 'there' }},\n\n"
        "Your checkout has been successfully recorded.\n\n"
        "Property: {{ $('Radius Check').item.json.propertyName }}\n"
        "Booking Reference: {{ $('Radius Check').item.json.bookingUid }}\n"
        "Checkout Time: {{ $('Radius Check').item.json.submissionTimestamp }}\n\n"
        "The job is now marked as complete. Great work!\n\n"
        "Thank you,"
    ),
    position=[3850, -300]
)

n_send_admin_approved = gmail_node(
    "Send Admin Checkout Email",
    send_to  = ADMIN_EMAIL,
    subject  = "=Job Completed — {{ $('Radius Check').item.json.propertyName }}",
    message  = (
        "=A cleaning job has been completed.\n\n"
        "Property:  {{ $('Radius Check').item.json.propertyName }}\n"
        "Booking:   {{ $('Radius Check').item.json.bookingUid }}\n"
        "Cleaner:   {{ $('Radius Check').item.json.assignedCleaner }}\n"
        "Checkout:  {{ $('Radius Check').item.json.submissionTimestamp }}\n"
        "Duration:  {{ $('Radius Check').item.json.durationMinutes }} minutes\n"
        "GPS Status: Inside allowed radius\n\n"
        "Maintenance issue reported: {{ $('Radius Check').item.json.issueReported || 'No' }}\n\n"
        "This is an automated notification."
    ),
    position=[4100, -300]
)

# Rewire: Update Reservations COMPLETED → Get Cleaner Profile (remove direct Respond Approved + maintenance/supply)
C['Update Reservations COMPLETED']['main'][0] = [
    {"node": "Get Cleaner Profile", "type": "main", "index": 0}
]

# Get Cleaner Profile → Send Cleaner Checkout Email
C["Get Cleaner Profile"] = {"main": [[{"node": "Send Cleaner Checkout Email", "type": "main", "index": 0}]]}

# Send Cleaner Checkout Email → Send Admin Checkout Email
C["Send Cleaner Checkout Email"] = {"main": [[{"node": "Send Admin Checkout Email", "type": "main", "index": 0}]]}

# Send Admin Checkout Email → Respond Approved + Is Maintenance? + Parse Supply Items
C["Send Admin Checkout Email"] = {"main": [[
    {"node": "Respond Approved",    "type": "main", "index": 0},
    {"node": "Is Maintenance?",     "type": "main", "index": 0},
    {"node": "Parse Supply Items",  "type": "main", "index": 0},
]]}

# Move Respond Approved, Is Maintenance?, Append Maintenance Ticket, Parse Supply Items, Append Supply Usage positions
pos_updates = {
    "Respond Approved":       [4350, -450],
    "Is Maintenance?":        [4350, -200],
    "Append Maintenance Ticket": [4600, -200],
    "Parse Supply Items":     [4350, -50],
    "Append Supply Usage":    [4600, -50],
}

# ─────────────────────────────────────────────────────────────
# 2. PRE-GPS REJECT PATH
#    Current: Reject Pre-GPS → Respond Pre-GPS Reject
#    New:     Reject Pre-GPS → Get Cleaner Profile (Rejected)
#                               → Send Cleaner Pre-GPS Reject Email → Respond Pre-GPS Reject
# ─────────────────────────────────────────────────────────────

n_get_profile_rejected = gs_lookup(
    "Get Cleaner Profile (Rejected)",
    "cleanerId",
    "={{ $json.cleanerId }}",
    [1600, 420]
)

n_send_cleaner_rejected = gmail_node(
    "Send Cleaner Pre-GPS Reject Email",
    send_to  = "={{ $json.cleanerEmail }}",
    subject  = "=Checkout Could Not Be Completed — {{ $('Merge Submission and Job').item.json.propertyName }}",
    message  = (
        "=Hi {{ $json.cleanerName || 'there' }},\n\n"
        "Your checkout submission could not be processed.\n\n"
        "Reason: {{ $('Reject Pre-GPS').item.json.validationMsg }}\n\n"
        "Property: {{ $('Merge Submission and Job').item.json.propertyName }}\n"
        "Booking Reference: {{ $('Merge Submission and Job').item.json.bookingUid }}\n\n"
        "Please contact your manager if you need assistance.\n\n"
        "Thank you,"
    ),
    position=[1850, 420]
)

# Rewire: Reject Pre-GPS → Get Cleaner Profile (Rejected)
C['Reject Pre-GPS']['main'][0] = [
    {"node": "Get Cleaner Profile (Rejected)", "type": "main", "index": 0}
]

C["Get Cleaner Profile (Rejected)"] = {"main": [[
    {"node": "Send Cleaner Pre-GPS Reject Email", "type": "main", "index": 0}
]]}

C["Send Cleaner Pre-GPS Reject Email"] = {"main": [[
    {"node": "Respond Pre-GPS Reject", "type": "main", "index": 0}
]]}

# ─────────────────────────────────────────────────────────────
# 3. OUTSIDE RADIUS REJECT PATH
#    Current: Reject GPS Outside → Respond Outside Radius
#    New:     Reject GPS Outside → Get Cleaner Profile (Outside)
#                                   → Send Cleaner Outside Radius Email → Respond Outside Radius
# ─────────────────────────────────────────────────────────────

n_get_profile_outside = gs_lookup(
    "Get Cleaner Profile (Outside)",
    "cleanerId",
    "={{ $json.cleanerId }}",
    [3100, 100]
)

n_send_cleaner_outside = gmail_node(
    "Send Cleaner Outside Radius Email",
    send_to  = "={{ $json.cleanerEmail }}",
    subject  = "=Checkout Rejected — Location Outside Allowed Radius",
    message  = (
        "=Hi {{ $json.cleanerName || 'there' }},\n\n"
        "Your checkout could not be accepted because your location was detected "
        "outside the allowed distance from the property.\n\n"
        "Property: {{ $('Radius Check').item.json.propertyName }}\n"
        "Booking Reference: {{ $('Radius Check').item.json.bookingUid }}\n"
        "Detected Distance: {{ $('Radius Check').item.json.distance }} metres\n\n"
        "Please move closer to the property and try again. "
        "If you believe this is an error, contact your manager.\n\n"
        "Thank you,"
    ),
    position=[3350, 100]
)

# Rewire: Reject GPS Outside → Get Cleaner Profile (Outside)
C['Reject GPS Outside']['main'][0] = [
    {"node": "Get Cleaner Profile (Outside)", "type": "main", "index": 0}
]

C["Get Cleaner Profile (Outside)"] = {"main": [[
    {"node": "Send Cleaner Outside Radius Email", "type": "main", "index": 0}
]]}

C["Send Cleaner Outside Radius Email"] = {"main": [[
    {"node": "Respond Outside Radius", "type": "main", "index": 0}
]]}

# ─────────────────────────────────────────────────────────────
# 4. Add new nodes to workflow + update positions
# ─────────────────────────────────────────────────────────────

new_nodes = [
    n_get_profile_approved,
    n_send_cleaner_approved,
    n_send_admin_approved,
    n_get_profile_rejected,
    n_send_cleaner_rejected,
    n_get_profile_outside,
    n_send_cleaner_outside,
]
wf['nodes'].extend(new_nodes)

for node in wf['nodes']:
    if node['name'] in pos_updates:
        node['position'] = pos_updates[node['name']]

with open(PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, indent=2, ensure_ascii=False)

print(f'Done. Total nodes: {len(wf["nodes"])}')
print('\nNew nodes added:')
for n in new_nodes:
    print(f'  - {n["name"]}')

print('\nConnections check:')
for src in ['Update Reservations COMPLETED','Get Cleaner Profile',
            'Send Cleaner Checkout Email','Send Admin Checkout Email',
            'Reject Pre-GPS','Get Cleaner Profile (Rejected)','Send Cleaner Pre-GPS Reject Email',
            'Reject GPS Outside','Get Cleaner Profile (Outside)','Send Cleaner Outside Radius Email']:
    for i, branch in enumerate(C.get(src, {}).get('main', [])):
        for c in branch:
            print(f'  {src} [{i}] -> {c["node"]}')
