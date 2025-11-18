# Test Documentation — Campus Umbrella Rental Service (CSV + Tkinter GUI)

This document summarizes the key defects encountered, their root causes, applied fixes, and the verification/regression tests
performed for the Campus Umbrella Rental Service project.

> **Scope**: Python 3.12, Windows (VS Code Terminal), local CSV storage, Tkinter GUI, optional `tkcalendar`.

---

## 1) Environment & Context

- **Runtime**: Python 3.12 on Windows (VS Code terminal).
- **GUI**: Tkinter (+ optional `tkcalendar`).
- **Data storage**: CSVs in `DATA_DIR`, configurable via `UMBRELLA_DATA_DIR` env var **or** hard-coded default in code.
- **Default DATA_DIR** (example): `./Data_csv`.
- **Default credentials**:
  - Student: `S123456 / student123`
  - Staff: `T001 / staff123`

---

## 2) Incident Log

### INC-01 — Staff Login Crash (`TclError: bad window path name ".!frame.!staffui"`)

**Symptom**  
When logging in as Staff, the GUI raised:
```
_tkinter.TclError: bad window path name ".!frame.!staffui"
```
Stack pointed to `StaffUI.__init__` during creation of a child `ttk.Frame(self)`.

**Reproduction**  
1. Launch app.  
2. Choose **Staff** role on login screen.  
3. Enter valid credentials and click **Login**.  
4. Crash occurs immediately.

**Expected**  
Staff UI renders with **Front Desk** tab active.

**Diagnosis (Root Cause)**  
Tkinter error indicates that the **parent widget was destroyed** (or not yet fully realized) while constructing `StaffUI` children. This typically happens if the parent frame is cleared/destroyed and child widgets continue to pack into an invalidated path.

**Fix (Applied)**  
- Ensure a **fresh container** frame is created **after** clearing old widgets and used as the **stable** parent.  
- Avoid destroying the container while children are being constructed.  
- Keep `App._clear()` and `_on_login_success()` order consistent: create `container`, then child frames (`TimeBar`, `StaffUI`), **no concurrent destroy/pack** overlap.

**Verification**  
- Manual: login as **Staff**; UI loads `Front Desk` without error.
- Regression: Smoke-test launching UI (manual, Tkinter not headless-friendly for CI).

---

### INC-02 — `ModuleNotFoundError: No module named 'campus_rental_csv_gui'` (pytest)

**Symptom**  
Running `python -m pytest -q` failed to import the main module.

**Reproduction**  
1. Project tree had `tests/` alongside `campus_rental_csv_gui.py`.  
2. `pytest` invoked from inside `tests/` folder or VS Code mis-set working dir.

**Expected**  
Tests discover the module from project root.

**Fix (Applied)**  
- Added `tests/conftest.py` to prepend the **project root** to `sys.path`:
  ```python
  ROOT = pathlib.Path(__file__).resolve().parents[1]
  sys.path.insert(0, str(ROOT))
  ```
- Run `pytest` from **project root**.

**Verification**  
- `pytest` discovers and imports the module; tests run.

---

### INC-03 — Reservation Rule Messaging (Double Reserve)

**Symptom**  
Test expected block **“open reservation”**, but the app returned **“Umbrella is not available (status: Reserved).”**

**Reproduction**  
1. Student reserves umbrella for today.  
2. Student attempts **another** reservation while the first is still open.

**Expected**  
Block **because student already has an open reservation**, not because the umbrella is reserved: this yields clearer UX and stable business rule.

**Root Cause**  
`reserve_umbrella_range` checked **umbrella availability first**, then student’s open-reservation rule. Re-trying the same umbrella hit the *availability* branch first.

**Fix (Applied)**  
Reorder validation to:
1) `can_student_reserve(sid)` (check **open reservation / overdue**),  
2) then **umbrella availability** checks.

**Verification**  
- Unit test `test_double_reserve_blocked` now passes.
- Manual: UI shows banner/disabled button and consistent error message.

**Regression**  
- Student can still reserve **if** no open reservation and no overdue fees.

---

### INC-04 — Overdue Rounding Edge Case (+1 second past due)

