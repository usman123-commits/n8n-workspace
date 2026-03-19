"""
Add human-readable notes to every node in every workflow.
Only touches the 'notes' field — no logic, connections, or parameters change.
Usage: python3 add_notes.py
"""
import json, sys, os, urllib.request

API = "http://localhost:5678/api/v1"
KEY = os.environ.get("N8N_API_KEY", "")

# ── Workflow 1: Hostfully to Operto Reservation Cleaning Sync ──
W1 = {
    "id": "JKS8Imjt5Nvp1ReG",
    "notes": {
        "Schedule Trigger":
            "Runs on a schedule to poll Hostfully for new bookings.\nWhy: we need to detect new reservations automatically.",

        "Initialize Cursor":
            "Sets the pagination cursor to blank so we start from the first page.\nWhy: Hostfully API uses cursor-based pagination.",

        "Fetch Hostfully Leads":
            "Calls Hostfully API to get the first page of reservations.\nWhy: this is how we pull booking data into our system.",

        "Fetch Hostfully Leads1":
            "Fetches the next page of reservations using the cursor.\nWhy: some properties have more bookings than fit in one API page.",

        "Accumulate Leads":
            "Collects all reservation pages into a single list.\nWhy: we need all bookings together before filtering.",

        "Has More Pages?1":
            "Checks if the API returned a next-page cursor.\nWhy: if yes, loop back and fetch more; if no, move on to filtering.",

        "Read Last Timestamp":
            "Reads the last-processed timestamp from the sheet.\nWhy: so we only process bookings newer than what we've already seen.",

        "Filter New Bookings":
            "Keeps only BOOKED reservations created after the last timestamp.\nWhy: avoids re-processing old bookings.",

        "Output Leads Individually":
            "Splits the filtered list into individual items for the loop.\nWhy: Split In Batches needs single items.",

        "Split In Batches":
            "Processes one booking at a time.\nWhy: prevents race conditions when writing to Sheets.",

        "Lookup Reservation":
            "Checks if this bookingUid already exists in the Reservations tab.\nWhy: skip duplicates — don't create the same reservation twice.",

        "Ensure One Item":
            "Guarantees exactly one item passes through, even if lookup returned nothing.\nWhy: downstream nodes expect one item per iteration.",

        "Merge Lead and Lookup":
            "Combines the Hostfully data with any existing reservation data.\nWhy: gives us all fields in one object for the next decisions.",

        "Reservation Exists?":
            "Branches: TRUE = already in sheet (skip), FALSE = new booking (create).\nWhy: prevents duplicate reservation records.",

        "Cleaning Job Needed?":
            "Checks if a CleaningJobs row already exists for this booking.\nWhy: prevents duplicate cleaning job records.",

        "Create Reservation Record":
            "Appends a new row to the Reservations tab with booking details.\nWhy: this is our internal record of the booking.",

        "Prepare Cleaning Job Data":
            "Builds the cleaning job fields (date, time, status=PENDING, empty cleanerId).\nWhy: structures the data before writing to CleaningJobs.",

        "Create Cleaning Job Record":
            "Appends a new row to the CleaningJobs tab.\nWhy: creates the job that Phase 2 will pick up and assign to a cleaner.",

        "Update Reservation with Cleaning Job ID":
            "Links the reservation to its cleaning job by writing the job reference back.\nWhy: keeps Reservations and CleaningJobs cross-referenced.",

        "Compute Max After Loop":
            "Finds the latest createdUtcDateTime from all processed bookings.\nWhy: this becomes the new 'last timestamp' for the next run.",

        "Update Stored Timestamp":
            "Writes the new timestamp back to the sheet.\nWhy: next run will only pick up bookings after this point.",

        "Detect Extended Checkouts":
            "Finds bookings where checkout time changed vs what's in the sheet.\nWhy: checkout changes need special handling (Workflow 1A).",

        "Split Extended Candidates":
            "Loops through each extended checkout one at a time.\nWhy: each one triggers a separate webhook call.",

        "Lookup Reservation for Candidate":
            "Gets the existing reservation data for the checkout-changed booking.\nWhy: we need the old checkout time to compare.",

        "Reservation Exists Guard":
            "Only proceeds if the reservation actually exists in the sheet.\nWhy: can't process an extended checkout for a booking we don't have.",

        "Trigger Extended Checkout Handler":
            "Sends a webhook to Workflow 1A with old/new checkout details.\nWhy: Workflow 1A handles all the updates (sheets, calendar, email).",

        "Detect Cancellations":
            "Finds bookings that changed to CANCELLED status in Hostfully.\nWhy: cancellations need cleanup (Cancellation Handler workflow).",

        "Lookup Reservation for Cancellation":
            "Gets the existing reservation for the cancelled booking.\nWhy: we need bookingUid and propertyUid to send to the handler.",

        "Cancellation Idempotency Guard":
            "Skips if the reservation is already marked CANCELLED in our sheet.\nWhy: prevents sending duplicate cancellation webhooks.",

        "Trigger Cancellation Handler":
            "Sends a webhook to the Cancellation Handler workflow.\nWhy: that workflow handles all cancellation cleanup.",
    }
}

