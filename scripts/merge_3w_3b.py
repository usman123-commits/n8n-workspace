#!/usr/bin/env python3
"""
Phase 1 optimization — merge Workflow 3W (webhook ingestion) and 3B (scheduled
validation) into a single webhook-triggered workflow.

Strategy (minimal surgery to preserve behavior):
  - Keep all 3W nodes verbatim.
  - Take every 3B node EXCEPT: Schedule Trigger, Read ClockInSubmissions,
    Only PENDING, and their sticky notes.
  - Rewrite ONLY the "Merge Submission and Job" code node so it pulls the
    submission from 'Insert Structured Row' instead of 'Only PENDING'.all().
  - Fan-out "Insert Structured Row" into ['Respond Success', 'Get Booking'].
  - Shift all ported 3B nodes +1800px on X so they sit to the right of the 3W
    flow in the editor canvas.

All other 3B cross-node references like $('Radius Check').item.json are
untouched because we kept those node names intact.
"""
import json, sys, uuid, os, copy

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IN_3W = os.path.join(ROOT, 'workflows/drafts/cleaning/_fetch-3w.json')
IN_3B = os.path.join(ROOT, 'workflows/drafts/cleaning/_fetch-3b.json')
OUT   = os.path.join(ROOT, 'workflows/drafts/cleaning/workflow-3w-merged-clockin.json')

wf3w = json.load(open(IN_3W))
wf3b = json.load(open(IN_3B))

# ------------------------------------------------------------
# 1. Start from 3W.
# ------------------------------------------------------------
merged = {
    "name": "Workflow 3W – Clock-In Ingestion + Validation (Merged)",
    "nodes": copy.deepcopy(wf3w['nodes']),
    "connections": copy.deepcopy(wf3w['connections']),
    "settings": {k: v for k, v in wf3w.get('settings', {}).items()
                 if k not in ['availableInMCP', 'timeSavedMode', 'callerPolicy', 'binaryMode']},
}

# ------------------------------------------------------------
# 2. Pick 3B nodes to import.
# ------------------------------------------------------------
SKIP_3B = {'Schedule Trigger', 'Read ClockInSubmissions', 'Only PENDING',
           'Note: Schedule Trigger', 'Note: Read ClockInSubmissions', 'Note: Only PENDING'}
X_OFFSET = 1800
Y_OFFSET = 600  # push below 3W's canvas

existing_names = {n['name'] for n in merged['nodes']}
id_remap = {}  # old id -> new id, for any collisions
ported = []
for n in wf3b['nodes']:
    if n['name'] in SKIP_3B:
        continue
    nn = copy.deepcopy(n)
    # offset position
    pos = nn.get('position', [0, 0])
    nn['position'] = [pos[0] + X_OFFSET, pos[1] + Y_OFFSET]
    # ensure unique id (3B may collide with 3W)
    old_id = nn.get('id')
    if old_id:
        new_id = str(uuid.uuid4())
        id_remap[old_id] = new_id
        nn['id'] = new_id
    # ensure unique name (shouldn't clash, but be safe)
    if nn['name'] in existing_names:
        raise SystemExit(f"name collision: {nn['name']!r}")
    existing_names.add(nn['name'])
    ported.append(nn)

merged['nodes'].extend(ported)

# ------------------------------------------------------------
# 3. Rewrite the "Merge Submission and Job" code node.
#    Original read from $('Only PENDING').all() which no longer exists.
# ------------------------------------------------------------
for n in merged['nodes']:
    if n['name'] == 'Merge Submission and Job':
        n['parameters']['jsCode'] = (
            "// Single-item flow (was multi-item in 3B).\n"
            "// Submission data comes from the inserted row; job data is in $input (from Edit Fields).\n"
            "const submission = $('Insert Structured Row').first().json;\n"
            "const job = $input.first().json;\n"
            "return [{ json: { ...submission, ...job } }];\n"
        )
        break
else:
    raise SystemExit("Merge Submission and Job node missing")

# ------------------------------------------------------------
# 4. Port 3B connections — skipping anything that touches removed nodes.
# ------------------------------------------------------------
for src, cmap in wf3b['connections'].items():
    if src in SKIP_3B:
        continue
    # src node was ported; ensure entry exists
    new_entry = merged['connections'].setdefault(src, {})
    for ctype, arrs in cmap.items():
        tgt_arr_list = new_entry.setdefault(ctype, [])
        # extend lists to match
        while len(tgt_arr_list) < len(arrs):
            tgt_arr_list.append([])
        for i, arr in enumerate(arrs):
            for c in arr:
                if c['node'] in SKIP_3B:
                    continue
                # avoid duplicate
                if not any(x['node'] == c['node'] and x.get('index', 0) == c.get('index', 0)
                           for x in tgt_arr_list[i]):
                    tgt_arr_list[i].append(copy.deepcopy(c))

# ------------------------------------------------------------
# 5. Fan-out: Insert Structured Row -> [Respond Success, Get Booking].
#    3W already has Insert -> Respond Success. Add Insert -> Get Booking.
# ------------------------------------------------------------
entry = merged['connections'].setdefault('Insert Structured Row', {})
main = entry.setdefault('main', [[]])
if not main:
    main.append([])
already = {c['node'] for c in main[0]}
if 'Get Booking' not in already:
    main[0].append({'node': 'Get Booking', 'type': 'main', 'index': 0})

# ------------------------------------------------------------
# 6. Credentials for 3B nodes — already embedded in their JSON. No change.
# ------------------------------------------------------------

# ------------------------------------------------------------
# 7. Verification pass.
# ------------------------------------------------------------
node_names = {n['name'] for n in merged['nodes']}
for src, cmap in merged['connections'].items():
    assert src in node_names, f"connection source {src!r} is not a node"
    for ctype, arrs in cmap.items():
        for arr in arrs:
            for c in arr:
                assert c['node'] in node_names, f"connection target {c['node']!r} missing (from {src!r})"

print(f"Nodes total : {len(merged['nodes'])}")
print(f"Ported from 3B: {len(ported)}")
print(f"Connections sources: {len(merged['connections'])}")
with open(OUT, 'w', encoding='utf-8') as f:
    json.dump(merged, f, indent=2)
print(f"Wrote: {OUT}")
