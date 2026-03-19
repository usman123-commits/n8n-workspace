"""
For ALL 6 workflows:
  1. Disable notesInFlow on every node (remove the text under node names)
  2. Add color-coded sticky notes above each node that has notes
  3. Skip nodes that already have a sticky (from previous runs)

Colors:
  1=blue (triggers), 2=yellow (code/transforms), 3=orange (decisions),
  4=green (sheet ops), 5=red (HTTP/webhooks), 6=grey (loop/utility)
"""
import json, sys, os, uuid, urllib.request

API = "http://localhost:5678/api/v1"
KEY = os.environ.get("N8N_API_KEY", "")
BAD = {"availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"}

if not KEY:
    print("ERROR: N8N_API_KEY not set")
    sys.exit(1)

WORKFLOW_IDS = [
    "JKS8Imjt5Nvp1ReG",  # Workflow 1
    "AU1w579al67hGom7",  # Workflow 2
    "ieebrbqVyvQwb0ig",  # Workflow 3
    "B7duBLBoOCdLpztS",  # Workflow 3B
    "BQ6uHsWxBcegrfrv",  # Cancellation Handler
    "NZNbIHz9Qutwj1fa",  # Extended Checkout Handler
]

COLOR = {1: "BLUE", 2: "YELLOW", 3: "ORANGE", 4: "GREEN", 5: "RED", 6: "GREY"}

def pick_color(node_type, node_name):
    t = node_type.split(".")[-1]
    nl = node_name.lower()
    if t in ("scheduleTrigger", "googleSheetsTrigger", "webhook"):
        return 1
    if t in ("if", "switch") or "guard" in nl or "exists?" in nl or "needed?" in nl or "found?" in nl or "available?" in nl or "check" in nl:
        return 3
    if t == "httpRequest":
        return 5
    if t in ("googleSheets", "googleCalendar", "gmail"):
        return 4
    if t in ("splitInBatches", "splitOut", "noOp") or "pages" in nl or "skip" in nl:
        return 6
    return 2

def api_get(path):
    req = urllib.request.Request(f"{API}{path}", headers={"X-N8N-API-KEY": KEY})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def api_put(path, data):
    body = json.dumps(data).encode()
    req = urllib.request.Request(f"{API}{path}", data=body, method="PUT",
                                headers={"X-N8N-API-KEY": KEY, "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

for wf_id in WORKFLOW_IDS:
    print(f"\n{'='*60}")
    print(f"Fetching {wf_id}...")
    wf = api_get(f"/workflows/{wf_id}")
    print(f"  {wf['name']}  ({len(wf['nodes'])} nodes)")

    # 1. Remove old "Note: " stickies from previous runs
    before = len(wf["nodes"])
    wf["nodes"] = [n for n in wf["nodes"]
                   if not (n["type"] == "n8n-nodes-base.stickyNote"
                           and n.get("name", "").startswith("Note: "))]
    removed = before - len(wf["nodes"])
    if removed:
        print(f"  Removed {removed} old sticky notes")

    # 2. Disable notesInFlow on all nodes + build sticky list
    stickies = []
    for node in wf["nodes"]:
        # Turn off notesInFlow
        if node.get("notesInFlow"):
            node["notesInFlow"] = False

        if node["type"] == "n8n-nodes-base.stickyNote":
            continue
        notes = (node.get("notes") or "").strip()
        if not notes:
            continue

        name = node["name"]
        pos = node.get("position", [0, 0])
        color = pick_color(node["type"], name)

        stickies.append({
            "parameters": {
                "content": f"**{name}**\n\n{notes}",
                "width": 240,
                "height": 170,
                "color": color,
            },
            "id": str(uuid.uuid4()),
            "name": f"Note: {name}",
            "type": "n8n-nodes-base.stickyNote",
            "typeVersion": 1,
            "position": [pos[0] - 25, pos[1] - 210],
        })

    wf["nodes"].extend(stickies)

    # 3. Push
    payload = {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {k: v for k, v in wf.get("settings", {}).items() if k not in BAD},
    }
    result = api_put(f"/workflows/{wf_id}", payload)
    print(f"  Added {len(stickies)} sticky notes")
    print(f"  Disabled notesInFlow on all nodes")
    print(f"  OK: {result['name']}")

    # Summary by color
    counts = {}
    for s in stickies:
        c = s["parameters"]["color"]
        counts[c] = counts.get(c, 0) + 1
    for c in sorted(counts):
        print(f"    {COLOR[c]:>6}: {counts[c]}")

print(f"\n{'='*60}")
print("All done!")
