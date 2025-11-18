# Campus Umbrella Rental Service (CSV + Tkinter GUI)

A small Python GUI app (Tkinter) that simulates a campus umbrella rental service with **Student** and **Staff** roles.  
Data is stored in local **CSV files**. Includes a **Time Travel** bar to fast‑forward the simulated clock for testing.

---

## Features

- **Student**
  - Login with **SID / password** (stored as **plain text** in `students.csv`)
  - See **available umbrellas**
  - **Reserve** an umbrella for a date range **within the next 7 days** (calendar highlights allowed days)
  - Can have **only one** open reservation (Reserved/Active)
  - **Blocked** from reserving if any **overdue** payment is outstanding
  - View **My Status**, **History**, and **Payments**

- **Staff**
  - Login with **StaffID / password** (plain text in `staff.csv`)
  - **Front Desk** tab: auto‑loads **Reserved** and **Current In Use**; optional SID filter
  - One‑line **Actions**: **Checkout**, **Check‑in (ok / damaged)** with automatic fees, **Lost**
  - **Payments** tab: auto‑loads **Overdue (outstanding)**; optional SID filter; **Mark Paid / Void**
  - **Inventory** tab: list, add umbrella, set status
  - **Reports** tab: inventory snapshot, active past‑due list, outstanding payments
- **Testing helper**: **Time Travel** bar to offset “now” (hours/days)

> Notes
> - This version stores passwords in plain text to match project requirements. (Legacy files with a `pwd_hash` column are still accepted for login, but new seeds use `password`.)
> - Default fees: Overdue HK$20/day, Damaged HK$100 flat, Lost HK$300 flat.

---

## Requirements

- Python **3.9+** (tested with 3.12)
- Packages:
  - `tkcalendar` (for the date picker)

Tkinter ships with Python on Windows/macOS. On some Linux distros you may need `python3-tk`.

Install deps:

```bash
pip install tkcalendar
```

