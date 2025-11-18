# Test Plan — Campus Umbrella Rental Service (CSV + Tkinter GUI)

**Legend**  
Roles: STU (Student), STF (Staff)  
Data files: `students.csv`, `staff.csv`, `umbrellas.csv`, `reservations.csv`, `payments.csv`  
Time helpers: **Time Travel** bar (offset)

> **Build baseline:** Current app stores passwords in **plain text** (`password` column). Weekly analytics UI is **not** included in this build; see Section **G2** for future/optional weekly tests.

---

## A. Environment & Seeding

**ENV-01 Seed on first run**  
Pre: Empty (or missing) CSVs; valid `DATA_DIR`.  
Steps: Run app.  
Expected: All CSVs created with headers; default accounts (`S123456/student123`; `T001/staff123`); 6 umbrellas `UMB001…UMB006` with `status=Available`.

**ENV-02 Custom DATA_DIR via env var**  
Pre: Set `UMBRELLA_DATA_DIR` to a new folder.  
Steps: Run app.  
Expected: CSVs appear in that folder; app shows path on login.

**ENV-03 Migration of reservations columns**  
Pre: `reservations.csv` exists but missing `requested_days,start_date,end_date`.  
Steps: Run app.  
Expected: Columns added, existing rows preserved; `requested_days` default “1”.

**ENV-04 Seeded password columns (plain text)**  
Pre: Fresh seed.  
Steps: Open `students.csv` and `staff.csv`.  
Expected: Each row has `password` column populated (no hashing); legacy `pwd_hash` is optional/unused for new seeds.

---

## B. Authentication & Access Control

**AUTH-01 Student login success (plain text)**  
Pre: Defaults seeded.  
Steps: Login as Student with `S123456 / student123`.  
Expected: Student UI loaded.

**AUTH-02 Staff login success (plain text)**  
Steps: Login as Staff with `T001 / staff123`.  
Expected: Staff UI loaded (Front Desk default).

**AUTH-03 Wrong password**  
Steps: Try Student with bad password.  
Expected: Error dialog; no crash; stay on login.

**AUTH-04 Inactive account**  
Pre: Flip `is_active` to “0” for a student.  
Steps: Login.  
Expected: Error dialog; blocked.

---

## C. Student — Calendar & Reservation

**STU-01 Calendar window highlight**  
Steps: Open Student → Availability; observe calendar.  
Expected: Exactly **today..today+6** highlighted.

**STU-02 Pick valid range (same day)**  
Steps: Click today twice; select an available umbrella; Reserve.  
Expected: Reservation created; umbrella status → **Reserved**; row disappears from Available list.

**STU-03 Pick valid multi-day range (≤7)**  
Steps: Start today, end today+3; Reserve.  
Expected: `requested_days=4`; reservation created.

**STU-04 Reject start before today**  
Steps: Use Time Travel to set `-1d`; select date < “simulated today”.  
Expected: UI error: “Please pick within the next 7 days.”

**STU-05 Reject end before start**  
Steps: Select end earlier than start.  
Expected: UI error.

**STU-06 Reject end beyond allowed window**  
Steps: Start today, end today+7.  
Expected: Error: “Dates must be within the next 7 days”.

**STU-07 Block when open reservation exists**  
Pre: One reservation already Reserved/Active for `S123456`.  
Steps: Try reserving another umbrella.  
Expected: Red banner and disabled button; error on attempt.

**STU-08 Block when outstanding overdue exists**  
Pre: Add `payments.csv` row for SID=`S123456` with `reason=overdue,status=outstanding`.  
Steps: Open Student → Availability.  
Expected: Red banner “You have outstanding overdue payments.”; Reserve disabled.

**STU-09 Reserve unavailable umbrella**  
Pre: Set an umbrella status to Reserved/InUse/Maintenance.  
Steps: Try reserving it (directly selecting row if visible).  
Expected: Error “Umbrella is not available”.

**STU-10 Status panel details**  
Steps: Reserve once; check “My Status”.  
Expected: Shows `Res#`, umbrella code, `requested_days`, start/end, timestamps.

**STU-11 History shows latest first**  
Steps: Create multiple reservations; open History.  
Expected: Sorted by `reserved_at` desc.

**STU-12 Payments list format**  
Pre: Create overdue/damaged/lost payments.  
Steps: Open Payments.  
Expected: Amounts formatted `HK$…`, statuses display correctly.

---

## D. Staff — Front Desk (Reserved / Active + Actions)

**STF-FD-01 Auto-load lists**  
Steps: Login Staff → Front Desk.  
Expected: “Reserved (Awaiting Pickup)” and “Current In Use (Active)” populated automatically.

**STF-FD-02 Filter by SID**  
Pre: Multiple students with reservations.  
Steps: Enter SID filter; Apply.  
Expected: Both lists filter to that SID; Checkout/Lost fields prefilled.

