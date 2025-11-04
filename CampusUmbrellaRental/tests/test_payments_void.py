
def test_void_overdue_payment(app):
    rec = app.add_payment("S123456", "0", "overdue", 2000)
    ok = app.settle_payment(rec["id"], "void")
    assert ok
    p = [p for p in app.read_csv(app.PAYMENTS_CSV) if p["id"] == rec["id"]][0]
    assert p["status"] == "void"
