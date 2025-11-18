
def test_checkout_without_matching_reserved(app):
    ok, msg = app.staff_checkout("S999999", "UMB001", "T001")
    assert not ok and "no reserved record" in msg.lower()

def test_double_checkin_blocked(app):
    sid = "S123456"
    umb = app.list_available_umbrellas()[0]
    start = app.now_dt().date()
    ok, msg = app.reserve_umbrella_range(sid, umb["id"], start, start)
    assert ok, msg
    ok, msg = app.staff_checkout(sid, umb["id"], "T001")
    assert ok, msg
    ok1, msg1 = app.staff_checkin(umb["id"], "ok", "T001")
    assert ok1, msg1
    ok2, msg2 = app.staff_checkin(umb["id"], "ok", "T001")
    assert not ok2
