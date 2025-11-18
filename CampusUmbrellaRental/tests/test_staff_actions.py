
from datetime import timedelta

def _reserve_today(app, sid="S123456"):
    umb = app.list_available_umbrellas()[0]
    start = app.now_dt().date()
    end = start
    ok, msg = app.reserve_umbrella_range(sid, umb["id"], start, end)
    assert ok, msg
    return sid, umb["id"]

def test_checkout_success_on_or_after_start(app):
    sid, umb_id = _reserve_today(app)
    ok, msg = app.staff_checkout(sid, umb_id, "T001")
    assert ok, msg

def test_checkout_blocked_before_start(app):
    umb = app.list_available_umbrellas()[0]
    sid = "S123456"
    today = app.now_dt().date()
    ok, msg = app.reserve_umbrella_range(sid, umb["id"], today + timedelta(days=1), today + timedelta(days=1))
    assert ok, msg
    ok2, msg2 = app.staff_checkout(sid, umb["id"], "T001")
    assert not ok2 and "pickup not allowed" in msg2.lower()

def test_checkin_on_time_no_fee(app):
    sid, umb_id = _reserve_today(app)
    ok, msg = app.staff_checkout(sid, umb_id, "T001")
    assert ok, msg
    ok2, msg2 = app.staff_checkin(umb_id, "ok", "T001")
    assert ok2, msg2
    pays = [p for p in app.list_student_payments(sid) if p["reason"] == "overdue"]
    assert len(pays) == 0

def test_checkin_late_creates_overdue(app):
    sid, umb_id = _reserve_today(app)
    ok, msg = app.staff_checkout(sid, umb_id, "T001")
    assert ok, msg
    app.add_time_offset(timedelta(days=1))
    ok2, msg2 = app.staff_checkin(umb_id, "ok", "T001")
    assert ok2, msg2
    pays = [p for p in app.list_student_payments(sid) if p["reason"] == "overdue"]
    assert len(pays) == 1
    assert int(pays[0]["amount_cents"]) >= 2000

def test_checkin_damaged_creates_damaged_fee(app):
    sid, umb_id = _reserve_today(app)
    ok, msg = app.staff_checkout(sid, umb_id, "T001")
    assert ok, msg
    ok2, msg2 = app.staff_checkin(umb_id, "damaged", "T001")
    assert ok2, msg2
    pays = [p for p in app.list_student_payments(sid) if p["reason"] == "damaged"]
    assert len(pays) == 1
    assert int(pays[0]["amount_cents"]) == int(app.dollars_to_cents(app.FEE_DAMAGED_FLAT))

def test_mark_lost_flow(app):
    sid, umb_id = _reserve_today(app)
    ok, msg = app.staff_checkout(sid, umb_id, "T001")
    assert ok, msg
    ok2, msg2 = app.staff_mark_lost(sid, umb_id, "T001")
    assert ok2, msg2
    pays = [p for p in app.list_student_payments(sid) if p["reason"] == "lost"]
    assert len(pays) == 1
    assert int(pays[0]["amount_cents"]) == int(app.dollars_to_cents(app.FEE_LOST_FLAT))