Optionally use a virtualenv:

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install tkcalendar
```

---

## Getting Started

1. **Place the script** in your project folder, e.g. `main.py`.

2. **Choose a data folder** for the CSV “database”.

   **By default the app uses ./Data_csv inside the project folder. You can still point elsewhere by setting UMBRELLA_DATA_DIR.**  
   from pathlib import Path
   BASE_DIR = Path(__file__).resolve().parent
   DATA_DIR = Path(os.getenv("UMBRELLA_DATA_DIR", str(BASE_DIR / "Data_csv"))).expanduser().resolve()

3. **Run the app**

   - **VS Code**: Open the folder → select Python interpreter → open the file → press **Run** or:
   - **Terminal**:
     ```bash
     # Windows Standard (no Time Travel UI):
     main.py
     # or, Dev (with Time Travel UI):
     python main.py --dev
     ```

4. **First Run – Seeding**  
   If the CSV files don’t exist, the app will create and seed them automatically in `DATA_DIR`.

5. **Login with default accounts**
   - **Student**: `SID = S123456`, `password = student123`
   - **Staff**: `ID  = T001`,     `password = staff123`

---

## Using the App

### Time Travel (top bar)
- Shows **Simulated now**.
- Enter **offset hours** (can be negative) and click **Apply**, or use **+1h / +1d / +7d / −1d / Reset**.
- Use this to test **overdues**, **returns**, etc.

### Student
1. **Availability & Reserve**
   - Calendar highlights the **next 7 days**. Click to pick **start** and **end** (two clicks).
   - Select an umbrella in the table → **Reserve Selected**.
   - You **cannot** reserve if you already have **Reserved/Active** or have **outstanding overdue** payments.
2. **My Status** — shows your current open reservation (if any) with key timestamps.
3. **History** — list of all your reservations (latest first).
4. **Payments** — shows overdue/damaged/lost fees and statuses (outstanding/paid/void).

### Staff

#### Front Desk
- **Reserved (Awaiting Pickup)** and **Current In Use** auto‑load.
- Optional **SID** filter (also pre‑fills SID in checkout/lost inputs).
- **Actions (single‑line)**:
  - **Checkout**: enter SID + Umbrella ID/Code → validates start date → sets status **Active** and `due_at` (end date 23:59:59).
  - **Check‑in**: enter Umbrella ID/Code + Condition (**ok**/**damaged**):
    - If **late**, the app creates an **overdue** payment (HK$20/day, ceil to whole days).
    - If **damaged**, the app creates a **damaged** fee (HK$100).
  - **Lost**: enter SID + Umbrella → records a **lost** fee (HK$300) & closes reservation.

#### Payments
- Auto‑shows **Overdue (outstanding)** payments.
- Optional **SID** filter.
- Select a row and **Mark Paid** or **Void** (updates CSV accordingly).

#### Inventory
- **Refresh**, **Add** (new code), **Set Status** of umbrellas.

#### Reports
- Shows:
  - **Inventory summary** by umbrella status
  - **Active reservations past due** (based on current simulated time)
  - **Outstanding payments** (all reasons)
- *(Weekly KPIs can be added later by extracting the aggregator logic into testable helpers.)*

---

## Data Model (CSV files)

Stored under `DATA_DIR`:

- `students.csv`  
  `sid,name,email,password,is_active,created_at`

- `staff.csv`  
  `staff_id,name,email,role,password,is_active,created_at`

- `umbrellas.csv`  
  `id,code,status,location,note,created_at,updated_at`  
  `status ∈ {Available, Reserved, InUse, Overdue, Maintenance, Lost, Retired}`

- `reservations.csv`  
  `id,sid,umbrella_id,status,reserved_at,pickup_at,due_at,return_at,close_reason,notes,requested_days,start_date,end_date`  
  `status ∈ {Reserved, Active, Closed, Closed-Overdue, Closed-Damaged, Closed-Lost}`

- `payments.csv`  
  `id,sid,reservation_id,reason,amount_cents,status,created_at,paid_at,note`  
  `reason ∈ {overdue, damaged, lost}`; `status ∈ {outstanding, paid, void}`

**Date/time format:** `YYYY-MM-DD HH:MM:SS` (local time, adjusted by Time Travel offset)

**Config constants:**  
`MAX_RENTAL_DAYS = 7`  
`FEE_OVERDUE_PER_DAY = 20.0`  
`FEE_DAMAGED_FLAT = 100.0`  
`FEE_LOST_FLAT = 300.0`

---

## Running Tests

From the project root (the folder that contains `main.py`):

```bash
python -m pytest -q
```

- The suite uses a temporary `UMBRELLA_DATA_DIR` per test (via `tests/conftest.py`).
- If VS Code cannot import the module, ensure you run pytest **from the project root** or keep the provided `conftest.py` (adds the parent of `tests/` to `sys.path`).

---

## Project Structure (suggested)

```
.
├─ main.py        # main script
├─ README.md
├─TEST_PLAN.md
├─TEST_DOCUMENTATION
├─ tests/                          # pytest suite (optional, for CI)
└─ Data_csv/                       # your DATA_DIR (can be anywhere)
   ├─ students.csv
   ├─ staff.csv
   ├─ umbrellas.csv
   ├─ reservations.csv
   └─ payments.csv
```

---

## Tips & Troubleshooting

- **Calendar missing / red warning** — install `tkcalendar`:
  ```bash
  pip install tkcalendar
  ```
- **Cannot write CSVs** — ensure `DATA_DIR` exists and you have permissions. The app will try to create it.
- **Changed schema?** — the app auto‑migrates `reservations.csv` to include `requested_days/start_date/end_date` if missing. If files are corrupted, delete the CSVs to re‑seed.
- **Env var not picked up** — after `setx` on Windows, **restart VS Code**.
- **Login fails** — confirm CSVs exist and that the seeded accounts match the passwords above. To reseed with plain‑text passwords, delete `students.csv` and `staff.csv` and rerun.

---

## License

MIT (or your choice).
