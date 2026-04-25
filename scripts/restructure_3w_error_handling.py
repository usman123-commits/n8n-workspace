#!/usr/bin/env python3
"""
Restructure the merged 3W workflow:

  1. Remove short-link parsing path (React app now always sends raw lat,lng).
     - Delete: Is Short Link?, Resolve Short Link, Parse Short Link Response.
     - Connect Normalize and Check -> ParseAndValidate directly.
     - Simplify Reject If Already Approved (drop short-link source).

  2. Simplify Layer 1 error (pre-insert field validation).
     - Delete: Resolve Recipient, Basic LLM Chain, Google Gemini Chat Model,
       Extract Simplified Error, Send Error Email.
     - Wire Has Error? [error] directly to Respond Error (400)
       with a plain JSON message from $json.errorMessage.

  3. Move Respond Success to end of happy path; add terminal Respond nodes:
     - Rename Respond Success -> Respond Approved, wire after Send Aprooved Message.
     - Remove fan-out Insert Structured Row -> Respond Success (keep -> Lookup Inserted Row).
     - Add Respond Cleaner Not Assigned (403) after Reject Cleaner Not Assigned.
     - Add Respond Outside Radius (403) after Send Rejected message AND No Operation.

  4. Add Layer 2 runtime guards (alwaysOutputData + IF check empty):
     - Lookup Inserted Row -> Inserted Row Found? -> (ok: Get Booking, fail: Respond Insert Failed 500)
     - Get Booking -> Booking Found? -> (ok: Edit Fields, fail: Respond Booking Not Found 404)
     - Get Property Coordinates -> Property Found? -> (ok: Refining feilds, fail: Respond Property Missing 500)

  5. Gmail nodes: onError = continueRegularOutput (email failure must not
     block the final Respond node from firing).
"""
import json, uuid, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN  = os.path.join(ROOT, 'workflows/active/cleaning/_current_3w_merged.json')
OUT = os.path.join(ROOT, 'workflows/active/cleaning/workflow-3w-merged-clockin.json')

def new_id(): return str(uuid.uuid4())

wf = json.load(open(IN, encoding='utf-8'))

# ---------------------------------------------------------------------------
# Part 1: REMOVE nodes (short-link + Layer 1 Gemini/email machinery)
# ---------------------------------------------------------------------------
REMOVE = {
    'Is Short Link?', 'Resolve Short Link', 'Parse Short Link Response',
    'Resolve Recipient', 'Basic LLM Chain', 'Google Gemini Chat Model',
    'Extract Simplified Error', 'Send Error Email',
}
RENAME = {'Respond Success': 'Respond Approved'}

kept = []
for n in wf['nodes']:
    if n['name'] in REMOVE: continue
    if n['name'] in RENAME:
        n['name'] = RENAME[n['name']]
        if n['type'].endswith('respondToWebhook'):
            n['parameters']['responseBody'] = (
                '={\n'
                '  "status": "approved",\n'
                '  "message": "Clock-in confirmed. You are within the allowed radius. Proceed with cleaning.",\n'
                '  "bookingUid": "{{ $(\'Radius Check\').item.json.bookingUid }}"\n'
                '}'
            )
    kept.append(n)
wf['nodes'] = kept

new_conns = {}
for src, cmap in wf['connections'].items():
    if src in REMOVE: continue
    src2 = RENAME.get(src, src)
    new_cmap = {}
    for ctype, arrs in cmap.items():
        new_arrs = []
        for arr in arrs:
            new_arr = []
            for c in arr:
                if c['node'] in REMOVE: continue
                c2 = dict(c)
                if c2['node'] in RENAME:
                    c2['node'] = RENAME[c2['node']]
                new_arr.append(c2)
            new_arrs.append(new_arr)
        new_cmap[ctype] = new_arrs
    new_conns[src2] = new_cmap
wf['connections'] = new_conns

# ---------------------------------------------------------------------------
# Part 2: MODIFY existing nodes
# ---------------------------------------------------------------------------
GUARD_READS = {'Lookup Inserted Row', 'Get Booking', 'Get Property Coordinates'}

