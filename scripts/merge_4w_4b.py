"""
Merge Workflow 4W (Checkout Ingestion Webhook) + 4B (Checkout Validation Processor)
into a single webhook-triggered workflow with merged response contract.

Lessons baked in from 3W+3B merge:
  - No short-link path (React app sends raw lat,lng)
  - No Gemini LLM error chain (direct Respond Error)
  - Respond nodes at end of validation chain (best UX)
  - Layer 2 IF guards on Lookup Inserted Row, Get Booking, Get Property Coordinates
  - All Sheets nodes: mode="id" with numeric gid
  - Lookup Inserted Row intermediate step (gets row_number for later updates)
  - Gmail nodes: onError=continueRegularOutput   (no Gmail in 4 chain, but pattern preserved)
  - alwaysOutputData=true on guarded reads
  - Maintenance + Supply fan-out preserved (logged at insert time, regardless of GPS outcome)

Output: workflows/active/cleaning/workflow-4w-merged-checkout.json
"""
import json, uuid, copy, sys

ROOT = 'C:/folderF/n8n-workspace'
SRC_4W = f'{ROOT}/workflows/drafts/cleaning/_fetch-4w.json'
SRC_4B = f'{ROOT}/workflows/drafts/cleaning/_fetch-4b.json'
OUT    = f'{ROOT}/workflows/active/cleaning/workflow-4w-merged-checkout.json'

SS_ID = '1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw'
GID = {
    'CheckoutSubmissions': '1292187736',
    'CleaningJobs':        '2047086003',
    'Reservations':         '569949670',
    'Properties':           '766791868',
    'MaintenanceTickets':   '569911294',
    'SupplyUsageLog':       '469288724',
}
SHEETS_CRED = {"id": "q52dbWoN6OaKRDZO", "name": "Google Sheets account"}

def newid():
    return str(uuid.uuid4())

def load(p):
    with open(p, encoding='utf-8') as fp:
        return json.load(fp)

w4w = load(SRC_4W)
w4b = load(SRC_4B)

def find(wf, name):
    for n in wf['nodes']:
        if n['name'] == name:
            return copy.deepcopy(n)
    raise KeyError(name)

# ----------------------------------------------------------------------------
# 1. Take baseline nodes (preserved as-is, possibly with small param tweaks)
# ----------------------------------------------------------------------------

def doc_id_ref(value):
    return {"__rl": True, "value": value, "mode": "id"}

def gs_creds(node):
    """Ensure Google Sheets credential is set."""
    node.setdefault('credentials', {})
    node['credentials']['googleSheetsOAuth2Api'] = SHEETS_CRED
    return node

def force_sheet_id(node, gid):
    """Force sheetName to mode=id with numeric gid."""
    p = node['parameters']
    p['sheetName'] = doc_id_ref(gid)
    p['documentId'] = doc_id_ref(SS_ID)
    return node

# ===== from 4W =====
n_webhook   = find(w4w, 'Webhook')
n_normalize = find(w4w, 'Normalize and Check')
n_parse     = find(w4w, 'ParseAndValidate')
n_haserr    = find(w4w, 'Has Error?')
n_respond_error = find(w4w, 'Respond Error')

n_lookup_existing = gs_creds(force_sheet_id(find(w4w, 'Lookup Existing Checkout'),
                                            GID['CheckoutSubmissions']))
n_lookup_existing['parameters']['alwaysOutputData'] = True

n_reject_if_approved = find(w4w, 'Reject If Already Approved')
# Simplify: drop short-link path; only read from ParseAndValidate
n_reject_if_approved['parameters']['jsCode'] = (
    "const existing = $input.all();\n"
    "const parsed = $('ParseAndValidate').first().json;\n"
    "if (!parsed || parsed.hasError) throw new Error('Missing parsed submission');\n"
    "const hasApproved = existing.some(i => (i.json?.processingStatus ?? '').toString().trim() === 'APPROVED');\n"
    "if (hasApproved) return [{ json: { skipInsert: true, bookingUid: parsed.bookingUid } }];\n"
    "return [{ json: { ...parsed, skipInsert: false } }];"
)

n_should_insert = find(w4w, 'Should Insert?')
n_insert        = gs_creds(force_sheet_id(find(w4w, 'Insert into CheckoutSubmissions'),
                                          GID['CheckoutSubmissions']))
