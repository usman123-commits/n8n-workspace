# Cleaning Operations — Automation System Overview

This document explains what each automation does, when it runs, and what it produces. Written for non-technical readers — no coding knowledge required.

---

## How the System Works (Big Picture)

When a guest books a property, a chain of automations handles everything behind the scenes:

```
Guest books on Hostfully
       ↓
Automation picks it up → creates a cleaning job
       ↓
A cleaner is automatically assigned → gets an email + calendar invite
       ↓
Cleaner accepts the job → confirms via email link
       ↓
On the day: cleaner taps a link to clock in (GPS-verified)
       ↓
After cleaning: cleaner taps a link to clock out (with photos + notes)
       ↓
Job marked COMPLETED in the system
```

If anything goes wrong (guest cancels, checkout time changes, no cleaner available), the system handles it automatically and alerts the admin when human action is needed.

---

## The 10 Automations

---

### 1 — Booking Sync (Hostfully → Sheets)
**What it does:**
Watches Hostfully for new confirmed bookings across all properties. The moment a new booking appears, it automatically:
- Creates a reservation record in Google Sheets
- Creates a cleaning job record linked to that booking (scheduled for right after the guest checks out)

**When it runs:** Continuously in the background (polls every few minutes)  
**What triggers it:** A new booking appearing in Hostfully  
**What you see when it works:** A new row in the **Reservations** tab and a new row in **CleaningJobs** (both with status PENDING)  
**Human action required:** None — fully automatic

---

### 2 — Checkout Time Change Handler
**What it does:**
If a guest's checkout time changes after their booking was already recorded (e.g. Hostfully updates the reservation), this automation detects the change and updates everything:
- Updates the cleaning job with the new schedule
- If a cleaner is already assigned: reschedules their calendar event and sends them a notification email with the new time

**When it runs:** Triggered automatically by the Booking Sync (Automation 1) when it detects a checkout change  
**What you see:** Updated times in CleaningJobs and Reservations; cleaner receives an email if already assigned  
**Human action required:** None

---

### 3 — Cleaner Assignment
**What it does:**
The most important automation. It picks up newly created cleaning jobs and assigns a cleaner, then does everything needed to notify them:

- **Smart assignment:** Each property can have a fixed dedicated cleaner, or use round-robin across available cleaners (automatically picks whoever has done the fewest jobs recently)
- **Conflict check:** Won't assign a cleaner who already has a job scheduled at the same time
- **Calendar:** Creates a calendar event on both the admin calendar and the cleaner's personal calendar
- **Email:** Sends the cleaner a full assignment email with the property address, date, time, guest count, and two links — one to clock in on arrival (Step 1) and one to clock out when done (Step 2)
- **No cleaner available:** If all cleaners are busy, sends the admin an alert email and marks the job as NEEDS MANUAL ASSIGNMENT

**When it runs:** Automatically, every few minutes  
**What you see:** CleaningJobs row updated to ASSIGNED with cleaner name, calendar events created, cleaner receives email  
**Human action required:** Only if the admin alert fires (no cleaner available) — then manually assign in the system

---

### 4 — Job Accept / Decline Handler
**What it does:**
When a cleaner receives a job offer email, they see two buttons: **Accept** and **Decline**. Clicking either button instantly processes their response:

- **Accept:** Finalises the assignment, creates calendar events, sends a confirmation email, and marks the job as ASSIGNED
- **Decline:** Removes the offer from that cleaner and puts the job back in the queue — the Cleaner Assignment automation (3) will offer it to the next available cleaner on its next run
- **No response within 1 hour:** Treated the same as a decline (handled by Automation 5 below)

**When it runs:** Instantly when a cleaner clicks Accept or Decline in their email  
**What you see:** Job updates to ASSIGNED or returns to PENDING; cleaner sees a confirmation page in their browser  
**Human action required:** None — the cleaner's click handles everything

---

### 5 — Offer Timeout Checker
**What it does:**
A safety net. If a cleaner receives a job offer but doesn't click Accept or Decline within **1 hour**, this automation automatically treats it as a decline — adds that cleaner to the "already asked" list and puts the job back in the queue for the next cleaner.

This prevents a job from getting stuck in limbo if a cleaner ignores their email.

**When it runs:** Every 10 minutes, checking for offers older than 1 hour  
**What you see:** Timed-out job returns to PENDING status  
**Human action required:** None. If all cleaners time out or decline, the admin receives an alert email

---

### 6 — Clock-In (Arrival Verification)
**What it does:**
On the day of the cleaning, the cleaner opens their clock-in link (sent in their assignment email). The page:
1. Captures their GPS location
2. Sends it to the system
3. Verifies they are the correct cleaner for this booking
4. Checks they are within 100 metres of the property

If everything checks out: the job is marked IN PROGRESS and the cleaner gets a confirmation on screen.  
If they're too far from the property: the page tells them to move closer and try again.  
If they're the wrong cleaner: the page tells them to contact their manager.