# ── Workflow 2: PHASE 2 – Cleaner Assignment + Calendar Dispatch ──
W2 = {
    "id": "AU1w579al67hGom7",
    "notes": {
        "Schedule Trigger":
            "Runs every few minutes to check for unassigned cleaning jobs.\nWhy: new PENDING jobs appear when Workflow 1 creates them.",

        "Read Properties":
            "Loads all rows from the Properties tab.\nWhy: needed to look up property name, address, and fixedCleanerId.",

        "Read CleanersProfile":
            "Loads all rows from the CleanersProfile tab.\nWhy: needed for cleaner email, calendar ID, and assignment count.",

        "Read All Cleaning Jobs":
            "Loads all CleaningJobs rows (not just PENDING).\nWhy: used to check cleaner availability — can't double-book a cleaner on overlapping jobs.",

        "Single Item for Read Jobs":
            "Passes one item so the next read runs exactly once.\nWhy: CleanersProfile data is referenced later; we don't need it duplicated per row.",

        "Read Pending Cleaning Jobs":
            "Reads all rows from the CleaningJobs tab.\nWhy: next node filters to only PENDING ones.",

        "Filter Pending Only":
            "Keeps only jobs where status=PENDING, cleanerId is empty, no calendar event, and no processingFlag.\nWhy: these are the jobs that need a cleaner assigned.",

        "Attach CleanersProfile":
            "Attaches Properties, CleanersProfile, and all CleaningJobs data to each pending job item.\nWhy: the Assign Cleaner node needs all this data to make decisions inside the loop.",

        "Split In Batches":
            "Processes one cleaning job at a time.\nWhy: avoids conflicts when multiple jobs update the same cleaner's data.",

        "Lock Cleaning Job":
            "Sets a processingFlag on the job row to prevent other runs from picking it up.\nWhy: row-level lock — stops duplicate assignment if the schedule fires again before we finish.",

        "Lookup Reservation":
            "Gets the reservation details (propertyName, address, guest info) by bookingUid.\nWhy: the assignment email and calendar event need this info.",

        "Ensure One Item (Job or Reservation)":
            "Falls back to job data if reservation lookup returned nothing.\nWhy: assignment should still proceed even if reservation row is missing.",

        "Merge Job and Reservation":
            "Combines cleaning job fields with reservation fields into one object.\nWhy: downstream nodes need all data in one place.",

        "Assign Cleaner":
            "Picks the right cleaner using fixedCleanerId from Properties. Checks availability (no overlapping jobs).\nWhy: this is the core assignment logic — matches property to its dedicated cleaner.",

        "Cleaner Available?":
            "Branches based on whether a cleaner was found and is available.\nWhy: if no cleaner available, we need to flag for manual assignment.",

        "Mark Needs Manual Assignment":
            "Sets the job's processingFlag to 'NEEDS_MANUAL' and clears the lock.\nWhy: admin will see this and assign manually.",

        "Send Admin Alert":
            "Emails the admin that a job couldn't be auto-assigned.\nWhy: ensures no job silently gets stuck without a cleaner.",

        "Generate ClockIn Form Link":
            "Builds a pre-filled Google Form URL with bookingUid and cleanerId.\nWhy: the cleaner clicks this link to clock in on arrival (Phase 3).",

        "Update Job Assigned":
            "Writes cleanerId, assignedAt, and clockInLink to the CleaningJobs row.\nWhy: records who was assigned and when.",

        "Increment Assignment Count":
            "Adds 1 to the cleaner's assignmentCount.\nWhy: tracks workload for future load-balancing.",

        "Update Assignment Count in Sheet":
            "Writes the updated assignmentCount back to CleanersProfile.\nWhy: persists the count so it survives across runs.",

        "Restore Job Data After Count Update":
            "Brings back the job data that was lost after the count update node.\nWhy: the next nodes (calendar, email) need the job fields.",

        "Calculate Cleaning Time":
            "Computes calendar event start/end times from scheduledCleaningTimeUTC + 3 hours.\nWhy: calendar events need proper ISO timestamps.",

        "Already Has Calendar Event?":
            "Checks if calendarEventId is already set on the job.\nWhy: prevents creating duplicate calendar events.",

        "Create Admin Calendar Event":
            "Creates an event on the master admin calendar.\nWhy: admin sees all cleanings in one place.",

        "Create Cleaner Calendar Event":
            "Creates an event on the cleaner's specific calendar.\nWhy: the cleaner sees their upcoming job and clock-in link in the event description.",

        "Skip (Already Has Event)":
            "No-op when calendar event already exists.\nWhy: don't recreate what's already there.",

        "Prepare Event Id for Sheet":
            "Extracts the calendar event IDs from both create responses.\nWhy: we need to store them in CleaningJobs for future updates/cancellations.",

        "Update Job With Event Id":
            "Writes calendarEventId and adminCalendarEventId to CleaningJobs.\nWhy: links the job to its calendar events for cancellation/update workflows.",

        "Send Gmail to Cleaner":
            "Sends the assignment email with property details, time, and clock-in link.\nWhy: the cleaner needs to know about their new job.",

        "Finalize Assignment":
            "Sets status=ASSIGNED and clears the processingFlag lock.\nWhy: marks the job as fully processed and releases the lock.",

        "Mark jab as assigned in reservation":
            "Updates the Reservations tab cleaningStatus to ASSIGNED.\nWhy: keeps Reservations in sync with CleaningJobs status.",
    }
}