n_respond_dup   = find(w4w, 'Respond Duplicate')
# Update Respond Duplicate body to match 3W contract style (status:"duplicate")
n_respond_dup['parameters']['responseBody'] = (
    '={\n'
    '  "status": "duplicate",\n'
    '  "message": "Checkout already recorded for this booking.",\n'
    '  "bookingUid": "{{ $json.bookingUid }}"\n'
    '}'
)

n_is_maint      = find(w4w, 'Is Maintenance?')
n_append_maint  = gs_creds(force_sheet_id(find(w4w, 'Append Maintenance Ticket'),
                                          GID['MaintenanceTickets']))
n_parse_supply  = find(w4w, 'Parse Supply Items')
n_append_supply = gs_creds(force_sheet_id(find(w4w, 'Append Supply Usage'),
                                          GID['SupplyUsageLog']))

# ===== from 4B (the validation chain) =====
n_get_booking   = gs_creds(force_sheet_id(find(w4b, 'Get Booking'), GID['CleaningJobs']))
n_get_booking['parameters']['alwaysOutputData'] = True

n_merge_sub_job = find(w4b, 'Merge Submission and Job')
# Rewire merge: instead of pulling from 'Only PENDING' (no longer exists),
# pull from 'Lookup Inserted Row' (the upstream row we just inserted).
n_merge_sub_job['parameters']['jsCode'] = (
    "// Merge inserted-row submission with its CleaningJobs row, by position.\n"
    "const submissionItems = $('Lookup Inserted Row').all();\n"
    "const jobItems = $input.all();\n"
    "return jobItems.map((jobItem, i) => {\n"
    "  const submission = submissionItems[i]?.json || {};\n"
    "  const job = jobItem.json || {};\n"
    "  return { json: { ...submission, ...job } };\n"
    "});"
)

n_validate_pregps = find(w4b, 'Validate Pre-GPS')
# Extend to emit validationReason for cleaner Respond contract
n_validate_pregps['parameters']['jsCode'] = (
    "// Run all pre-GPS validations: cleaner match, clock-in status, duration min/max.\n"
    "const items = $input.all();\n"
    "return items.map(item => {\n"
    "  const j = item.json || {};\n"
    "  const cleanerFromForm = (j.cleanerIdFromForm ?? '').toString().trim();\n"
    "  const assignedCleaner = (j.cleanerId ?? '').toString().trim();\n"
    "  if (!cleanerFromForm || !assignedCleaner || cleanerFromForm !== assignedCleaner) {\n"
    "    return { json: { ...j, validationPass: 'FAIL', validationReason: 'cleaner_mismatch', validationMsg: 'You are not assigned to this booking. Please contact admin.' } };\n"
    "  }\n"
    "  const jobStatus = (j.status ?? '').toString().trim();\n"
    "  if (jobStatus !== 'IN_PROGRESS') {\n"
    "    return { json: { ...j, validationPass: 'FAIL', validationReason: 'not_clocked_in', validationMsg: 'No approved clock-in found for this booking. Please clock in first.' } };\n"
    "  }\n"
    "  const clockInTime = j.clockInTimeUTC ? new Date(j.clockInTimeUTC) : null;\n"
    "  const checkoutTime = j.submissionTimestamp ? new Date(j.submissionTimestamp) : null;\n"
    "  if (!clockInTime || isNaN(clockInTime.getTime()) || !checkoutTime || isNaN(checkoutTime.getTime())) {\n"
    "    return { json: { ...j, validationPass: 'FAIL', validationReason: 'invalid_timestamp', validationMsg: 'Invalid timestamp \\u2014 cannot calculate duration.' } };\n"
    "  }\n"
    "  const durationMin = Math.round((checkoutTime.getTime() - clockInTime.getTime()) / 60000);\n"
    "  if (durationMin < 30) {\n"
    "    return { json: { ...j, validationPass: 'FAIL', validationReason: 'too_soon', validationMsg: 'Checkout too soon (' + durationMin + ' min after clock-in). Minimum is 30 minutes.', durationMinutes: durationMin } };\n"
    "  }\n"
    "  if (durationMin > 360) {\n"
    "    const durationHrs = (durationMin / 60).toFixed(1);\n"
    "    return { json: { ...j, validationPass: 'FAIL', validationReason: 'too_late', validationMsg: 'Checkout too late (' + durationHrs + ' hrs after clock-in). Maximum is 6 hours.', durationMinutes: durationMin } };\n"
    "  }\n"
    "  return { json: { ...j, validationPass: 'PASS', validationReason: 'ok', validationMsg: 'Pre-GPS checks passed', durationMinutes: durationMin } };\n"
    "});"
)