**Symptom**  
`test_overdue_ceil_one_second` expected exactly **one overdue payment**, but none was created.

**Reproduction**  
1. Create **Active** reservation due at `23:59:59`.  
2. Fast-forward simulated time by **+1 second**.  
3. Check-in: expected overdue created (ceil to 1 day).

**Root Cause**  
`return_at` was formatted with **seconds precision** via `now_str()`. When adding +1s, computational clock might still result in a same-second string or rounding boundary, causing `ret <= due` comparison to pass, preventing overdue creation.

**Fix (Applied)**  
Use a **high-precision datetime** for comparison:
```python
ret_dt = now_dt()                # datetime with microseconds
res["return_at"] = ret_dt.strftime(DATE_FMT)  # store as string
if due_at and ret_dt > due_at:   # compare datetime objects
    days_over = ceil((ret_dt - due_at).total_seconds() / 86400.0)
    ...
```
**Verification**  
- Test `test_overdue_ceil_one_second` passes (1 overdue created).  
- Manual: late check-ins create overdue fee with day count = ceil(seconds/86400).

**Regression**  
- On-time check-in still creates **no** overdue; damaged/lost flows unaffected.

---

### INC-05 — Authentication Mode Change (Plain-Text Passwords)

**Change**  
Project requirement updated to **store passwords in plain text** in `students.csv` and `staff.csv`.

**Impacts**  
- CSV headers now include `password` (preferred) instead of `pwd_hash`.  
- Login functions check `password` first; legacy `pwd_hash` is **optional** (for backward compatibility).  
- Seeders updated to write `password` values.

**Verification**  
- Tests updated (`test_auth.py`) to assert plain-text presence and validate login success/failure.  
- Manual: default logins work as expected.

**Security Note**  
This is acceptable for a **local CSV demo**; **never** commit plain-text passwords in real systems.

---

## 3) Test Coverage Snapshot

### Unit / Functional (pytest)
- **Authentication**: student/staff success, wrong password, inactive account.
- **Reservation Rules**: calendar window, valid same-day & multi-day, range bounds, unavailable umbrella, duplicate reservation block, overdue block.
- **Staff Actions**: checkout rules (start date, no matching reserved), check-in ok/late/damaged, lost flow, double action guards.
- **Payments**: list outstanding overdue, filter, mark paid/void, settle rules, overdue blocks unblocking.
- **Inventory**: list, add, duplicate guard, status persist & not available when retired.
- **Time Helpers**: offset effects (overdue creation, “Simulated now”), ceil behavior.
- **CSV Utils**: `next_id`, cents↔dollars, read/write roundtrip.
- **Reports (current)**: inventory summary, active past-due, outstanding payments (weekly KPIs moved to future optional tests).

### Manual / UI
- Staff login rendering (INC-01).  
- Tab auto-refresh behaviors after actions.  
- Scrolling and large-list responsiveness.

---

## 4) How to Run Tests

From project **root** (folder containing `campus_rental_csv_gui.py`):
```bash
python -m pytest -q
```
- The suite uses an isolated temp `UMBRELLA_DATA_DIR` per test (see `tests/conftest.py`).
- If VS Code can’t import the module, ensure **you’re in the project root** or keep `conftest.py` that amends `sys.path`.

---

## 5) Open Risks & Follow-ups

- **Tkinter headless automation**: GUI tests are primarily manual; CI smoke tests cover only module imports and non-GUI logic.
- **Plain-text passwords**: acceptable for coursework demo; highlight in README and avoid publishing real data.
- **Weekly KPIs**: currently excluded from the UI; future work could enable deterministic aggregation helpers for unit tests.
- **Permissions**: read-only `DATA_DIR` or file locks may still throw OS-level errors; ensure try/catch surfaces user-friendly messages.

---

## 6) Appendix — Useful Commands

Create venv + install deps:
```bash
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install tkcalendar pytest
```

Run app:
```bash
python main.py
```

Set data dir (Windows PowerShell, current session):
```powershell
$env:UMBRELLA_DATA_DIR=".\Data_csv"
```

Reset seeds (delete CSVs in data dir, then relaunch).

---

**Last updated:** (see file timestamp)  
**Author:** Group 1