# ── Workflow 3: Form Responses 1 to ClockInSubmissions ──
W3 = {
    "id": "ieebrbqVyvQwb0ig",
    "notes": {
        "Google Sheets Trigger":
            "Fires when a new row appears in the Raw Form Responses tab.\nWhy: cleaners submit a Google Form on arrival — this picks up their submission.",

        "Split In Batches":
            "Processes one form submission at a time.\nWhy: each submission needs individual validation and duplicate checking.",

        "Normalize and Check":
            "Extracts the location field and detects if it's a shortened Google Maps link.\nWhy: short links need an HTTP request to resolve; full URLs can be parsed directly.",

        "Is Short Link?":
            "Branches: TRUE = short Maps link, FALSE = full URL or lat,lng.\nWhy: short links need resolving before we can extract coordinates.",

        "Resolve Short Link":
            "Makes an HTTP GET to the short Maps URL and follows redirects.\nWhy: the redirected page contains the actual lat/lng coordinates.",

        "Parse Short Link Response":
            "Extracts lat/lng from the resolved HTML using regex patterns.\nWhy: Google Maps embeds coordinates in the page in various formats.",

        "ParseAndValidate":
            "Parses lat/lng from a full Maps URL, raw coordinates, or DMS notation.\nWhy: cleaners may paste different location formats from their phone.",

        "Lookup Existing ClockIn":
            "Checks ClockInSubmissions for any APPROVED row with this bookingUid.\nWhy: duplicate protection — don't allow a second clock-in for the same booking.",

        "Reject If Already Approved":
            "If an APPROVED row exists, sets skipInsert=true to skip this submission.\nWhy: one booking = one clock-in. Duplicate submissions are silently dropped.",

        "Should Insert?":
            "Branches: TRUE = no approved row exists (insert), FALSE = already clocked in (skip).\nWhy: controls whether we write to ClockInSubmissions.",

        "Insert Structured Row":
            "Appends a normalized row to ClockInSubmissions with processingStatus=PENDING.\nWhy: Workflow 3B will pick this up and validate GPS + cleaner assignment.",
    }
}