n_pregps_check = find(w4b, 'Pre-GPS Check')
n_reject_pregps = gs_creds(force_sheet_id(find(w4b, 'Reject Pre-GPS'),
                                          GID['CheckoutSubmissions']))
# Switch matching to row_number for safety
n_reject_pregps['parameters']['columns']['matchingColumns'] = ['row_number']
n_reject_pregps['parameters']['columns']['value'] = {
    "row_number": "={{ $json.row_number }}",
    "processingStatus": "REJECTED",
    "resultMessage": "={{ $json.validationMsg }}",
    "processedAt": "={{ $now.toISO() }}"
}

n_pass_validated = find(w4b, 'Pass Validated Items')

n_get_coords = gs_creds(force_sheet_id(find(w4b, 'Get Property Coordinates'),
                                       GID['Properties']))
n_get_coords['parameters']['alwaysOutputData'] = True

n_merge_coords = find(w4b, 'Merge Coords with Submission')
n_distance     = find(w4b, 'Distance Calculation')
n_radius_check = find(w4b, 'Radius Check')
n_reject_outside = gs_creds(force_sheet_id(find(w4b, 'Reject GPS Outside'),
                                           GID['CheckoutSubmissions']))
n_update_approved = gs_creds(force_sheet_id(find(w4b, 'Update CheckoutSubmissions APPROVED'),
                                            GID['CheckoutSubmissions']))
n_update_jobs = gs_creds(force_sheet_id(find(w4b, 'Update CleaningJobs COMPLETED'),
                                        GID['CleaningJobs']))
# Fix stale $('Read CheckoutSubmissions') refs in 4B; pull from $json (carries through the chain)
n_update_jobs['parameters']['columns']['value'] = {
    "bookingUid": "={{ $json.bookingUid }}",
    "status": "COMPLETED",
    "clockOut": "={{ $json.submissionTimestamp }}",
    "gpsStatus": "INSIDE_RADIUS",
    "clockOutTimeUTC": "={{ $json.submissionTimestamp }}",
    "gpsClockOutLat": "={{ $json.gpsLat }}",
    "gpsClockOutLng": "={{ $json.gpsLng }}"
}

n_update_resv = gs_creds(force_sheet_id(find(w4b, 'Update Reservations COMPLETED'),
                                        GID['Reservations']))

# ----------------------------------------------------------------------------
# 2. Build NEW nodes: Lookup Inserted Row + 4 Layer-2 guard IFs + 5 Respond nodes
# ----------------------------------------------------------------------------

