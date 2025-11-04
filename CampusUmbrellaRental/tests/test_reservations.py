
from datetime import timedelta

def _first_available_id(app):
    av = app.list_available_umbrellas()
    assert av, "No available umbrellas in seed data"
    return av[0]["id"]

def test_student_reserve_same_day_success(app):
    sid = "S123456"
    umb_id = _first_available_id(app)
    start = app.now_dt().date()
    end = start
    ok, msg = app.reserve_umbrella_range(sid, umb_id, start, end)
    assert ok, msg

def test_double_reserve_blocked(app):
    sid = "S123456"
    umb_id = _first_available_id(app)
    start = app.now_dt().date()
    end = start
    ok, msg = app.reserve_umbrella_range(sid, umb_id, start, end)
    assert ok, msg
    ok2, msg2 = app.reserve_umbrella_range(sid, umb_id, start, end)
    assert not ok2 and "open reservation" in msg2.lower()

def test_end_beyond_window_rejected(app):
    sid = "S123456"
    umb_id = _first_available_id(app)
    start = app.now_dt().date()
    end = start + timedelta(days=7)  # beyond allowed (today..today+6)
    ok, msg = app.reserve_umbrella_range(sid, umb_id, start, end)
    assert not ok and "within the next 7 days" in msg