# ── Workflow 3B: ClockIn Validation Processor ──
W3B = {
    "id": "B7duBLBoOCdLpztS",
    "notes": {
        "Schedule Trigger":
            "Runs every 1 minute.\nWhy: polls for new PENDING clock-in submissions to validate.",

        "Read ClockInSubmissions":
            "Reads all rows from the ClockInSubmissions tab.\nWhy: next node filters to PENDING only.",

        "Only PENDING":
            "Keeps only rows where processingStatus=PENDING.\nWhy: already-processed rows (APPROVED/REJECTED) should not be re-validated.",

        "Get Booking":
            "Looks up the CleaningJobs row by bookingUid.\nWhy: we need the assigned cleanerId and propertyUid to validate against.",

        "Merge Submission and Job":
            "Combines the submission data with the CleaningJobs data.\nWhy: validation needs both the form submission and the job details in one object.",

        "Validate Cleaner Assignment":
            "Checks if cleanerIdFromForm matches cleanerId in CleaningJobs.\nWhy: only the assigned cleaner should be able to clock in for a job.",

        "Reject Cleaner Not Assigned":
            "Sets processingStatus=REJECTED with message 'Cleaner not assigned to this booking'.\nWhy: someone tried to clock in for a job they're not assigned to.",

        "Pass TRUE items":
            "Passes through items that passed cleaner validation.\nWhy: holds them for the merge with property coordinates.",

        "Get Property Coordinates":
            "Looks up latitude/longitude from the Properties tab by propertyUid.\nWhy: we compare the cleaner's GPS against the property location.",

        "Refining feilds":
            "Extracts just the coordinate fields from the property lookup.\nWhy: clean data for the merge — only lat/lng needed.",

        "Merge Coords with Submission":
            "Combines submission+job data with property coordinates by position.\nWhy: the distance calculation needs both GPS points in one object.",

        "DistanceCalculation":
            "Haversine formula: calculates meters between cleaner GPS and property GPS.\nWhy: determines if the cleaner is physically at the property.",

        "Radius Check":
            "Branches: TRUE = within 100m (approve), FALSE = too far (reject).\nWhy: 100m radius ensures the cleaner is actually on-site.",

        "Approve ClockIn":
            "Sets processingStatus=APPROVED in ClockInSubmissions.\nWhy: marks this submission as valid.",

        "Update CleaningJob IN_PROGRESS":
            "Sets CleaningJobs status=IN_PROGRESS, writes clockInTimeUTC and GPS data.\nWhy: the job is now actively being cleaned.",

        "Reject Outside Radius":
            "Sets processingStatus=REJECTED with distance info in ClockInSubmissions.\nWhy: cleaner is too far from the property to be on-site.",
    }
}

