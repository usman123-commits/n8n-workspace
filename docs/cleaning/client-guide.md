# Cleaning Operations — How to Use the System

---

## How It Works in Plain English

When a guest books a property, the system automatically schedules a cleaning, assigns a cleaner, sends them their job details, and tracks the whole cleaning from arrival to completion. **You only need to act when the system emails you.**

---

## What Happens Automatically

| Event | What the System Does |
|-------|---------------------|
| New booking confirmed | Creates a cleaning job, assigns a cleaner, sends them an email + calendar invite |
| Guest checkout time changes | Updates the cleaning schedule, notifies cleaner if already assigned |
| Cleaner doesn't respond within 1 hour | Moves on to the next available cleaner automatically |
| Booking cancelled | Cancels the job, removes calendar events, notifies the cleaner |
| All cleaners unavailable | Sends YOU an alert email |

---

## Your Job as Admin

**Day to day — almost nothing.** The system runs itself.

You only need to step in for these situations:

### 1. You receive a "No Cleaner Available" alert
A job couldn't be assigned automatically.

**What to do:**
1. Open **CleaningJobs** in the spreadsheet
2. Find the row with status `NEEDS_MANUAL_ASSIGNMENT`
3. Pick a cleaner, enter their ID in the `cleanerId` column, change status to `ASSIGNED`
4. Message the cleaner directly with the job details

---

### 2. A maintenance issue was reported
A cleaner flagged a problem at checkout.

**What to do:**
1. Open **MaintenanceTickets** in the spreadsheet
2. Review the issue — description, photos, priority
3. Arrange a repair and mark it resolved when done

---

### 3. A cleaner cancels last minute
**What to do:**
1. Open **CleaningJobs** → find the booking
2. Clear the `cleanerId` and `assignedCleaner` fields, set status back to `PENDING`
3. The system will pick it up and assign someone else automatically

---

## The Cleaner's Experience

Cleaners receive one email per job with everything they need:

- Property address, date, time, guest count
- **Clock-In Link** — tap on arrival
- **Clock-Out Link** — tap when done

### Clocking In
1. Open the Clock-In link on their phone (GPS must be on)
2. Tap "I have arrived" → tap "Submit"
3. Green screen = confirmed ✅
4. Yellow screen = too far from property → move closer → tap "Try Again"
5. Red screen = contact manager (wrong cleaner or booking issue)

### Clocking Out
1. Open the Clock-Out link
2. Confirm checkout, optionally report any maintenance issues or supplies used
3. Tap Submit → done

---

## The Spreadsheet — Key Tabs

| Tab | What's in It |
|-----|-------------|
| **CleaningJobs** | Every job — status, assigned cleaner, clock-in/out times |
| **Reservations** | Every guest booking |
| **CleanersProfile** | Cleaner details — add/remove cleaners here |
| **Properties** | Property details — GPS coordinates, fixed cleaner if any |
| **MaintenanceTickets** | Issues reported by cleaners at checkout |
| **SupplyUsageLog** | Supplies used per job |
| **CancelledBookings** | Log of all cancellations |

---

## Common Tasks

**Add a new cleaner** → Open **CleanersProfile**, add a new row with their name, email, and calendar ID. They'll be included in assignments automatically.

**Set a fixed cleaner for a property** → Open **Properties**, enter the cleaner's ID in the `fixedCleanerId` column for that property.

**Find a specific job** → Open **CleaningJobs**, filter the `bookingUid` column.

**Check if a cleaner clocked in** → Open **ClockInSubmissions**, filter by `bookingUid` — status will show APPROVED or REJECTED.

**Change the GPS radius for clock-in** → Contact your technical contact (currently set to 100 metres).

---

## What to Share With Your Cleaners

> You'll receive an email for each job with your property address, date, time, and two links.
>
> **On arrival:** Open the Clock-In link, tap "I have arrived", then Submit. Green screen = you're in.  
> If it says you're too far away, walk to the front door and tap Try Again.
>
> **When finished:** Open the Clock-Out link, confirm checkout, report any issues, tap Submit.
>
> Keep location (GPS) turned on when using both links.
