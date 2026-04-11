# Cleaner Checkout Form — Reference

**Form ID:** `1Z4ENq8lEnyguZDlF8LusaTwvdDK4IVCXnD3kD3LpPGw`
**Responder URL:** `https://docs.google.com/forms/d/e/1FAIpQLSdPGfvk8ArvU5KQjE838bK3LNeK0vLaPkHcbeJLb_7tCblxqw/viewform`

---

## Prefilled Entry IDs

| Field | Entry ID | Pre-fill? |
|-------|----------|-----------|
| Booking ID | `entry.2041344083` | Yes (from CleaningJobs) |
| Cleaner ID | `entry.617396720` | Yes (assigned cleaner) |
| Property Name | `entry.2003908779` | Yes (from Properties) |
| Confirm Checkout | `entry.1014359367` | No |
| Capture Location (GPS) | `entry.656972742` | No |
| Any maintenance issues? | `entry.1823853853` | No |
| Issue Type | `entry.720437571` | No |
| Issue Description | `entry.1494524605` | No |
| Photo of Issue | — | No (file upload — not prefillable) |
| Issue Priority | `entry.263447783` | No |
| Trash Bags — Qty Used | `entry.1940591710` | No |
| All-Purpose Cleaner — Qty Used | `entry.130140961` | No |
| Glass Cleaner — Qty Used | `entry.227672401` | No |
| Disinfectant — Qty Used | `entry.1313170783` | No |
| Toilet Cleaner — Qty Used | `entry.369782477` | No |
| Floor Cleaner — Qty Used | `entry.841490969` | No |
| Sponges — Qty Used | `entry.1560383040` | No |
| Paper Towels — Qty Used | `entry.406844411` | No |
| Laundry Detergent — Qty Used | `entry.1646603886` | No |
| Fabric Softener — Qty Used | `entry.1310967941` | No |
| Dish Soap — Qty Used | `entry.1565358973` | No |
| Air Freshener — Qty Used | `entry.221201833` | No |
| Microfiber Cloths — Qty Used | `entry.2035447362` | No |
| Mop Pads — Qty Used | `entry.1986172710` | No |
| Low Stock Alert | `entry.2013406669` | No |

---

## Prefilled Link Template (for Workflow 2)

Workflow 2 generates this link per cleaning job and includes it in the assignment email + calendar event.

```
https://docs.google.com/forms/d/e/1FAIpQLSdPGfvk8ArvU5KQjE838bK3LNeK0vLaPkHcbeJLb_7tCblxqw/viewform?usp=pp_url&entry.2041344083={{bookingUid}}&entry.617396720={{cleanerId}}&entry.2003908779={{propertyName}}
```

Only the first 3 fields are pre-filled. The cleaner fills everything else on site.

---

## Example Prefilled Link (full — updated after supply question redesign)

```
https://docs.google.com/forms/d/e/1FAIpQLSdPGfvk8ArvU5KQjE838bK3LNeK0vLaPkHcbeJLb_7tCblxqw/viewform?usp=pp_url&entry.2041344083=Booking+ID&entry.617396720=Cleaner+ID&entry.2003908779=Property+Name&entry.1014359367=Yes&entry.656972742=Capture+Location+(GPS)&entry.1823853853=Yes&entry.720437571=Plumbing&entry.1494524605=Describe+the+issue+in+detail.+(Only+if+you+reported+an+issue+above)&entry.263447783=Low&entry.1940591710=Trash+Bags+%E2%80%94+Qty+Used&entry.130140961=All-Purpose+Clean&entry.227672401=Glass+Cleaner&entry.1313170783=Disinfectant&entry.369782477=Toilet+Cleaner&entry.841490969=Floor+Cleaner&entry.1560383040=Sponges&entry.406844411=Paper+Towels&entry.1646603886=Laundry+Detergent&entry.1310967941=Fabric+Softener&entry.1565358973=Dish+Soap&entry.221201833=Air+Freshener&entry.2035447362=Microfiber+Cloths&entry.1986172710=Mop+Pads&entry.2013406669=Yes+-+some+items+are+running+low
```