# ── Cancellation Handler ──
WC = {
    "id": "BQ6uHsWxBcegrfrv",
    "notes": {
        "Receive Cancellation Payload":
            "Webhook that receives bookingUid and propertyUid.\nWhy: Workflow 1 calls this when Hostfully reports a cancelled booking.",

        "Lookup Cleaning Job":
            "Finds the CleaningJobs row by bookingUid.\nWhy: we need to know the job's current status and calendarEventId.",

        "Prepare Cancellation Context":
            "Merges webhook payload with job data and sets _jobFound flag.\nWhy: downstream nodes need to know if a job exists for this booking.",

        "Job Found?":
            "Branches: TRUE = job exists (process cancellation), FALSE = no job (ignore).\nWhy: can't cancel a job that doesn't exist.",

        "Route by Job Status":
            "Switch: PENDING → simple cancel, ASSIGNED → cancel + notify cleaner, other → NoOp.\nWhy: assigned jobs need calendar updates and cleaner email; pending jobs don't.",

        "Update CleaningJob CANCELLED PENDING":
            "Sets status=CANCELLED on CleaningJobs.\nWhy: marks the job as cancelled (no cleaner was assigned, so no notification needed).",

        "Update Reservation CANCELLED PENDING":
            "Sets cleaningStatus=CANCELLED on Reservations.\nWhy: keeps Reservations in sync with CleaningJobs.",

        "Prepare Log Row PENDING":
            "Builds a CancelledBookings log row with cleanerNotified=false.\nWhy: audit trail — records that cancellation happened without cleaner notification.",

        "Log to CancelledBookings PENDING":
            "Appends the log row to CancelledBookings tab.\nWhy: permanent record of the cancellation.",

        "Update CleaningJob CANCELLED ASSIGNED":
            "Sets status=CANCELLED, clears calendar IDs on CleaningJobs.\nWhy: marks job cancelled and removes calendar references.",

        "Update Reservation CANCELLED ASSIGNED":
            "Sets cleaningStatus=CANCELLED on Reservations.\nWhy: keeps Reservations in sync.",

        "Update Admin Calendar Event":
            "Renames the admin calendar event to 'CANCELLED – [property]'.\nWhy: admin sees at a glance that this cleaning was cancelled.",

        "Update Cleaner Calendar Event":
            "Renames the cleaner's calendar event to 'CANCELLED – [property]'.\nWhy: cleaner sees the cancellation on their calendar.",

        "Lookup Cleaner Email":
            "Gets the cleaner's email from CleanersProfile.\nWhy: needed to send the cancellation notification email.",

        "Lookup Property Name":
            "Gets the property name from Properties tab.\nWhy: email subject needs the property name, not just the UID.",

        "Prepare Cancellation Email":
            "Builds the email subject and body with property and booking details.\nWhy: cleaner needs clear info about which booking was cancelled.",

        "Send Cancellation Email":
            "Sends the cancellation notification via Gmail.\nWhy: cleaner must be informed so they don't show up for a cancelled job.",

        "Prepare Log Row ASSIGNED":
            "Builds a CancelledBookings log row with cleanerNotified=true.\nWhy: audit trail — records that the cleaner was notified.",

        "Log to CancelledBookings ASSIGNED":
            "Appends the log row to CancelledBookings tab.\nWhy: permanent record of the cancellation with notification proof.",

        "NoOp":
            "Does nothing — fallback for statuses that don't need cancellation handling.\nWhy: jobs that are IN_PROGRESS or COMPLETED need different handling (not implemented yet).",
    }
}