for n in wf['nodes']:
    if n['name'] == 'Normalize and Check':
        n['parameters']['jsCode'] = (
            "// Normalize field names from the React webhook payload.\n"
            "// Webhook nests POST body under $json.body — unwrap it.\n"
            "const raw = $input.first().json;\n"
            "const item = raw.body || raw;\n"
            "const captureLocation = (item.captureLocation || item['Capture Location'] || '').toString().trim();\n"
            "return [{ json: {\n"
            "  'Booking ID':       (item.bookingId       || item['Booking ID']      || '').toString().trim(),\n"
            "  'Cleaner ID':       (item.cleanerId       || item['Cleaner ID']      || '').toString().trim(),\n"
            "  'Confirm Arrival':  (item.confirmArrival  || item['Confirm Arrival'] || '').toString().trim(),\n"
            "  'Capture Location': captureLocation,\n"
            "  'submittedAt':      (item.submittedAt     || item['Timestamp']       || new Date().toISOString()),\n"
            "  captureLocation\n"
            "} }];"
        )
    if n['name'] == 'Reject If Already Approved':
        n['parameters']['jsCode'] = (
            "// Check if there's already an APPROVED row for this bookingUid.\n"
            "// If yes, short-circuit and don't insert a new one.\n"
            "const existing = $input.all();\n"
            "const parsed = $('ParseAndValidate').first().json;\n"
            "if (!parsed) throw new Error('Missing parsed submission');\n"
            "const hasApproved = existing.some(i =>\n"
            "  (i.json?.processingStatus ?? '').toString().trim() === 'APPROVED');\n"
            "if (hasApproved) return [{ json: { skipInsert: true, bookingUid: parsed.bookingUid } }];\n"
            "return [{ json: { ...parsed, skipInsert: false } }];"
        )
    if n['name'] == 'Respond Error':
        n['parameters']['responseBody'] = (
            '={\n'
            '  "status": "error",\n'
            '  "message": "{{ $json.errorMessage || \'Invalid submission\' }}"\n'
            '}'
        )
        n['parameters'].setdefault('options', {})['responseCode'] = 400
    if n['name'] == 'Respond Duplicate':
        n['parameters']['responseBody'] = (
            '={\n'
            '  "status": "duplicate",\n'
            '  "message": "Clock-in already recorded for this booking.",\n'
            '  "bookingUid": "{{ $json.bookingUid }}"\n'
            '}'
        )
    if n['type'].endswith('gmail'):
        n['onError'] = 'continueRegularOutput'
    if n['name'] in GUARD_READS:
        n['alwaysOutputData'] = True

# ---------------------------------------------------------------------------
# Part 3: ADD new Respond + IF guard nodes
# ---------------------------------------------------------------------------
def respond(name, code, body, x, y):
    return {
        'id': new_id(),
        'name': name,
        'type': 'n8n-nodes-base.respondToWebhook',
        'typeVersion': 1.1,
        'position': [x, y],
        'parameters': {
            'respondWith': 'json',
            'responseBody': body,
            'options': {'responseCode': code},
        },
    }

def if_exists(name, left_expr, x, y):
    return {
        'id': new_id(),
        'name': name,
        'type': 'n8n-nodes-base.if',
        'typeVersion': 2.2,
        'position': [x, y],
        'parameters': {
            'conditions': {
                'options': {
                    'caseSensitive': True,
                    'leftValue': '',
                    'typeValidation': 'strict',
                    'version': 1,
                },
                'conditions': [{
                    'id': new_id(),
                    'leftValue': left_expr,
                    'rightValue': '',
                    'operator': {
                        'type': 'string',
                        'operation': 'exists',
                        'singleValue': True,
                    },
                }],
                'combinator': 'and',
            },
            'options': {},
        },
    }