**When it runs:** When the cleaner taps their clock-in link  
**What you see:** CleaningJobs row updated to IN_PROGRESS with GPS coordinates and clock-in time; Reservations updated to IN_PROGRESS  
**Human action required:** None — cleaner handles it via their phone

---

### 7 — Clock-In Validation (Background Check)
**What it does:**
Works alongside the Clock-In automation (6). Reads submitted clock-in records and performs the GPS and assignment checks in the background, then marks each submission as APPROVED or REJECTED with a reason.

**When it runs:** Every minute, processing any pending clock-in submissions  
**What you see:** ClockInSubmissions rows updated to APPROVED or REJECTED  
**Human action required:** None

> **Note:** In the current setup, Automation 6 and Automation 7 work together — 6 receives the submission and 7 validates it.

---

### 8 — Clock-Out (Job Completion)
**What it does:**
When the cleaner finishes, they open their clock-out link. The page collects:
- Their GPS location (verified to be at the property)
- An option to report any maintenance issues (with description, photos, and priority level)
- Supply usage (what cleaning supplies were used and how many)

The system then:
- Records the checkout submission
- Logs any maintenance issues to a separate Maintenance Tickets list
- Logs supply usage to a Supply Usage log
- Responds to the cleaner immediately ("checkout recorded")

**When it runs:** When the cleaner taps their clock-out link  
**What you see:** CheckoutSubmissions row created; MaintenanceTickets row added if an issue was reported; SupplyUsageLog rows added for each supply used  
**Human action required:** Review maintenance tickets if any were flagged

---

### 9 — Checkout Validation (Background Check)
**What it does:**
After the clock-out is submitted, this automation validates the GPS location and assignment in the background. When approved:
- Marks the CleaningJob as COMPLETED
- Records the clock-out time and GPS status

**When it runs:** Every minute, processing pending checkout submissions  
**What you see:** CleaningJobs row updated to COMPLETED  
**Human action required:** None

---

### 10 — Cancellation Handler
**What it does:**
When a booking is cancelled in Hostfully (and Automation 1 detects it), this automation handles all the cleanup:

- **If no cleaner was assigned yet:** Marks the job and reservation as CANCELLED
- **If a cleaner was already assigned:** Additionally cancels their calendar events (renames them to "CANCELLED") and sends them an email letting them know the job is off

All cancellations are logged in a Cancelled Bookings record.

**When it runs:** Instantly when a cancellation is detected  
**What you see:** Job and reservation marked CANCELLED; cleaner notified if one was assigned; CancelledBookings log updated  
**Human action required:** None

---

## Full Journey — Timeline Example

| Time | What Happens | Who Does It |
|------|-------------|-------------|
| Guest books online | Automation 1 picks it up, creates job | Automatic |
| Within minutes | Automation 3 assigns a cleaner, sends email | Automatic |
| Cleaner gets email | Clicks Accept | Cleaner |
| Cleaner accepts | Automation 4 finalises assignment, creates calendar event | Automatic |
| Day before checkout | Cleaner sees calendar invite | Cleaner (no action needed) |
| Day of cleaning | Cleaner opens clock-in link, GPS verified | Cleaner + Automation 6 & 7 |
| After cleaning | Cleaner opens clock-out link, reports any issues | Cleaner + Automation 8 & 9 |
| Job complete | Marked COMPLETED in system, payroll data ready | Automatic |
| If guest cancels | Cleaner notified, calendar cleared | Automatic (Automation 10) |

---

## When the Admin Needs to Step In

The system handles almost everything automatically. The admin only needs to act in these situations:

| Situation | What the System Does | What Admin Should Do |
|-----------|---------------------|----------------------|
| No cleaner available (all busy or declined) | Sends admin an alert email, marks job NEEDS MANUAL ASSIGNMENT | Manually assign a cleaner and update the system |
| Maintenance issue reported at checkout | Creates a ticket in Maintenance Tickets | Review the ticket and arrange a repair |
| Cleaner clock-in rejected (wrong person or too far away) | Cleaner sees an error on their phone | Contact the cleaner if needed |

---

## Data at a Glance

All automation data lives in one Google Spreadsheet. Key tabs:

| Tab | What It Contains |
|-----|----------------|
| Reservations | Every guest booking — arrival, checkout, property, guest name |
| CleaningJobs | Every cleaning job — status, assigned cleaner, clock-in/out times |
| CleanersProfile | Cleaner details — contact info, assignment history |
| Properties | Property details — address, GPS coordinates, fixed cleaner if any |
| ClockInSubmissions | Clock-in record for each job — GPS, timestamp, approval status |
| CheckoutSubmissions | Clock-out record for each job |
| MaintenanceTickets | Issues reported by cleaners at checkout |
| SupplyUsageLog | Supplies used per job |
| CancelledBookings | Log of all cancellations |