# ── Extended Checkout Handler ──
WE = {
    "id": "NZNbIHz9Qutwj1fa",
    "notes": {
        "Receive Extended Checkout Payload":
            "Webhook that receives bookingUid, old/new checkout times, cleanerId.\nWhy: Workflow 1 calls this when a guest's checkout time changes.",

        "Lookup Cleaning Job":
            "Finds the CleaningJobs row by bookingUid.\nWhy: we need current job status and calendar event IDs.",

        "Prepare Job Found":
            "Merges webhook payload with job data and sets _jobFound flag.\nWhy: downstream nodes need to know if this booking has a cleaning job.",

        "Job Found?":
            "Branches: TRUE = job exists (update it), FALSE = no job (skip).\nWhy: can't update a job that doesn't exist.",

        "Route by Job Status":
            "Switch: PENDING → update times only, ASSIGNED → update times + reschedule calendar + email cleaner.\nWhy: assigned jobs have calendar events and a cleaner to notify.",

        "Update CleaningJob PENDING":
            "Updates checkout/cleaning times on CleaningJobs for a PENDING job.\nWhy: the cleaning needs to happen at the new checkout time.",

        "Update CleaningJob ASSIGNED":
            "Updates checkout/cleaning times on CleaningJobs for an ASSIGNED job.\nWhy: same as PENDING, but calendar/email steps follow.",

        "Skip (Job Active or Completed)":
            "No-op for jobs already IN_PROGRESS or COMPLETED.\nWhy: can't reschedule a cleaning that's already started or done.",

        "Calculate New Cleaning Window":
            "Computes new calendar event start/end from the updated checkout time + 3 hours.\nWhy: calendar events need proper ISO timestamps.",

        "Update Admin Calendar Event":
            "Moves the admin calendar event to the new time window.\nWhy: admin calendar must reflect the actual cleaning schedule.",

        "Update Cleaner Calendar Event":
            "Moves the cleaner's calendar event to the new time window.\nWhy: cleaner must see the updated schedule.",

        "Lookup Cleaner Email":
            "Gets the cleaner's email from CleanersProfile.\nWhy: needed to send the schedule change notification.",

        "Prepare Reassignment Email":
            "Builds the email with old time, new time, and property details.\nWhy: cleaner needs to know the exact schedule change.",

        "Send Reassignment Email":
            "Sends the schedule change notification via Gmail.\nWhy: cleaner must be aware of the time change to show up correctly.",

        "Update Reservation":
            "Updates checkout on Reservations for an ASSIGNED job.\nWhy: keeps Reservations in sync with the new checkout time.",

        "Update Reservation Only":
            "Updates checkout on Reservations for a PENDING job.\nWhy: same sync, but no calendar/email needed for unassigned jobs.",

        "Prepare Log Row":
            "Builds an ExtendedCheckouts log row with old/new times and notification status.\nWhy: audit trail of every checkout change.",

        "Log to ExtendedCheckouts":
            "Appends the log row to ExtendedCheckouts tab.\nWhy: permanent record of the checkout extension.",
    }
}

ALL_WORKFLOWS = [W1, W2, W3, W3B, WC, WE]

def safe_payload(wf):
    """Strip to only the 4 safe fields for PUT."""
    bad_settings = {"availableInMCP", "timeSavedMode", "callerPolicy", "binaryMode"}
    return {
        "name": wf["name"],
        "nodes": wf["nodes"],
        "connections": wf["connections"],
        "settings": {k: v for k, v in wf.get("settings", {}).items() if k not in bad_settings},
    }

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

def main():
    if not KEY:
        print("ERROR: N8N_API_KEY not set. Run: export $(grep -v '^#' .env | xargs)")
        sys.exit(1)

    for spec in ALL_WORKFLOWS:
        wf_id = spec["id"]
        notes_map = spec["notes"]
        print(f"\n--- Fetching workflow {wf_id} ---")
        try:
            wf = api_get(f"/workflows/{wf_id}")
        except Exception as e:
            print(f"  SKIP (fetch failed): {e}")
            continue

        updated = 0
        for node in wf.get("nodes", []):
            name = node.get("name", "")
            if name in notes_map:
                node["notes"] = notes_map[name]
                updated += 1

        if updated == 0:
            print(f"  No matching nodes found, skipping PUT.")
            continue

        payload = safe_payload(wf)
        print(f"  Updated notes on {updated}/{len(wf['nodes'])} nodes. Pushing...")
        try:
            result = api_put(f"/workflows/{wf_id}", payload)
            print(f"  OK: {result.get('name', '?')}")
        except Exception as e:
            print(f"  FAILED: {e}")

    print("\nDone.")

if __name__ == "__main__":
    main()