new_nodes = [
    if_exists('Inserted Row Found?', "={{ $json.bookingUid }}",     2280, 488),
    if_exists('Booking Found?',      "={{ $json.cleaningJobId }}",  2520, 488),
    if_exists('Property Found?',     "={{ $json.latitude }}",       3440, 680),
    respond('Respond Insert Failed', 500,
        '={\n  "status": "error",\n  "message": "Clock-in could not be saved. Please try again. If this keeps happening, contact admin."\n}',
        2280, 300),
    respond('Respond Booking Not Found', 404,
        '={\n  "status": "error",\n  "message": "Booking not found in system. Please verify the booking ID or contact admin."\n}',
        2520, 300),
    respond('Respond Property Missing', 500,
        '={\n  "status": "error",\n  "message": "Property coordinates not configured. Please contact admin."\n}',
        3440, 880),
    respond('Respond Cleaner Not Assigned', 403,
        '={\n  "status": "rejected",\n  "reason": "cleaner_mismatch",\n  "message": "You are not assigned to this booking. Please contact admin.",\n  "bookingUid": "{{ $json.bookingUid }}"\n}',
        3520, 296),
    respond('Respond Outside Radius', 403,
        '={\n  "status": "rejected",\n  "reason": "outside_radius",\n  "message": "Your location is outside the allowed 100m radius. Please move closer to the property and try again.",\n  "bookingUid": "{{ $(\'Radius Check\').item.json.bookingUid }}"\n}',
        5320, 776),
]
wf['nodes'].extend(new_nodes)

# ---------------------------------------------------------------------------
# Part 4: REWIRE connections
# ---------------------------------------------------------------------------
C = wf['connections']
def set_main(src, outs):
    C.setdefault(src, {})['main'] = outs

set_main('Normalize and Check',
         [[{'node': 'ParseAndValidate', 'type': 'main', 'index': 0}]])

set_main('ParseAndValidate',
         [[{'node': 'Has Error?', 'type': 'main', 'index': 0}]])

set_main('Has Error?', [
    [{'node': 'Respond Error', 'type': 'main', 'index': 0}],
    [{'node': 'Lookup Existing ClockIn', 'type': 'main', 'index': 0}],
])

set_main('Insert Structured Row',
         [[{'node': 'Lookup Inserted Row', 'type': 'main', 'index': 0}]])

set_main('Lookup Inserted Row',
         [[{'node': 'Inserted Row Found?', 'type': 'main', 'index': 0}]])

set_main('Inserted Row Found?', [
    [{'node': 'Get Booking', 'type': 'main', 'index': 0}],
    [{'node': 'Respond Insert Failed', 'type': 'main', 'index': 0}],
])

set_main('Get Booking',
         [[{'node': 'Booking Found?', 'type': 'main', 'index': 0}]])

set_main('Booking Found?', [
    [{'node': 'Edit Fields', 'type': 'main', 'index': 0}],
    [{'node': 'Respond Booking Not Found', 'type': 'main', 'index': 0}],
])

set_main('Get Property Coordinates',
         [[{'node': 'Property Found?', 'type': 'main', 'index': 0}]])

set_main('Property Found?', [
    [{'node': 'Refining feilds', 'type': 'main', 'index': 0}],
    [{'node': 'Respond Property Missing', 'type': 'main', 'index': 0}],
])

set_main('Reject Cleaner Not Assigned',
         [[{'node': 'Respond Cleaner Not Assigned', 'type': 'main', 'index': 0}]])

set_main('Send Aprooved Message',
         [[{'node': 'Respond Approved', 'type': 'main', 'index': 0}]])

set_main('Send Rejected message',
         [[{'node': 'Respond Outside Radius', 'type': 'main', 'index': 0}]])

set_main('No Operation, do nothing',
         [[{'node': 'Respond Outside Radius', 'type': 'main', 'index': 0}]])

# ---------------------------------------------------------------------------
# Part 5: Verify
# ---------------------------------------------------------------------------
node_names = {n['name'] for n in wf['nodes']}
for src, cmap in wf['connections'].items():
    assert src in node_names, f"connection source {src!r} missing"
    for ctype, arrs in cmap.items():
        for arr in arrs:
            for c in arr:
                assert c['node'] in node_names, f"target {c['node']!r} missing (from {src!r})"

# ---------------------------------------------------------------------------
# Part 6: Write (n8n-safe subset)
# ---------------------------------------------------------------------------
safe = {
    'name': wf['name'],
    'nodes': wf['nodes'],
    'connections': wf['connections'],
    'settings': {k: v for k, v in wf.get('settings', {}).items()
                 if k not in ['availableInMCP', 'timeSavedMode', 'callerPolicy', 'binaryMode']},
}
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(safe, f, indent=2)

print(f"Nodes total: {len(wf['nodes'])}")
print(f"Connections sources: {len(wf['connections'])}")
print(f"Removed: {len(REMOVE)} | Added: {len(new_nodes)}")
print(f"Wrote: {OUT}")