**STF-FD-03 Checkout success**  
Pre: Student has a Reserved record for a specific umbrella with `start_date ≤ today`.  
Steps: Enter SID + umbrella code; click Checkout.  
Expected: Reservation → **Active**; sets `pickup_at` now; `due_at = end_date 23:59:59`; umbrella → **InUse**.

**STF-FD-04 Checkout before start_date (blocked)**  
Pre: Reserved with `start_date = today+1`.  
Steps: Try Checkout.  
Expected: Error: “Pickup not allowed before start date”.

**STF-FD-05 Checkout without matching Reserved**  
Steps: Enter any SID/umbrella combo not matching a Reserved booking.  
Expected: Error: “No Reserved record…”.

**STF-FD-06 Check-in on-time (ok)**  
Pre: Active reservation; Time Travel so `now ≤ due_at`.  
Steps: Enter umbrella; Condition=`ok`; Check-in.  
Expected: Reservation → **Closed**; umbrella → **Available**; **no** payment created.

**STF-FD-07 Check-in late (ok) creates overdue**  
Pre: Active; Time Travel beyond `due_at` by `1h+`.  
Steps: Check-in (`ok`).  
Expected: Reservation → **Closed-Overdue**; one payment created: `reason=overdue`, `amount=ceil(late_days)*20`.

**STF-FD-08 Check-in damaged on-time**  
Pre: Active; `now ≤ due`.  
Steps: Check-in with `Condition=damaged`.  
Expected: Reservation → **Closed-Damaged**; umbrella → **Maintenance**; payment `reason=damaged`, amount `HK$100`; **no** overdue.

**STF-FD-09 Check-in damaged late (both fees)**  
Pre: Active; `now` past due.  
Steps: Check-in (`damaged`).  
Expected: Two payments: overdue + damaged; reservation **Closed-Damaged** (overdue presence is captured via payments and `Closed-Damaged` state).

**STF-FD-10 Lost flow**  
Pre: Active reservation for SID & umbrella.  
Steps: “Lost — SID + Umbrella → Mark Lost”.  
Expected: Reservation → **Closed-Lost**; umbrella → **Lost**; payment `reason=lost`, amount `HK$300`.

**STF-FD-11 Double actions blocked**  
Steps: Attempt to Checkout same Reserved twice; or Check-in same Active twice.  
Expected: Second attempt errors: no matching record.

---

## E. Staff — Payments tab

**STF-PAY-01 Auto-load outstanding overdue**  
Steps: Open Payments tab.  
Expected: Only `status=outstanding` **and** `reason=overdue` rows shown.

**STF-PAY-02 Filter by SID**  
Pre: Multiple SIDs with overdue.  
Steps: Enter SID; Apply.  
Expected: List filtered.

**STF-PAY-03 Mark Paid sets paid_at**  
Pre: Select one outstanding overdue row.  
Steps: “Mark Selected as PAID”; add optional note.  
Expected: Row disappears from list; CSV updated `status=paid`, `paid_at=now`, note appended.

**STF-PAY-04 Void outstanding**  
Steps: Void selected.  
Expected: `status=void`, `paid_at` empty, note appended; row disappears.

**STF-PAY-05 Cannot modify non-outstanding**  
Pre: Change one payment to `status=paid`.  
Steps: Try to mark it paid/void again via code path.  
Expected: Error “Only outstanding payments can be updated.”

**STF-PAY-06 Student unblocked after payment**  
Pre: Student blocked by overdue (outstanding).  
Steps: Mark that payment as **PAID**; login Student → Availability.  
Expected: Red banner gone; Reserve enabled.

---

## F. Staff — Inventory

**STF-INV-01 Inventory list loads**  
Steps: Open Inventory.  
Expected: All umbrellas listed, sorted by id.

**STF-INV-02 Add umbrella success**  
Steps: Add code `UMB999`; location “MainStation”.  
Expected: New row with `status=Available`; `updated_at` set.

**STF-INV-03 Add duplicate code (blocked)**  
Pre: Ensure `UMB999` exists.  
Steps: Add `UMB999` again.  
Expected: Error “Code already exists.”

**STF-INV-04 Set status persists**  
Steps: Select an umbrella; Set `Status=Maintenance`.  
Expected: Saved; list refresh shows new status & `updated_at`.

**STF-INV-05 Retired not available**  
Pre: Set an umbrella to `Retired`.  
Steps: Student → Availability.  
Expected: That umbrella **not shown** in available list.

---

## G. Reports (Current Build)

**REP-01 Inventory summary**  
Steps: Open Reports.  
Expected: Counts per umbrella status listed.

**REP-02 Active past-due list**  
Pre: Have **Active** reservations where `due_at < now` (use Time Travel).  
Steps: Refresh Reports.  
Expected: Those `Res#` lines appear under “Active Reservations Past Due”.

**REP-03 Outstanding payments list**  
Pre: Have various **outstanding** payments (any reason).  
Steps: Refresh Reports.  
Expected: They appear with `Pay#`, `SID`, `reservation_id`, `reason`, and formatted amount.

### G2. Reports — Weekly KPIs (Future / Optional)
If weekly analytics UI/helpers are added later, validate:

