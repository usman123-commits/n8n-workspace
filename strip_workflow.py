import json, sys

with open(sys.argv[1], encoding="utf-8") as f:
    wf = json.load(f)

safe = {
    "name": wf["name"],
    "nodes": wf["nodes"],
    "connections": wf["connections"],
    "settings": {
        k: v for k, v in wf.get("settings", {}).items()
        if k not in ["availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"]
    }
}

print(json.dumps(safe))
