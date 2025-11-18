# umbrella_app.py
# Campus Umbrella Rental Service (CSV + Tkinter GUI)
# - Student cannot reserve if: (a) they already have a Reserved/Active item, OR (b) they have outstanding OVERDUE payments
# - Student tab shows a red banner + disables Reserve button when blocked
# - Student picks a start/end within the next 7 days (highlighted on calendar)
# - Staff / Front Desk: Reserved + Current In Use + single-line Actions (Checkout / Check-in / Lost)
# - Staff / Payments: Outstanding Overdue list with SID filter + Mark Paid/Void
# - Staff / Reports: Weekly report with "Weeks Back" selector
# - Time Travel bar to fast-forward/rewind simulated time for testing
# - Standard (no Time Travel UI)
# python umbrella_app.py
# - Dev (with Time Travel UI)
# python umbrella_app.py --dev

import csv
import os
import hashlib
from datetime import datetime, timedelta, date
from math import ceil
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox, simpledialog

try:
    from tkcalendar import Calendar
except Exception:
    Calendar = None

APP_NAME = "Campus Umbrella Rental Service"

# Project root = folder that contains main.py
PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = PROJECT_ROOT / "Data_csv"

# Env var still wins; otherwise use ./Data_csv beside main.py
DATA_DIR = os.path.abspath(os.getenv("UMBRELLA_DATA_DIR", str(DEFAULT_DATA_DIR)))

MAX_RENTAL_DAYS = 7
DEFAULT_RENTAL_DAYS = 1
FEE_OVERDUE_PER_DAY = 20.0
FEE_DAMAGED_FLAT = 100.0
FEE_LOST_FLAT = 300.0

DATE_FMT = "%Y-%m-%d %H:%M:%S"
TIME_OFFSET_SECONDS = 0  # “Time Travel” offset

STUDENTS_CSV      = os.path.join(DATA_DIR, "students.csv")
STAFF_CSV         = os.path.join(DATA_DIR, "staff.csv")
UMBRELLAS_CSV     = os.path.join(DATA_DIR, "umbrellas.csv")
RESERVATIONS_CSV  = os.path.join(DATA_DIR, "reservations.csv")
PAYMENTS_CSV      = os.path.join(DATA_DIR, "payments.csv")

STUDENTS_HEADERS = ["sid", "name", "email", "password", "is_active", "created_at"]
STAFF_HEADERS    = ["staff_id", "name", "email", "role", "password", "is_active", "created_at"]
UMBRELLAS_HEADERS= ["id", "code", "status", "location", "note", "created_at", "updated_at"]
RESERVATIONS_HEADERS = [
    "id","sid","umbrella_id","status",
    "reserved_at","pickup_at","due_at","return_at",
    "close_reason","notes","requested_days","start_date","end_date"
]
PAYMENTS_HEADERS = ["id","sid","reservation_id","reason","amount_cents","status","created_at","paid_at","note"]

UMBRELLA_STATUSES = ["Available","Reserved","InUse","Overdue","Maintenance","Lost","Retired"]
RESERVATION_STATUSES = ["Reserved","Active","Closed","Closed-Overdue","Closed-Damaged","Closed-Lost"]
PAYMENT_STATUSES = ["outstanding","paid","void"]

# ---------------- Time helpers ----------------
def now_dt() -> datetime:
    return datetime.now() + timedelta(seconds=TIME_OFFSET_SECONDS)

def now_str() -> str:
    return now_dt().strftime(DATE_FMT)

def parse_dt(s: str):
    if not s:
        return None
    return datetime.strptime(s, DATE_FMT)

def set_time_offset_seconds(sec: int):
    global TIME_OFFSET_SECONDS
    TIME_OFFSET_SECONDS = sec

def add_time_offset(delta: timedelta):
    global TIME_OFFSET_SECONDS
    TIME_OFFSET_SECONDS += int(delta.total_seconds())

def offset_human():
    s = TIME_OFFSET_SECONDS
    sign = "-" if s < 0 else "+"
    s = abs(s)
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, _  = divmod(rem, 60)
    if d: return f"{sign}{d}d {h}h {m}m"
    if h: return f"{sign}{h}h {m}m"
    if m: return f"{sign}{m}m"
    return "0"

# ===== Weekly helpers =====
def start_of_week(d):
    """Return the Monday (date) of the week for a date or datetime."""
    if isinstance(d, datetime):
        d = d.date()
    return d - timedelta(days=d.weekday())

def week_key_from_dt(dt):
    """Return the Monday date (date object) for a datetime; None if dt is None."""
    if not dt:
        return None
    return start_of_week(dt.date())

def week_label(week_start_date):
    """Pretty label for a week start (date)."""
    iso = week_start_date.isocalendar()  # (year, week, weekday)
    return f"{week_start_date.isoformat()}  [ISO {iso[0]}-W{iso[1]:02d}]"

# ---------------- CSV helpers ----------------
def ensure_data_dir_and_seed():
    os.makedirs(DATA_DIR, exist_ok=True)

    if not os.path.exists(STUDENTS_CSV):
        write_csv(STUDENTS_CSV, STUDENTS_HEADERS, [{
            "sid": "S123456",
            "name": "Alice Student",
            "email": "alice.student@example.edu",
            "password": "student123",
            "is_active": "1",
            "created_at": now_str(),
        }])

    if not os.path.exists(STAFF_CSV):
        write_csv(STAFF_CSV, STAFF_HEADERS, [{
            "staff_id": "T001",
            "name": "Bob Staff",
            "email": "bob.staff@example.edu",
            "role": "clerk",
            "password": "staff123",
            "is_active": "1",
            "created_at": now_str(),
        }])

    if not os.path.exists(UMBRELLAS_CSV):
        rows = []
        for i in range(1, 7):
            rows.append({
                "id": str(i),
                "code": f"UMB{i:03d}",
                "status": "Available",
                "location": "MainStation",
                "note": "",
                "created_at": now_str(),
                "updated_at": now_str(),
            })
        write_csv(UMBRELLAS_CSV, UMBRELLAS_HEADERS, rows)

    if not os.path.exists(RESERVATIONS_CSV):
        write_csv(RESERVATIONS_CSV, RESERVATIONS_HEADERS, [])
    else:
        _migrate_reservations_columns()

    if not os.path.exists(PAYMENTS_CSV):
        write_csv(PAYMENTS_CSV, PAYMENTS_HEADERS, [])

def _migrate_reservations_columns():
    with open(RESERVATIONS_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        existing = reader.fieldnames or []
    changed = False
    for col in ["requested_days","start_date","end_date"]:
        if col not in existing:
            for r in rows:
                r[col] = "1" if col == "requested_days" else ""
            changed = True
    if changed:
        write_csv(RESERVATIONS_CSV, RESERVATIONS_HEADERS, rows)

def read_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))

