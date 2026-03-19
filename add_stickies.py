"""
Add color-coded sticky notes above every annotated node in Workflow 1.
Colors by purpose:
  Blue   = triggers
  Yellow = data transforms / code
  Orange = decisions / branching
  Green  = sheet reads / writes
  Red    = external HTTP calls / webhooks
  Grey   = loop control / pagination
"""
import json, sys, os, uuid, urllib.request

API = "http://localhost:5678/api/v1"
KEY = os.environ.get("N8N_API_KEY", "")
WF_ID = "JKS8Imjt5Nvp1ReG"
bad_settings = {"availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"}

if not KEY:
    print("ERROR: N8N_API_KEY not set")
    sys.exit(1)

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

def pick_color(node_type, node_name):
    t = node_type.split(".")[-1]
    name_lower = node_name.lower()
    if t in ("scheduleTrigger", "googleSheetsTrigger"):
        return 1  # blue
    if t == "if" or "guard" in name_lower or "exists?" in name_lower or "needed?" in name_lower:
        return 3  # orange
    if t == "httpRequest":
        return 5  # red
    if t == "googleSheets":
        return 4  # green
    if t in ("splitInBatches", "splitOut", "noOp") or "pages" in name_lower:
        return 6  # grey
    if t == "code":
        return 2  # yellow
    return 2

color_labels = {1: "BLUE", 2: "YELLOW", 3: "ORANGE", 4: "GREEN", 5: "RED", 6: "GREY"}

# Fetch workflow
print(f"Fetching workflow {WF_ID}...")
wf = api_get(f"/workflows/{WF_ID}")
print(f"  Name: {wf['name']}")
print(f"  Nodes: {len(wf['nodes'])}")

# Remove old sticky notes we created (named "Note: ...")
original_count = len(wf["nodes"])
wf["nodes"] = [n for n in wf["nodes"]
               if not (n["type"] == "n8n-nodes-base.stickyNote"
                       and n.get("name", "").startswith("Note: "))]
removed = original_count - len(wf["nodes"])
if removed:
    print(f"  Removed {removed} old sticky notes")

# Create new sticky notes
sticky_nodes = []
for node in wf["nodes"]:
    if node["type"] == "n8n-nodes-base.stickyNote":
        continue
    notes = (node.get("notes") or "").strip()
    if not notes:
        continue

    name = node["name"]
    pos = node.get("position", [0, 0])
    color = pick_color(node["type"], name)

    sticky = {
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
    }
    sticky_nodes.append(sticky)

wf["nodes"].extend(sticky_nodes)

# Push
payload = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {k: v for k, v in wf.get("settings", {}).items() if k not in bad_settings},
}

print(f"\nPushing {len(sticky_nodes)} sticky notes...")
result = api_put(f"/workflows/{WF_ID}", payload)
print(f"OK: {result['name']}")
print(f"\nColor legend:")
for c, label in sorted(color_labels.items()):
    print(f"  {label:>6} = ", end="")
    if c == 1: print("Triggers")
    elif c == 2: print("Data transforms / code")
    elif c == 3: print("Decisions / branching")
    elif c == 4: print("Sheet reads & writes")
    elif c == 5: print("External HTTP / webhooks")
    elif c == 6: print("Loop control / pagination")

print(f"\nSticky notes added:")
for s in sticky_nodes:
    c = s["parameters"]["color"]
    print(f"  [{color_labels[c]:>6}] {s['name']}")
