import json, uuid, os

def uid():
    return str(uuid.uuid4())

SPREADSHEET_ID  = "1q6LUdIogNrE6krKhA0HcK9iWT7yaV5MiWDeAFEkl6kw"
RESERVATIONS_GID = "569949670"
CLEANING_JOBS_GID = "2047086003"
AGENCY_UID      = "35842d2f-b5c1-46fa-a33d-a12756b42ed8"
HOSTFULLY_CRED  = {"id": "9KxNwfaP8qRHdRPm", "name": "Hostfully API"}
SHEETS_CRED     = {"id": "q52dbWoN6OaKRDZO", "name": "Google Sheets account"}
CLOUD_BASE      = "https://n8n.srv1566844.hstgr.cloud"

def doc():
    return {"__rl": True, "value": SPREADSHEET_ID, "mode": "id"}

def tab(gid):
    return {"__rl": True, "value": gid, "mode": "id"}

# ── Node IDs ──────────────────────────────────────────────────
IDS = {k: uid() for k in [
    "webhook", "respond200", "agency_check", "fetch_lead",
    "route_event",
    # NEW_BOOKING path
    "lookup_res", "res_exists", "create_res",
    "prep_job", "create_job", "update_res_jobid",
    # BOOKING_UPDATED path
    "is_cancelled",
    "lookup_cancel", "cancel_guard", "trigger_cancel",
    "prep_candidate", "lookup_candidate", "res_guard", "trigger_extended",
]}

# ── Positions (x, y) ─────────────────────────────────────────
P = {
    "webhook":        [0,    200],
    "respond200":     [280,  200],
    "agency_check":   [560,  200],
    "fetch_lead":     [840,  200],
    "route_event":    [1120, 200],
    # NEW_BOOKING (top branch, y=0)
    "lookup_res":     [1400,  -60],
    "res_exists":     [1680,  -60],
    "create_res":     [1960,  -60],
    "prep_job":       [2240,  -60],
    "create_job":     [2520,  -60],
    "update_res_jobid":[2800, -60],
    # BOOKING_UPDATED (bottom branch)
    "is_cancelled":   [1400, 460],
    # cancellation sub-branch
    "lookup_cancel":  [1680, 340],
    "cancel_guard":   [1960, 340],
    "trigger_cancel": [2240, 340],
    # extended checkout sub-branch
    "prep_candidate": [1680, 580],
    "lookup_candidate":[1960, 580],
    "res_guard":      [2240, 580],
    "trigger_extended":[2520, 580],
}

NODES = []

# ─────────────────────────────────────────────────────────────
# 1. Webhook
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["webhook"],
    "name": "Webhook",
    "type": "n8n-nodes-base.webhook",
    "typeVersion": 2,
    "position": P["webhook"],
    "webhookId": "hf-booking-event-v2",
    "parameters": {
        "path": "hostfully-booking-event",
        "httpMethod": "POST",
        "responseMode": "responseNode",
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 2. Respond 200 immediately (Hostfully retries on non-2xx)
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["respond200"],
    "name": "Respond 200",
    "type": "n8n-nodes-base.respondToWebhook",
    "typeVersion": 1,
    "position": P["respond200"],
    "parameters": {
        "respondWith": "json",
        "responseBody": '{"received":true}',
        "options": {"responseCode": 200}
    }
})

