"""
Convert the OTTO workflows from Google Sheets nodes to MongoDB nodes.

Source (latest versions): workflows/drafts/otto/new_src/*.json  (+ original/rider-pickup for the rider workflow)
Output:                   workflows/drafts/otto/mongo/*.json

Only data access changes. Business logic, node names and routing stay the same.
Collections: BotConfig, Conversation, Order, MenuItem, Handoff, pendingConfirmations, pendingCancellations.

Usage: python convert_to_mongo.py            (run from workflows/drafts/otto)
Set MONGO_CRED_ID / MONGO_CRED_NAME env vars to bake in the real n8n credential.
"""
import json, os, uuid, copy

SRC = 'new_src'
OUT = 'mongo'
CRED = {'mongoDb': {'id': os.environ.get('MONGO_CRED_ID', 'MONGO_CRED_ID'),
                    'name': os.environ.get('MONGO_CRED_NAME', 'MongoDB account')}}

# --------------------------------------------------------------------------- helpers

def load(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def node_by_name(wf, name):
    for n in wf['nodes']:
        if n['name'] == name:
            return n
    raise KeyError(name)

def mongo(name, position, operation, collection, keep=None, **params):
    """Build a MongoDB node (typeVersion 1.3). `keep` = flags copied from the replaced Sheets node."""
    p = {'operation': operation, 'collection': collection}
    p.update(params)
    n = {'parameters': p, 'id': str(uuid.uuid4()), 'name': name,
         'type': 'n8n-nodes-base.mongoDb', 'typeVersion': 1.3,
         'position': position, 'credentials': copy.deepcopy(CRED)}
    for k in ('alwaysOutputData', 'onError', 'executeOnce', 'retryOnFail'):
        if keep and k in keep:
            n[k] = keep[k]
    return n

def replace_node(wf, old_name, new_node):
    for i, n in enumerate(wf['nodes']):
        if n['name'] == old_name:
            wf['nodes'][i] = new_node
            return
    raise KeyError(old_name)

def code_node(name, position, js):
    return {'parameters': {'jsCode': js}, 'id': str(uuid.uuid4()), 'name': name,
            'type': 'n8n-nodes-base.code', 'typeVersion': 2, 'position': position}

def set_code(wf, name, js):
    node_by_name(wf, name)['parameters']['jsCode'] = js

def edit_code(wf, name, *pairs):
    """Exact-string replacements inside a Code node; fails loudly if a pattern is missing."""
    n = node_by_name(wf, name)
    js = n['parameters']['jsCode']
    for old, new in pairs:
        if old not in js:
            raise ValueError('pattern not found in %s: %r' % (name, old))
        js = js.replace(old, new)
    n['parameters']['jsCode'] = js

def insert_before(wf, target, new_node):
    """Put new_node between every predecessor of `target` and `target`."""
    conns = wf['connections']
    for src, outs in conns.items():
        for branch in outs.get('main', []):
            for c in branch:
                if c['node'] == target:
                    c['node'] = new_node['name']
    conns[new_node['name']] = {'main': [[{'node': target, 'type': 'main', 'index': 0}]]}
    wf['nodes'].append(new_node)

def below(node, dy=170):
    x, y = node['position']
    return [x, y + dy]

def q(expr_obj_js):
    """n8n expression producing a JSON query string from a JS object literal."""
    return '={{ JSON.stringify(' + expr_obj_js + ') }}'

PHONE_EXTRACT = "$('Extract Message').first().json.phone"
MAX_CTX = "parseInt($('Bot Config Map').first().json.MAX_CONTEXT_MESSAGES || '20', 10)"

# JS shared by the builders: normalise an items array into [{name, qty, price?}] with real numbers
NORMALIZE_ITEMS_JS = """function normalizeItems(raw) {
  let arr = raw;
  if (typeof arr === 'string') { try { arr = JSON.parse(arr); } catch (e) { arr = []; } }
  if (!Array.isArray(arr)) arr = [];
  return arr.filter(i => i && i.name).map(i => {
    const out = { name: String(i.name), qty: Number(i.qty || 1) };
    const price = Number(i.price);
    if (i.price !== undefined && i.price !== null && i.price !== '' && isFinite(price)) out.price = price;
    return out;
  });
}"""

# --------------------------------------------------------------------------- main bot

def convert_main():
    wf = load(os.path.join(SRC, 'WhatsApp OTTO Bot -- Baileys (Free Demo).json'))

    # --- Config: Sheet ID no longer used
    cfg = node_by_name(wf, 'Config')['parameters']['assignments']['assignments']
    cfg[:] = [a for a in cfg if a['name'] != 'SHEET_ID']

    # --- sticky note wording
    sn = node_by_name(wf, 'Setup Instructions')['parameters']
    sn['content'] = sn['content'].replace('BotConfig tab in Google Sheet', 'BotConfig collection in MongoDB')

    # --- Read Bot Config
    old = node_by_name(wf, 'Read Bot Config')
    replace_node(wf, 'Read Bot Config', mongo(
        'Read Bot Config', old['position'], 'find', 'BotConfig', keep=old, query='{}', options={}))

    # --- Check Handoff (latest handoff row for this phone)
    old = node_by_name(wf, 'Check Handoff')
    replace_node(wf, 'Check Handoff', mongo(
        'Check Handoff', old['position'], 'find', 'Handoff', keep=old,
        query=q('{ phone: $json.phone }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    edit_code(wf, 'Compute Latest Handoff Status', ('row_number: latest.row_number', '_id: String(latest._id)'))

    # --- Log Incoming + Log Outgoing -> one Conversation insert of two docs
    li = node_by_name(wf, 'Log Incoming')
    lo = node_by_name(wf, 'Log Outgoing')
    build_conv = code_node('Build Conversation Docs', [li['position'][0] - 224, li['position'][1]], """// Data sources:
//   $('Extract Message').first().json -> phone, profileName, messageBody, timestamp, sessionDate
//   $('Process Reply').first().json   -> aiReply
// Output: 2 items (user message, assistant reply) shaped like the Conversation collection.
const m = $('Extract Message').first().json;
const reply = $('Process Reply').first().json;

function toIso(ts) {
  if (typeof ts === 'number' || /^\\d+$/.test(String(ts || ''))) {
    const n = Number(ts);
    const d = new Date(n < 1e12 ? n * 1000 : n);
    if (!isNaN(d)) return d.toISOString();
  }
  const d = new Date(ts);
  return isNaN(d) ? new Date().toISOString() : d.toISOString();
}

return [
  { json: {
      phone: m.phone,
      profileName: m.profileName,
      message: m.messageBody,
      role: 'user',
      timestamp: toIso(m.timestamp),
      sessionId: m.sessionDate
  } },
  { json: {
      phone: m.phone,
      profileName: 'BOT',
      message: reply.aiReply,
      role: 'assistant',
      timestamp: new Date().toISOString(),
      sessionId: m.sessionDate
  } }
];""")
    log_conv = mongo('Log Conversation', li['position'], 'insert', 'Conversation', keep=li,
                     fields='phone,profileName,message,role,timestamp,sessionId',
                     options={'dateFields': 'timestamp'})
    # rewire: Send via Baileys -> Build Conversation Docs -> Log Conversation -> Track Spend
    wf['nodes'] = [n for n in wf['nodes'] if n['name'] not in ('Log Incoming', 'Log Outgoing')]
    wf['nodes'] += [build_conv, log_conv]
    c = wf['connections']
    c.pop('Log Incoming', None); c.pop('Log Outgoing', None)
    c['Send via Baileys'] = {'main': [[{'node': 'Build Conversation Docs', 'type': 'main', 'index': 0}]]}
    c['Build Conversation Docs'] = {'main': [[{'node': 'Log Conversation', 'type': 'main', 'index': 0}]]}
    c['Log Conversation'] = {'main': [[{'node': 'Track Spend', 'type': 'main', 'index': 0}]]}

    # --- Update Spend (upsert by key)
    old = node_by_name(wf, 'Update Spend')
    replace_node(wf, 'Update Spend', mongo(
        'Update Spend', old['position'], 'findOneAndUpdate', 'BotConfig', keep=old,
        updateKey='key', fields='key,value', upsert=True, options={}))

    # --- Append Order
    old = node_by_name(wf, 'Append Order')
    replace_node(wf, 'Append Order', mongo(
        'Append Order', old['position'], 'insert', 'Order', keep=old,
        fields='orderId,timestamp,phone,profileName,items,totalAmount,deliveryAddress,status,notes,jid',
        options={'dateFields': 'timestamp'}))
    insert_before(wf, 'Append Order', code_node('Build Order Doc', below(old, 0)[:1] + [old['position'][1] + 170], NORMALIZE_ITEMS_JS + """

// Data sources:
//   $('Extract Message').first().json -> phone, profileName, jid
//   $('Process Reply').first().json.orderData -> items, total, address (from the <<<ORDER:...>>> tag)
const m = $('Extract Message').first().json;
const od = $('Process Reply').first().json.orderData || {};
const total = Number(od.total);

return [{ json: {
  orderId: 'OTTO-' + Date.now(),
  timestamp: new Date().toISOString(),
  phone: m.phone,
  profileName: m.profileName,
  items: normalizeItems(od.items),
  totalAmount: isFinite(total) ? total : 0,
  deliveryAddress: od.address || '',
  status: 'preparing',
  notes: '',
  jid: m.jid
} }];"""))

    # --- Log Handoff
    old = node_by_name(wf, 'Log Handoff')
    replace_node(wf, 'Log Handoff', mongo(
        'Log Handoff', old['position'], 'insert', 'Handoff', keep=old,
        fields='timestamp,phone,profileName,reason,lastMessage,status',
        options={'dateFields': 'timestamp'}))
    insert_before(wf, 'Log Handoff', code_node('Build Handoff Doc', [old['position'][0], old['position'][1] + 170], """// Data sources:
//   $('Extract Message').first().json -> phone, profileName, messageBody
//   $('Process Reply').first().json.handoffData -> reason (from the <<<HANDOFF:...>>> tag)
const m = $('Extract Message').first().json;
const h = $('Process Reply').first().json.handoffData || {};

return [{ json: {
  timestamp: new Date().toISOString(),
  phone: m.phone,
  profileName: m.profileName,
  reason: h.reason || '',
  lastMessage: m.messageBody,
  status: 'active'
} }];"""))
    nh = node_by_name(wf, 'Notify Owner Handoff')['parameters']
    nh['jsonBody'] = nh['jsonBody'].replace('Change status to resolved in Handoffs sheet', 'Set status to resolved in the Handoff collection')

    # --- Pending confirmations ------------------------------------------------
    old = node_by_name(wf, 'Check Pending Confirmation')
    replace_node(wf, 'Check Pending Confirmation', mongo(
        'Check Pending Confirmation', old['position'], 'find', 'pendingConfirmations', keep=old,
        query=q('{ phone: ' + PHONE_EXTRACT + ', awaitingConfirmation: true }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    set_code(wf, 'Compute Pending Status', """const phone = $('Extract Message').first().json.phone;
const rows = $input.all().map(i => i.json).filter(r => r && r.phone);
rows.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
const row = rows[0];

if (!row) {
  return [{ json: { awaiting: false, phone } }];
}

const minutesSince = (Date.now() - new Date(row.timestamp).getTime()) / 60000;
if (!(minutesSince <= 30)) {
  return [{ json: { awaiting: false, expired: true, phone, _id: String(row._id), awaitingConfirmation: false } }];
}

return [{
  json: {
    awaiting: true,
    pendingOrderPayload: row.pendingOrderPayload || {},
    reason: row.reason || '',
    phone: row.phone,
    _id: String(row._id),
    customerMessage: $('Extract Message').first().json.messageBody
  }
}];""")

    for hist, pending_src in (('Fetch History (For Confirmation)', 'confirm'), ('Fetch History (For Cancellation)', 'cancel')):
        old = node_by_name(wf, hist)
        replace_node(wf, hist, mongo(
            hist, old['position'], 'find', 'Conversation', keep=old,
            query=q('{ phone: ' + PHONE_EXTRACT + ' }'),
            options={'sort': '{"timestamp": -1}', 'limit': '={{ ' + MAX_CTX + ' }}'}))

    HIST_OLD = """let historyLines = [];
for (const item of allItems) {
  const row = item.json;
  if (!row.message || !row.direction) continue;
  const role = row.direction === 'outgoing' ? 'Bot' : 'Customer';
  historyLines.push(role + ': ' + String(row.message));
}"""
    HIST_NEW = """let historyLines = [];
// Mongo returns newest first -> reverse to chronological order
for (const item of allItems.slice().reverse()) {
  const row = item.json;
  if (!row.message || !row.role) continue;
  const who = row.role === 'assistant' ? 'Bot' : 'Customer';
  historyLines.push(who + ': ' + String(row.message));
}"""
    edit_code(wf, 'Build Classify Input', (HIST_OLD, HIST_NEW), ('row_number: pending.row_number', '_id: pending._id'))
    edit_code(wf, 'Build Cancellation Classify Input', (HIST_OLD, HIST_NEW), ('row_number: pending.row_number', '_id: pending._id'))
    edit_code(wf, 'Parse Confirmation', ('row_number: pending.row_number,', '_id: pending._id,\n    awaitingConfirmation: false,'))

    def clear_node(name, collection):
        o = node_by_name(wf, name)
        replace_node(wf, name, mongo(name, o['position'], 'findOneAndUpdate', collection, keep=o,
                                     updateKey='_id', fields='awaitingConfirmation', upsert=False, options={}))
    for nm in ('Clear Pending Flag (Confirmed)', 'Clear Pending Flag (Not Confirmed)', 'Clear Pending Flag (Expired)'):
        clear_node(nm, 'pendingConfirmations')

    # --- Pending cancellations ------------------------------------------------
    old = node_by_name(wf, 'Check Pending Cancellation')
    replace_node(wf, 'Check Pending Cancellation', mongo(
        'Check Pending Cancellation', old['position'], 'find', 'pendingCancellations', keep=old,
        query=q('{ phone: ' + PHONE_EXTRACT + ', awaitingConfirmation: true }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    set_code(wf, 'Compute Pending Cancellation Status', """const phone = $('Extract Message').first().json.phone;
const rows = $input.all().map(i => i.json).filter(r => r && r.phone);
rows.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
const row = rows[0];

if (!row) {
  return [{ json: { awaiting: false, phone } }];
}

const minutesSince = (Date.now() - new Date(row.timestamp).getTime()) / 60000;
if (!(minutesSince <= 30)) {
  return [{ json: { awaiting: false, expired: true, phone, _id: String(row._id), awaitingConfirmation: false } }];
}

return [{
  json: {
    awaiting: true,
    orderId: row.orderId,
    items: Array.isArray(row.items) ? row.items : [],
    total: row.total,
    address: row.address,
    status: row.status,
    orderTimestamp: row.timestamp,
    phone: row.phone,
    _id: String(row._id),
    customerMessage: $('Extract Message').first().json.messageBody
  }
}];""")
    edit_code(wf, 'Parse Cancellation Confirmation',
              ('row_number: pending.row_number,', '_id: pending._id,\n    awaitingConfirmation: false,'))
    for nm in ('Clear Pending Cancellation Flag (Confirmed)', 'Clear Pending Cancellation Flag (Not Confirmed)',
               'Clear Pending Cancellation Flag (Expired)'):
        clear_node(nm, 'pendingCancellations')

    return wf, 'WhatsApp OTTO Bot -- Baileys (Free Demo).json'

# --------------------------------------------------------------------------- tool workflows

def convert_check_duplicate():
    wf = load(os.path.join(SRC, 'OTTO Tool -- Check Duplicate Order.json'))
    old = node_by_name(wf, 'Get Orders By Phone')
    replace_node(wf, 'Get Orders By Phone', mongo(
        'Get Orders By Phone', old['position'], 'find', 'Order', keep=old,
        query=q('{ phone: $json.phone }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    edit_code(wf, 'Find Duplicate',
              ("const rows = $input.all().map(i => i.json);", "const rows = $input.all().map(i => i.json).filter(r => r && r.orderId);"),
              ("try { lastItems = JSON.parse(newest.items || '[]'); } catch (e) {}",
               "lastItems = Array.isArray(newest.items) ? newest.items : [];"))

    old = node_by_name(wf, 'Save Pending Confirmation')
    replace_node(wf, 'Save Pending Confirmation', mongo(
        'Save Pending Confirmation', old['position'], 'insert', 'pendingConfirmations', keep=old,
        fields='phone,pendingOrderPayload,reason,timestamp,awaitingConfirmation,workflowName,workflowId,executionId',
        options={'dateFields': 'timestamp'}))
    insert_before(wf, 'Save Pending Confirmation', code_node('Build Pending Confirmation Doc', [old['position'][0], old['position'][1] + 170],
        NORMALIZE_ITEMS_JS + """

// Data sources:
//   $('When Executed by Another Workflow').first().json -> phone, items (JSON string), total, address
//   $('Find Duplicate').first().json -> reason
const t = $('When Executed by Another Workflow').first().json;
const total = Number(t.total);

return [{ json: {
  phone: String(t.phone),
  pendingOrderPayload: {
    items: normalizeItems(t.items),
    total: isFinite(total) ? total : String(t.total),
    address: t.address || ''
  },
  reason: $('Find Duplicate').first().json.reason,
  timestamp: new Date().toISOString(),
  awaitingConfirmation: true,
  workflowName: $workflow.name,
  workflowId: $workflow.id,
  executionId: $execution.id
} }];"""))
    return wf, 'OTTO Tool -- Check Duplicate Order.json'

def convert_check_prev_order():
    wf = load(os.path.join(SRC, 'OTTO Tool -- Check Previous Order For Cancellation.json'))
    old = node_by_name(wf, 'Read Orders By Phone')
    replace_node(wf, 'Read Orders By Phone', mongo(
        'Read Orders By Phone', old['position'], 'find', 'Order', keep=old,
        query=q('{ phone: $json.phone }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    edit_code(wf, 'Pick Most Recent Order',
              ("let items = [];\ntry { items = JSON.parse(row.items || '[]'); } catch (e) {}",
               "const items = Array.isArray(row.items) ? row.items : [];"))

    old = node_by_name(wf, 'Append Pending Cancellation Row')
    replace_node(wf, 'Append Pending Cancellation Row', mongo(
        'Append Pending Cancellation Row', old['position'], 'insert', 'pendingCancellations', keep=old,
        fields='phone,timestamp,orderId,items,total,address,status,awaitingConfirmation,workflowName,workflowId,executionId',
        options={'dateFields': 'timestamp'}))
    insert_before(wf, 'Append Pending Cancellation Row', code_node('Build Pending Cancellation Doc', [old['position'][0], old['position'][1] + 170], """// Data source: $json = output of 'Is Actionable? (status = preparing)' (pass-through of 'Pick Most Recent Order')
//   -> phone, orderId, items (array), total, address, status
const o = $json;
const total = Number(o.total);

return [{ json: {
  phone: String(o.phone),
  orderId: o.orderId,
  items: o.items,
  total: isFinite(total) ? total : String(o.total),
  address: o.address || '',
  status: o.status,
  timestamp: new Date().toISOString(),
  awaitingConfirmation: true,
  workflowName: $workflow.name,
  workflowId: $workflow.id,
  executionId: $execution.id
} }];"""))
    return wf, 'OTTO Tool -- Check Previous Order For Cancellation.json'

def convert_check_status():
    wf = load(os.path.join(SRC, 'OTTO Tool -- Check Order Status.json'))
    old = node_by_name(wf, 'Fetch Orders')
    replace_node(wf, 'Fetch Orders', mongo(
        'Fetch Orders', old['position'], 'find', 'Order', keep=old,
        query=q('{ phone: $json.query }'),
        options={'sort': '{"timestamp": -1}', 'limit': 1}))
    edit_code(wf, 'Format Order Status',
              ("const latest = valid[valid.length - 1].json;", "const latest = valid[0].json; // newest first (sorted in the Mongo query)"),
              ("Items: ${latest.items}", "Items: ${JSON.stringify(latest.items)}"))
    return wf, 'OTTO Tool -- Check Order Status.json'

def convert_get_menu():
    wf = load(os.path.join(SRC, 'OTTO Tool -- Get Menu.json'))
    old = node_by_name(wf, 'Fetch Menu')
    replace_node(wf, 'Fetch Menu', mongo(
        'Fetch Menu', old['position'], 'find', 'MenuItem', keep=old,
        query='{"available": true}', options={}))
    return wf, 'OTTO Tool -- Get Menu.json'

# --------------------------------------------------------------------------- rider pickup

def convert_rider():
    wf = load(os.path.join('original', 'rider-pickup.8tKYsQHImhE1wpbQ.json'))
    cfg = node_by_name(wf, 'Config')['parameters']['assignments']['assignments']
    cfg[:] = [a for a in cfg if a['name'] != 'SHEET_ID']

    note = node_by_name(wf, 'Setup Notes')['parameters']
    note['content'] = ('## OTTO -- Rider Pickup Notification\n\n'
                       'Polls the Order collection (MongoDB) every minute. When status = "on_the_way" and riderNotified is not yet true, '
                       'sends a WhatsApp message via the bridge and marks the order as notified so it never fires twice.\n\n'
                       '**Requires:**\n- Order documents must have a `jid` field (set by the main bot when the order is placed). '
                       'Orders without a jid cannot be notified.\n- Staff must set status to exactly "on_the_way" when handing the order to a rider.')

    old = node_by_name(wf, 'Read All Orders')
    replace_node(wf, 'Read All Orders', mongo(
        'Read All Orders', old['position'], 'find', 'Order', keep=old,
        query='{"status": "on_the_way", "riderNotified": {"$ne": true}}', options={}))
    edit_code(wf, 'Find Newly On-The-Way Orders',
              ("// Case-insensitive, contains-match on status so small staff typos in casing\n"
               "// (\"On The Way\", \"ON THE WAY\") still match -- exact-match sheet filtering\n"
               "// would silently miss those.\n",
               "// Status is an enum in Mongo (on_the_way); the query already filters it, this is a safety net.\n"),
              ("const notYetNotified = (r) => String(r.riderNotified || '').toLowerCase() !== 'true';",
               "const notYetNotified = (r) => r.riderNotified !== true;"))
    edit_code(wf, 'Build Rider Message',
              ("  let orderItems = [];\n  try { orderItems = JSON.parse(row.items || '[]'); } catch (e) {}",
               "  const orderItems = Array.isArray(row.items) ? row.items : [];"),
              ("row_number: row.row_number,", "_id: String(row._id),"))

    old = node_by_name(wf, 'Mark Rider Notified')
    replace_node(wf, 'Mark Rider Notified', mongo(
        'Mark Rider Notified', old['position'], 'findOneAndUpdate', 'Order', keep=old,
        updateKey='_id', fields='riderNotified', upsert=False, options={}))
    insert_before(wf, 'Mark Rider Notified', code_node('Build Rider Notified Update', [old['position'][0], old['position'][1] + 170],
        """// The HTTP node output has no order data, so rebuild one update item per order from 'Build Rider Message'.
return $('Build Rider Message').all().map(i => ({ json: { _id: i.json._id, riderNotified: true } }));"""))
    return wf, 'OTTO -- Rider Pickup Notification.json'

# --------------------------------------------------------------------------- run

def finalize(wf):
    # keep only fields the n8n public API accepts on create/update, plus identity for local tracking
    return {'name': wf['name'], 'nodes': wf['nodes'], 'connections': wf['connections'],
            'settings': {k: v for k, v in wf.get('settings', {}).items()
                         if k not in ('availableInMCP', 'timeSavedMode', 'callerPolicy', 'binaryMode')}}

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    for fn in (convert_main, convert_check_duplicate, convert_check_prev_order,
               convert_check_status, convert_get_menu, convert_rider):
        wf, fname = fn()
        left = [n['name'] for n in wf['nodes'] if n['type'] == 'n8n-nodes-base.googleSheets']
        assert not left, 'Sheets nodes left in %s: %s' % (fname, left)
        with open(os.path.join(OUT, fname), 'w', encoding='utf-8') as f:
            json.dump(finalize(wf), f, indent=2, ensure_ascii=False)
        print('wrote', fname, '-', len(wf['nodes']), 'nodes')