**REP-W-01 Weekly selector bounds**  
Steps: Set Weeks Back to 1; Refresh. Then set to 52; Refresh.  
Expected: Bounds enforced; UI responsive.

**REP-W-02 Weekly counts: reserved/checkout/returns**  
Pre: Create reservations with spaced `reserved_at`, `pickup_at`, `return_at` across weeks via Time Travel.  
Steps: Refresh.  
Expected: Each metric increments in the week of its own timestamp.

**REP-W-03 Weekly amounts by reason (created_at)**  
Pre: Create overdue/damaged/lost payments at known dates.  
Steps: Refresh.  
Expected: Sums appear in corresponding week rows.

**REP-W-04 Weekly Paid$ by paid_at**  
Pre: Mark some payments as paid with `paid_at` in specific week(s).  
Steps: Refresh.  
Expected: Paid$ totals reflect `paid_at` weeks, independent of `created_at`.

---

## H. Time Travel (Offset)

**TIME-01 Offset changes “Simulated now” label**  
Steps: Apply `+1h`, `+1d`, `-1d`, Reset.  
Expected: Label updates; no crash.

**TIME-02 Calendar window shifts with offset**  
Steps: Apply `+2d`; open Student calendar.  
Expected: Highlighted window is (offset today)..(offset today+6).

**TIME-03 Overdue detection via offset**  
Pre: Active reservation due at known datetime.  
Steps: Move offset past due by hours; Check-in.  
Expected: Overdue payment created with correct days (**ceil**).

---

## I. CSV & Utilities

**CSV-01 next_id increments correctly**  
Pre: `umbrellas.csv` with max id N.  
Steps: Add new umbrella.  
Expected: `id=N+1`.

**CSV-02 cents/dollars conversions**  
Steps: Convert `20.0 → 2000`; `2000 → HK$20.00`.  
Expected: Accurate (no floating surprises).

**CSV-03 Write then read roundtrip**  
Steps: Add a reservation; restart app.  
Expected: Data persists and loads identically.

---

## J. Negative / Edge Cases

**NEG-01 Empty inputs on actions**  
Steps: Staff → Click Checkout with empty fields.  
Expected: Warning “Enter SID and Umbrella ID/Code.”

**NEG-02 Nonexistent umbrella**  
Steps: Staff → Check-in with bogus code.  
Expected: “Umbrella not found.”

**NEG-03 Nonexistent student checkout**  
Steps: Staff → Checkout with invalid SID.  
Expected: “No Reserved record for this student and umbrella.”

**NEG-04 Reserve exactly 7 days**  
Steps: Start=today; End=today+6; Reserve.  
Expected: Success; `requested_days=7`.

**NEG-05 Overdue rounding behavior**  
Pre: `due_at` 23:59:59; return at `due+1 second`.  
Steps: Check-in.  
Expected: Overdue days = **1** (ceil behavior).

**NEG-06 Multiple payments visibility**  
Pre: One reservation generates overdue + damaged (late+damaged).  
Steps: Student → Payments; Staff → Payments.  
Expected: Both rows visible with correct reasons/amounts.

**NEG-07 Payment update error path**  
Pre: Select nothing; click **Mark Paid**.  
Expected: Warning “Select an overdue payment first.”

**NEG-08 Inventory with long note**  
Steps: Set long note via CSV edit; open Inventory.  
Expected: UI renders; no crash/truncation exception.

**NEG-09 Permission denied (manual)**  
Pre: Make `DATA_DIR` read-only.  
Steps: Try actions that write.  
Expected: Graceful error or OS error surfaced; app should not crash the whole process.

---

## K. Regression Guards (after future changes)

**REG-01 Student block logic**  
Pre: Outstanding **overdue** exists; no other debts.  
Steps: Student tries to reserve.  
Expected: Blocked (**only overdue** blocks, not paid/void or other reasons).

**REG-02 Start-date enforcement at checkout**  
Pre: Reserved starts tomorrow.  
Steps: Staff Checkout today.  
Expected: Blocked.

**REG-03 Close states mapping**  
Steps: Check-in `ok` → **Closed**; late `ok` → **Closed-Overdue**; `damaged` → **Closed-Damaged**; `lost` → **Closed-Lost**.  
Expected: Exact statuses.

**REG-04 Umbrella state transitions**  
Steps: Reserve → **Reserved**; Checkout → **InUse**; Check-in `ok` → **Available**; Check-in `damaged` → **Maintenance**; Lost → **Lost**.  
Expected: Exact transitions.

---

## L. Performance / UX (manual sanity)

**UX-01 List refresh responsiveness**  
Steps: Do actions (checkout/check-in/mark paid) and watch lists auto-refresh.  
Expected: Immediate update; no noticeable delay.

**UX-02 Scroll behavior with many rows**  
Pre: Seed >50 reservations; >50 payments.  
Steps: Navigate tabs, scroll trees.  
Expected: Smooth scrolling; no layout break.