# ─────────────────────────────────────────────────────────────
# 3. Agency Check — drop events not from our agency
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["agency_check"],
    "name": "Agency Check",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": P["agency_check"],
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "agency-uid-check",
                "leftValue": "={{ $json.body.agency_uid }}",
                "rightValue": AGENCY_UID,
                "operator": {"type": "string", "operation": "equals"}
            }],
            "combinator": "and"
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 4. Fetch Lead by UID — get full booking from Hostfully API
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["fetch_lead"],
    "name": "Fetch Lead by UID",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": P["fetch_lead"],
    "credentials": {"httpHeaderAuth": HOSTFULLY_CRED},
    "parameters": {
        "method": "GET",
        "url": "=https://platform.hostfully.com/api/v3/leads/{{ $json.body.lead_uid }}",
        "authentication": "predefinedCredentialType",
        "nodeCredentialType": "httpHeaderAuth",
        "sendQuery": True,
        "queryParameters": {
            "parameters": [{"name": "agencyUid", "value": AGENCY_UID}]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 5. Route on Event Type (Switch)
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["route_event"],
    "name": "Route on Event Type",
    "type": "n8n-nodes-base.switch",
    "typeVersion": 3,
    "position": P["route_event"],
    "parameters": {
        "mode": "rules",
        "rules": {
            "values": [
                {
                    "conditions": {
                        "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                        "conditions": [{
                            "id": "route-new",
                            "leftValue": "={{ $('Webhook').first().json.body.event_type }}",
                            "rightValue": "NEW_BOOKING",
                            "operator": {"type": "string", "operation": "equals"}
                        }],
                        "combinator": "and"
                    },
                    "renameOutput": True,
                    "outputKey": "NEW_BOOKING"
                },
                {
                    "conditions": {
                        "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
                        "conditions": [{
                            "id": "route-updated",
                            "leftValue": "={{ $('Webhook').first().json.body.event_type }}",
                            "rightValue": "BOOKING_UPDATED",
                            "operator": {"type": "string", "operation": "equals"}
                        }],
                        "combinator": "and"
                    },
                    "renameOutput": True,
                    "outputKey": "BOOKING_UPDATED"
                }
            ]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 6. Lookup Reservation (dup check for NEW_BOOKING)
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["lookup_res"],
    "name": "Lookup Reservation",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["lookup_res"],
    "alwaysOutputData": True,
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "lookupRows",
        "documentId": doc(),
        "sheetName": tab(RESERVATIONS_GID),
        "filtersUI": {
            "values": [{"lookupColumn": "bookingUid", "lookupValue": "={{ $json.uid }}"}]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 7. Reservation Exists?
#    TRUE  → already in sheet, skip
#    FALSE → new, proceed to create
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["res_exists"],
    "name": "Reservation Exists?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": P["res_exists"],
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict", "version": 1},
            "conditions": [{
                "id": "if-reservation-exists",
                "leftValue": "={{ $json._noMatch }}",
                "rightValue": True,
                "operator": {"type": "boolean", "operation": "notEquals"}
            }],
            "combinator": "and"
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 8. Create Reservation Record
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["create_res"],
    "name": "Create Reservation Record",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["create_res"],
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "append",
        "documentId": doc(),
        "sheetName": tab(RESERVATIONS_GID),
        "columns": {
            "mappingMode": "defineBelow",
            "value": {
                "bookingUid":        "={{ $json.uid }}",
                "propertyUid":       "={{ $json.propertyUid }}",
                "guestName":         "={{ ($json.guestInformation?.firstName || '') + ' ' + ($json.guestInformation?.lastName || '') }}",
                "checkIn":           "={{ $json.checkInLocalDateTime }}",
                "checkOut":          "={{ $json.checkOutLocalDateTime }}",
                "adultCount":        "={{ $json.guestInformation?.adultCount ?? '' }}",
                "source":            "={{ $json.channel }}",
                "createdUtc":        "={{ $json.metadata?.createdUtcDateTime }}",
                "cleaningStatus":    "PENDING",
                "maintenanceStatus": "NONE",
                "payrollStatus":     "NOT_STARTED",
                "createdAtSystem":   "={{ $now.toISO() }}"
            }
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 9. Prepare Cleaning Job Data
#    Fixed: reads from Fetch Lead by UID directly (no Merge node)
# ─────────────────────────────────────────────────────────────
PREPARE_JOB_CODE = (
    "// Read directly from the fetched lead\n"
    "const ZONED_REGEX = /[zZ]|[+-]\\d{2}:\\d{2}$/;\n"
    "const lead = $('Fetch Lead by UID').first().json;\n"
    "\n"
    "const bookingUid   = lead?.uid || '';\n"
    "const cleaningJobId = bookingUid ? bookingUid + '_CLEAN' : '';\n"
    "const rawCheckout  = lead?.checkOutZonedDateTime;\n"
    "if (!rawCheckout || typeof rawCheckout !== 'string' || rawCheckout.trim() === '')\n"
    "  throw new Error('Missing checkOutZonedDateTime from Hostfully lead');\n"
    "const s = rawCheckout.trim();\n"
    "if (!ZONED_REGEX.test(s))\n"
    "  throw new Error('Invalid checkout time: timezone offset or Z required');\n"
    "const checkoutDate = new Date(s);\n"
    "if (isNaN(checkoutDate.getTime()))\n"
    "  throw new Error('Cannot parse checkout time: ' + s);\n"
    "const checkoutTimeUTC          = checkoutDate.toISOString();\n"
    "const scheduledCleaningTimeUTC = checkoutTimeUTC;\n"
    "const localDT      = (lead.checkOutLocalDateTime || '').trim();\n"
    "const cleaningDate = localDT.substring(0, 10);\n"
    "const cleaningTime = localDT.substring(11, 16);\n"
    "\n"
    "return [{ json: {\n"
    "  cleaningJobId,\n"
    "  bookingUid,\n"
    "  propertyUid:             lead.propertyUid || '',\n"
    "  cleaningDate,\n"
    "  cleaningTime,\n"
    "  checkoutTimeUTC,\n"
    "  scheduledCleaningTimeUTC,\n"
    "  createdAtSystem: new Date().toISOString()\n"
    "} }];"
)

NODES.append({
    "id": IDS["prep_job"],
    "name": "Prepare Cleaning Job Data",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": P["prep_job"],
    "parameters": {"jsCode": PREPARE_JOB_CODE}
})

# ─────────────────────────────────────────────────────────────
# 10. Create Cleaning Job Record
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["create_job"],
    "name": "Create Cleaning Job Record",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["create_job"],
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "append",
        "documentId": doc(),
        "sheetName": tab(CLEANING_JOBS_GID),
        "columns": {
            "mappingMode": "defineBelow",
            "value": {
                "cleaningJobId":            "={{ $json.cleaningJobId }}",
                "bookingUid":               "={{ $json.bookingUid }}",
                "propertyUid":              "={{ $json.propertyUid }}",
                "cleaningDate":             "={{ $json.cleaningDate }}",
                "cleaningTime":             "={{ $json.cleaningTime }}",
                "checkoutTimeUTC":          "={{ $json.checkoutTimeUTC }}",
                "scheduledCleaningTimeUTC": "={{ $json.scheduledCleaningTimeUTC }}",
                "status":                   "PENDING",
                "createdAtSystem":          "={{ $json.createdAtSystem }}"
            }
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 11. Update Reservation with Cleaning Job ID
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["update_res_jobid"],
    "name": "Update Reservation with Cleaning Job ID",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["update_res_jobid"],
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "update",
        "documentId": doc(),
        "sheetName": tab(RESERVATIONS_GID),
        "columns": {
            "mappingMode": "defineBelow",
            "value": {
                "bookingUid":    "={{ $json.bookingUid }}",
                "cleaningJobId": "={{ $json.cleaningJobId }}"
            },
            "matchingColumns": ["bookingUid"],
            "schema": []
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 12. Is Cancelled? (BOOKING_UPDATED routing)
#    TRUE  → cancellation path
#    FALSE → extended checkout check path
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["is_cancelled"],
    "name": "Is Cancelled?",
    "type": "n8n-nodes-base.if",
    "typeVersion": 2,
    "position": P["is_cancelled"],
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": False, "leftValue": "", "typeValidation": "loose", "version": 2},
            "conditions": [{
                "id": "is-cancelled-check",
                "leftValue": "={{ $json.status }}",
                "rightValue": "CANCELLED",
                "operator": {"type": "string", "operation": "equals"}
            }],
            "combinator": "and"
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 13. Lookup Reservation for Cancellation
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["lookup_cancel"],
    "name": "Lookup Reservation for Cancellation",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["lookup_cancel"],
    "alwaysOutputData": True,
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "lookupRows",
        "documentId": doc(),
        "sheetName": tab(RESERVATIONS_GID),
        "filtersUI": {
            "values": [{"lookupColumn": "bookingUid", "lookupValue": "={{ $json.uid }}"}]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 14. Cancellation Idempotency Guard
#    Simplified: single event, not a batch loop
# ─────────────────────────────────────────────────────────────
CANCEL_GUARD_CODE = (
    "// Single-event version — skip if no reservation or already cancelled\n"
    "const lookup = $input.first().json;\n"
    "const lead   = $('Fetch Lead by UID').first().json;\n"
    "\n"
    "// No reservation row — nothing to cancel\n"
    "if (lookup._noMatch) return [];\n"
    "\n"
    "// Already cancelled — idempotent, skip\n"
    "const status = (lookup.cleaningStatus ?? '').toString().trim().toUpperCase();\n"
    "if (status === 'CANCELLED') return [];\n"
    "\n"
    "return [{ json: lead }];"
)

NODES.append({
    "id": IDS["cancel_guard"],
    "name": "Cancellation Idempotency Guard",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": P["cancel_guard"],
    "parameters": {"jsCode": CANCEL_GUARD_CODE}
})

# ─────────────────────────────────────────────────────────────
# 15. Trigger Cancellation Handler
#     Fixed: localhost → cloud URL
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["trigger_cancel"],
    "name": "Trigger Cancellation Handler",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": P["trigger_cancel"],
    "parameters": {
        "method": "POST",
        "url": f"{CLOUD_BASE}/webhook/cancellation-handler",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {"name": "bookingUid",  "value": "={{ $json.uid }}"},
                {"name": "propertyUid", "value": "={{ $json.propertyUid }}"}
            ]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 16. Prepare Extended Checkout Candidate
#    Extracts the fields Reservation Exists Guard needs
# ─────────────────────────────────────────────────────────────
PREP_CANDIDATE_CODE = (
    "// Extract extended-checkout candidate fields from the fetched lead\n"
    "const ZONED_REGEX = /[zZ]|[+-]\\d{2}:\\d{2}$/;\n"
    "const lead = $input.first().json;\n"
    "\n"
    "// Only BOOKED leads qualify for extended checkout\n"
    "if (lead.type !== 'BOOKING' || lead.status !== 'BOOKED') return [];\n"
    "\n"
    "const rawZoned = lead.checkOutZonedDateTime;\n"
    "if (!rawZoned || !ZONED_REGEX.test(rawZoned.trim())) return [];\n"
    "const checkoutDate = new Date(rawZoned.trim());\n"
    "if (isNaN(checkoutDate.getTime())) return [];\n"
    "\n"
    "const checkoutTimeUTC = checkoutDate.toISOString();\n"
    "const localDT         = (lead.checkOutLocalDateTime || '').trim();\n"
    "\n"
    "return [{ json: {\n"
    "  bookingUid:                   lead.uid || '',\n"
    "  propertyUid:                  lead.propertyUid || '',\n"
    "  newCheckOut:                  localDT,\n"
    "  newCheckoutTimeUTC:           checkoutTimeUTC,\n"
    "  newScheduledCleaningTimeUTC:  checkoutTimeUTC,\n"
    "  newCleaningDate:              localDT.substring(0, 10),\n"
    "  newCleaningTime:              localDT.substring(11, 16)\n"
    "} }];"
)

NODES.append({
    "id": IDS["prep_candidate"],
    "name": "Prepare Extended Checkout Candidate",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": P["prep_candidate"],
    "parameters": {"jsCode": PREP_CANDIDATE_CODE}
})

# ─────────────────────────────────────────────────────────────
# 17. Lookup Reservation for Candidate
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["lookup_candidate"],
    "name": "Lookup Reservation for Candidate",
    "type": "n8n-nodes-base.googleSheets",
    "typeVersion": 4.5,
    "position": P["lookup_candidate"],
    "alwaysOutputData": True,
    "credentials": {"googleSheetsOAuth2Api": SHEETS_CRED},
    "parameters": {
        "operation": "lookupRows",
        "documentId": doc(),
        "sheetName": tab(RESERVATIONS_GID),
        "filtersUI": {
            "values": [{"lookupColumn": "bookingUid", "lookupValue": "={{ $json.bookingUid }}"}]
        },
        "options": {}
    }
})

# ─────────────────────────────────────────────────────────────
# 18. Reservation Exists Guard
#    Simplified: single event — compare new vs stored checkout
# ─────────────────────────────────────────────────────────────
RES_GUARD_CODE = (
    "// Single-event version: pass through only if checkout is genuinely later\n"
    "const lookup    = $input.first().json;\n"
    "const candidate = $('Prepare Extended Checkout Candidate').first().json;\n"
    "\n"
    "// No reservation in sheet — nothing to extend\n"
    "if (lookup._noMatch) return [];\n"
    "\n"
    "// Normalise both to ISO-like strings for safe string comparison\n"
    "const sheetCO = (lookup.checkOut ?? '').toString().trim().replace(' ', 'T');\n"
    "const newCO   = (candidate.newCheckOut ?? '').toString().trim().replace(' ', 'T');\n"
    "\n"
    "// Only proceed if new checkout is strictly later than stored\n"
    "if (!newCO || newCO <= sheetCO) return [];\n"
    "\n"
    "return [{ json: candidate }];"
)

NODES.append({
    "id": IDS["res_guard"],
    "name": "Reservation Exists Guard",
    "type": "n8n-nodes-base.code",
    "typeVersion": 2,
    "position": P["res_guard"],
    "parameters": {"jsCode": RES_GUARD_CODE}
})

# ─────────────────────────────────────────────────────────────
# 19. Trigger Extended Checkout Handler
#     Fixed: localhost → cloud URL
# ─────────────────────────────────────────────────────────────
NODES.append({
    "id": IDS["trigger_extended"],
    "name": "Trigger Extended Checkout Handler",
    "type": "n8n-nodes-base.httpRequest",
    "typeVersion": 4.2,
    "position": P["trigger_extended"],
    "parameters": {
        "method": "POST",
        "url": f"{CLOUD_BASE}/webhook/extended-checkout-handler",
        "sendBody": True,
        "bodyParameters": {
            "parameters": [
                {"name": "bookingUid",                  "value": "={{ $json.bookingUid }}"},
                {"name": "propertyUid",                 "value": "={{ $json.propertyUid }}"},
                {"name": "newCheckOut",                 "value": "={{ $json.newCheckOut }}"},
                {"name": "newCheckoutTimeUTC",          "value": "={{ $json.newCheckoutTimeUTC }}"},
                {"name": "newScheduledCleaningTimeUTC", "value": "={{ $json.newScheduledCleaningTimeUTC }}"},
                {"name": "newCleaningDate",             "value": "={{ $json.newCleaningDate }}"},
                {"name": "newCleaningTime",             "value": "={{ $json.newCleaningTime }}"}
            ]
        },
        "options": {}
    }
})

# ── Connections ───────────────────────────────────────────────
CONNS = {
    "Webhook": {"main": [
        [{"node": "Respond 200", "type": "main", "index": 0}]
    ]},
    "Respond 200": {"main": [
        [{"node": "Agency Check", "type": "main", "index": 0}]
    ]},
    "Agency Check": {"main": [
        # TRUE (agency matches) → fetch lead
        [{"node": "Fetch Lead by UID", "type": "main", "index": 0}],
        # FALSE (unknown agency) → stop
        []
    ]},
    "Fetch Lead by UID": {"main": [
        [{"node": "Route on Event Type", "type": "main", "index": 0}]
    ]},
    "Route on Event Type": {"main": [
        # output 0 → NEW_BOOKING
        [{"node": "Lookup Reservation", "type": "main", "index": 0}],
        # output 1 → BOOKING_UPDATED
        [{"node": "Is Cancelled?", "type": "main", "index": 0}]
    ]},
    # ── NEW_BOOKING path ──
    "Lookup Reservation": {"main": [
        [{"node": "Reservation Exists?", "type": "main", "index": 0}]
    ]},
    "Reservation Exists?": {"main": [
        # TRUE (exists) → no-op
        [],
        # FALSE (new) → create
        [{"node": "Create Reservation Record", "type": "main", "index": 0}]
    ]},
    "Create Reservation Record": {"main": [
        [{"node": "Prepare Cleaning Job Data", "type": "main", "index": 0}]
    ]},
    "Prepare Cleaning Job Data": {"main": [
        [{"node": "Create Cleaning Job Record", "type": "main", "index": 0}]
    ]},
    "Create Cleaning Job Record": {"main": [
        [{"node": "Update Reservation with Cleaning Job ID", "type": "main", "index": 0}]
    ]},
    # ── BOOKING_UPDATED path ──
    "Is Cancelled?": {"main": [
        # TRUE (CANCELLED) → cancellation path
        [{"node": "Lookup Reservation for Cancellation", "type": "main", "index": 0}],
        # FALSE (BOOKED) → extended checkout path
        [{"node": "Prepare Extended Checkout Candidate", "type": "main", "index": 0}]
    ]},
    "Lookup Reservation for Cancellation": {"main": [
        [{"node": "Cancellation Idempotency Guard", "type": "main", "index": 0}]
    ]},
    "Cancellation Idempotency Guard": {"main": [
        [{"node": "Trigger Cancellation Handler", "type": "main", "index": 0}]
    ]},
    "Prepare Extended Checkout Candidate": {"main": [
        [{"node": "Lookup Reservation for Candidate", "type": "main", "index": 0}]
    ]},
    "Lookup Reservation for Candidate": {"main": [
        [{"node": "Reservation Exists Guard", "type": "main", "index": 0}]
    ]},
    "Reservation Exists Guard": {"main": [
        [{"node": "Trigger Extended Checkout Handler", "type": "main", "index": 0}]
    ]},
}

WF = {
    "name": "Workflow 1 — Hostfully Booking Ingest (Webhook)",
    "nodes": NODES,
    "connections": CONNS,
    "settings": {
        "executionOrder": "v1",
        "saveManualExecutions": True,
        "errorWorkflow": ""
    },
    "active": False
}

out = os.path.join(os.path.dirname(__file__), "..", "workflows", "drafts", "cleaning", "workflow-1-hostfully-webhook.json")
out = os.path.normpath(out)
with open(out, "w", encoding="utf-8") as f:
    json.dump(WF, f, indent=2, ensure_ascii=False)

print(f"Written: {out}")
print(f"Nodes:   {len(NODES)}")
print(f"Connections from: {list(CONNS.keys())}")
