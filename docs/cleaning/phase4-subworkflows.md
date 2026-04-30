# Phase 4 — Sub-Workflow Extraction

**Goal:** Extract reusable logic into standalone sub-workflows to reduce node counts in large workflows and ensure consistent behaviour across callers.

**Started:** 2026-05-01  
**Status:** In progress — building and testing sub-workflows. Existing workflows unchanged until approved.

---

## Decision Log — What to Extract (and What Not To)

Before building, all candidate nodes were audited across 3W (61 nodes), 4W (46 nodes), cancellationHandler (40 nodes), and Extended Checkout Handler (36 nodes).

| Candidate | Decision | Reason |
|-----------|----------|--------|
| `sw-haversine-gps-check` | **Build** | Identical haversine formula + same Properties sheet lookup duplicated in 3W and 4W |
| `sw-normalize-webhook-body` | **Skip** | 3W and 4W normalize nodes are workflow-specific (different fields, different validation rules — clock-in vs checkout) — no shared code to extract |
| `sw-send-cleaner-email` | **Skip** | Each workflow's email has different templates, fields and tone — coincidental Gmail usage, not shared logic |

---

## Sub-Workflows Built

### 1. `SW — Haversine GPS Check`

**n8n workflow ID:** `qGJzBKSxwt69YqHl`  
**File:** `workflows/drafts/cleaning/sw-haversine-gps-check.json`  
**Status:** Built and tested ✅

**Contract:**

| Direction | Fields |
|-----------|--------|
| Input | `gpsLat` (string), `gpsLng` (string), `propertyUid` (string) |
| Output | `distance` (integer, metres), `withinRadius` (boolean), `gpsLat`, `gpsLng`, `propertyLat`, `propertyLng` |

**Behaviour:**
- Looks up `latitude`/`longitude` from the **Properties** tab (gid `766791868`) by `propertyUid`
- If property not found → workflow stops, caller gets 0 items (treat as error)
- Calculates Haversine distance in metres between cleaner GPS and property GPS
- Returns `withinRadius: true` if `distance <= 100`

**Nodes (3 total):**
```
Execute Workflow Trigger
  → Get Property Coordinates  (Sheets lookup, Properties tab)
  → Calculate Distance         (Code — Haversine + withinRadius flag)
```

**Replaces in callers (when integrated):**
- 3W nodes: `Merge Coords with Submission` + `DistanceCalculation`
- 4W nodes: `Merge Coords with Submission` + `Distance Calculation`
- `Get Property Coordinates` in both callers becomes the sub-workflow call
- `Radius Check` IF node in callers can be replaced by routing on `$json.withinRadius`

**Node count reduction when integrated:**
- 3W: −3 nodes (Merge + Distance + Radius Check → 1 Execute Workflow node)
- 4W: −3 nodes (same)

---

## Test Workflow

**n8n workflow ID:** `BwnNdWgtWeLzqnkb`  
**File:** `workflows/drafts/cleaning/sw-haversine-gps-check-test.json`  
**Webhook:** `POST /webhook/test-haversine`

**Test cases:**

| # | Input | Expected |
|---|-------|----------|
| T1 | `gpsLat: 36.1644189, gpsLng: -86.659628, propertyUid: 33f964cf-...` (exact property coords) | `distance: 0, withinRadius: true` |
| T2 | `gpsLat: 36.1664189, gpsLng: -86.659628` (same property, ~222m north) | `distance: ~222, withinRadius: false` |
| T3 | `propertyUid: 00000000-0000-0000-0000-000000000000` (unknown) | workflow stops — no response body (property not found) |

**Reference property used for tests:**  
`33f964cf-2531-47f8-8133-fd501e9f6814` — 112 Hermitage House — `36.1644189, -86.659628`

---

## Integration Plan (pending user approval)

Once tests pass, the following changes will be made to existing workflows:

### 3W — Clock-In Ingestion + Validation (Merged) — `EbYPXFGOuXeDH5Cw`

Replace these nodes:
- `Get Property Coordinates` (Sheets lookup)
- `Merge Coords with Submission` (Code)
- `DistanceCalculation` (Code)
- `Radius Check` (IF)

With:
- `Call GPS Check` (Execute Workflow → `qGJzBKSxwt69YqHl`)
  - Input: pass `{ gpsLat, gpsLng, propertyUid }` from current item
  - Route downstream on `$json.withinRadius` instead of `$json.distance <= 100`

### 4W — Checkout Ingestion + Validation (Merged) — `0Pe136GvJRf26Kln`

Same replacement as 3W above.

---

## Rollout Order

1. ~~Build `sw-haversine-gps-check`~~ ✅ Done
2. ~~Create test workflow~~ ✅ Done
3. ~~Run and verify all 3 test cases~~ ✅ All passing
4. User approves → integrate into 3W
5. Test 3W clock-in happy path end-to-end
6. User approves → integrate into 4W
7. Test 4W checkout happy path end-to-end
8. Archive test workflow (`BwnNdWgtWeLzqnkb`) — delete from n8n after integration confirmed
