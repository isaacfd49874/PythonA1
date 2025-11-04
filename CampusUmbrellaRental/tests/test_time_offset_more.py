
from datetime import timedelta

def test_timebar_apply_and_reset(app):
    baseline = app.now_str()
    app.add_time_offset(timedelta(hours=1))
    advanced = app.now_str()
    assert advanced != baseline
    app.set_time_offset_seconds(0)
    reset = app.now_str()
    assert reset[:10] == baseline[:10]

def test_overdue_ceil_one_second(app):
    sid = "S123456"
    umb = app.list_available_umbrellas()[0]
    start = app.now_dt().date()
    ok, msg = app.reserve_umbrella_range(sid, umb["id"], start, start)
    assert ok, msg
    ok, msg = app.staff_checkout(sid, umb["id"], "T001")
    assert ok, msg

    active = [r for r in app.read_csv(app.RESERVATIONS_CSV) if r["sid"] == sid and r["umbrella_id"] == umb["id"] and r["status"] == "Active"]
    assert active, "active reservation not found"
    due_at = app.parse_dt(active[0]["due_at"])

    seconds = int((due_at - app.now_dt()).total_seconds()) + 2
    app.add_time_offset(timedelta(seconds=seconds))

    ok2, msg2 = app.staff_checkin(umb["id"], "ok", "T001")
    assert ok2, msg2
    pays = [p for p in app.list_student_payments(sid) if p["reason"] == "overdue"]
    assert len(pays) == 1
    assert int(pays[0]["amount_cents"]) >= 2000
