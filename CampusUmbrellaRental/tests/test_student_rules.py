
from datetime import timedelta

def _first_available_id(app):
    av = app.list_available_umbrellas()
    assert av, "No available umbrellas"
    return av[0]["id"]

def test_start_before_today_rejected(app):
    sid = "S123456"
    umb_id = _first_available_id(app)
    today = app.now_dt().date()
    yesterday = today - timedelta(days=1)
    ok, msg = app.reserve_umbrella_range(sid, umb_id, yesterday, yesterday)
    assert not ok and "within the next 7 days" in msg

def test_end_before_start_rejected(app):
    sid = "S123456"
    umb_id = _first_available_id(app)
    today = app.now_dt().date()
    ok, msg = app.reserve_umbrella_range(sid, umb_id, today, today - timedelta(days=1))
    assert not ok

def test_reserve_unavailable_umbrella(app):
    sid = "S123456"
    all_umb = app.read_csv(app.UMBRELLAS_CSV)
    target = all_umb[0]
    target["status"] = "Reserved"
    app.write_csv(app.UMBRELLAS_CSV, app.UMBRELLAS_HEADERS, all_umb)
    ok, msg = app.reserve_umbrella_range(sid, target["id"], app.now_dt().date(), app.now_dt().date())
    assert not ok and "not available" in msg.lower()