def write_csv(path, headers, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        for r in rows:
            w.writerow(r)

def append_csv(path, headers, row):
    exists = os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not exists:
            w.writeheader()
        w.writerow(row)

def next_id(rows, id_key="id"):
    mx = 0
    for r in rows:
        try:
            mx = max(mx, int(r.get(id_key, 0)))
        except ValueError:
            pass
    return str(mx + 1)

# ---------------- Utils ----------------
def hash_password(pwd: str) -> str:
    return hashlib.sha256(pwd.encode("utf-8")).hexdigest()

def dollars_to_cents(x: float) -> int:
    return int(round(x * 100))

def cents_to_str(cents: int) -> str:
    return f"HK${cents / 100:.2f}"

# ---------------- Domain lookups ----------------
def find_student(sid):
    return next((s for s in read_csv(STUDENTS_CSV) if s["sid"] == sid), None)

def find_staff(staff_id):
    return next((s for s in read_csv(STAFF_CSV) if s["staff_id"] == staff_id), None)

def get_umbrella_by_id_or_code(val):
    val = str(val)
    for r in read_csv(UMBRELLAS_CSV):
        if r["id"] == val or r["code"] == val:
            return r
    return None

def save_umbrella(updated):
    rows = read_csv(UMBRELLAS_CSV)
    for i, r in enumerate(rows):
        if r["id"] == updated["id"]:
            rows[i] = updated
            break
    write_csv(UMBRELLAS_CSV, UMBRELLAS_HEADERS, rows)

def list_available_umbrellas():
    return [u for u in read_csv(UMBRELLAS_CSV) if u["status"] == "Available"]

def list_student_reservations(sid):
    return [r for r in read_csv(RESERVATIONS_CSV) if r["sid"] == sid]

def list_student_open_reservations(sid):
    return [r for r in list_student_reservations(sid) if r["status"] in ("Reserved","Active")]

def list_reserved_reservations(sid_filter=None):
    rows = [r for r in read_csv(RESERVATIONS_CSV) if r["status"] == "Reserved"]
    if sid_filter:
        rows = [r for r in rows if r["sid"] == sid_filter]
    return rows

def list_active_reservations(sid_filter=None):
    rows = [r for r in read_csv(RESERVATIONS_CSV) if r["status"] == "Active"]
    if sid_filter:
        rows = [r for r in rows if r["sid"] == sid_filter]
    return rows

def list_outstanding_overdue_payments(sid_filter=None):
    rows = [p for p in read_csv(PAYMENTS_CSV) if p["status"] == "outstanding" and p["reason"] == "overdue"]
    if sid_filter:
        rows = [p for p in rows if p["sid"] == sid_filter]
    return rows

def list_student_payments(sid, status=None):
    rows = [p for p in read_csv(PAYMENTS_CSV) if p["sid"] == sid]
    return [p for p in rows if (status is None or p["status"] == status)]

def student_has_outstanding_overdue(sid) -> bool:
    """Only block on OVERDUE bills (per your request)."""
    return any(
        p["status"] == "outstanding" and p["reason"] == "overdue"
        for p in list_student_payments(sid)
    )

def save_reservation(updated):
    rows = read_csv(RESERVATIONS_CSV)
    for i, r in enumerate(rows):
        if r["id"] == updated["id"]:
            rows[i] = updated
            break
    write_csv(RESERVATIONS_CSV, RESERVATIONS_HEADERS, rows)

def add_reservation(rec):
    rows = read_csv(RESERVATIONS_CSV)
    rec["id"] = next_id(rows, "id")
    append_csv(RESERVATIONS_CSV, RESERVATIONS_HEADERS, rec)
    return rec["id"]

def add_payment(sid, reservation_id, reason, amount_cents, note=""):
    rows = read_csv(PAYMENTS_CSV)
    rec = {
        "id": next_id(rows, "id"),
        "sid": sid,
        "reservation_id": str(reservation_id),
        "reason": reason,
        "amount_cents": str(amount_cents),
        "status": "outstanding",
        "created_at": now_str(),
        "paid_at": "",
        "note": note,
    }
    append_csv(PAYMENTS_CSV, PAYMENTS_HEADERS, rec)
    return rec

def settle_payment(payment_id: str, new_status: str, note_append: str = ""):
    rows = read_csv(PAYMENTS_CSV)
    updated = False
    for r in rows:
        if r["id"] == str(payment_id):
            if r["status"] != "outstanding":
                raise ValueError("Only outstanding payments can be updated.")
            if new_status not in ("paid","void"):
                raise ValueError("new_status must be 'paid' or 'void'.")
            r["status"] = new_status
            r["paid_at"] = now_str() if new_status == "paid" else ""
            if note_append:
                r["note"] = (r.get("note","") + f" | {note_append}").strip(" |")
            updated = True
            break
    if not updated:
        raise ValueError("Payment not found.")
    write_csv(PAYMENTS_CSV, PAYMENTS_HEADERS, rows)
    return True

# ---------------- Business logic ----------------
def login_student(sid, pwd):
    s = find_student(sid)
    if not s or s.get("is_active") != "1":
        return None

    # Preferred: plain-text column
    if "password" in s and s["password"] != "":
        return s if s["password"] == pwd else None

    return None


def login_staff(staff_id, pwd):
    s = find_staff(staff_id)
    if not s or s.get("is_active") != "1":
        return None

    # Preferred: plain-text column
    if "password" in s and s["password"] != "":
        return s if s["password"] == pwd else None

    return None


def can_student_reserve(sid):
    if student_has_outstanding_overdue(sid):
        return False, "You have outstanding overdue payments."
    if list_student_open_reservations(sid):
        return False, "You already have an open reservation."
    return True, ""

def reserve_umbrella_range(sid, umbrella_id_or_code, start_d: date, end_d: date):
    # Must be within next 7 days (inclusive)
    today = now_dt().date()
    allowed_end = today + timedelta(days=6)
    if start_d < today or end_d < start_d or end_d > allowed_end:
        return False, "Dates must be within the next 7 days and end >= start."

    # 🔁 MOVE THIS UP: check student eligibility first
    ok, reason = can_student_reserve(sid)
    if not ok:
        return False, reason

    # Then check umbrella
    umbrella = get_umbrella_by_id_or_code(umbrella_id_or_code)
    if not umbrella:
        return False, "Umbrella not found."
    if umbrella["status"] != "Available":
        return False, f"Umbrella is not available (status: {umbrella['status']})."

    requested_days = (end_d - start_d).days + 1
    if requested_days > MAX_RENTAL_DAYS:
        return False, f"Max rental is {MAX_RENTAL_DAYS} days."

    res_id = add_reservation({
        "sid": sid,
        "umbrella_id": umbrella["id"],
        "status": "Reserved",
        "reserved_at": now_str(),
        "pickup_at": "",
        "due_at": "",
        "return_at": "",
        "close_reason": "",
        "notes": "",
        "requested_days": str(requested_days),
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
    })
    umbrella["status"] = "Reserved"
    umbrella["updated_at"] = now_str()
    save_umbrella(umbrella)
    return True, f"Reserved #{res_id} from {start_d.isoformat()} to {end_d.isoformat()} ({requested_days} day(s))."

def staff_checkout(sid, umbrella_id_or_code, staff_id):
    umbrella = get_umbrella_by_id_or_code(umbrella_id_or_code)
    if not umbrella:
        return False, "Umbrella not found."
    res = next((r for r in read_csv(RESERVATIONS_CSV)
                if r["sid"] == sid and r["umbrella_id"] == umbrella["id"] and r["status"] == "Reserved"), None)
    if not res:
        return False, "No Reserved record for this student and umbrella."

    # Enforce start_date window
    start_iso = res.get("start_date") or ""
    end_iso   = res.get("end_date")   or ""
    try:
        start_d = date.fromisoformat(start_iso) if start_iso else now_dt().date()
        end_d   = date.fromisoformat(end_iso)   if end_iso   else start_d
    except Exception:
        start_d = now_dt().date()
        end_d   = start_d

    if now_dt().date() < start_d:
        return False, f"Pickup not allowed before start date ({start_d.isoformat()})."

    # Activate
    res["status"] = "Active"
    res["pickup_at"] = now_str()
    due_dt = datetime.combine(end_d, datetime.max.time()).replace(hour=23, minute=59, second=59, microsecond=0)
    res["due_at"] = due_dt.strftime(DATE_FMT)
    save_reservation(res)

    umbrella["status"] = "InUse"
    umbrella["updated_at"] = now_str()
    save_umbrella(umbrella)

    return True, f"Checked out. Due at {res['due_at']}."

def staff_checkin(umbrella_id_or_code, condition, staff_id):
    umbrella = get_umbrella_by_id_or_code(umbrella_id_or_code)
    if not umbrella:
        return False, "Umbrella not found."
    res = next((r for r in read_csv(RESERVATIONS_CSV)
                if r["umbrella_id"] == umbrella["id"] and r["status"] == "Active"), None)
    if not res:
        return False, "No Active reservation found for this umbrella."

    res["return_at"] = now_str()

    # Overdue?
    overdue_payment = None
    due_at = parse_dt(res["due_at"])
    ret_at = parse_dt(res["return_at"])
    if due_at and ret_at and ret_at > due_at:
        days_over = ceil((ret_at - due_at).total_seconds() / 86400.0)
        amount = dollars_to_cents(days_over * FEE_OVERDUE_PER_DAY)
        overdue_payment = add_payment(res["sid"], res["id"], "overdue", amount, note=f"{days_over} day(s) overdue")

    if condition == "damaged":
        add_payment(res["sid"], res["id"], "damaged", dollars_to_cents(FEE_DAMAGED_FLAT))
        umbrella["status"] = "Maintenance"
        res["status"] = "Closed-Damaged"
        res["close_reason"] = "damaged"
    else:
        umbrella["status"] = "Available"
        res["status"] = "Closed" if not overdue_payment else "Closed-Overdue"
        res["close_reason"] = "returned"

    save_reservation(res)
    umbrella["updated_at"] = now_str()
    save_umbrella(umbrella)

    msg = "Check-in completed."
    if overdue_payment:
        msg += f" Overdue fee: {cents_to_str(int(overdue_payment['amount_cents']))}."
    if condition == "damaged":
        msg += f" Damaged fee: {cents_to_str(dollars_to_cents(FEE_DAMAGED_FLAT))}."
    return True, msg

def staff_mark_lost(sid, umbrella_id_or_code, staff_id):
    umbrella = get_umbrella_by_id_or_code(umbrella_id_or_code)
    if not umbrella:
        return False, "Umbrella not found."
    res = next((r for r in read_csv(RESERVATIONS_CSV)
                if r["umbrella_id"] == umbrella["id"] and r["sid"] == sid and r["status"] == "Active"), None)
    if not res:
        return False, "No Active reservation found for this student and umbrella."
    add_payment(sid, res["id"], "lost", dollars_to_cents(FEE_LOST_FLAT))
    res["status"] = "Closed-Lost"
    res["return_at"] = now_str()
    res["close_reason"] = "lost"
    save_reservation(res)
    umbrella["status"] = "Lost"
    umbrella["updated_at"] = now_str()
    save_umbrella(umbrella)
    return True, "Marked as lost and fee recorded."

# ---------------- Tkinter GUI ----------------
class App(tk.Tk):
    def __init__(self, dev_mode: bool = False):
        super().__init__()
        self.dev_mode = dev_mode
        self.title(APP_NAME)
        self.geometry("1180x780")
        self.resizable(True, True)
        self._show_login()

    def _clear(self):
        for w in self.winfo_children():
            w.destroy()

    def _show_login(self):
        self._clear()
        LoginFrame(self, on_login=self._on_login_success).pack(fill="both", expand=True)

    def _on_login_success(self, role, user):
        self._clear()
        container = ttk.Frame(self); container.pack(fill="both", expand=True)

        # Show Time Travel bar only in --dev mode
        if self.dev_mode:
            TimeBar(container, on_time_changed=lambda: self._refresh_child(container)).pack(fill="x")

        if role == "student":
            StudentUI(container, user, on_logout=self._show_login).pack(fill="both", expand=True)
        else:
            # pass dev flag to StaffUI so reports can change their header line
            StaffUI(container, user, on_logout=self._show_login, dev_mode=self.dev_mode).pack(fill="both", expand=True)

    def _refresh_child(self, container: ttk.Frame):
        for child in container.winfo_children():
            if hasattr(child, "refresh_all"):
                try: child.refresh_all()
                except Exception: pass
                break

class TimeBar(ttk.LabelFrame):
    def __init__(self, master, on_time_changed):
        super().__init__(master, text="Time Travel (Test Only)")
        self.on_time_changed = on_time_changed
        self.lbl_now = ttk.Label(self, text=self._now_text()); self.lbl_now.pack(side="left", padx=8, pady=6)
        ttk.Label(self, text="Offset hours (±):").pack(side="left", padx=(10,4))
        self.var_hours = tk.StringVar(value="0")
        ttk.Entry(self, textvariable=self.var_hours, width=6).pack(side="left", padx=2)
        ttk.Button(self, text="Apply", command=self._apply_hours).pack(side="left", padx=4)
        ttk.Button(self, text="+1h", command=lambda: self._bump(hours=1)).pack(side="left", padx=2)
        ttk.Button(self, text="+1d", command=lambda: self._bump(days=1)).pack(side="left", padx=2)
        ttk.Button(self, text="+7d", command=lambda: self._bump(days=7)).pack(side="left", padx=2)
        ttk.Button(self, text="-1d", command=lambda: self._bump(days=-1)).pack(side="left", padx=2)
        ttk.Button(self, text="Reset", command=self._reset).pack(side="left", padx=8)

    def _now_text(self):
        return f"Simulated now: {now_str()} (offset {offset_human()})"
    def _apply_hours(self):
        try:
            hours = float(self.var_hours.get().strip())
        except ValueError:
            messagebox.showerror("Invalid", "Enter a number of hours (can be negative)."); return
        set_time_offset_seconds(int(hours * 3600))
        self.lbl_now.config(text=self._now_text())
        if self.on_time_changed: self.on_time_changed()
    def _bump(self, days=0, hours=0):
        add_time_offset(timedelta(days=days, hours=hours))
        self.lbl_now.config(text=self._now_text())
        if self.on_time_changed: self.on_time_changed()
    def _reset(self):
        set_time_offset_seconds(0)
        self.lbl_now.config(text=self._now_text())
        if self.on_time_changed: self.on_time_changed()

class LoginFrame(ttk.Frame):
    def __init__(self, master, on_login):
        super().__init__(master, padding=20)
        self.on_login = on_login
        self.role_var = tk.StringVar(value="student")
        self.id_var = tk.StringVar()
        self.pw_var = tk.StringVar()

        ttk.Label(self, text=APP_NAME, font=("Segoe UI", 16, "bold")).pack(pady=(0, 16))
        ttk.Label(self, text=f"Data folder: {DATA_DIR}", foreground="#666").pack(pady=(0, 6))

        rb = ttk.Frame(self); rb.pack(pady=8)
        ttk.Radiobutton(rb, text="Student", variable=self.role_var, value="student", command=self._update_label).pack(side="left", padx=8)
        ttk.Radiobutton(rb, text="Staff",   variable=self.role_var, value="staff",   command=self._update_label).pack(side="left", padx=8)

        form = ttk.Frame(self); form.pack(pady=12)
        self.id_label = ttk.Label(form, text="SID"); self.id_label.grid(row=0, column=0, sticky="e", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.id_var, width=30).grid(row=0, column=1, padx=6, pady=6)
        ttk.Label(form, text="Password").grid(row=1, column=0, sticky="e", padx=6, pady=6)
        ttk.Entry(form, textvariable=self.pw_var, show="*", width=30).grid(row=1, column=1, padx=6, pady=6)

        ttk.Button(self, text="Login", command=self._login).pack(pady=10)
        ttk.Label(self, text="Default accounts:\nStudent SID=S123456 / password=student123\nStaff   ID =T001    / password=staff123",
                  foreground="#555").pack(pady=6)

        self.columnconfigure(0, weight=1)
        self._update_label()

    def _update_label(self):
        self.id_label.config(text="SID" if self.role_var.get() == "student" else "Staff ID")

    def _login(self):
        role = self.role_var.get()
        uid = self.id_var.get().strip()
        pw  = self.pw_var.get().strip()
        if not uid or not pw:
            messagebox.showerror("Error", "Please enter ID and password."); return
        user = login_student(uid, pw) if role == "student" else login_staff(uid, pw)
        if not user:
            messagebox.showerror("Error", "Invalid credentials or inactive account."); return
        self.on_login(role, user)

# ---------------- Student UI ----------------
class StudentUI(ttk.Frame):
    def __init__(self, master, user, on_logout):
        super().__init__(master, padding=10)
        self.user = user
        self.on_logout = on_logout
        self.range_start = None
        self.range_end = None

        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text=f"Logged in as Student: {user['sid']} - {user['name']}", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self.on_logout).pack(side="right")

        self.tabs = ttk.Notebook(self); self.tabs.pack(fill="both", expand=True, pady=10)

        self.tab_avail = ttk.Frame(self.tabs); self.tabs.add(self.tab_avail, text="Availability & Reserve")
        self.tab_status= ttk.Frame(self.tabs); self.tabs.add(self.tab_status, text="My Status")
        self.tab_hist  = ttk.Frame(self.tabs); self.tabs.add(self.tab_hist,   text="History")
        self.tab_pay   = ttk.Frame(self.tabs); self.tabs.add(self.tab_pay,    text="Payments")

        # Availability + Reserve
        if Calendar is None:
            ttk.Label(self.tab_avail, text="tkcalendar is required. Install: pip install tkcalendar", foreground="red").pack(pady=8)

        ctrl = ttk.Frame(self.tab_avail); ctrl.pack(fill="x", pady=(8,4))
        ttk.Button(ctrl, text="Refresh umbrellas", command=self.refresh_avail).pack(side="left", padx=4)
        self.lbl_hint = ttk.Label(ctrl, text="", foreground="#555"); self.lbl_hint.pack(side="left", padx=12)
        self.lbl_block = ttk.Label(ctrl, text="", foreground="#b00"); self.lbl_block.pack(side="right", padx=8)

        cal_frame = ttk.LabelFrame(self.tab_avail, text="Choose Start & End (click twice)")
        cal_frame.pack(side="left", fill="y", padx=6, pady=6)
        if Calendar is not None:
            self.cal = Calendar(cal_frame, selectmode="day", date_pattern="yyyy-mm-dd")
            self.cal.pack(padx=6, pady=6)
            self.cal.bind("<<CalendarSelected>>", self._on_calendar_select)
        else:
            self.cal = None

        sel_frame = ttk.LabelFrame(self.tab_avail, text="Selected Range")
        sel_frame.pack(side="left", fill="y", padx=6, pady=6)
        self.lbl_start = ttk.Label(sel_frame, text="Start: -"); self.lbl_start.pack(anchor="w", padx=6, pady=4)
        self.lbl_end   = ttk.Label(sel_frame, text="End:   -"); self.lbl_end.pack(anchor="w", padx=6, pady=4)
        ttk.Button(sel_frame, text="Clear selection", command=self._clear_selection).pack(padx=6, pady=6)

        right = ttk.Frame(self.tab_avail); right.pack(side="left", fill="both", expand=True, padx=6, pady=6)
        self.tree_avail = make_tree(right, ["id","code","status","location","note"])
        self.tree_avail.pack(fill="both", expand=True, pady=6)
        self.btn_reserve = ttk.Button(right, text="Reserve Selected (use chosen dates)", command=self.reserve_selected)
        self.btn_reserve.pack(anchor="w", padx=4, pady=4)
        ttk.Label(right, text="Note: Pickup and return are handled at Main Station by staff.", foreground="#555").pack(anchor="w", padx=6, pady=(0,6))

        # My status
        self.status_text = tk.Text(self.tab_status, height=10); self.status_text.pack(fill="both", expand=True, pady=6)

        # History
        self.tree_hist = make_tree(self.tab_hist, ["id","umbrella_id","status","start_date","end_date","reserved_at","pickup_at","due_at","return_at","requested_days","close_reason"])
        self.tree_hist.pack(fill="both", expand=True, pady=6)
        ttk.Button(self.tab_hist, text="Refresh", command=self.refresh_history).pack(anchor="w", padx=4, pady=4)

        # Payments
        self.tree_pay = make_tree(self.tab_pay, ["id","reason","amount","status","created_at","paid_at","note"])
        self.tree_pay.pack(fill="both", expand=True, pady=6)
        ttk.Button(self.tab_pay, text="Refresh", command=self.refresh_payments).pack(anchor="w", padx=4, pady=4)

        self.refresh_all()

    def refresh_all(self):
        self._refresh_calendar_hint_and_highlight()
        self._update_reserve_banner_and_button()
        self.refresh_avail()
        self.refresh_status()
        self.refresh_history()
        self.refresh_payments()

    def _refresh_calendar_hint_and_highlight(self):
        today = now_dt().date()
        allowed_end = today + timedelta(days=6)
        self.lbl_hint.config(text=f"Allowed window: {today.isoformat()} … {allowed_end.isoformat()} (7 days)")
        if self.cal is not None:
            self.cal.calevent_remove('all')
            d = today
            while d <= allowed_end:
                self.cal.calevent_create(d, "Allowed", "allowed")
                d += timedelta(days=1)
            self.cal.tag_config("allowed", background="#d4f7d0", foreground="black")

    def _update_reserve_banner_and_button(self):
        ok, reason = can_student_reserve(self.user["sid"])
        if ok:
            self.lbl_block.config(text="", foreground="#0a0")
            self.btn_reserve.config(state="normal")
        else:
            self.lbl_block.config(text=f"Reservation blocked: {reason}", foreground="#b00")
            self.btn_reserve.config(state="disabled")

    def _clear_selection(self):
        self.range_start = None
        self.range_end = None
        self.lbl_start.config(text="Start: -")
        self.lbl_end.config(text="End:   -")

    def _on_calendar_select(self, _evt):
        if self.cal is None:
            return
        sel = self.cal.get_date()
        try:
            d = date.fromisoformat(sel)
        except Exception:
            return
        today = now_dt().date()
        allowed_end = today + timedelta(days=6)
        if not (today <= d <= allowed_end):
            messagebox.showerror("Invalid date", "Please pick within the next 7 days."); return
        if self.range_start is None or (self.range_start is not None and self.range_end is not None):
            self.range_start = d
            self.range_end = None
            self.lbl_start.config(text=f"Start: {d.isoformat()}")
            self.lbl_end.config(text="End:   -")
        else:
            if d < self.range_start:
                messagebox.showerror("Invalid range", "End date must be on/after start date.")
                return
            self.range_end = d
            self.lbl_end.config(text=f"End:   {d.isoformat()}")

    def refresh_avail(self):
        rows = list_available_umbrellas()
        fill_tree(self.tree_avail, rows, fmt=lambda r: [r["id"], r["code"], r["status"], r["location"], r["note"]])

    def reserve_selected(self):
        ok, reason = can_student_reserve(self.user["sid"])
        if not ok:
            messagebox.showerror("Reservation blocked", reason)
            self._update_reserve_banner_and_button()
            return
        if self.range_start is None or self.range_end is None:
            messagebox.showwarning("Pick dates", "Click the calendar to choose start and end dates."); return
        sel = self.tree_avail.selection()
        if not sel:
            messagebox.showwarning("Select", "Please select an umbrella to reserve."); return
        umb_id = self.tree_avail.item(sel[0])["values"][0]
        ok, msg = reserve_umbrella_range(self.user["sid"], umb_id, self.range_start, self.range_end)
        (messagebox.showinfo if ok else messagebox.showerror)("Reservation", msg)
        if ok:
            self._clear_selection()
        self.refresh_all()

    def refresh_status(self):
        sid = self.user["sid"]
        open_res = list_student_open_reservations(sid)
        self.status_text.delete("1.0", "end")
        if not open_res:
            self.status_text.insert("end", "No open reservation.\n")
        else:
            for r in open_res:
                um = get_umbrella_by_id_or_code(r["umbrella_id"]) or {"code": "?"}
                req_days = r.get("requested_days") or str(DEFAULT_RENTAL_DAYS)
                self.status_text.insert("end",
                    f"Reservation #{r['id']} — Umbrella {um['code']}\n"
                    f"Status: {r['status']}   Requested: {req_days} day(s)\n"
                    f"Start:    {r.get('start_date','-')}   End: {r.get('end_date','-')}\n"
                    f"Reserved: {r['reserved_at']}\n"
                    f"Pickup:   {r['pickup_at'] or '-'}\n"
                    f"Due:      {r['due_at'] or '-'}\n\n"
                )

    def refresh_history(self):
        rows = sorted(list_student_reservations(self.user["sid"]), key=lambda x: x["reserved_at"], reverse=True)
        def fmt(r):
            return [
                r["id"], r["umbrella_id"], r["status"],
                r.get("start_date",""), r.get("end_date",""),
                r["reserved_at"], r["pickup_at"], r["due_at"], r["return_at"],
                r.get("requested_days",""), r["close_reason"]
            ]
        fill_tree(self.tree_hist, rows, fmt=fmt)

    def refresh_payments(self):
        pays = list_student_payments(self.user["sid"])
        fill_tree(self.tree_pay, pays, fmt=lambda p: [p["id"], p["reason"], cents_to_str(int(p["amount_cents"])), p["status"], p["created_at"], p["paid_at"], p["note"]])