def make_lookup_inserted():
    return {
        "id": newid(),
        "name": "Lookup Inserted Row",
        "type": "n8n-nodes-base.googleSheets",
        "typeVersion": 4.5,
        "position": [0, 0],
        "parameters": {
            "operation": "read",
            "documentId": doc_id_ref(SS_ID),
            "sheetName": doc_id_ref(GID['CheckoutSubmissions']),
            "filtersUI": {
                "values": [
                    {"lookupColumn": "bookingUid", "lookupValue": "={{ $('Reject If Already Approved').first().json.bookingUid }}"},
                    {"lookupColumn": "submissionTimestamp", "lookupValue": "={{ $('Reject If Already Approved').first().json.submissionTimestamp }}"}
                ]
            },
            "options": {},
            "alwaysOutputData": True,
        },
        "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    }

def make_if_exists(name, field):
    return {
        "id": newid(),
        "name": name,
        "type": "n8n-nodes-base.if",
        "typeVersion": 2.2,
        "position": [0, 0],
        "parameters": {
            "conditions": {
                "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "loose", "version": 2},
                "conditions": [{
                    "id": newid(),
                    "leftValue": f"={{{{ $json.{field} }}}}",
                    "rightValue": "",
                    "operator": {"type": "string", "operation": "exists", "singleValue": True}
                }],
                "combinator": "and"
            },
            "options": {}
        }
    }

def respond_node(name, status_code, body):
    return {
        "id": newid(),
        "name": name,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.5,
        "position": [0, 0],
        "parameters": {
            "respondWith": "json",
            "responseBody": body,
            "options": {"responseCode": status_code}
        }
    }

n_lookup_inserted    = make_lookup_inserted()
n_if_inserted_found  = make_if_exists("Inserted Row Found?",  "row_number")
n_if_booking_found   = make_if_exists("Booking Found?",       "cleanerId")
n_if_property_found  = make_if_exists("Property Found?",      "latitude")

n_respond_approved = respond_node("Respond Approved", 200,
    '={\n  "status": "approved",\n  "message": "Checkout confirmed. Job marked complete.",\n  "bookingUid": "{{ $json.bookingUid }}"\n}')

n_respond_pregps_reject = respond_node("Respond Pre-GPS Reject", 403,
    '={\n  "status": "rejected",\n  "reason": "{{ $json.validationReason }}",\n  "message": "{{ $json.validationMsg }}",\n  "bookingUid": "{{ $json.bookingUid }}"\n}')

n_respond_outside = respond_node("Respond Outside Radius", 403,
    '={\n  "status": "rejected",\n  "reason": "outside_radius",\n  "message": "Your location is outside the allowed 100m radius. Please move closer to the property and try again.",\n  "bookingUid": "{{ $json.bookingUid }}"\n}')

n_respond_insert_failed = respond_node("Respond Insert Failed", 500,
    '={\n  "status": "error",\n  "message": "Checkout could not be saved. Please try again. If this keeps happening, contact admin."\n}')

n_respond_booking_404 = respond_node("Respond Booking Not Found", 404,
    '={\n  "status": "error",\n  "message": "Booking not found in system. Please verify the booking ID or contact admin."\n}')

n_respond_property_500 = respond_node("Respond Property Missing", 500,
    '={\n  "status": "error",\n  "message": "Property coordinates not configured. Please contact admin."\n}')

# Tweak Respond Error to match 3W contract (already does, just verify code is 400)
n_respond_error['parameters']['options']['responseCode'] = 400
n_respond_error['parameters']['responseBody'] = (
    '={\n'
    '  "status": "error",\n'
    '  "message": "{{ $json.errorMessage || \'Unknown error\' }}"\n'
    '}'
)

# ----------------------------------------------------------------------------
# 3. Layout (left-to-right)
# ----------------------------------------------------------------------------
LAYOUT = [
    # row 1 - main spine
    [(-2400, 200, n_webhook),
     (-2150, 200, n_normalize),
     (-1900, 200, n_parse),
     (-1650, 200, n_haserr),
     (-1400, 350, n_respond_error),
     (-1400, 100, n_lookup_existing),
     (-1150, 100, n_reject_if_approved),
     ( -900, 100, n_should_insert),
     ( -650, 250, n_respond_dup),
     ( -650,   0, n_insert),
     ( -400, 100, n_lookup_inserted),
     ( -150, 100, n_if_inserted_found),
     (  100, 250, n_respond_insert_failed),
     (  100,   0, n_get_booking),
     (  350,   0, n_if_booking_found),
     (  600, 250, n_respond_booking_404),
     (  600,   0, n_merge_sub_job),
     (  850,   0, n_validate_pregps),
     ( 1100,   0, n_pregps_check),
     ( 1350, 250, n_reject_pregps),
     ( 1600, 250, n_respond_pregps_reject),
     ( 1350, -100, n_pass_validated),
     ( 1600, -100, n_get_coords),
     ( 1850, -100, n_if_property_found),
     ( 2100, 100, n_respond_property_500),
     ( 2100, -200, n_merge_coords),
     ( 2350, -200, n_distance),
     ( 2600, -200, n_radius_check),
     ( 2850, -50, n_reject_outside),
     ( 3100, -50, n_respond_outside),
     ( 2850, -300, n_update_approved),
     ( 3100, -300, n_update_jobs),
     ( 3350, -300, n_update_resv),
     ( 3600, -300, n_respond_approved),
     # branch B/C: maintenance + supplies fan-out from Insert
     ( -400, -150, n_is_maint),
     ( -150, -150, n_append_maint),
     ( -400, -300, n_parse_supply),
     ( -150, -300, n_append_supply),
    ],
]

nodes = []
for row in LAYOUT:
    for x, y, n in row:
        n['position'] = [x, y]
        nodes.append(n)

# ----------------------------------------------------------------------------
# 4. Connections
# ----------------------------------------------------------------------------
def link(c, src, dst, src_idx=0):
    c.setdefault(src, {"main": []})
    while len(c[src]['main']) <= src_idx:
        c[src]['main'].append([])
    c[src]['main'][src_idx].append({"node": dst, "type": "main", "index": 0})

C = {}
link(C, "Webhook", "Normalize and Check")
link(C, "Normalize and Check", "ParseAndValidate")
link(C, "ParseAndValidate", "Has Error?")
link(C, "Has Error?", "Respond Error", src_idx=0)            # error path
link(C, "Has Error?", "Lookup Existing Checkout", src_idx=1) # ok path
link(C, "Lookup Existing Checkout", "Reject If Already Approved")
link(C, "Reject If Already Approved", "Should Insert?")
link(C, "Should Insert?", "Insert into CheckoutSubmissions", src_idx=0)
link(C, "Should Insert?", "Respond Duplicate", src_idx=1)

# Insert fan-out: validation chain + maintenance + supplies
link(C, "Insert into CheckoutSubmissions", "Lookup Inserted Row")
link(C, "Insert into CheckoutSubmissions", "Is Maintenance?")
link(C, "Insert into CheckoutSubmissions", "Parse Supply Items")
link(C, "Is Maintenance?", "Append Maintenance Ticket", src_idx=0)
link(C, "Parse Supply Items", "Append Supply Usage")

# Validation chain
link(C, "Lookup Inserted Row", "Inserted Row Found?")
link(C, "Inserted Row Found?", "Get Booking", src_idx=0)
link(C, "Inserted Row Found?", "Respond Insert Failed", src_idx=1)
link(C, "Get Booking", "Booking Found?")
link(C, "Booking Found?", "Merge Submission and Job", src_idx=0)
link(C, "Booking Found?", "Respond Booking Not Found", src_idx=1)
link(C, "Merge Submission and Job", "Validate Pre-GPS")
link(C, "Validate Pre-GPS", "Pre-GPS Check")
link(C, "Pre-GPS Check", "Pass Validated Items", src_idx=0)
link(C, "Pre-GPS Check", "Reject Pre-GPS", src_idx=1)
link(C, "Reject Pre-GPS", "Respond Pre-GPS Reject")
link(C, "Pass Validated Items", "Get Property Coordinates")
link(C, "Get Property Coordinates", "Property Found?")
link(C, "Property Found?", "Merge Coords with Submission", src_idx=0)
link(C, "Property Found?", "Respond Property Missing", src_idx=1)
link(C, "Merge Coords with Submission", "Distance Calculation")
link(C, "Distance Calculation", "Radius Check")
link(C, "Radius Check", "Update CheckoutSubmissions APPROVED", src_idx=0)
link(C, "Radius Check", "Reject GPS Outside", src_idx=1)
link(C, "Reject GPS Outside", "Respond Outside Radius")
link(C, "Update CheckoutSubmissions APPROVED", "Update CleaningJobs COMPLETED")
link(C, "Update CleaningJobs COMPLETED", "Update Reservations COMPLETED")
link(C, "Update Reservations COMPLETED", "Respond Approved")

# ----------------------------------------------------------------------------
# 5. Sticky Note
# ----------------------------------------------------------------------------
sticky = {
    "id": newid(),
    "name": "Sticky Note",
    "type": "n8n-nodes-base.stickyNote",
    "typeVersion": 1,
    "position": [-2400, -200],
    "parameters": {
        "content": (
            "## Workflow 4W — Checkout Ingestion + Validation (Merged)\n"
            "Webhook: POST /webhook/checkout\n\n"
            "Replaces old 4W + 4B. Single sync request/response.\n"
            "Response contract mirrors 3W:\n"
            " 200 approved | 200 duplicate | 400 error | 403 rejected (pre-GPS or radius) | 404 not found | 500 insert/property fail\n"
            "Maintenance + Supply logs fan out from Insert (logged regardless of GPS outcome)."
        ),
        "height": 240,
        "width": 520
    }
}
nodes.append(sticky)

# ----------------------------------------------------------------------------
# 6. Workflow envelope (PUT-safe: only name/nodes/connections/settings)
# ----------------------------------------------------------------------------
out = {
    "name": "Workflow 4W — Checkout Ingestion + Validation (Merged)",
    "nodes": nodes,
    "connections": C,
    "settings": {"executionOrder": "v1"}
}

with open(OUT, 'w', encoding='utf-8') as fp:
    json.dump(out, fp, indent=2, ensure_ascii=False)

print(f'Wrote: {OUT}')
print(f'Total nodes: {len(nodes)}')
for n in nodes:
    print(f'  - {n["name"]}')