# ---------------- Staff UI (Front Desk / Payments / Inventory / Reports) ----------------
class StaffUI(ttk.Frame):
    def __init__(self, master, user, on_logout, dev_mode: bool = False):
        super().__init__(master, padding=10)
        self.dev_mode = dev_mode
        self.user = user
        self.on_logout = on_logout  # <-- FIX: store callback, do NOT call it

        top = ttk.Frame(self); top.pack(fill="x")
        ttk.Label(top, text=f"Logged in as Staff: {user['staff_id']} - {user['name']}", font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self.on_logout).pack(side="right")

        self.tabs = ttk.Notebook(self); self.tabs.pack(fill="both", expand=True, pady=10)
        self.tab_desk = ttk.Frame(self.tabs); self.tabs.add(self.tab_desk, text="Front Desk")
        self.tab_pay  = ttk.Frame(self.tabs); self.tabs.add(self.tab_pay,  text="Payments")
        self.tab_inv  = ttk.Frame(self.tabs); self.tabs.add(self.tab_inv,  text="Inventory")
        self.tab_rep  = ttk.Frame(self.tabs); self.tabs.add(self.tab_rep,  text="Reports")

        self._build_desk_tab()
        self._build_payments_tab()
        self._build_inventory_tab()
        self._build_reports_tab()

        self.load_frontdesk_views()
        self.load_payment_views()

    def refresh_all(self):
        self.load_frontdesk_views()
        self.load_payment_views()
        self.refresh_inventory()
        self.refresh_reports()

    # Front Desk
    def _build_desk_tab(self):
        grp_filter = ttk.LabelFrame(self.tab_desk, text="Filter (SID)")
        grp_filter.pack(fill="x", padx=6, pady=6)
        self.filter_sid_var = tk.StringVar()
        ttk.Label(grp_filter, text="SID (leave empty = all)").pack(side="left", padx=6, pady=6)
        ttk.Entry(grp_filter, textvariable=self.filter_sid_var, width=20).pack(side="left", padx=6, pady=6)
        ttk.Button(grp_filter, text="Apply Filter", command=self.load_frontdesk_views).pack(side="left", padx=6, pady=6)
        ttk.Button(grp_filter, text="Clear", command=lambda: (self.filter_sid_var.set(""), self.load_frontdesk_views())).pack(side="left", padx=6, pady=6)

        grp_res = ttk.LabelFrame(self.tab_desk, text="Reserved (Awaiting Pickup)")
        grp_res.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self.tree_reserved = make_tree(grp_res, ["id","sid","umbrella_id","start_date","end_date","reserved_at"])
        self.tree_reserved.pack(fill="both", expand=True, pady=6)

        grp_active = ttk.LabelFrame(self.tab_desk, text="Current In Use (Active)")
        grp_active.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self.tree_active = make_tree(grp_active, ["id","sid","umbrella_id","pickup_at","due_at"])
        self.tree_active.pack(fill="both", expand=True, pady=6)

        grp_actions = ttk.LabelFrame(self.tab_desk, text="Actions (single-line)")
        grp_actions.pack(fill="x", padx=6, pady=(0,6))
        row = ttk.Frame(grp_actions); row.pack(fill="x", padx=6, pady=6)

        # Checkout
        self.checkout_sid_var = tk.StringVar(); self.checkout_umb_var = tk.StringVar()
        ttk.Label(row, text="Checkout — SID").pack(side="left", padx=(0,4))
        ttk.Entry(row, textvariable=self.checkout_sid_var, width=14).pack(side="left", padx=(0,8))
        ttk.Label(row, text="Umbrella ID/Code").pack(side="left", padx=(0,4))
        ttk.Entry(row, textvariable=self.checkout_umb_var, width=14).pack(side="left", padx=(0,8))
        ttk.Button(row, text="Checkout", command=self.do_checkout).pack(side="left", padx=(0,10))

        ttk.Separator(row, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        # Check-in
        self.checkin_umb_var = tk.StringVar(); self.checkin_cond_var = tk.StringVar(value="ok")
        ttk.Label(row, text="Check-in — Umbrella").pack(side="left", padx=(0,4))
        ttk.Entry(row, textvariable=self.checkin_umb_var, width=14).pack(side="left", padx=(0,8))
        ttk.Label(row, text="Condition").pack(side="left", padx=(0,4))
        ttk.Combobox(row, textvariable=self.checkin_cond_var, values=["ok","damaged"], width=12, state="readonly").pack(side="left", padx=(0,8))
        ttk.Button(row, text="Check-in", command=self.do_checkin).pack(side="left", padx=(0,10))

        ttk.Separator(row, orient="vertical").pack(side="left", fill="y", padx=8, pady=2)

        # Lost
        self.lost_sid_var = tk.StringVar(); self.lost_umb_var = tk.StringVar()
        ttk.Label(row, text="Lost — SID").pack(side="left", padx=(0,4))
        ttk.Entry(row, textvariable=self.lost_sid_var, width=14).pack(side="left", padx=(0,8))
        ttk.Label(row, text="Umbrella ID/Code").pack(side="left", padx=(0,4))
        ttk.Entry(row, textvariable=self.lost_umb_var, width=14).pack(side="left", padx=(0,8))
        ttk.Button(row, text="Mark Lost", command=self.do_lost).pack(side="left")

    def load_frontdesk_views(self):
        sid = self.filter_sid_var.get().strip()
        res = list_reserved_reservations(sid_filter=sid if sid else None)
        fill_tree(self.tree_reserved, res, fmt=lambda r: [r["id"], r["sid"], r["umbrella_id"], r.get("start_date",""), r.get("end_date",""), r["reserved_at"]])
        act = list_active_reservations(sid_filter=sid if sid else None)
        fill_tree(self.tree_active, act, fmt=lambda r: [r["id"], r["sid"], r["umbrella_id"], r["pickup_at"], r["due_at"]])
        if sid:
            self.checkout_sid_var.set(sid)
            self.lost_sid_var.set(sid)

    def do_checkout(self):
        sid = self.checkout_sid_var.get().strip()
        umb = self.checkout_umb_var.get().strip()
        if not sid or not umb:
            messagebox.showwarning("Input", "Enter SID and Umbrella ID/Code."); return
        ok, msg = staff_checkout(sid, umb, self.user.get("staff_id",""))
        (messagebox.showinfo if ok else messagebox.showerror)("Checkout", msg)
        self.load_frontdesk_views()

    def do_checkin(self):
        umb = self.checkin_umb_var.get().strip()
        cond = self.checkin_cond_var.get().strip()
        if not umb:
            messagebox.showwarning("Input", "Enter Umbrella ID/Code."); return
        ok, msg = staff_checkin(umb, cond, self.user.get("staff_id",""))
        (messagebox.showinfo if ok else messagebox.showerror)("Check-in", msg)
        self.load_frontdesk_views()

    def do_lost(self):
        sid = self.lost_sid_var.get().strip()
        umb = self.lost_umb_var.get().strip()
        if not sid or not umb:
            messagebox.showwarning("Input", "Enter SID and Umbrella ID/Code."); return
        ok, msg = staff_mark_lost(sid, umb, self.user.get("staff_id",""))
        (messagebox.showinfo if ok else messagebox.showerror)("Lost", msg)
        self.load_frontdesk_views()

    # Payments
    def _build_payments_tab(self):
        grp_filter = ttk.LabelFrame(self.tab_pay, text="Filter (SID)")
        grp_filter.pack(fill="x", padx=6, pady=6)
        self.pay_filter_sid_var = tk.StringVar()
        ttk.Label(grp_filter, text="SID (leave empty = all)").pack(side="left", padx=6, pady=6)
        ttk.Entry(grp_filter, textvariable=self.pay_filter_sid_var, width=20).pack(side="left", padx=6, pady=6)
        ttk.Button(grp_filter, text="Apply Filter", command=self.load_payment_views).pack(side="left", padx=6, pady=6)
        ttk.Button(grp_filter, text="Clear", command=lambda: (self.pay_filter_sid_var.set(""), self.load_payment_views())).pack(side="left", padx=6, pady=6)

        grp_pay = ttk.LabelFrame(self.tab_pay, text="Overdue Payments (Outstanding)")
        grp_pay.pack(fill="both", expand=True, padx=6, pady=(0,6))
        self.tree_overdue = make_tree(grp_pay, ["id","sid","reservation_id","amount","status","created_at","note"])
        self.tree_overdue.pack(fill="both", expand=True, pady=6)

        grp_actions = ttk.LabelFrame(self.tab_pay, text="Payment Actions")
        grp_actions.pack(fill="x", padx=6, pady=(0,8))
        ttk.Button(grp_actions, text="Mark Selected as PAID", command=self.mark_payment_paid).pack(side="left", padx=6, pady=6)
        ttk.Button(grp_actions, text="Void Selected", command=self.void_payment).pack(side="left", padx=6, pady=6)

    def load_payment_views(self):
        sid = self.pay_filter_sid_var.get().strip()
        pays = list_outstanding_overdue_payments(sid_filter=sid if sid else None)
        fill_tree(self.tree_overdue, pays, fmt=lambda p: [p["id"], p["sid"], p["reservation_id"], cents_to_str(int(p["amount_cents"])), p["status"], p["created_at"], p["note"]])

    def _selected_overdue_payment_id(self):
        sel = self.tree_overdue.selection()
        if not sel:
            return None
        return str(self.tree_overdue.item(sel[0])["values"][0])

    def mark_payment_paid(self):
        pid = self._selected_overdue_payment_id()
        if not pid:
            messagebox.showwarning("Select", "Select an overdue payment first."); return
        note = simpledialog.askstring("Mark Paid", "Optional note to append:", parent=self) or ""
        try:
            settle_payment(pid, "paid", note_append=note)
            messagebox.showinfo("Done", "Payment marked as PAID.")
            self.load_payment_views()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def void_payment(self):
        pid = self._selected_overdue_payment_id()
        if not pid:
            messagebox.showwarning("Select", "Select an overdue payment first."); return
        note = simpledialog.askstring("Void Payment", "Reason / note to append:", parent=self) or ""
        try:
            settle_payment(pid, "void", note_append=note)
            messagebox.showinfo("Done", "Payment voided.")
            self.load_payment_views()
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # Inventory
    def _build_inventory_tab(self):
        grp_actions = ttk.LabelFrame(self.tab_inv, text="Inventory Actions")
        grp_actions.pack(fill="x", padx=6, pady=(6,3))
        ttk.Button(grp_actions, text="Refresh", command=self.refresh_inventory).pack(side="left", padx=4, pady=6)
        ttk.Button(grp_actions, text="Add", command=self.add_umbrella_dialog).pack(side="left", padx=4, pady=6)
        ttk.Button(grp_actions, text="Set Status", command=self.set_status_dialog).pack(side="left", padx=4, pady=6)

        grp_list = ttk.LabelFrame(self.tab_inv, text="Inventory List")
        grp_list.pack(fill="both", expand=True, padx=6, pady=(3,6))
        self.tree_inv = make_tree(grp_list, ["id","code","status","location","note","updated_at"])
        self.tree_inv.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh_inventory()

    def refresh_inventory(self):
        rows = sorted(read_csv(UMBRELLAS_CSV), key=lambda x: int(x["id"]))
        fill_tree(self.tree_inv, rows, fmt=lambda u: [u["id"], u["code"], u["status"], u["location"], u["note"], u["updated_at"]])

    def add_umbrella_dialog(self):
        code = simpledialog.askstring("Add Umbrella", "Code (e.g., UMB007):", parent=self)
        if not code: return
        loc = simpledialog.askstring("Add Umbrella", "Location:", parent=self) or "MainStation"
        rows = read_csv(UMBRELLAS_CSV)
        if any(r["code"] == code for r in rows):
            messagebox.showerror("Error", "Code already exists."); return
        rec = {"id": next_id(rows,"id"), "code": code, "status":"Available", "location":loc, "note":"", "created_at":now_str(), "updated_at":now_str()}
        append_csv(UMBRELLAS_CSV, UMBRELLAS_HEADERS, rec)
        self.refresh_inventory()

    def set_status_dialog(self):
        sel = self.tree_inv.selection()
        if not sel:
            messagebox.showwarning("Select", "Select an umbrella."); return
        umb_id = str(self.tree_inv.item(sel[0])["values"][0])
        dialog = tk.Toplevel(self); dialog.title("Set Status"); dialog.geometry("300x160")
        ttk.Label(dialog, text=f"Umbrella ID: {umb_id}").pack(pady=8)
        var = tk.StringVar(value="Available")
        ttk.Combobox(dialog, textvariable=var, values=UMBRELLA_STATUSES, state="readonly").pack(pady=6)
        def do_set():
            umb = get_umbrella_by_id_or_code(umb_id)
            if not umb: messagebox.showerror("Error","Umbrella not found."); dialog.destroy(); return
            umb["status"] = var.get(); umb["updated_at"] = now_str(); save_umbrella(umb)
            messagebox.showinfo("Saved", "Status updated."); self.refresh_inventory(); dialog.destroy()
        ttk.Button(dialog, text="Save", command=do_set).pack(pady=8)

    # Reports
    def _build_reports_tab(self):
        grp_btns = ttk.LabelFrame(self.tab_rep, text="Report Controls")
        grp_btns.pack(fill="x", padx=6, pady=(6,3))

        # Weeks Back selector
        self.weeks_var = tk.IntVar(value=8)
        try:
            Spinbox = ttk.Spinbox
        except AttributeError:
            Spinbox = tk.Spinbox
        ttk.Label(grp_btns, text="Weeks Back:").pack(side="left", padx=6, pady=6)
        Spinbox(grp_btns, from_=1, to=52, textvariable=self.weeks_var, width=6).pack(side="left", padx=4, pady=6)
        ttk.Button(grp_btns, text="Refresh", command=self.refresh_reports).pack(side="left", padx=6, pady=6)

        grp_out = ttk.LabelFrame(self.tab_rep, text="Report Output")
        grp_out.pack(fill="both", expand=True, padx=6, pady=(3,6))
        self.rep_text = tk.Text(grp_out, height=24)
        self.rep_text.pack(fill="both", expand=True, padx=6, pady=6)
        self.refresh_reports()

    def refresh_reports(self):
        # ------- Inventory snapshot & active overdue list -------
        ums = read_csv(UMBRELLAS_CSV)
        inv_counts = {s: 0 for s in UMBRELLA_STATUSES}
        for u in ums:
            inv_counts[u["status"]] = inv_counts.get(u["status"], 0) + 1

        overdue_active = []
        for r in read_csv(RESERVATIONS_CSV):
            if r["status"] == "Active" and r["due_at"]:
                if now_dt() > parse_dt(r["due_at"]):
                    overdue_active.append(r)

        outstanding = [p for p in read_csv(PAYMENTS_CSV) if p["status"] == "outstanding"]

        # ------- Weekly aggregation -------
        try:
            n_weeks = int(self.weeks_var.get())
        except Exception:
            n_weeks = 8
        n_weeks = max(1, min(52, n_weeks))

        base_week = start_of_week(now_dt())      # date
        week_list = [base_week - timedelta(days=7*i) for i in range(n_weeks)]
        week_list_sorted = sorted(week_list, reverse=True)  # newest first

        weekly = {w: {
            "reserved": 0,
            "checkout": 0,
            "returns": 0,
            "overdue_cents": 0,
            "damaged_cents": 0,
            "lost_cents": 0,
            "paid_cents": 0
        } for w in week_list_sorted}

        # Reservations: reserved_at / pickup_at / return_at
        for r in read_csv(RESERVATIONS_CSV):
            dt_reserved = parse_dt(r.get("reserved_at",""))
            dt_pickup   = parse_dt(r.get("pickup_at",""))
            dt_return   = parse_dt(r.get("return_at",""))

            wk = week_key_from_dt(dt_reserved)
            if wk in weekly: weekly[wk]["reserved"] += 1

            wk = week_key_from_dt(dt_pickup)
            if wk in weekly: weekly[wk]["checkout"] += 1

            wk = week_key_from_dt(dt_return)
            if wk in weekly: weekly[wk]["returns"] += 1

        # Payments: created_at by reason; paid_at for money actually received
        for p in read_csv(PAYMENTS_CSV):
            reason = (p.get("reason","") or "").lower()
            cents  = int(p.get("amount_cents","0") or 0)

            wk_created = week_key_from_dt(parse_dt(p.get("created_at","")))
            if wk_created in weekly:
                if reason == "overdue":
                    weekly[wk_created]["overdue_cents"] += cents
                elif reason == "damaged":
                    weekly[wk_created]["damaged_cents"] += cents
                elif reason == "lost":
                    weekly[wk_created]["lost_cents"] += cents

            if p.get("status") == "paid":
                wk_paid = week_key_from_dt(parse_dt(p.get("paid_at","")))
                if wk_paid in weekly:
                    weekly[wk_paid]["paid_cents"] += cents

        # ------- Render text -------
        self.rep_text.delete("1.0", "end")
        if self.dev_mode:
            self.rep_text.insert("end", f"Simulated now: {now_str()} (offset {offset_human()})\n\n")
        else:
            self.rep_text.insert("end", f"Current time: {now_str()}\n\n")

        self.rep_text.insert("end", "Inventory Summary:\n")
        for k in UMBRELLA_STATUSES:
            self.rep_text.insert("end", f"  {k}: {inv_counts.get(k,0)}\n")

        self.rep_text.insert("end", "\nActive Reservations Past Due:\n")
        if not overdue_active:
            self.rep_text.insert("end", "  None\n")
        else:
            for r in overdue_active:
                self.rep_text.insert("end", f"  Res#{r['id']} SID={r['sid']} Umb={r['umbrella_id']} Due={r['due_at']}\n")

        self.rep_text.insert("end", "\nOutstanding Payments (All Reasons):\n")
        if not outstanding:
            self.rep_text.insert("end", "  None\n")
        else:
            for p in outstanding:
                self.rep_text.insert("end", f"  Pay#{p['id']} SID={p['sid']} Res#{p['reservation_id']} {p['reason']} {cents_to_str(int(p['amount_cents']))}\n")

        # Weekly table
        self.rep_text.insert("end", f"\nWeekly Summary (last {n_weeks} week(s), newest first):\n")
        header = (
            "WeekStart".ljust(22) +
            "Res".rjust(5) + "  " +
            "Out".rjust(5) + "  " +
            "Ret".rjust(5) + "  " +
            "Overdue$".rjust(12) + "  " +
            "Damaged$".rjust(12) + "  " +
            "Lost$".rjust(12) + "  " +
            "Paid$".rjust(12) + "\n"
        )
        self.rep_text.insert("end", header)
        self.rep_text.insert("end", "-" * (len(header)-1) + "\n")

        for w in week_list_sorted:
            row = weekly[w]
            line = (
                week_label(w).ljust(22) +
                f"{row['reserved']:>5}  " +
                f"{row['checkout']:>5}  " +
                f"{row['returns']:>5}  " +
                f"{cents_to_str(row['overdue_cents']):>12}  " +
                f"{cents_to_str(row['damaged_cents']):>12}  " +
                f"{cents_to_str(row['lost_cents']):>12}  " +
                f"{cents_to_str(row['paid_cents']):>12}\n"
            )
            self.rep_text.insert("end", line)

# ---------------- UI utils ----------------
def make_tree(parent, columns):
    tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="browse")
    for c in columns:
        tree.heading(c, text=c)
        tree.column(c, width=120, anchor="center")
    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscroll=vsb.set)
    tree.pack(side="left", fill="both", expand=True)
    vsb.pack(side="left", fill="y")
    return tree

def fill_tree(tree, rows, fmt=lambda r: list(r.values())):
    for i in tree.get_children():
        tree.delete(i)
    for r in rows:
        tree.insert("", "end", values=fmt(r))

# ---------------- Main ----------------
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Campus Umbrella Rental Service")
    parser.add_argument("--dev", action="store_true",
                        help="Enable developer mode (Time Travel controls)")
    args = parser.parse_args()

    ensure_data_dir_and_seed()
    app = App(dev_mode=args.dev)
    app.mainloop()

if __name__ == "__main__":
    main()